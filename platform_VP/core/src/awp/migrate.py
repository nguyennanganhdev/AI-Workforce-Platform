"""Schema migrations of the platform's tables: `python -m awp migrate` (upgrade to head), `--check` (the database is at
head and matches the models), `--stamp` (declare a database that `create_all` built to be at head), `--storage`
(AgentScope's own tables, with AgentScope's own scripts).

Alembic runs its own event loop (`asyncio.run` in migrations/env.py), so these functions are for synchronous callers:
the command line, a deploy script, a test. The app itself only reads the revision (`current`).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from .db import metadata

HERE = Path(__file__).resolve().parent / "migrations"
VERSION_TABLE = "awp_alembic_version"


def only_ours(obj, name, type_, reflected, compare_to) -> bool:
    """Autogenerate filter: a database may hold other schemas (AgentScope's storage tables); only the tables of our metadata,
    and their columns and indexes, are compared."""
    if type_ == "table":
        return name in metadata.tables
    table = getattr(obj, "table", None)
    return table is None or table.name in metadata.tables


def config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(HERE))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def head() -> str:
    return ScriptDirectory.from_config(config("")).get_current_head()


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(config(url), revision)


def downgrade(url: str, revision: str = "base") -> None:
    command.downgrade(config(url), revision)


async def _inspect(url: str, work) -> Any:
    from .workforce import tables  # noqa: F401  (the wf_* tables belong to the metadata)

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(work)
    finally:
        await engine.dispose()


def _context(conn) -> MigrationContext:
    return MigrationContext.configure(conn, opts={"version_table": VERSION_TABLE, "compare_type": True,
                                                         "include_object": only_ours})


async def current(url: str) -> str | None:
    """The revision the database is at (None: no migration was ever applied)."""
    return await _inspect(url, lambda conn: _context(conn).get_current_revision())


def drift(url: str) -> list:
    """What differs between the database and the models, as Alembic's autogenerate sees it (empty: no drift)."""
    return asyncio.run(_inspect(url, lambda conn: compare_metadata(_context(conn), metadata)))


def check(url: str) -> list[str]:
    """Reasons the database is not what the code expects; empty when it is at head and matches the models."""
    at = asyncio.run(current(url))
    problems = [] if at == head() else [f"the database is at revision {at}, the code at {head()}: run `python -m awp migrate`"]
    return problems + [f"differs from the models: {d}" for d in map(str, drift(url))]


def stamp(url: str) -> None:
    """Record head as the revision of a database that `create_all` built. Refuses a database that differs from the models."""
    problems = [f"differs from the models: {d}" for d in map(str, drift(url))]
    if problems:
        raise RuntimeError("cannot stamp, " + "; ".join(problems))
    command.stamp(config(url), "head")


def upgrade_storage(url: str) -> None:
    """AgentScope's storage tables, with the scripts shipped in AgentScope (their own history, table `alembic_version`)."""
    import agentscope.app.storage._sql as sql

    folder = Path(sql.__file__).resolve().parent / "_alembic"
    cfg = Config(str(folder / "alembic.ini"))
    cfg.set_main_option("script_location", str(folder))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
