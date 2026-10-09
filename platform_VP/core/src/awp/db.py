"""The platform's own database (separate from AgentScope's storage)."""
from __future__ import annotations

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
    select,
    insert,
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
    Column("user_id", String(120), nullable=False),
    Column("leader_agent_id", String(60)),
    Column("leader_session_id", String(60)),
    Column("intake", JSON, nullable=False, default=dict),
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
    UniqueConstraint("tenant", "key", "version", name="uq_profile_version"),
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

inbound = Table(
    "awp_inbound", metadata,
    Column("tenant", String(80), primary_key=True),
    Column("domain", String(80), primary_key=True),
    Column("message_id", String(200), primary_key=True),
    Column("case_id", String(40), nullable=False),
    Column("created_at", Float, nullable=False),
)

outbox = Table(
    "awp_outbox", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", String(40), nullable=False, index=True),
    Column("kind", String(24), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("status", String(12), nullable=False, default="pending"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text),
    Column("created_at", Float, nullable=False),
)


class Database:
    """Thin wrapper over an async SQLAlchemy engine."""

    def __init__(self, url: str) -> None:
        kwargs = {}
        if url.startswith("sqlite") and ":memory:" not in url:
            kwargs = {"connect_args": {"timeout": 30}}
        if url.startswith("sqlite") and ":memory:" in url:
            from sqlalchemy.pool import StaticPool

            kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        self.engine: AsyncEngine = create_async_engine(url, **kwargs)

    async def create_all(self) -> None:
        from .workforce import schema  # registers the Workforce tables before migrations
        from .workforce.migrate import migrate
        async with self.engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                from sqlalchemy import text
                await conn.execute(text("SELECT pg_advisory_xact_lock(724103818)"))
            await conn.run_sync(lambda sync: metadata.create_all(sync, tables=[t for t in metadata.sorted_tables
                if not t.name.startswith("awp_wf_")]))
            await migrate(conn)

    async def dispose(self) -> None:
        await self.engine.dispose()
