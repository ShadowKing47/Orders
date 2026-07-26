from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    tool_input: dict
    tool_use_id: str


@dataclass(frozen=True)
class ClassifierResult:
    should_wake: bool


@dataclass(frozen=True)
class AgentOutput:
    new_memory_summary: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    next_wake_up_duration_seconds: int | None = None
    is_terminal: bool = False
