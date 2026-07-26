"""Entrypoint: FastAPI server + Temporal Workers (fast-tasks classifier worker, llm-tasks main worker)."""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from temporalio.client import Client
from temporalio.worker import Worker

from backend import activities, db
from backend.routers import router, set_temporal_client
from backend.workflows import OrderSupervisorWorkflow
from config import get_settings

_FAST_TASK_ACTIVITIES = [activities.run_classifier]
_LLM_TASK_ACTIVITIES = [
    activities.run_main_agent,
    activities.compact_memory,
    activities.generate_final_output,
    activities.execute_tool,
    activities.persist_event,
    activities.update_run_state,
]


async def _run_workers(client: Client) -> None:
    settings = get_settings()

    fast_worker = Worker(
        client,
        task_queue=settings.FAST_TASK_QUEUE,
        workflows=[],
        activities=_FAST_TASK_ACTIVITIES,
    )
    llm_worker = Worker(
        client,
        task_queue=settings.LLM_TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=_LLM_TASK_ACTIVITIES,
    )

    await asyncio.gather(fast_worker.run(), llm_worker.run())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    await db.init_pool(settings.DATABASE_URL)
    await db.init_db()

    client = await Client.connect(settings.TEMPORAL_HOST)
    set_temporal_client(client)

    worker_task = asyncio.create_task(_run_workers(client))

    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await db.close_pool()


app = FastAPI(title="Order Supervisor System", lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.FASTAPI_PORT)
