"""Durable domain records. All mutable execution writes use a fenced transaction."""

import time
import uuid
from contextlib import asynccontextmanager

from sqlalchemy import JSON, BigInteger, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings


def uid() -> str:
    return str(uuid.uuid4())


def now() -> float:
    return time.time()


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "vp_schema_version"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)


class User(Base):
    __tablename__ = "vp_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password: Mapped[str] = mapped_column(Text)
    disabled: Mapped[bool] = mapped_column(default=False)


class Membership(Base):
    __tablename__ = "vp_memberships"
    workspace: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))


class Login(Base):
    __tablename__ = "vp_logins"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    expires: Mapped[float]


class Record(Base):
    """Versioned configuration/resources; bodies are validated at the API boundary."""

    __tablename__ = "vp_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    owner: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(default=now)
    updated: Mapped[float] = mapped_column(default=now)


class Revision(Base):
    __tablename__ = "vp_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    body: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(default=now)
    __table_args__ = (UniqueConstraint("agent_id", "number"),)


class Session(Base):
    __tablename__ = "vp_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    owner: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="idle")
    team: Mapped[list] = mapped_column(JSON)
    board: Mapped[dict] = mapped_column(JSON, default=dict)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    turn: Mapped[int] = mapped_column(Integer, default=0)
    budget: Mapped[int] = mapped_column(BigInteger)
    spent: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)
    created: Mapped[float] = mapped_column(default=now)
    updated: Mapped[float] = mapped_column(default=now)


class Event(Base):
    __tablename__ = "vp_events"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(40))
    body: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(default=now)


class Job(Base):
    __tablename__ = "vp_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    dedupe: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(24), default="agent")
    body: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str] = mapped_column(String(100), default="")
    lease_until: Mapped[float] = mapped_column(default=0.0)
    available: Mapped[float] = mapped_column(default=now)
    created: Mapped[float] = mapped_column(default=now)
    error: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (Index("vp_jobs_ready", "status", "available", "lease_until"),)


class Artifact(Base):
    """Task, message, evidence, snapshot or result scoped to a pinned session."""

    __tablename__ = "vp_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), default="")
    turn: Mapped[int] = mapped_column(Integer, default=0)
    body: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(default=now)


class Wallet(Base):
    __tablename__ = "vp_wallets"
    workspace: Mapped[str] = mapped_column(String(36), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    budget: Mapped[int] = mapped_column(BigInteger)
    spent: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)


class Reservation(Base):
    __tablename__ = "vp_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    month: Mapped[str] = mapped_column(String(7))
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    generation: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(BigInteger)
    charged: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(default=now)


class Audit(Base):
    __tablename__ = "vp_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(100))
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(default=now)


class RateWindow(Base):
    __tablename__ = "vp_rate_windows"
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    bucket: Mapped[int] = mapped_column(Integer, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)


def make_engine(url: str):
    return create_async_engine(url, pool_pre_ping=True)


engine = make_engine(settings.database_url)
factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def transaction():
    async with factory() as db, db.begin():
        yield db


async def initialize():
    # Serialized initial migration. Refuse incompatible schema rather than guessing an upgrade.
    from sqlalchemy import insert, select, text

    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("SELECT pg_advisory_xact_lock(7361829)"))
        await conn.run_sync(Base.metadata.create_all)
        version = await conn.scalar(select(SchemaVersion.version))
        if version is None:
            await conn.execute(insert(SchemaVersion).values(version=1))
        elif version != 1:
            raise RuntimeError("Unsupported platform schema version; run the documented migration")


async def lock_session(db: AsyncSession, session_id: str) -> Session:
    from sqlalchemy import select

    session = await db.scalar(select(Session).where(Session.id == session_id).with_for_update())
    if session is None:
        raise LookupError("Session not found")
    return session


async def emit(db: AsyncSession, session: Session, event_type: str, body: dict):
    # Caller must own the row lock; the DB log is also the transactional outbox.
    session.seq += 1
    session.updated = now()
    db.add(Event(session_id=session.id, seq=session.seq, type=event_type, body=body))
