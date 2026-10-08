"""Local durable LangGraph checkpointer for Reception development and tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def open_sqlite_checkpointer(path: str | Path) -> AsyncIterator[AsyncSqliteSaver]:
    database_path = Path(path).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(database_path)) as saver:
        await saver.setup()
        yield saver
