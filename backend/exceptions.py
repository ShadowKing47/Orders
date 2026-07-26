class OrderSupervisorError(Exception):
    """Base class for all application-specific errors in this system."""


class WorkflowError(OrderSupervisorError):
    """Raised for errors originating in workflow-level orchestration logic."""


class DatabaseError(OrderSupervisorError):
    """Raised for errors originating from db.py operations."""


class ActivityError(OrderSupervisorError):
    """Raised for errors originating inside Temporal activities (agents.py calls, tool execution)."""


class AgentParsingError(ActivityError):
    """Raised when an LLM response cannot be parsed into the expected structure."""


class NonRetryableAgentError(ActivityError):
    """Raised when the Anthropic API returns a request-shaped error (e.g. 400) that retries cannot fix."""
