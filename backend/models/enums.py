from enum import StrEnum


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    PAUSED = "PAUSED"


class EventType(StrEnum):
    ORDER_EVENT = "order_event"
    TOOL_EXECUTED = "tool_executed"
    MEMORY_COMPACTED = "memory_compacted"
    SYSTEM_ERROR = "system_error"
    INSTRUCTION_ADDED = "instruction_added"
