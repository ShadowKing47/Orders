"""Temporal Workflows: pure state machines. ZERO imports of requests/httpx/databases/anthropic/datetime.

Use workflow.now() instead of datetime.now(). This file must never import backend.db or backend.agents.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from backend.models.activity_io import AgentOutput
    from backend.models.enums import RunStatus
    from backend import activities

_ACTIVITY_START_TO_CLOSE_TIMEOUT = timedelta(minutes=2)
_ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(seconds=30)
_DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=5)
_FAST_TASK_QUEUE = "fast-tasks"
_MAX_EVENT_COUNT_BEFORE_CONTINUE = 4000  # buffer well below Temporal's ~50k event-history limit


@dataclass
class OrderSupervisorWorkflowInput:
    run_id: str
    order_id: str
    initial_instructions: list[str] = field(default_factory=list)
    # Populated only when continuing a long-running workflow via continue_as_new
    # (see the event_count check in run()); a fresh run leaves these at their defaults.
    resumed_memory_summary: str = ""
    resumed_next_wake_up_time: datetime | None = None


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self) -> None:
        self.is_terminal: bool = False
        self.unprocessed_events: list[dict] = []
        self.extra_instructions: list[str] = []
        self.current_memory_summary: str = ""
        self.next_wake_up_time = None
        self.is_paused: bool = False
        self.status: RunStatus = RunStatus.RUNNING
        self.event_count: int = 0
        # Set by pause_workflow/resume_workflow signal handlers, which ONLY mutate state.
        # The main run() loop is the sole place that executes Activities (including the
        # persistence Activity for these), so event history stays a clean sequential trace
        # instead of interleaved activity calls spawned from concurrent signal handlers.
        self._status_persist_pending: bool = False

    @workflow.signal
    def inject_event(self, event_data: dict) -> None:
        self.unprocessed_events.append(event_data)
        self.event_count += 1

    @workflow.signal
    def add_instruction(self, instruction: str) -> None:
        self.extra_instructions.append(instruction)
        self.event_count += 1

    @workflow.signal
    def pause_workflow(self) -> None:
        self.is_paused = True
        self.status = RunStatus.PAUSED
        self._status_persist_pending = True

    @workflow.signal
    def resume_workflow(self) -> None:
        self.is_paused = False
        self.status = RunStatus.SLEEPING if self.next_wake_up_time else RunStatus.RUNNING
        self._status_persist_pending = True

    @workflow.query
    def get_state(self) -> dict:
        return {
            "status": self.status.value,
            "memory_summary": self.current_memory_summary,
            "next_wake_up_time": self.next_wake_up_time.isoformat() if self.next_wake_up_time else None,
            "is_paused": self.is_paused,
        }

    def _should_wake(self) -> bool:
        if self._status_persist_pending:
            return True
        if self.unprocessed_events:
            return True
        if self.next_wake_up_time and workflow.now() >= self.next_wake_up_time:
            return True
        return False

    async def _persist_run_state(self) -> None:
        self.event_count += 1
        await workflow.execute_activity(
            activities.update_run_state,
            args=[workflow.info().workflow_id, self.status, self.current_memory_summary, self.next_wake_up_time],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )

    async def _run_main_agent_and_update(self, events: list[dict], idempotency_prefix: str) -> None:
        output: AgentOutput = await workflow.execute_activity(
            activities.run_main_agent,
            args=[self.current_memory_summary, events, self.extra_instructions, workflow.info().workflow_id, idempotency_prefix],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
        self.event_count += 1

        self.current_memory_summary = output.new_memory_summary
        wake_seconds = output.next_wake_up_duration_seconds
        self.next_wake_up_time = workflow.now() + timedelta(seconds=wake_seconds)
        self.is_terminal = output.is_terminal

        self.status = RunStatus.SLEEPING if not self.is_terminal else RunStatus.COMPLETED
        await self._persist_run_state()

    @workflow.run
    async def run(self, workflow_input: OrderSupervisorWorkflowInput) -> None:
        self.extra_instructions = list(workflow_input.initial_instructions)

        if workflow_input.resumed_next_wake_up_time is not None:
            # Continuing after continue_as_new: skip the initial agent call, carry state forward.
            self.current_memory_summary = workflow_input.resumed_memory_summary
            self.next_wake_up_time = workflow_input.resumed_next_wake_up_time
            self.status = RunStatus.SLEEPING
        else:
            await self._run_main_agent_and_update(events=[], idempotency_prefix=f"{workflow_input.run_id}:init")

        iteration = 0
        while not self.is_terminal:
            # Every loop iteration starts here, whatever woke it up — this is the ONLY place
            # that turns _status_persist_pending into an Activity call, so pause/resume state
            # changes always appear as a normal sequential step in the loop, never as an
            # activity spawned concurrently from inside a signal handler.
            if self._status_persist_pending:
                await self._persist_run_state()
                self._status_persist_pending = False
                continue

            if self.event_count > _MAX_EVENT_COUNT_BEFORE_CONTINUE:
                workflow.continue_as_new(
                    OrderSupervisorWorkflowInput(
                        run_id=workflow_input.run_id,
                        order_id=workflow_input.order_id,
                        initial_instructions=self.extra_instructions,
                        resumed_memory_summary=self.current_memory_summary,
                        resumed_next_wake_up_time=self.next_wake_up_time,
                    )
                )
                return

            await workflow.wait_condition(lambda: not self.is_paused or self._status_persist_pending)

            if self.is_paused:
                # Still paused — the wait above only returned because a pending persist
                # arrived. Loop back to the top, which will handle it via the check above.
                continue

            self.status = RunStatus.RUNNING if self.unprocessed_events else RunStatus.SLEEPING
            await workflow.wait_condition(self._should_wake)

            if self._status_persist_pending:
                continue

            if self.unprocessed_events:
                iteration += 1
                events_batch = self.unprocessed_events
                self.unprocessed_events = []
                self.status = RunStatus.RUNNING

                important_events = []
                for idx, event in enumerate(events_batch):
                    should_wake = await workflow.execute_activity(
                        activities.run_classifier,
                        args=[str(event), workflow_input.run_id, f"{workflow_input.run_id}:classify:{iteration}:{idx}"],
                        task_queue=_FAST_TASK_QUEUE,
                        start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
                        heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
                        retry_policy=_DEFAULT_RETRY_POLICY,
                    )
                    self.event_count += 1
                    if should_wake:
                        important_events.append(event)

                if important_events:
                    await self._run_main_agent_and_update(
                        events=important_events,
                        idempotency_prefix=f"{workflow_input.run_id}:agent:{iteration}",
                    )
                else:
                    # No important events: loop back to sleep, keep existing wake schedule.
                    self.status = RunStatus.SLEEPING
            else:
                iteration += 1
                await self._run_main_agent_and_update(
                    events=[], idempotency_prefix=f"{workflow_input.run_id}:scheduled:{iteration}"
                )

        await workflow.execute_activity(
            activities.generate_final_output,
            args=[self.current_memory_summary, workflow_input.run_id, f"{workflow_input.run_id}:final"],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
