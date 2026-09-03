# Order Supervisor System — Documentation

## What this is

An AI-supervised order management proof-of-concept. Each order gets its own
long-running Temporal workflow that acts as a "supervisor": it watches for
order events (payment failures, shipment updates, customer messages), decides
whether they're worth reacting to, hands important ones to an LLM agent that
can take action (notify the customer, escalate to a human, mark the order
complete) or simply schedule when to check again, and keeps a running memory
summary of everything that's happened — closing out with a final summary of
learnings and feedback once the order reaches a terminal state.

The system is built so that a single order's supervision can run
indefinitely (days, weeks) without the workflow's event history blowing past
Temporal's limits, without polluting the LLM's context with unbounded raw
history, and without hammering the Anthropic API when many orders need
attention at once.

## The orchestrator

**`backend/workflows.py`** — specifically the `OrderSupervisorWorkflow` class
— is the orchestrator. One instance of this workflow exists per order run. It
is the single place that:

- Decides *when* the main agent should run (workflow start, an incoming
  event/signal, or a scheduled wake-up timer).
- Batches and classifies incoming events before deciding whether they're
  important enough to wake the (expensive) main agent.
- Sequences every Activity call (LLM calls, DB writes, tool execution) in a
  deterministic order.
- Owns the run's status as the single source of truth (`RUNNING`, `SLEEPING`,
  `PAUSED`, `COMPLETED`, `TERMINATED`).
- Produces the final summary when a run ends, whether by the agent's own
  decision or a human clicking Terminate.

Everything else in the backend either **feeds** the orchestrator (FastAPI
routes sending signals) or is **called by** it (Activities doing the actual
I/O). The workflow file itself does zero I/O — no `anthropic`, `asyncpg`, or
`datetime.now()` imports — so it stays deterministic and replay-safe, which
is a hard requirement for any Temporal workflow.

## Stack

