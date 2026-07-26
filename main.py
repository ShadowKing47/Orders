"""Entrypoint: FastAPI server + Temporal Workers (fast-tasks classifier worker, llm-tasks main worker)."""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    activities.consolidate_instructions,
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
        # Haiku (the classifier model) is faster and has higher rate limits than the
        # main-agent model, so this queue can tolerate more concurrent Anthropic calls.
        max_concurrent_activities=settings.FAST_TASK_MAX_CONCURRENT_ACTIVITIES,
    )
    llm_worker = Worker(
        client,
        task_queue=settings.LLM_TASK_QUEUE,
        workflows=[OrderSupervisorWorkflow],
        activities=_LLM_TASK_ACTIVITIES,
        # Caps how many run_main_agent/compact_memory/etc. activities execute at once on
        # this worker. Without this, a burst of events across many orders (e.g. 100 orders
        # all hitting payment_failed at once) would let Temporal fan out unboundedly and
        # slam the Anthropic API with concurrent requests, triggering a 429 thundering herd
        # as everything backs off and retries around the same time. Temporal queues the
        # excess work in memory instead of ever sending it to Anthropic.
        max_concurrent_activities=settings.LLM_TASK_MAX_CONCURRENT_ACTIVITIES,
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


async def _require_x_mac_header(request: Request, call_next):
    if request.method != "OPTIONS" and request.headers.get("x-mac") != get_settings().X_MAC_SECRET:
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid X-Mac header"})
    return await call_next(request)


app = FastAPI(title="Order Supervisor System", lifespan=lifespan)
app.middleware("http")(_require_x_mac_header)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.FASTAPI_PORT)
