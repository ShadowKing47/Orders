"""Temporal Activities: all side effects (DB writes, LLM calls, tool execution) live here."""

import asyncio
import json
from dataclasses import dataclass, replace
from datetime import datetime

from temporalio import activity

from backend import agents, db
from config import get_settings
from backend.exceptions import AgentParsingError
from backend.models.activity_io import AgentOutput, ToolCall
from backend.models.enums import EventType, RunStatus
from backend.models.tools import all_tool_schemas, scheduled_check_in_tool_schemas

_HEARTBEAT_INTERVAL_SECONDS = 10


@dataclass(frozen=True)
class _MainAgentLoopState:
    """Accumulator threaded through the tool-handling loop, replacing an if/elif chain with a dispatch table."""

    result_text: str
    next_wake_up_duration_seconds: int | None = None
    is_terminal: bool = False


async def _persist_tool_call(tool_call: ToolCall, run_id: str, idempotency_key: str, result_text: str) -> None:
    if await db.event_exists(idempotency_key):
        return
    await db.persist_event(
        run_id,
        EventType.TOOL_EXECUTED,
        {"tool_name": tool_call.tool_name, "params": tool_call.tool_input, "result": result_text},
        idempotency_key,
    )


async def _handle_schedule_next_wake_up(
    tool_call: ToolCall, state: _MainAgentLoopState, run_id: str, idempotency_key: str
) -> _MainAgentLoopState:
    result_text = "scheduled"
    await _persist_tool_call(tool_call, run_id, idempotency_key, result_text)
    return replace(
        state,
        result_text=result_text,
        next_wake_up_duration_seconds=tool_call.tool_input.get("next_wake_up_duration_seconds"),
    )


async def _handle_mark_order_complete(
    tool_call: ToolCall, state: _MainAgentLoopState, run_id: str, idempotency_key: str
) -> _MainAgentLoopState:
    result_text = f"order marked complete: {tool_call.tool_input.get('final_status')}"
    await _persist_tool_call(tool_call, run_id, idempotency_key, result_text)
    return replace(
        state,
        result_text=result_text,
        is_terminal=True,
    )


async def _handle_generic_tool(
    tool_call: ToolCall, state: _MainAgentLoopState, run_id: str, idempotency_key: str
) -> _MainAgentLoopState:
    result_text = await execute_tool(tool_call.tool_name, tool_call.tool_input, run_id, idempotency_key)
    return replace(state, result_text=result_text)


_TOOL_HANDLERS = {
    "schedule_next_wake_up": _handle_schedule_next_wake_up,
    "mark_order_complete": _handle_mark_order_complete,
}


async def _run_with_heartbeat(coro) -> object:
    """Awaits a coroutine while heartbeating periodically.

    Uses the native async Anthropic client (backend.agents), so cancellation
    (e.g. on heartbeat timeout) propagates natively via asyncio/httpx into the
    in-flight HTTP request instead of leaking a background thread that keeps
    running the request to completion after Temporal has already moved on.
    """

    task = asyncio.ensure_future(coro)
    while not task.done():
        activity.heartbeat()
        await asyncio.wait([task], timeout=_HEARTBEAT_INTERVAL_SECONDS)
    return task.result()


@activity.defn
async def run_classifier(event: str, run_id: str, idempotency_key: str) -> bool:
    settings = get_settings()
    return await _run_with_heartbeat(
        agents.run_classifier(settings.ANTHROPIC_API_KEY, settings.CLASSIFIER_MODEL, event)
    )


def _tool_result_block(tool_call: ToolCall, result_text: str) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_call.tool_use_id, "content": result_text}


def _assistant_content_from_tool_calls(tool_calls: list[ToolCall]) -> list[dict]:
    return [
        {"type": "tool_use", "id": tc.tool_use_id, "name": tc.tool_name, "input": tc.tool_input}
        for tc in tool_calls
    ]


