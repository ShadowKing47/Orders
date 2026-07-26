# Order Supervisor System

An AI-supervised order management POC. A Temporal workflow orchestrates a fast
classifier and a capable main agent (both backed by Claude) to monitor orders,
react to events, and decide when to sleep, act, or terminate.

## Architecture

- **`main.py`** — FastAPI server + two Temporal workers in one process:
  - `fast-tasks` queue: the lightweight event classifier.
  - `llm-tasks` queue: the main agent, memory compaction, and all DB writes.
- **`backend/workflows.py`** — `OrderSupervisorWorkflow`, a deterministic state
  machine. No I/O, no `anthropic`/`asyncpg`/`datetime.now()` imports.
- **`backend/activities.py`** — all side effects (LLM calls, DB writes, tool
  execution), each activity idempotent via a caller-supplied idempotency key.
- **`backend/agents.py`** — Anthropic SDK calls. Never touches the database.
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

1. Copy your credentials into the root `.env` (see `.env` for the expected
   keys: `DATABASE_URL`, `TEMPORAL_HOST`, `ANTHROPIC_API_KEY`, `FASTAPI_PORT`).
   Also set `NEXT_PUBLIC_API_URL` there — `frontend/load-env.js` reads it out
   of the root `.env` and writes `frontend/.env.local` before each
   `next dev`/`next build`, so there is still only one source of truth for env
   vars even though Next.js requires its own `.env.local`.

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
`terminate`), and run listing/detail.
