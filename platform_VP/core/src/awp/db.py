"""The platform's own database (separate from AgentScope's storage)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

metadata = MetaData()

cases = Table(
    "awp_cases", metadata,
    Column("id", String(40), primary_key=True),
    Column("tenant", String(80), nullable=False, index=True),
    Column("domain", String(80), nullable=False),
    Column("external_ref", String(200), nullable=False, default=""),
    Column("status", String(20), nullable=False, default="open"),
    Column("user_id", String(200), nullable=False),  # a workflow's case carries the partner's external_user_id (<= 200)
    Column("leader_agent_id", String(60)),
    Column("leader_session_id", String(60)),
    Column("meta", JSON, nullable=False, default=dict),  # how the case came in: workflow, route, summary
    Column("result", JSON),
    Column("budget_usd", Float, nullable=False, default=0.0),
    Column("budget_tokens", Integer, nullable=False, default=0),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    UniqueConstraint("tenant", "domain", "external_ref", name="uq_case_external"),
)

case_items = Table(
    "awp_case_items", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(40), nullable=False),
    Column("ref", String(16), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("author", String(80), nullable=False),
    Column("addressee", String(80)),
    Column("data", JSON, nullable=False, default=dict),
    Column("created_at", Float, nullable=False),
    UniqueConstraint("case_id", "ref", name="uq_item_ref"),
    Index("ix_item_case", "case_id", "id"),
)

cursors = Table(
    "awp_cursors", metadata,
    Column("case_id", String(40), primary_key=True),
    Column("agent_key", String(120), primary_key=True),
    Column("last_item_id", Integer, nullable=False, default=0),
)

case_sessions = Table(
    "awp_case_sessions", metadata,
    Column("session_id", String(60), primary_key=True),
    Column("case_id", String(40), nullable=False, index=True),
    Column("agent_id", String(60), nullable=False),
    Column("agent_name", String(80), nullable=False, default=""),
    Column("role", String(12), nullable=False),  # leader | worker
)

ledger = Table(
    "awp_ledger", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant", String(80), nullable=False, index=True),
    Column("case_id", String(40), index=True),
    Column("session_id", String(60)),
    Column("agent_id", String(60)),
    Column("agent_name", String(80)),
    Column("model", String(120), nullable=False),
    Column("tier", String(16)),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("cache_read_tokens", Integer, nullable=False, default=0),
    Column("cache_write_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float, nullable=False, default=0.0),
    Column("priced", Integer, nullable=False, default=0),
    Column("created_at", Float, nullable=False),
)

profiles = Table(
    "awp_profiles", metadata,
    Column("id", String(40), primary_key=True),
    Column("tenant", String(80), nullable=False),
    Column("key", String(80), nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", String(12), nullable=False),  # draft | published | retired
    Column("data", JSON, nullable=False),
    Column("created_at", Float, nullable=False),
    Column("published_at", Float),  # the last time this version went live (a rollback publishes it again)
    Column("published_by", String(80)),
    UniqueConstraint("tenant", "key", "version", name="uq_profile_version"),
    # One published version of a key: two publishers at once cannot both win, whatever they read (profiles/store.py).
    Index("uq_profile_published", "tenant", "key", unique=True,
          sqlite_where=text("status = 'published'"), postgresql_where=text("status = 'published'")),
)

# Who holds a profile key. The live sub-agent templates are keyed by the key alone, so a key belongs to one tenant at a
# time: every draft and every publish reads this row under its lock first (profiles/store.py `_own`), and the primary key
# decides between two tenants that take a new key at the same moment.
profile_keys = Table(
    "awp_profile_keys", metadata,
    Column("key", String(80), primary_key=True),
    Column("tenant", String(80), nullable=False),
)

# What happened to a profile key, in order: create, eval, publish, override, rollback, retire. Written in the transaction
# of the change it records, so the history cannot say something that did not happen.
profile_events = Table(
    "awp_profile_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant", String(80), nullable=False),
    Column("key", String(80), nullable=False),
    Column("version", Integer),
    Column("kind", String(16), nullable=False),
    Column("actor", String(80), nullable=False, default=""),
    Column("detail", JSON, nullable=False, default=dict),
    Column("created_at", Float, nullable=False),
    Index("ix_profile_event_key", "tenant", "key", "id"),
)

# A chat in which an admin builds agents (M2): what was said, and the proposals now on the table.
builder_sessions = Table(
    "awp_builder_sessions", metadata,
    Column("id", String(40), primary_key=True),
    Column("tenant", String(80), nullable=False, index=True),
    Column("messages", JSON, nullable=False, default=list),
    Column("proposals", JSON, nullable=False, default=list),
    Column("revision", Integer, nullable=False, default=0),  # goes up with every write: two writers cannot both win
    Column("created_by", String(80), nullable=False, default=""),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
)

# An evaluation case a tenant wrote for one profile key (the platform's own cases are code: evals/defaults.py).
eval_cases = Table(
    "awp_eval_cases", metadata,
    Column("id", String(40), primary_key=True),
    Column("tenant", String(80), nullable=False),
    Column("key", String(80), nullable=False),
    Column("name", String(120), nullable=False),
    Column("input", Text, nullable=False),
    Column("fixtures", JSON, nullable=False, default=dict),  # tool name -> what it answers in the sandbox
    Column("checks", JSON, nullable=False, default=dict),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    UniqueConstraint("tenant", "key", "name", name="uq_eval_case_name"),
)

# One run of every case against one exact version. `profile_hash` is the content that ran: a draft edited afterwards
# has no passing run.
eval_runs = Table(
    "awp_eval_runs", metadata,
    Column("id", String(40), primary_key=True),
    Column("tenant", String(80), nullable=False),
    Column("key", String(80), nullable=False),
    Column("version", Integer, nullable=False),
    Column("profile_hash", String(80), nullable=False),
    Column("cases_hash", String(80)),  # the cases that ran (the platform's and the tenant's): a case written afterwards did not
    Column("status", String(12), nullable=False),  # running | passed | failed | error
    Column("score", Float),  # cases passed / cases run
    Column("results", JSON, nullable=False, default=list),  # one entry per case: checks, cost, duration
    Column("cost_usd", Float, nullable=False, default=0.0),
    Column("duration_s", Float),
    Column("started_by", String(80), nullable=False, default=""),
    Column("error", String(300)),
    Column("deadline", Float, nullable=False),  # its process moves this on while it lives: `running` after it is a dead run
    Column("created_at", Float, nullable=False),
    Column("finished_at", Float),
    Index("ix_eval_run_version", "tenant", "key", "version", "created_at"),
    # One running run of a version, whoever asks and in whichever process (evals/runner.py `start`).
    Index("uq_eval_run_running", "tenant", "key", "version", unique=True,
          sqlite_where=text("status = 'running'"), postgresql_where=text("status = 'running'")),
)

agent_map = Table(
    "awp_agent_map", metadata,
    Column("tenant", String(80), primary_key=True),
    Column("key", String(80), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("agent_id", String(60), nullable=False),
)

credential_map = Table(
    "awp_credential_map", metadata,
    Column("user_id", String(120), primary_key=True),
    Column("spec_id", String(80), primary_key=True),
    Column("credential_id", String(60), nullable=False),
)


def _finite(value):
    """The same structure with NaN and the infinities replaced by None."""
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


def dumps(value) -> str:
    """JSON for a JSON column. `NaN` and `Infinity` are not JSON: PostgreSQL refuses them for ever, SQLite would keep them.
    They are stored as null on both, so a tool result with a float that overflowed cannot make a write fail."""
    try:
        return json.dumps(value, allow_nan=False)
    except ValueError:
        return json.dumps(_finite(value), allow_nan=False)


def engine_options(url: str, *, pool_size: int = 10, max_overflow: int = 20, pool_timeout: float = 30.0,
                   pool_recycle: float = 1800.0) -> dict:
    """create_async_engine keyword arguments for a URL: PostgreSQL gets a sized, pre-pinged pool and an explicit isolation
    level (the code relies on READ COMMITTED and row locks, not on what the server's default happens to be)."""
    if not url.startswith("postgresql"):
        return {}
    return {"pool_size": pool_size, "max_overflow": max_overflow, "pool_timeout": pool_timeout,
            "pool_recycle": pool_recycle, "pool_pre_ping": True, "isolation_level": "READ COMMITTED"}


class Database:
    """Thin wrapper over an async SQLAlchemy engine."""

    def __init__(self, url: str, **pool: Any) -> None:
        """`pool` (pool_size, max_overflow, pool_timeout, pool_recycle) applies to PostgreSQL only."""
        kwargs: dict[str, Any] = {"json_serializer": dumps, **engine_options(url, **pool)}
        if url.startswith("sqlite") and ":memory:" not in url:
            kwargs["connect_args"] = {"timeout": 30}
        if url.startswith("sqlite") and ":memory:" in url:
            from sqlalchemy.pool import StaticPool

            kwargs.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
        self.engine: AsyncEngine = create_async_engine(url, **kwargs)
        self.dialect = self.engine.dialect.name
        if url.startswith("sqlite") and ":memory:" not in url:
            # Write-ahead log: a reader never blocks a writer. A run cancelled in the middle of a statement
            # (an interrupt) can strand a read lock, and in the default journal mode that lock makes every
            # later commit wait for the busy timeout and fail.
            @event.listens_for(self.engine.sync_engine, "connect")
            def _wal(dbapi_conn, _record) -> None:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()

    async def create_all(self) -> None:
        from .workforce import tables  # noqa: F401  (registers wf_* on the shared metadata)

        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
