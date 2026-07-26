"""Temporal Workflows: pure state machines. ZERO imports of requests/httpx/databases/anthropic/datetime.

Use workflow.now() instead of datetime.now(). This file must never import backend.db or backend.agents.
"""

import asyncio
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
_CLASSIFIER_BYPASS_BACKLOG_THRESHOLD = 5  # dead-man's switch against a stuck-on-NO classifier
_INSTRUCTION_CONSOLIDATION_THRESHOLD = 3  # batch new instructions before paying for an LLM merge
_INSTRUCTION_LLM_CONSOLIDATION_MIN_CHARS = 500  # below this, a plain local join is cheaper and just as correct


@dataclass
class OrderSupervisorWorkflowInput:
    run_id: str
    order_id: str
    initial_instructions: list[str] = field(default_factory=list)
    # Populated only when continuing a long-running workflow via continue_as_new
    # (see the event_count check in run()); a fresh run leaves these at their defaults.
    resumed_memory_summary: str = ""
    resumed_next_wake_up_time: datetime | None = None
    resumed_standing_orders: str = ""


@workflow.defn
class OrderSupervisorWorkflow:
    def __init__(self) -> None:
        self.is_terminal: bool = False
        self.unprocessed_events: list[dict] = []
        # Consolidated "standing orders" string (see _maybe_consolidate_instructions) plus
        # any newly added instructions not yet folded into it. Both are included in every
        # main-agent prompt, so nothing is lost while waiting to batch-consolidate — but
        # pending_instructions is deliberately kept small and short-lived, rather than
        # letting a raw, ever-growing list of instructions accumulate and pollute every
        # prompt for the life of a multi-week run.
        self.standing_orders: str = ""
        self.pending_instructions: list[str] = []
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
        self.pending_instructions.append(instruction)
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

    @workflow.signal
    def terminate_workflow(self) -> None:
        # Deliberately NOT the same as handle.terminate() (a hard external kill giving the
        # workflow zero chance to run more code). This signal only flips is_terminal, so the
        # main loop's `while not self.is_terminal` exits naturally on its next check and the
        # workflow still reaches generate_final_output below the loop — every path that ends
        # a run (agent-driven completion or a human clicking Terminate) produces a final
        # summary. Any in-flight activity when this signal arrives still runs to completion
        # first; this only stops the *next* iteration from starting new work.
        self.is_terminal = True
        self.is_paused = False  # don't let a paused run get stuck waiting past termination
        self.status = RunStatus.TERMINATED
        self.next_wake_up_time = None  # a terminated run will never wake again
        self._status_persist_pending = True

    @workflow.query
    def get_state(self) -> dict:
        return {
            "status": self.status.value,
            "memory_summary": self.current_memory_summary,
            "next_wake_up_time": self.next_wake_up_time.isoformat() if self.next_wake_up_time else None,
            "is_paused": self.is_paused,
            "standing_orders": self.standing_orders,
        }

    def _should_wake(self) -> bool:
        if self._status_persist_pending:
            return True
        if len(self.pending_instructions) >= _INSTRUCTION_CONSOLIDATION_THRESHOLD:
            return True
        if self.unprocessed_events:
            return True
        if self.next_wake_up_time and workflow.now() >= self.next_wake_up_time:
            return True
        return False

    def _effective_instructions(self) -> list[str]:
        """Standing orders plus any not-yet-consolidated instructions, for main-agent prompts."""
        instructions = []
        if self.standing_orders:
            instructions.append(self.standing_orders)
        instructions.extend(self.pending_instructions)
        return instructions

    async def _persist_run_state(self) -> None:
        self.event_count += 1
        await workflow.execute_activity(
            activities.update_run_state,
            args=[workflow.info().workflow_id, self.status, self.current_memory_summary, self.next_wake_up_time],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )

    async def _consolidate_pending_instructions(self, idempotency_prefix: str) -> None:
        pending_text = "\n".join(self.pending_instructions)
        if len(pending_text) > _INSTRUCTION_LLM_CONSOLIDATION_MIN_CHARS:
            self.standing_orders = await workflow.execute_activity(
                activities.consolidate_instructions,
                args=[self.standing_orders, self.pending_instructions, idempotency_prefix],
                start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
                heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
                retry_policy=_DEFAULT_RETRY_POLICY,
            )
        else:
            # Short enough that an LLM merge/conflict-resolution pass isn't worth paying for —
            # a plain local join covers it just as well.
            self.standing_orders = f"{self.standing_orders}\n{pending_text}" if self.standing_orders else pending_text
        self.pending_instructions = []
        self.event_count += 1

    async def _run_main_agent_and_update(self, events: list[dict], idempotency_prefix: str) -> None:
        output: AgentOutput = await workflow.execute_activity(
            activities.run_main_agent,
            args=[
                self.current_memory_summary,
                events,
                self._effective_instructions(),
                workflow.info().workflow_id,
                idempotency_prefix,
            ],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
        self.event_count += 1

        self.current_memory_summary = output.new_memory_summary

        if self.is_terminal:
            # A terminate_workflow signal landed while this activity was in flight — don't
            # let the activity's own is_terminal=False resurrect a run that was told to stop.
            # The signal handler already set status=TERMINATED; leave it as-is.
            return

        self.is_terminal = output.is_terminal
        self.status = RunStatus.SLEEPING if not self.is_terminal else RunStatus.COMPLETED
        # A run the agent just marked complete (e.g. via mark_order_complete) will never wake
        # again — don't persist a stale future wake-up time alongside a terminal status.
        self.next_wake_up_time = None if self.is_terminal else workflow.now() + timedelta(
            seconds=output.next_wake_up_duration_seconds
        )
        await self._persist_run_state()

    @workflow.run
    async def run(self, workflow_input: OrderSupervisorWorkflowInput) -> None:
        if workflow_input.resumed_next_wake_up_time is not None:
            # Continuing after continue_as_new: skip the initial agent call, carry state forward.
            self.current_memory_summary = workflow_input.resumed_memory_summary
            self.next_wake_up_time = workflow_input.resumed_next_wake_up_time
            self.standing_orders = workflow_input.resumed_standing_orders
            self.status = RunStatus.SLEEPING
        else:
            self.pending_instructions = list(workflow_input.initial_instructions)
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

            if len(self.pending_instructions) >= _INSTRUCTION_CONSOLIDATION_THRESHOLD:
                # Same reasoning as above: consolidation is an Activity call, so it only ever
                # happens here, sequentially, never inside the add_instruction signal handler.
                await self._consolidate_pending_instructions(f"{workflow_input.run_id}:consolidate:{self.event_count}")
                continue

            if self.event_count > _MAX_EVENT_COUNT_BEFORE_CONTINUE:
                workflow.continue_as_new(
                    OrderSupervisorWorkflowInput(
                        run_id=workflow_input.run_id,
                        order_id=workflow_input.order_id,
                        initial_instructions=self.pending_instructions,
                        resumed_memory_summary=self.current_memory_summary,
                        resumed_next_wake_up_time=self.next_wake_up_time,
                        resumed_standing_orders=self.standing_orders,
                    )
                )
                return

            await workflow.wait_condition(lambda: not self.is_paused or self._status_persist_pending)

            if self.is_paused:
                # Still paused — the wait above only returned because a pending persist
                # arrived. Loop back to the top, which will handle it via the check above.
                continue

            self.status = RunStatus.RUNNING if self.unprocessed_events else RunStatus.SLEEPING
            # wait_condition only re-checks its callback when a new workflow event arrives
            # (signal, activity completion, timer firing) — it does NOT poll the wall clock.
            # Without an explicit timeout here, nothing would ever wake the workflow at
            # next_wake_up_time if no other signal happens to arrive first: passing timeout=
            # makes the SDK schedule a real Temporal timer for that duration, whose firing is
            # itself an event that re-triggers the check. TimeoutError is the expected/normal
            # "scheduled wake-up reached" path, not an error.
            timeout = (self.next_wake_up_time - workflow.now()) if self.next_wake_up_time else None
            try:
                await workflow.wait_condition(self._should_wake, timeout=timeout)
            except asyncio.TimeoutError:
                pass

            if self._status_persist_pending:
                continue

            if self.unprocessed_events:
                iteration += 1
                events_batch = self.unprocessed_events
                self.unprocessed_events = []
                self.status = RunStatus.RUNNING

                if len(events_batch) >= _CLASSIFIER_BYPASS_BACKLOG_THRESHOLD:
                    # Dead-man's switch: if a stuck-on-NO classifier let a backlog build up
                    # this large, don't trust it to keep gatekeeping — force the main agent
                    # to review the whole batch directly rather than risk silently dropping
                    # events that were actually important.
                    important_events = events_batch
                else:
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

        if self._status_persist_pending:
            # The `while` condition is checked before the loop body runs, so if is_terminal
            # became True while the workflow was idle (not mid-iteration) — e.g. terminate_workflow
            # signaled while sleeping — the loop body's own _status_persist_pending handling
            # never gets a chance to run, and TERMINATED would never reach the DB without this.
            await self._persist_run_state()
            self._status_persist_pending = False

        await workflow.execute_activity(
            activities.generate_final_output,
            args=[self.current_memory_summary, workflow_input.run_id, f"{workflow_input.run_id}:final"],
            start_to_close_timeout=_ACTIVITY_START_TO_CLOSE_TIMEOUT,
            heartbeat_timeout=_ACTIVITY_HEARTBEAT_TIMEOUT,
            retry_policy=_DEFAULT_RETRY_POLICY,
        )