| Layer | Technology |
|---|---|
| Orchestration | [Temporal](https://temporal.io) (`temporalio` Python SDK 1.30) — durable workflow execution, signals, queries, timers |
| Backend API | FastAPI 0.140 + Uvicorn |
| LLM | Anthropic Claude — Haiku (`claude-haiku-4-5`) as a cheap event classifier, Sonnet (`claude-sonnet-5`) as the main reasoning agent, via the async `anthropic` SDK (0.120) |
| Database | Postgres (Supabase), accessed directly via `asyncpg` (no ORM) |
| Validation | Pydantic 2 (request/response models) + `pydantic-settings` (env-based config) |
| Frontend | Next.js 16 (App Router, React 19) |
| Styling | Tailwind CSS 3 with a custom semantic color-token theme, `@tailwindcss/typography` for Markdown rendering |
| Markdown rendering | `react-markdown` (agent memory/final-summary text) |


## File-by-file: what does what

### Root

| File | Purpose |
|---|---|
| `main.py` | Entrypoint. Boots the FastAPI app (with its `lifespan` hook initializing the DB pool and Temporal client), and runs two Temporal Workers in the same process: one polling `fast-tasks` (just the classifier activity) and one polling `llm-tasks` (the main agent, memory compaction, instruction consolidation, final summary, tool execution, DB state updates). 
| `config.py` | `Settings` (a `pydantic-settings` `BaseSettings`), loaded once via `@lru_cache` from the root `.env`. Every tunable — model IDs, task queue names, per-queue concurrency caps, timeouts, the default wake-up duration — lives here, not scattered across the codebase. |
| `requirements.txt` | Pinned backend dependencies. |
| `README.md` | Setup/run instructions. |
| `run.txt` | A more detailed, copy-pasteable local setup walkthrough. |
| `Dockerfile` | Builds/runs the backend only; the frontend is expected to run locally with `npm run dev` during POC iteration. |
| `trash/implementation.md` | Living design log — every deviation from the original spec, why it was made, and what was verified live vs. just typechecked. |

### `backend/` — the orchestrator and its supporting modules

| File | Purpose |
|---|---|
| **`workflows.py`** | **The orchestrator.** `OrderSupervisorWorkflow`: the main `run()` loop, all `@workflow.signal` handlers (`inject_event`, `add_instruction`, `pause_workflow`, `resume_workflow`, `terminate_workflow`), the `get_state` query, and every `workflow.execute_activity(...)` call site. Pure state machine — no I/O. |
| `activities.py` | Every `@activity.defn` — the only place side effects happen. Runs the classifier, runs the main agent's tool-calling loop, compacts memory, consolidates instructions, generates the final summary, executes tools (mocked for the POC), and persists run state. A small dispatch table (`_TOOL_HANDLERS`) replaces an if/elif chain for handling the main agent's tool calls. |
| `agents.py` | All Anthropic API calls, using a cached `AsyncAnthropic` client. Loads prompts from `backend/prompts/v1/*.txt`. Never touches the database — returns plain data back to `activities.py`, which is responsible for persistence. |
| `db.py` | The only module allowed to talk to Postgres (via `asyncpg`, no ORM). Owns schema creation (`CREATE TABLE IF NOT EXISTS`), all CRUD for supervisor configs, order runs, run events, and final outputs. Explicitly forbidden from being imported by `workflows.py`. |
| `routers.py` | FastAPI route definitions. Translates HTTP requests into Temporal Client calls: starting workflows, sending signals, running queries, and reading run/event/final-output data back from the DB for display. |
| `exceptions.py` | The application's exception hierarchy (`OrderSupervisorError` → `DatabaseError`, `ActivityError` → `AgentParsingError`, `NonRetryableAgentError`). Used to distinguish retryable Activity failures (Temporal will retry) from ones that shouldn't be retried (e.g. a 400 from Anthropic). |
| `models/enums.py` | `RunStatus` and `EventType` string enums, shared across the whole backend. |
| `models/api.py` | Pydantic request/response models for the FastAPI routes. |
| `models/activity_io.py` | Plain (non-Pydantic) frozen dataclasses used purely inside the Temporal boundary: `ToolCall`, `AgentOutput`. Kept separate from `models/api.py` because Activity/workflow payloads don't need Pydantic's validation machinery. |
| `models/tools.py` | The 4 tool schemas the main agent can call (`ScheduleNextWakeUpTool`, `SendCustomerNotificationTool`, `EscalateToHumanTool`, `MarkOrderCompleteTool`), a registry, and two functions — `all_tool_schemas()` vs. `scheduled_check_in_tool_schemas()` — controlling which subset is offered to the LLM depending on context. |
| `prompts/v1/*.txt` | Every prompt template as a plain text file, loaded and cached at runtime: `classifier.txt`, `main_agent.txt`, `compactor.txt`, `final_summary.txt`, `instruction_consolidator.txt`. |

### `frontend/` — Next.js App Router UI

| File | Purpose |
|---|---|
| `app/layout.tsx` | Root layout: fixed top bar, left nav rail, font loading (`next/font/google`). |
| `app/page.tsx` | Redirects `/` → `/runs`. |
| `app/runs/page.tsx` | Lists all runs (status, order id) and hosts the "Start New Run" form. |
| `app/runs/[id]/page.tsx` | The run detail page — the main "orchestrator" of the UI in the sense that it composes every other run-related component: memory, timeline, final summary, manual controls, event/instruction injection, and the background poller. |
| `app/supervisors/page.tsx` | Lists supervisor configs and hosts the "Create Supervisor Config" form. |
| `app/components/BentoCard.tsx` | Shared card/panel shell used by nearly every section. |
| `app/components/StatusPill.tsx` | Colored status badge (`RUNNING`/`SLEEPING`/`PAUSED`/`COMPLETED`/`TERMINATED`). |
| `app/components/MemorySummary.tsx` | Renders the agent's running memory summary as Markdown. Server Component — `react-markdown` here costs zero client-side JS. |
| `app/components/Timeline.tsx` | Server Component; fetches and renders a run's recent event history. |
| `app/components/FinalSummary.tsx` | Server Component; fetches and renders the run's final summary (what happened / learnings / feedback) once one exists. |
| `app/components/EventInjector.tsx` | Client Component form for manually injecting an order event — a repeatable key/value field builder instead of a raw JSON textarea. |
| `app/components/InstructionAdder.tsx` | Client Component form for adding a standing instruction to a run. |
| `app/components/ControlPanel.tsx` | Client Component with Pause/Resume/Terminate buttons; owns submission/loading state and polls for the final summary right after a Terminate click. |
| `app/components/RunPoller.tsx` | Client Component, renders nothing. Background "smart polling" — see Optimizations below. |
| `app/components/CreateRunForm.tsx` / `CreateSupervisorForm.tsx` | Client Component forms for the two creation flows. |
| `app/components/icons/index.tsx` | Inline SVG icon set used throughout. |
| `lib/api.ts` | The only place that calls the backend. Typed fetch wrappers for every route, attaching `Content-Type` to every request. |
| `tailwind.config.ts` | Custom semantic color tokens (surface, on-surface, error-container, etc.) plus the typography plugin. |

## Optimizations

A running list of deliberate performance/cost/robustness decisions, in the
order they matter most:

1. **Dynamic tool injection on scheduled check-ins.** When the main agent
   wakes up on a schedule with no new events to react to, it's only given the
   `schedule_next_wake_up` tool — not the full toolset. LLMs are biased
   toward action; handing an idle agent customer-facing/escalation tools
   invites it to hallucinate a reason to use one just because it's
   available. (`activities.py`, `models/tools.py`)

2. **A cheap classifier gates the expensive main agent.** Every incoming
   event first goes through a fast Haiku-based classifier (`fast-tasks`
   queue, its own worker, higher concurrency cap) that decides yes/no on
   whether it's worth waking the (slower, costlier) Sonnet-based main agent.
   Only events the classifier flags as important reach the main agent.
   (`workflows.py`, `agents.py::run_classifier`)

3. **A dead-man's-switch against a stuck classifier.** If unprocessed events
   pile up past a threshold (`_CLASSIFIER_BYPASS_BACKLOG_THRESHOLD = 5`)
   without the classifier ever waking the main agent, the workflow stops
   trusting the classifier's gatekeeping and forces the whole batch through
   to the main agent directly — protecting against silently dropping
   important events if the classifier is misbehaving. (`workflows.py`)

4. **Idempotent Activities everywhere.** Every Activity that writes to the
   DB or calls the LLM takes a caller-supplied idempotency key and checks
   `db.event_exists(...)` (or an equivalent) before doing real work. Temporal
   retries Activities on failure/worker restart; without this, a retry could
   double-charge an LLM call or double-insert a DB row. (`activities.py`,
   `db.py`)

5. **Async Anthropic client, not sync-in-a-thread.** `agents.py` uses
   `anthropic.AsyncAnthropic` directly rather than wrapping the sync client
   in `asyncio.to_thread`. This means cancellation (e.g. from a Temporal
   heartbeat timeout) propagates natively into the in-flight HTTP request
   instead of leaking an orphaned background thread that keeps running after
   Temporal has moved on.

6. **Heartbeating + bounded retries on every LLM Activity.** Every
   LLM-calling Activity (`run_main_agent`, `compact_memory`,
   `consolidate_instructions`, `run_classifier`, `generate_final_output`)
   heartbeats every 10 seconds while awaiting the Anthropic call, and is
   executed with `start_to_close_timeout` (2 min), `heartbeat_timeout` (30s),
   and a capped `retry_policy` (`maximum_attempts=5`). An Anthropic hang is
   caught by the heartbeat timeout instead of freezing the workflow forever;
   a string of 5xxs exhausts its retries and fails cleanly instead of
   retrying indefinitely. (`workflows.py`)

7. **Per-task-queue concurrency caps prevent a 429 thundering herd.** The
   classifier's `fast-tasks` worker and the main agent's `llm-tasks` worker
   each have their own `max_concurrent_activities` cap
   (`FAST_TASK_MAX_CONCURRENT_ACTIVITIES=20`,
   `LLM_TASK_MAX_CONCURRENT_ACTIVITIES=8`). Without this, a burst of events
   across many orders could fan out unboundedly and slam the Anthropic API
   with concurrent requests, triggering a 429 pileup as everything backs off
   and retries at once. Temporal queues the excess work in memory instead.
   (`main.py`, `config.py`)

8. **Instruction consolidation, with a cheap local-join threshold.** Rather
   than resending every instruction ever added to a run inside every
   main-agent prompt (unbounded growth, eventually confusing the model or
   bloating token count), instructions accumulate in a small pending list and
   get folded into one `standing_orders` string once 3 have queued up. That
   fold-in only pays for an LLM call (conflict resolution / summarization)
   when the pending text exceeds 500 characters
   (`_INSTRUCTION_LLM_CONSOLIDATION_MIN_CHARS`) — below that, it's just a
   local string join, since a few short instructions don't need an LLM to
   merge. (`workflows.py`)

9. **`continue_as_new` guards against Temporal's event-history limit.** A
   long-running order (weeks of events, wake-ups, tool calls) would
   eventually approach Temporal's ~50k-event-per-workflow-history ceiling. A
   plain `event_count` counter triggers `continue_as_new` once it crosses
   `_MAX_EVENT_COUNT_BEFORE_CONTINUE = 4000`, carrying memory, wake-up time,
   and standing orders forward into a fresh workflow history transparently.
   (`workflows.py`)

10. **Signal handlers only mutate state; the main loop is the only place
    that executes Activities.** `pause_workflow`, `resume_workflow`,
    `terminate_workflow` and friends set flags/status and a
    `_status_persist_pending` bit — they never call `workflow.execute_activity`
    themselves. Only the main `run()` loop turns that pending flag into a
    real persistence Activity call. This keeps Temporal's event history a
    clean sequential trace instead of activities spawned concurrently from
    inside signal handlers, and avoids race conditions between a signal
    arriving and an in-flight activity completing. (`workflows.py`)

11. **Graceful terminate via signal, not a hard `handle.terminate()` kill.**
    Clicking Terminate sends a `terminate_workflow` signal rather than
    forcibly killing the workflow execution. This lets the workflow exit its
    own loop naturally and still reach `generate_final_output`, so every
    path that ends a run — agent-driven completion or a human terminating it
    — produces a final summary. Two related race conditions were found and
    fixed during this: a "resurrection" race (an in-flight activity's stale
    result overwriting a just-arrived terminate signal) and an "unpersisted
    terminal status" bug (the loop's `while` condition exiting before the
    loop body's own persist-on-exit logic could run). (`workflows.py`,
    `routers.py`)

