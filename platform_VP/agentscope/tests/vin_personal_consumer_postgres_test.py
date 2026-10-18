"""N2 consumers on a disposable PostgreSQL DB upgraded through 0023."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine

from workforce.console.test_vin_personal_automation import (  # noqa: F401
    automation,
    test_once_enqueue_two_nodes_runs_once_with_ledger_and_separate_outbox,
    test_delivery_retry_uses_exact_saved_body_and_no_new_model_call,
    test_expired_run_claim_rejects_stale_worker_without_rerunning,
)
from agentscope.app.vin_platform import VinPlatformService
from workforce.console.test_vin_job_history import (  # noqa: F401
    test_paged_ledger_crosses_100_and_filters_source_without_leaking_jobs,
    test_saved_delivery_repair_after_125_runs_does_not_call_model_twice,
)
from agentscope.app.vin_platform import _tables as t


@pytest_asyncio.fixture
async def authority(monkeypatch):
    url = os.getenv("VIN_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL VIN_TEST_ADMIN_URL required")
    parsed = urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Only disposable loopback PostgreSQL is allowed")
    import asyncpg
    from alembic import command
    from alembic.config import Config
    control = await asyncpg.connect(url)
    name = "vin_n2_consumer_" + uuid4().hex
    await control.execute('CREATE DATABASE "' + name + '"')
    database_url = urlunsplit(parsed._replace(scheme="postgresql+asyncpg", path="/" + name))
    engine = create_async_engine(database_url)
    try:
        cfg = Config(str(Path(__file__).parents[1] / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", database_url)
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with engine.begin() as db:
            assert (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0025_vin_packs"
            for user, role in (("admin", "PLATFORM_ADMIN"), ("alice", "VIN_USER"), ("bob", "VIN_USER")):
                await db.execute(text("""INSERT INTO auth_users(id,tenant_id,email,username,password_hash,status,role,created_at,updated_at)
                    VALUES(:u,'vin',:email,:u,'offline-not-a-login','active',:r,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                    {"u": user, "email": user + "@fixture.invalid", "r": role})
                await db.execute(insert(t.accounts).values(user_id=user, tenant_id="vin", eligible=True, revision=1))
        authority = VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(), encryption_key=Fernet.generate_key())
        # The common consumer fixture creates the job table for SQLite. On PG
        # it must already exist from migrations; verify and retain its schema.
        await authority.check_schema()
        from agentscope.app.workforce.foundation._tables import durable_jobs
        original_create = durable_jobs.create
        monkeypatch.setattr(durable_jobs, "create", lambda connection, **kwargs: original_create(connection, checkfirst=True))
        yield authority
    finally:
        await engine.dispose()
        assert name.startswith("vin_n2_consumer_") and len(name) == 48
        await control.execute('DROP DATABASE "' + name + '" WITH (FORCE)')
        await control.close()
