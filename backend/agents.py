"""Anthropic client logic. NEVER imports db.py or executes tools directly.

Tool calls are extracted and returned to the calling Activity, which is
responsible for execution and DB writes.
"""

from functools import lru_cache
from pathlib import Path

import anthropic
from cachetools import TTLCache, cached
from cachetools.keys import hashkey

from backend.exceptions import AgentParsingError, NonRetryableAgentError
from backend.models.activity_io import ToolCall
from backend.models.tools import all_tool_schemas

_PROMPTS_DIR = Path(__file__).parent / "prompts" / "v1"

_CLIENT_CACHE_TTL_SECONDS = 1200  # 20 minutes


@lru_cache(maxsize=None)
def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


@cached(cache=TTLCache(maxsize=8, ttl=_CLIENT_CACHE_TTL_SECONDS), key=lambda api_key: hashkey(api_key))
def _get_client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key)


def _raise_for_api_error(exc: anthropic.APIError) -> None:
    status = getattr(exc, "status_code", None)
    if status == 400:
        raise NonRetryableAgentError(f"Non-retryable Anthropic API error: {exc}") from exc
    # 429/5xx and anything else: let it propagate so Temporal retries the activity.
    raise exc


async def run_classifier(api_key: str, model: str, event: str) -> bool:
    prompt = _load_prompt("classifier.txt").format(event=event)
    client = _get_client(api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        _raise_for_api_error(exc)
        raise  # unreachable, satisfies type checkers

    text = "".join(block.text for block in response.content if block.type == "text").strip().upper()
    if text.startswith("YES"):
        return True
    if text.startswith("NO"):
        return False
    # Ambiguous/unparseable classifier output: default to waking up (safe side).
    return True


async def run_main_agent(
    api_key: str,
    model: str,
    memory: str,
    events: list[dict],
    instructions: list[str],
    tool_results: list[dict] | None = None,
    prior_assistant_content: list[dict] | None = None,
) -> tuple[str, list[ToolCall]]:
    """Calls the main agent. Returns (stop_reason, tool_calls). Does not execute tools.

    If tool_results/prior_assistant_content are provided, this continues an
    existing agentic-loop turn (the Activity re-prompts after executing tools).
    """
    prompt = _load_prompt("main_agent.txt").format(
        memory=memory or "(no memory yet)",
        events=events,
        instructions=instructions,
    )

    messages: list[dict] = [{"role": "user", "content": prompt}]
    if prior_assistant_content is not None:
        messages.append({"role": "assistant", "content": prior_assistant_content})
    if tool_results:
        messages.append({"role": "user", "content": tool_results})

    client = _get_client(api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            tools=all_tool_schemas(),
            messages=messages,
        )
    except anthropic.APIError as exc:
        _raise_for_api_error(exc)
        raise

    tool_calls = [
        ToolCall(tool_name=block.name, tool_input=block.input, tool_use_id=block.id)
        for block in response.content
        if block.type == "tool_use"
    ]
    return response.stop_reason, tool_calls


async def compact_memory(api_key: str, model: str, history: list[dict]) -> str:
    prompt = _load_prompt("compactor.txt").format(history=history)
    client = _get_client(api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        _raise_for_api_error(exc)
        raise

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise AgentParsingError("compact_memory: model returned no text content")
    return "".join(text_blocks).strip()
