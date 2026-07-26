"""Database access layer. Uses asyncpg directly against Supabase/Postgres.

CRITICAL: This module must NEVER be imported inside backend/workflows.py.
Only backend/activities.py and backend/routers.py may import this module.
"""

import json
from datetime import datetime

import asyncpg

from backend.exceptions import DatabaseError
from backend.models.enums import EventType, RunStatus

_pool: asyncpg.Pool | None = None

_SCHEMA_VERSION_SQL = """
CREATE TABLE IF NOT EXISTS _schema_version (version INT);
"""

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS supervisor_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    extra_instructions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_runs (
    run_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    supervisor_config_id UUID NOT NULL REFERENCES supervisor_configs(id),
    status TEXT NOT NULL,
    memory_summary TEXT NOT NULL DEFAULT '',
    next_wake_up_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS run_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES order_runs(run_id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS run_final_outputs (
    run_id TEXT PRIMARY KEY REFERENCES order_runs(run_id),
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def init_pool(database_url: str) -> None:
    global _pool
    if _pool is not None:
        return
    _pool = await asyncpg.create_pool(
        dsn=database_url, min_size=1, max_size=10, init=_init_connection
    )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise DatabaseError("Database pool is not initialized. Call init_pool() on startup.")
    return _pool


async def init_db() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(_SCHEMA_VERSION_SQL)
            row = await conn.fetchrow("SELECT version FROM _schema_version LIMIT 1")
            if row is None:
                await conn.execute("INSERT INTO _schema_version (version) VALUES (1)")
            await conn.execute(_TABLES_SQL)


async def event_exists(idempotency_key: str) -> bool:
    pool = get_pool()
    row = await pool.fetchrow("SELECT 1 FROM run_events WHERE idempotency_key = $1", idempotency_key)
    return row is not None


def _row_with_str_id(row: asyncpg.Record, id_field: str = "id") -> dict:
    data = dict(row)
    data[id_field] = str(data[id_field])
    return data


async def insert_supervisor_config(name: str, description: str, extra_instructions: list[str]) -> dict:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO supervisor_configs (name, description, extra_instructions)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, name, description, extra_instructions, created_at
        """,
        name,
        description,
        extra_instructions,
    )
    return _row_with_str_id(row)


async def get_supervisor_config(config_id: str) -> dict | None:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, description, extra_instructions, created_at FROM supervisor_configs WHERE id = $1",
        config_id,
    )
    return _row_with_str_id(row) if row else None


async def list_supervisor_configs() -> list[dict]:
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT id, name, description, extra_instructions, created_at FROM supervisor_configs ORDER BY created_at DESC"
    )
    return [_row_with_str_id(row) for row in rows]


async def insert_order_run(run_id: str, order_id: str, supervisor_config_id: str) -> dict:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO order_runs (run_id, order_id, supervisor_config_id, status, memory_summary)
        VALUES ($1, $2, $3, $4, '')
        RETURNING run_id, order_id, supervisor_config_id, status, memory_summary, next_wake_up_at, created_at
        """,
        run_id,
        order_id,
        supervisor_config_id,
        RunStatus.RUNNING.value,
    )
    return _row_with_str_id(row, "supervisor_config_id")


async def get_order_run(run_id: str) -> dict | None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT run_id, order_id, supervisor_config_id, status, memory_summary, next_wake_up_at, created_at
        FROM order_runs WHERE run_id = $1
        """,
        run_id,
    )
    return _row_with_str_id(row, "supervisor_config_id") if row else None


async def list_order_runs() -> list[dict]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT run_id, order_id, supervisor_config_id, status, memory_summary, next_wake_up_at, created_at
        FROM order_runs ORDER BY created_at DESC
        """
    )
    return [_row_with_str_id(row, "supervisor_config_id") for row in rows]


async def update_run_state(
    run_id: str,
    status: RunStatus,
    memory_summary: str,
    next_wake_up_at: datetime | None,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE order_runs
        SET status = $2, memory_summary = $3, next_wake_up_at = $4, updated_at = now()
        WHERE run_id = $1
        """,
        run_id,
        status.value,
        memory_summary,
        next_wake_up_at,
    )


async def persist_event(
    run_id: str,
    event_type: EventType,
    payload: dict,
    idempotency_key: str,
) -> None:
    if await event_exists(idempotency_key):
        return
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO run_events (run_id, event_type, payload, idempotency_key)
        VALUES ($1, $2, $3::jsonb, $4)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        run_id,
        event_type.value,
        payload,
        idempotency_key,
    )


async def insert_final_output(run_id: str, summary: str) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO run_final_outputs (run_id, summary)
        VALUES ($1, $2)
        ON CONFLICT (run_id) DO NOTHING
        """,
        run_id,
        summary,
    )
