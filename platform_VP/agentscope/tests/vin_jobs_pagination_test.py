"""C09 keysets cross the 100-job boundary without leaking another owner."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, update

from agentscope.app.vin_platform._contracts import PersonalJobPage, PlatformError
from agentscope.app.vin_platform import _tables as t
from agentscope.app.workforce.foundation._tables import durable_jobs
from vin_fixtures import authority as authority, seed_personal_job_history  # noqa: F401


@pytest.mark.asyncio
async def test_keyset_reads_205_tied_jobs_and_legacy_reader_is_complete(authority):
    context, jobs = await seed_personal_job_history(authority)
    await seed_personal_job_history(authority, user_id="bob", count=2)
    await seed_personal_job_history(authority, kind="delivery", count=2)
    tied_at = datetime(2026, 10, 18, tzinfo=UTC)
    async with authority.engine.begin() as db:
        await db.execute(update(durable_jobs).values(created_at=tied_at))
    expected = sorted(job.job_id for job in jobs)
    seen, sizes, cursor = [], [], None
    while True:
        page = await authority.jobs.list_page(context, "schedule-run", cursor=cursor)
        assert isinstance(page, PersonalJobPage)
        assert all(job.personal_user_id == "alice" and job.job_type == "schedule-run" for job in page.items)
        sizes.append(len(page.items))
        seen.extend(job.job_id for job in page.items)
        if not page.has_more:
            assert page.next_cursor is None
            break
        assert page.next_cursor == page.items[-1].job_id
        cursor = page.next_cursor
    assert sizes == [100, 100, 5]
    assert seen == expected and len(set(seen)) == 205
    assert [job.job_id for job in await authority.jobs.list(context, "schedule-run")] == expected
    single = await authority.jobs.list_page(context, "schedule-run", limit=1)
    assert single.items[0].job_id == expected[0] and single.next_cursor == expected[0]


@pytest.mark.asyncio
async def test_cursor_scope_validation_and_authorization_rechecked_each_page(authority):
    context, jobs = await seed_personal_job_history(authority, count=3)
    bob, bob_jobs = await seed_personal_job_history(authority, user_id="bob", count=1)
    _, deliveries = await seed_personal_job_history(authority, kind="delivery", count=1)
    foreign = await authority.context("other")
    foreign_job = await authority.jobs.enqueue(foreign, kind="schedule-run", key="foreign", payload={})
    for cursor in (bob_jobs[0].job_id, deliveries[0].job_id, foreign_job.job_id, "missing", "", 10):
        with pytest.raises(PlatformError, match="INVALID_JOB_CURSOR"):
            await authority.jobs.list_page(context, "schedule-run", cursor=cursor)
    for limit in (0, 101, -1, True, "100"):
        with pytest.raises(PlatformError, match="INVALID_PAGINATION"):
            await authority.jobs.list_page(context, "schedule-run", limit=limit)
    with pytest.raises(PlatformError, match="INVALID_JOB_KIND"):
        await authority.jobs.list_page(context, "unknown")
    assert (await authority.jobs.list_page(bob, "delivery")).items == []
    first = await authority.jobs.list_page(context, "schedule-run", limit=1)
    async with authority.engine.begin() as db:
        await db.execute(delete(durable_jobs).where(durable_jobs.c.id == first.next_cursor))
    with pytest.raises(PlatformError, match="INVALID_JOB_CURSOR"):
        await authority.jobs.list_page(context, "schedule-run", cursor=first.next_cursor)
    async with authority.engine.begin() as db:
        await db.execute(update(t.accounts).where(t.accounts.c.user_id == "alice").values(revision=t.accounts.c.revision + 1))
    with pytest.raises(PlatformError, match="AUTHORIZATION_REVOKED"):
        await authority.jobs.list_page(context, "schedule-run", cursor=jobs[-1].job_id)


def test_job_page_schema_is_in_openapi():
    path = Path(__file__).resolve().parents[3] / "docs/vin-platform/openapi-v1.json"
    schemas = json.loads(path.read_text(encoding="utf-8"))["components"]["schemas"]
    assert schemas["PersonalJobPage"]["properties"]["items"]["items"]["$ref"] == "#/components/schemas/DurableJob"
    assert set(schemas["PersonalJobPage"]["required"]) == {"items", "next_cursor", "has_more"}