@activity.defn
async def run_main_agent(
    memory: str,
    events: list[dict],
    instructions: list[str],
    run_id: str,
    idempotency_key: str,
) -> AgentOutput:
    settings = get_settings()

    tool_results: list[dict] | None = None
    prior_assistant_content: list[dict] | None = None
    collected_tool_calls: list[ToolCall] = []
    next_wake_up_duration_seconds: int | None = None
    is_terminal = False

    # Empty-check-in guard: an agent woken on schedule with no new events must not be
    # handed customer-facing/escalation tools, or it's liable to hallucinate a reason to
    # use one just because it's available. Only offer schedule_next_wake_up in that case.
    tool_schemas = all_tool_schemas() if events else scheduled_check_in_tool_schemas()

    # Agentic tool loop: keep calling the main agent until it stops requesting tools.
    for _ in range(10):  # hard safety cap on loop iterations
        try:
            stop_reason, tool_calls = await _run_with_heartbeat(
                agents.run_main_agent(
                    settings.ANTHROPIC_API_KEY,
                    settings.MAIN_AGENT_MODEL,
                    memory,
                    events,
                    instructions,
                    tool_schemas,
                    tool_results,
                    prior_assistant_content,
                )
            )
        except Exception as exc:
            raise AgentParsingError(f"run_main_agent failed: {exc}") from exc

        if stop_reason != "tool_use" or not tool_calls:
            break

        prior_assistant_content = _assistant_content_from_tool_calls(tool_calls)
        tool_results = []
        for tool_call in tool_calls:
            collected_tool_calls.append(tool_call)
            handler = _TOOL_HANDLERS.get(tool_call.tool_name, _handle_generic_tool)
            loop_state = await handler(
                tool_call,
                _MainAgentLoopState(result_text=""),
                run_id,
                f"{idempotency_key}:{tool_call.tool_use_id}",
            )
            if loop_state.next_wake_up_duration_seconds is not None:
                next_wake_up_duration_seconds = loop_state.next_wake_up_duration_seconds
            if loop_state.is_terminal:
                is_terminal = True
            tool_results.append(_tool_result_block(tool_call, loop_state.result_text))

        if is_terminal:
            break

    if next_wake_up_duration_seconds is None or not isinstance(next_wake_up_duration_seconds, int):
        next_wake_up_duration_seconds = settings.DEFAULT_WAKE_UP_SECONDS

    # Only compact memory if new facts entered the system (events) or a real-world action was
    # taken. Updating the internal schedule_next_wake_up timer does not change order state.
    has_real_tool_call = any(tc.tool_name != "schedule_next_wake_up" for tc in collected_tool_calls)
    if events or has_real_tool_call:
        new_memory_summary = await compact_memory(
            memory,
            [{"events": events, "tool_calls": [tc.tool_name for tc in collected_tool_calls]}],
            run_id,
            f"{idempotency_key}:compact",
        )
    else:
        new_memory_summary = memory

    return AgentOutput(
        new_memory_summary=new_memory_summary,
        tool_calls=tuple(collected_tool_calls),
        next_wake_up_duration_seconds=next_wake_up_duration_seconds,
        is_terminal=is_terminal,
    )


@activity.defn
async def compact_memory(memory: str, new_events: list[dict], run_id: str, idempotency_key: str) -> str:
    settings = get_settings()
    history = [{"prior_memory": memory}, *new_events]
    new_summary = await _run_with_heartbeat(
        agents.compact_memory(settings.ANTHROPIC_API_KEY, settings.COMPACTOR_MODEL, history)
    )
    await db.persist_event(run_id, EventType.MEMORY_COMPACTED, {"summary": new_summary}, idempotency_key)
    return new_summary


@activity.defn
async def consolidate_instructions(
    current_standing_orders: str, new_instructions: list[str], idempotency_key: str
) -> str:
    settings = get_settings()
    return await _run_with_heartbeat(
        agents.consolidate_instructions(
            settings.ANTHROPIC_API_KEY, settings.MAIN_AGENT_MODEL, current_standing_orders, new_instructions
        )
    )


@activity.defn
async def generate_final_output(memory: str, run_id: str, idempotency_key: str) -> None:
    settings = get_settings()
    if await db.event_exists(idempotency_key):
        return
    summary = await _run_with_heartbeat(
        agents.generate_final_summary(settings.ANTHROPIC_API_KEY, settings.MAIN_AGENT_MODEL, memory)
    )
    await db.insert_final_output(run_id, summary)
    await db.persist_event(run_id, EventType.MEMORY_COMPACTED, {"final_summary": summary}, idempotency_key)


@activity.defn
async def execute_tool(tool_name: str, params: dict, run_id: str, idempotency_key: str) -> str:
    if await db.event_exists(idempotency_key):
        return "already executed (idempotent replay)"

    # Tool execution is mocked for this POC: log the call and return a canned success string.
    result_text = f"Mock execution of '{tool_name}' succeeded with params: {json.dumps(params)}"
    await db.persist_event(
        run_id,
        EventType.TOOL_EXECUTED,
        {"tool_name": tool_name, "params": params, "result": result_text},
        idempotency_key,
    )
    return result_text


@activity.defn
async def update_run_state(
    run_id: str,
    status: RunStatus,
    memory: str,
    next_wake_up: datetime | None,
) -> None:
    await db.update_run_state(run_id, status, memory, next_wake_up)
