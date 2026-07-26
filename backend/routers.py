"""FastAPI route definitions. Dependency-injects the Temporal Client for workflow interactions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.service import RPCError

from backend import db
from backend.models.api import (
    CreateRunRequest,
    CreateSupervisorConfigRequest,
    InjectEventRequest,
    InstructionRequest,
    RunResponse,
    SupervisorConfigResponse,
)
from backend.models.enums import RunStatus
from backend.workflows import OrderSupervisorWorkflow, OrderSupervisorWorkflowInput
from config import get_settings

router = APIRouter(prefix="/api")

_temporal_client: Client | None = None


def set_temporal_client(client: Client) -> None:
    global _temporal_client
    _temporal_client = client


def get_temporal_client() -> Client:
    if _temporal_client is None:
        raise HTTPException(status_code=503, detail="Temporal client is not initialized yet.")
    return _temporal_client


TemporalClientDep = Annotated[Client, Depends(get_temporal_client)]


def _workflow_id_for_order(order_id: str) -> str:
    return f"order-supervisor-{order_id}"


@router.post("/supervisors", response_model=SupervisorConfigResponse)
async def create_supervisor_config(payload: CreateSupervisorConfigRequest) -> SupervisorConfigResponse:
    row = await db.insert_supervisor_config(payload.name, payload.description, payload.extra_instructions)
    return SupervisorConfigResponse(**row)


@router.get("/supervisors", response_model=list[SupervisorConfigResponse])
async def list_supervisor_configs() -> list[SupervisorConfigResponse]:
    rows = await db.list_supervisor_configs()
    return [SupervisorConfigResponse(**row) for row in rows]


@router.get("/supervisors/{config_id}", response_model=SupervisorConfigResponse)
async def get_supervisor_config(config_id: str) -> SupervisorConfigResponse:
    row = await db.get_supervisor_config(config_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Supervisor config not found")
    return SupervisorConfigResponse(**row)


@router.post("/runs", response_model=RunResponse)
async def create_run(payload: CreateRunRequest, client: TemporalClientDep) -> RunResponse:
    config = await db.get_supervisor_config(payload.supervisor_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Supervisor config not found")

    run_id = _workflow_id_for_order(payload.order_id)

    try:
        await client.start_workflow(
            OrderSupervisorWorkflow.run,
            OrderSupervisorWorkflowInput(
                run_id=run_id,
                order_id=payload.order_id,
                initial_instructions=list(config["extra_instructions"]),
            ),
            id=run_id,
            task_queue=get_settings().LLM_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except RPCError as exc:
        raise HTTPException(status_code=409, detail=f"Run already exists for order {payload.order_id}") from exc

    row = await db.insert_order_run(run_id, payload.order_id, payload.supervisor_config_id)
    return RunResponse(**row)


@router.get("/runs", response_model=list[RunResponse])
async def list_runs() -> list[RunResponse]:
    rows = await db.list_order_runs()
    return [RunResponse(**row) for row in rows]


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str) -> RunResponse:
    row = await db.get_order_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(**row)


def _get_handle(client: Client, run_id: str):
    return client.get_workflow_handle(run_id)


@router.post("/runs/{run_id}/events")
async def inject_event(run_id: str, payload: InjectEventRequest, client: TemporalClientDep) -> dict:
    handle = _get_handle(client, run_id)
    await handle.signal(
        OrderSupervisorWorkflow.inject_event,
        {"event_type": payload.event_type, "payload": payload.payload},
    )
    return {"status": "signaled"}


@router.post("/runs/{run_id}/instructions")
async def add_instruction(run_id: str, payload: InstructionRequest, client: TemporalClientDep) -> dict:
    handle = _get_handle(client, run_id)
    await handle.signal(OrderSupervisorWorkflow.add_instruction, payload.instruction)
    return {"status": "signaled"}


async def _current_run_or_404(run_id: str) -> dict:
    run = await db.get_order_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/interrupt")
async def interrupt_run(run_id: str, client: TemporalClientDep) -> dict:
    # The workflow itself persists PAUSED via pause_workflow's signal handler (source of truth).
    # The router only forwards the signal — it must not write status here, or a delayed/lost
    # signal would leave the DB showing PAUSED while the workflow keeps running (split-brain).
    handle = _get_handle(client, run_id)
    await handle.signal(OrderSupervisorWorkflow.pause_workflow)
    return {"status": "paused"}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, client: TemporalClientDep) -> dict:
    handle = _get_handle(client, run_id)
    await handle.signal(OrderSupervisorWorkflow.resume_workflow)
    return {"status": "resumed"}


@router.post("/runs/{run_id}/terminate")
async def terminate_run(run_id: str, client: TemporalClientDep) -> dict:
    # Exception to "workflow is the source of truth": terminate() forcefully kills the workflow,
    # which cannot run an activity to persist its own final state. This DB write is a best-effort
    # projection of that termination, not an independent source of truth.
    run = await _current_run_or_404(run_id)
    handle = _get_handle(client, run_id)
    await handle.terminate()
    await db.update_run_state(run_id, RunStatus.TERMINATED, run["memory_summary"], None)
    return {"status": "terminated"}
