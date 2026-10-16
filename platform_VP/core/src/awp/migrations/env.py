"""Alembic environment of the platform's own tables (`awp_*`, `wf_*`).

Async, on the metadata of `awp.db`. The version table is `awp_alembic_version`, not Alembic's default, so that this
schema can share a database with AgentScope's storage tables, which keep their own history in `alembic_version`.
The URL is the `sqlalchemy.url` of the config (`awp.migrate` sets it from AWP_DB_URL).
"""
from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from awp.db import metadata
from awp.migrate import only_ours
from awp.workforce import tables  # noqa: F401  (registers the wf_* tables on the metadata)

VERSION_TABLE = "awp_alembic_version"
config = context.config


def _configure(**kw) -> None:
    name = kw["connection"].dialect.name if "connection" in kw else kw["url"]
    context.configure(target_metadata=metadata, version_table=VERSION_TABLE, compare_type=True, include_object=only_ours,
                      render_as_batch=name.startswith("sqlite"), **kw)


def run_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                      poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
