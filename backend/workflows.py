"""Temporal Workflows: pure state machines. ZERO imports of requests/httpx/databases/anthropic/datetime.

Use workflow.now() instead of datetime.now(). This file must never import backend.db or backend.agents.
"""

from dataclasses import dataclass, field
from datetime import timedelta

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


@dataclass
class OrderSupervisorWorkflowInput:
    run_id: str
    order_id: str
    initial_instructions: list[str] = field(default_factory=list)


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

    @workflow.signal
    def inject_event(self, event_data: dict) -> None:
        self.unprocessed_events.append(event_data)

    @workflow.signal
    def add_instruction(self, instruction: str) -> None:
        self.extra_instructions.append(instruction)

    @workflow.signal
    def pause_workflow(self) -> None:
        self.is_paused = True

    @workflow.signal
    def resume_workflow(self) -> None:
        self.is_paused = False

    @workflow.query
    def get_state(self) -> dict:
        return {
            "status": self.status.value,
            "memory_summary": self.current_memory_summary,
            "next_wake_up_time": self.next_wake_up_time.isoformat() if self.next_wake_up_time else None,
            "is_paused": self.is_paused,
        }

    def _should_wake(self) -> bool:
        if self.unprocessed_events:
            return True
        if self.next_wake_up_time and workflow.now() >= self.next_wake_up_time:
            return True
        return False

    async def _run_main_agent_and_update(self, events: list[dict], idempotency_prefix: str) -> None:
        output: AgentOutput = await workflow.execute_activity(
            activities.run_main_agent,
            args=[self.current_memory_summary, events, self.extra_instructions, workflow.info().workflow_id, idempotency_prefix],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )

        self.current_memory_summary = output.new_memory_summary
        wake_seconds = output.next_wake_up_duration_seconds
        self.next_wake_up_time = workflow.now() + timedelta(seconds=wake_seconds)
        self.is_terminal = output.is_terminal

        self.status = RunStatus.SLEEPING if not self.is_terminal else RunStatus.COMPLETED
        await workflow.execute_activity(
            activities.update_run_state,
            args=[workflow.info().workflow_id, self.status, self.current_memory_summary, self.next_wake_up_time],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )

    @workflow.run
    async def run(self, workflow_input: OrderSupervisorWorkflowInput) -> None:
        self.extra_instructions = list(workflow_input.initial_instructions)

        await self._run_main_agent_and_update(events=[], idempotency_prefix=f"{workflow_input.run_id}:init")

        iteration = 0
        while not self.is_terminal:
            await workflow.wait_condition(lambda: not self.is_paused)

            self.status = RunStatus.RUNNING if self.unprocessed_events else RunStatus.SLEEPING
            await workflow.wait_condition(self._should_wake)

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
