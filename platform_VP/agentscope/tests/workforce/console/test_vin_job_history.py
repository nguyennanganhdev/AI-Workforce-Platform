"""C09 ledger and crash repair remain usable past the first 100 jobs."""

from types import SimpleNamespace

import pytest
from sqlalchemy import delete, update

from vin_fixtures import authority as authority, seed_personal_job_history  # noqa: F401
from workforce.console.test_vin_personal_automation import automation as automation  # noqa: F401
from agentscope.app._service._personal_jobs import ledger, repair_delivery
from agentscope.app.vin_platform import PlatformError
from agentscope.app.workforce.foundation._tables import durable_jobs


@pytest.mark.asyncio
async def test_paged_ledger_crosses_100_and_filters_source_without_leaking_jobs(authority, monkeypatch):
    monkeypatch.setenv('VIN_PLATFORM_ENABLED', 'true')
    context, jobs = await seed_personal_job_history(authority, count=250)
    _, foreign = await seed_personal_job_history(authority, user_id='bob', count=1)
    async with authority.engine.begin() as db:
        for index, job in enumerate(jobs):
            await db.execute(update(durable_jobs).where(durable_jobs.c.id == job.job_id).values(
                payload={**job.payload, 'body': {'schedule_id': 'target' if index % 2 == 0 else 'other'}}))
    storage = SimpleNamespace(vin_platform_service=authority)
    seen, sizes, cursor = [], [], None
    while True:
        page = await ledger(storage, 'alice', 'schedule-run', 'target', cursor=cursor)
        sizes.append(len(page['items']))
        seen.extend(row['id'] for row in page['items'])
        assert all(not {'payload', 'fencing_token', 'lease_owner', 'lease_expires_at'} & row.keys() for row in page['items'])
        if not page['has_more']:
            assert page['next_cursor'] is None
            break
        cursor = page['next_cursor']
    assert sizes == [25] * 5 and len(set(seen)) == 125
    assert set(seen) == {job.job_id for job in jobs[::2]}
    with pytest.raises(PlatformError, match='INVALID_JOB_CURSOR'):
        await ledger(storage, 'alice', 'schedule-run', 'target', cursor=foreign[0].job_id)
    with pytest.raises(PlatformError, match='INVALID_JOB_CURSOR'):
        await ledger(storage, 'alice', 'schedule-run', 'target', cursor=jobs[1].job_id)
    await authority.set_eligibility(await authority.context('admin'), context.initiator_user_id, False)
    with pytest.raises(PlatformError):
        await authority.jobs.list_page(context, 'schedule-run', cursor=seen[24])


@pytest.mark.asyncio
async def test_saved_delivery_repair_after_125_runs_does_not_call_model_twice(automation):
    a = automation
    _, history = await seed_personal_job_history(a.authority, count=125)
    async with a.authority.engine.begin() as db:
        await db.execute(update(durable_jobs).where(durable_jobs.c.id.in_([job.job_id for job in history])).values(status='succeeded'))
    await a.manager._build_trigger(a.record)()
    await a.worker.run_one()
    runs = await a.authority.jobs.list(a.context, 'schedule-run')
    run = next(job for job in runs if (job.result or {}).get('deliveries'))
    assert len(runs) == 126 and len(a.calls) == 1
    # The run committed its saved reply but the outbox insert was lost.
    async with a.authority.engine.begin() as db:
        await db.execute(delete(durable_jobs).where(durable_jobs.c.job_type == 'delivery'))
    assert await repair_delivery(a.storage, 'alice', 'schedule-run', a.record.id, run.job_id) == {'queued': True}
    await a.worker.run_one()
    assert len(a.calls) == 1 and len(a.deliveries) == 1
    await a.authority.set_eligibility(await a.authority.context('admin'), 'alice', False)
    with pytest.raises(PlatformError):
        await repair_delivery(a.storage, 'alice', 'schedule-run', a.record.id, run.job_id)
