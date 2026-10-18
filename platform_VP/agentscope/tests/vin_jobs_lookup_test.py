"""Filtered C09 history and direct repair lookup on SQLite and migrated PG."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.app.vin_platform import PlatformError, VinPlatformService
from vin_fixtures import seed_authority, seed_personal_job_history


@pytest_asyncio.fixture(params=["sqlite", "postgres"])
async def history_authority(request, tmp_path):
    control, name = None, None
    if request.param == "postgres":
        admin_url = os.environ.get("VIN_TEST_ADMIN_URL")
        if not admin_url:
            pytest.skip("VIN_TEST_ADMIN_URL for disposable loopback PostgreSQL required")
        import asyncpg
        parsed = urlsplit(admin_url.replace("postgresql+asyncpg:", "postgresql:"))
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("Disposable loopback PostgreSQL required")
        control = await asyncpg.connect(admin_url)
        name = "vin_job_history_" + uuid4().hex
        await control.execute('CREATE DATABASE "' + name + '"')
        url = urlunsplit(parsed._replace(scheme="postgresql+asyncpg", path="/" + name))
    else:
        url = "sqlite+aiosqlite:///" + str(tmp_path / "history.db")
    engine = create_async_engine(url)
    try:
        if control is not None:
            from alembic import command
            from alembic.config import Config
            cfg = Config(str(Path(__file__).parents[1] / "src/agentscope/app/storage/_sql/_alembic/alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", url)
            await asyncio.to_thread(command.upgrade, cfg, "head")
        await seed_authority(engine, create_schema=control is None)
        yield VinPlatformService(SimpleNamespace(_require_engine=lambda: engine), SimpleNamespace(),
            encryption_key=Fernet.generate_key())
    finally:
        await engine.dispose()
        if control is not None:
            try:
                await control.execute('DROP DATABASE "' + name + '" WITH (FORCE)')
            finally:
                await control.close()


@pytest.mark.asyncio
async def test_filter_before_limit_reads_125_from_second_source_and_direct_lookup(history_authority):
    authority = history_authority
    context, jobs = await seed_personal_job_history(authority, count=250,
        source_ids=["schedule-a"] * 125 + ["schedule-b"] * 125)
    await seed_personal_job_history(authority, user_id="bob", count=125, source_ids=["schedule-b"])
    first = await authority.jobs.list_page(context, "schedule-run", source_id="schedule-b")
    second = await authority.jobs.list_page(context, "schedule-run", source_id="schedule-b", cursor=first.next_cursor)
    assert (len(first.items), len(second.items)) == (100, 25)
    assert first.has_more and not second.has_more and second.next_cursor is None
    expected = [job.job_id for job in jobs[125:]]
    assert [job.job_id for job in first.items + second.items] == expected
    found = await authority.jobs.get(context, "schedule-run", jobs[-1].job_id, source_id="schedule-b")
    assert found.job_id == expected[-1] and found.payload["body"]["sequence"] == 249
    assert [job.job_id for job in await authority.jobs.list(context, "schedule-run", source_id="schedule-b")] == expected
    with pytest.raises(PlatformError, match="INVALID_JOB_CURSOR"):
        await authority.jobs.list_page(context, "schedule-run", source_id="schedule-a", cursor=first.next_cursor)


@pytest.mark.asyncio
async def test_lookup_isolation_filters_and_saved_revision_rechecked(history_authority):
    authority = history_authority
    context, jobs = await seed_personal_job_history(authority, count=125, source_ids=["schedule-a"])
    bob = await authority.context("bob")
    for who, kind, source, ident in ((bob, "schedule-run", "schedule-a", jobs[-1].job_id),
            (context, "delivery", "schedule-a", jobs[-1].job_id),
            (context, "schedule-run", "schedule-b", jobs[-1].job_id),
            (context, "schedule-run", "schedule-a", "missing")):
        with pytest.raises(PlatformError, match="JOB_NOT_FOUND"):
            await authority.jobs.get(who, kind, ident, source_id=source)
    for source, run in (("", None), (3, None), (None, "parent")):
        with pytest.raises(PlatformError, match="INVALID_JOB_FILTER"):
            await authority.jobs.list_page(context, "schedule-run", source_id=source, run_id=run)
    with pytest.raises(PlatformError, match="INVALID_JOB_ID"):
        await authority.jobs.get(context, "schedule-run", "")
    admin = await authority.context("admin")
    await authority.set_eligibility(admin, "alice", False)
    with pytest.raises(PlatformError):
        await authority.jobs.get(context, "schedule-run", jobs[-1].job_id)
    await authority.set_eligibility(admin, "alice", True)
    current = await authority.context("alice")
    with pytest.raises(PlatformError, match="AUTHORIZATION_REVOKED"):
        await authority.jobs.get(current, "schedule-run", jobs[-1].job_id)
    # History remains visible to its owner; execution/repair lookup is stricter.
    assert len(await authority.jobs.list(current, "schedule-run")) == 125


@pytest.mark.asyncio
async def test_delivery_parent_filter_escapes_wildcards_and_builder_source(history_authority):
    authority = history_authority
    context, _ = await seed_personal_job_history(authority, count=0)
    wanted = await authority.jobs.enqueue(context, kind="delivery", key="parent_%:message", payload={"channel_id": "dm-a"})
    await authority.jobs.enqueue(context, kind="delivery", key="parent_xy:message", payload={"channel_id": "dm-a"})
    page = await authority.jobs.list_page(context, "delivery", source_id="dm-a", run_id="parent_%")
    assert [job.job_id for job in page.items] == [wanted.job_id]
    assert (await authority.jobs.get(context, "delivery", wanted.job_id, run_id="parent_%")).job_id == wanted.job_id
    with pytest.raises(PlatformError, match="JOB_NOT_FOUND"):
        await authority.jobs.get(context, "delivery", wanted.job_id, run_id="parent_xy")
    _, batches = await seed_personal_job_history(authority, kind="publish-batch", count=2, source_ids=["conversation-a", "conversation-b"])
    page = await authority.jobs.list_page(context, "publish-batch", source_id="conversation-b")
    assert [job.job_id for job in page.items] == [batches[-1].job_id]
