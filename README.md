# Order Supervisor System

An AI-supervised order management POC. A Temporal workflow orchestrates a fast
classifier and a capable main agent (both backed by Claude) to monitor orders,
react to events, and decide when to sleep, act, or terminate.

## Architecture

- **`main.py`** — FastAPI server + two Temporal workers in one process:
  - `fast-tasks` queue: the lightweight event classifier.
  - `llm-tasks` queue: the main agent, memory compaction, and all DB writes.
  - CORS middleware (`CORS_ALLOWED_ORIGINS`) and an `X-Mac` shared-secret
    header gate (`X_MAC_SECRET`) sit in front of every route.
- **`backend/workflows.py`** — `OrderSupervisorWorkflow`, a deterministic state
  machine. No I/O, no `anthropic`/`asyncpg`/`datetime.now()` imports.
  - The workflow is the sole source of truth for run status. Signal handlers
    (`pause_workflow`, `resume_workflow`) only mutate state and set a pending
    flag; the main loop is the only place that executes the persistence
    Activity, keeping Temporal's event history a clean sequential trace.
  - Guards against Temporal's ~50k-event history limit via a plain
    `event_count` counter that triggers `continue_as_new` past a threshold,
    carrying memory/wake-up-time/instructions forward transparently.
- **`backend/activities.py`** — all side effects (LLM calls, DB writes, tool
  execution), each activity idempotent via a caller-supplied idempotency key.
  Heartbeats while awaiting LLM calls; cancellation propagates natively since
  `agents.py` uses `AsyncAnthropic` (no background thread to leak).
- **`backend/agents.py`** — Anthropic SDK calls via the async client. Never
  touches the database.
- **`backend/db.py`** — asyncpg pool against Supabase/Postgres. Never imported
  by `workflows.py`.
- **`frontend/`** — Next.js App Router UI: create supervisor configs, start
  runs, inject events, add instructions, pause/resume/terminate.

## Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase (or any Postgres) project — get the **session pooler** connection
  string from Project Settings → Database → Connect (the direct `db.*.supabase.co`
  host requires IPv6 and may not resolve on all networks).
- [Temporal CLI](https://docs.temporal.io/cli) for a local dev server:
  `brew install temporal`
- An Anthropic API key.

## Setup

1. Copy your credentials into the root `.env` — this is the **single source
   of truth** for every env var, backend and frontend alike:
   - `DATABASE_URL`, `TEMPORAL_HOST`, `ANTHROPIC_API_KEY`, `FASTAPI_PORT`
   - `CORS_ALLOWED_ORIGINS` (default `http://localhost:3000`)
   - `X_MAC_SECRET` / `NEXT_PUBLIC_X_MAC_SECRET` (same value on both — sent as
     the `X-Mac` header on every frontend request, validated by the backend)
   - `NEXT_PUBLIC_API_URL` (backend base URL for the frontend)

   `frontend/next.config.js` reads the root `.env` directly at config-load
   time and injects any `NEXT_PUBLIC_*` key into Next.js's `env` field — no
   generated `.env.local` file, no `dotenv` dependency.

2. Start a local Temporal dev server:
   ```bash
   temporal server start-dev
   ```

3. Backend:
   ```bash
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python main.py
   ```
   This initializes the DB schema (`CREATE TABLE IF NOT EXISTS`), connects to
   Temporal, starts both workers, and serves FastAPI on `FASTAPI_PORT`.

4. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Visit `http://localhost:3000`.

See `run.txt` for a more detailed, copy-pasteable walkthrough.

## Docker

The `Dockerfile` builds and runs the backend only (`python main.py`). For fast
UI iteration during the POC, run the Next.js app locally with `npm run dev`
against the containerized (or locally-run) backend.

```bash
docker build -t order-supervisor .
docker run --env-file .env -p 8000:8000 order-supervisor
```

## API

See `backend/routers.py` for the full route list: supervisor config CRUD, run
lifecycle (`start`, `events`, `instructions`, `interrupt`, `resume`,
`terminate`), and run listing/detail. Every request must carry an `X-Mac`
header matching `X_MAC_SECRET`, or the backend rejects it with 401.

## Further reading

`trash/implementation.md` documents the system in depth — every module,
every deliberate deviation from the original spec (and why), and what was
verified against live Temporal/Supabase/Anthropic infrastructure rather than
just typechecked.
