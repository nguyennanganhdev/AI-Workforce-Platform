"""Async SQLAlchemy engine, sessions, and transaction scopes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings


@dataclass(frozen=True)
class Database:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def dispose(self) -> None:
        await self.engine.dispose()


def create_database(database_url: str | None = None) -> Database:
    url = database_url or Settings.from_env().database_url
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return Database(engine=engine, sessions=sessions)


@asynccontextmanager
async def session_scope(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session and always close it; caller owns transaction boundaries."""
    async with sessions() as session:
        yield session


@asynccontextmanager
async def transaction_scope(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Commit on success and roll back when the caller raises."""
    async with sessions.begin() as session:
        yield session
