from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field


class BaseTool(BaseModel, ABC):
    """Base class for Anthropic tool schemas. Subclasses declare their own fields as the tool's input schema."""

    tool_name: ClassVar[str]
    tool_description: ClassVar[str]

    @classmethod
    @abstractmethod
    def to_anthropic_schema(cls) -> dict:
        ...


class ScheduleNextWakeUpTool(BaseTool):
    tool_name: ClassVar[str] = "schedule_next_wake_up"
    tool_description: ClassVar[str] = (
        "Schedule when the supervisor should next re-evaluate this order. "
        "Use this when there is nothing urgent to do right now."
    )

    next_wake_up_duration_seconds: int = Field(
        ..., description="Seconds from now to wake up and re-evaluate the order.", gt=0
    )

    @classmethod
    def to_anthropic_schema(cls) -> dict:
        return {
            "name": cls.tool_name,
            "description": cls.tool_description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "next_wake_up_duration_seconds": {
                        "type": "integer",
                        "description": "Seconds from now to wake up and re-evaluate the order.",
                        "exclusiveMinimum": 0,
                    }
                },
                "required": ["next_wake_up_duration_seconds"],
            },
        }


class SendCustomerNotificationTool(BaseTool):
    tool_name: ClassVar[str] = "send_customer_notification"
    tool_description: ClassVar[str] = "Send a notification message to the customer about their order."

    message: str = Field(..., description="The message to send to the customer.")

    @classmethod
    def to_anthropic_schema(cls) -> dict:
        return {
            "name": cls.tool_name,
            "description": cls.tool_description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The message to send to the customer."}
                },
                "required": ["message"],
            },
        }


class EscalateToHumanTool(BaseTool):
    tool_name: ClassVar[str] = "escalate_to_human"
    tool_description: ClassVar[str] = "Escalate this order to a human support agent for manual handling."

    reason: str = Field(..., description="Why this order needs human attention.")

    @classmethod
    def to_anthropic_schema(cls) -> dict:
        return {
            "name": cls.tool_name,
            "description": cls.tool_description,
            "input_schema": {
                "type": "object",
                "properties": {"reason": {"type": "string", "description": "Why this order needs human attention."}},
                "required": ["reason"],
            },
        }


class MarkOrderCompleteTool(BaseTool):
    tool_name: ClassVar[str] = "mark_order_complete"
    tool_description: ClassVar[str] = (
        "Mark this order as reaching a terminal state (e.g. delivered, cancelled, refund_completed). "
        "This ends supervision of the order permanently."
    )

    final_status: str = Field(..., description="The terminal status reached, e.g. 'delivered', 'cancelled', 'refund_completed'.")

    @classmethod
    def to_anthropic_schema(cls) -> dict:
        return {
            "name": cls.tool_name,
            "description": cls.tool_description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "final_status": {
                        "type": "string",
                        "description": "The terminal status reached, e.g. 'delivered', 'cancelled', 'refund_completed'.",
                    }
                },
                "required": ["final_status"],
            },
        }


TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    ScheduleNextWakeUpTool.tool_name: ScheduleNextWakeUpTool,
    SendCustomerNotificationTool.tool_name: SendCustomerNotificationTool,
    EscalateToHumanTool.tool_name: EscalateToHumanTool,
    MarkOrderCompleteTool.tool_name: MarkOrderCompleteTool,
}


def all_tool_schemas() -> list[dict]:
    return [tool_cls.to_anthropic_schema() for tool_cls in TOOL_REGISTRY.values()]
