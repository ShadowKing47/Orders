from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import RunStatus


class CreateSupervisorConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    extra_instructions: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class SupervisorConfigResponse(BaseModel):
    id: str
    name: str
    description: str
    extra_instructions: list[str]
    created_at: datetime


class CreateRunRequest(BaseModel):
    supervisor_config_id: str = Field(..., min_length=1)
    order_id: str = Field(..., min_length=1, max_length=200)


class RunResponse(BaseModel):
    run_id: str
    order_id: str
    supervisor_config_id: str
    status: RunStatus
    memory_summary: str
    next_wake_up_at: datetime | None
    created_at: datetime


class InjectEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class InstructionRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)