12. **Module-level prompt caching.** `_load_prompt(name)` is
    `@lru_cache(maxsize=None)` — unbounded, but safe, since the set of prompt
    filenames is small and fixed (5 total). First call per prompt reads from
    disk; every call after that is a cache hit, with no eviction risk.
    (`agents.py`)

13. **TTL'd Anthropic client cache.** The Anthropic client is cached per API
    key with a 20-minute TTL (`cachetools.TTLCache`) rather than an
    unbounded `@lru_cache` — avoids creating a fresh client (and its
    underlying HTTP connection pool) on every call while still recycling
    stale clients periodically. (`agents.py`)

14. **Smart client-side polling on the run detail page.** `RunPoller.tsx` is
    a Client Component that renders nothing — it polls `getRun(runId)` every
    10 seconds and only calls `router.refresh()` (a full Server Component
    re-render) if the run's `status` actually changed since the last known
    value. It doesn't start polling at all once a run is `COMPLETED` or
    `TERMINATED` (dead workflows can't change state). This closes the gap
    where a workflow wakes up and acts on its own schedule but a user sitting
    on the page would otherwise see nothing update until they clicked
    something or manually reloaded — without polling unconditionally or
    re-rendering the server tree every tick regardless of whether anything
    changed. (`app/components/RunPoller.tsx`)

15. **Dead code removed after an audit.** An unregistered/undispatched
    Activity wrapper, unused imports, a never-instantiated dataclass, an
    unused exception class, and an unused package barrel export were found
    (each cross-checked against every call site before deletion) and
    removed, keeping the codebase's actual surface area matching what's
    really in use.
