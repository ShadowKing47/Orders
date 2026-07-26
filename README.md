# Order Supervisor System

An AI-supervised order management POC. A Temporal workflow orchestrates a fast
classifier and a capable main agent (both backed by Claude) to monitor orders,
react to events, and decide when to sleep, act, or terminate.

The orchestrator is **`backend/workflows.py`** (`OrderSupervisorWorkflow`) — see
`documentation.md` for a full file-by-file breakdown, the stack, and the
optimizations applied.

## Architecture

**Short version:** the Next.js frontend never talks to Temporal directly — it
only calls the FastAPI backend over HTTP. FastAPI starts one Temporal
workflow per order and, after that, only sends it signals (inject an event,
add an instruction, pause/resume/terminate) or reads its persisted state back
from Postgres. The workflow itself (`OrderSupervisorWorkflow`) is the
orchestrator: it decides when to wake, classifies events through a cheap
Haiku model before bothering the slower Sonnet-based main agent, dispatches
every LLM call/DB write/tool execution as a Temporal Activity, and writes its
status and memory back to Postgres so the API/UI can read it without going
through Temporal at all.

```
Browser (Next.js) --HTTP--> FastAPI (routers.py) --signals/start--> Temporal workflow (workflows.py)
                                  |                                         |
                                  |                                  execute_activity
                                  v                                         v
                              Postgres  <---------- writes ---------  Activities (activities.py)
                                                                            |
                                                                     Anthropic (agents.py)
```

- **`main.py`** — FastAPI server + two Temporal workers in one process:
  - `fast-tasks` queue: the lightweight event classifier.
  - `llm-tasks` queue: the main agent, memory compaction, and all DB writes.
  - CORS middleware (`CORS_ALLOWED_ORIGINS`) and an `X-Mac` shared-secret
    header gate (`X_MAC_SECRET`) sit in front of every route.
- **`backend/workflows.py`** — `OrderSupervisorWorkflow`, a deterministic state
  machine and the system's orchestrator. No I/O, no `anthropic`/`asyncpg`/
  `datetime.now()` imports.
  - The workflow is the sole source of truth for run status. Signal handlers
    (`pause_workflow`, `resume_workflow`, `terminate_workflow`) only mutate
    state and set a pending flag; the main loop is the only place that
    executes the persistence Activity, keeping Temporal's event history a
    clean sequential trace.
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
  runs, inject events, add instructions, pause/resume/terminate, and view a
  run's memory, timeline, and final summary. A client-side poller
  (`RunPoller.tsx`) refreshes the page automatically when a run's status
  changes in the background (e.g. a scheduled wake-up), without spamming the
  server when nothing has changed.

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

1. Create a single `.env` file at the **repository root**
   (`/Users/noel/Documents/Orders/.env` — the same folder as `main.py` and
   `requirements.txt`, one level *above* `frontend/`). This one file is the
   **single source of truth** for every env var, backend and frontend alike —
   there is no separate `frontend/.env.local`.

   | Variable | Required | Default | Purpose |
   |---|---|---|---|
   | `DATABASE_URL` | Yes | — | Postgres connection string. For Supabase, use the **session pooler** URI from Project Settings → Database → Connect (the direct `db.*.supabase.co` host needs IPv6 and may not resolve on all networks). |
   | `TEMPORAL_HOST` | Yes | — | Host:port of the Temporal server, e.g. `localhost:7233` for the local dev server. |
   | `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key used for both the classifier (Haiku) and main agent (Sonnet). |
   | `FASTAPI_PORT` | No | `8000` | Port the backend listens on. |
   | `CORS_ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated list of origins allowed to call the backend. |
   | `X_MAC_SECRET` | No | `""` | Shared-secret value the backend requires on every request's `X-Mac` header. |
   | `NEXT_PUBLIC_X_MAC_SECRET` | Yes (if `X_MAC_SECRET` is set) | — | Must be **identical** to `X_MAC_SECRET` — this is what the frontend actually sends. |
   | `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Backend base URL the frontend calls. |

   Only keys prefixed `NEXT_PUBLIC_` are exposed to the frontend/browser;
   everything else (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `X_MAC_SECRET`, etc.)
   stays backend-only. `frontend/next.config.js` reads the root `.env`
   directly at config-load time and injects any `NEXT_PUBLIC_*` key into
   Next.js's `env` field — no generated `.env.local` file, no `dotenv`
   dependency, and nothing to duplicate between backend and frontend.

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
`terminate`), run listing/detail, run event history, and final-output
retrieval. Every request must carry an `X-Mac` header matching
`X_MAC_SECRET`, or the backend rejects it with 401.

## Further reading

- **`documentation.md`** — project overview, full stack, a file-by-file map of
  what does what, and every deliberate optimization applied (idempotency,
  dynamic tool injection, dead-man's-switch classifier bypass, instruction
  consolidation with a cheap local-join threshold, per-queue activity
  concurrency caps, smart client-side polling, and more).
