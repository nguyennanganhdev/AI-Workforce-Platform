"""Personal run/delivery fences reuse the existing SQL queue."""

from datetime import timedelta

import pytest
from sqlalchemy import update

from vin_platform_authority_test import authority as authority, setup_quota  # noqa: F401
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._service import now
from agentscope.app.workforce.foundation._tables import durable_jobs
from agentscope.app.workforce.foundation.event_delivery import JobLeaseLostError


@pytest.mark.asyncio
async def test_personal_queue_scope_idempotency_and_fence(authority):
    async with authority.engine.begin() as db:
        await db.run_sync(durable_jobs.create)
    ctx = await setup_quota(authority)
    jobs = authority.jobs
    first = await jobs.enqueue(ctx, kind="schedule-run", key="schedule1:2026-10-18T12:00:00Z", payload={"instruction": "fixture"})
    again = await jobs.enqueue(ctx, kind="schedule-run", key="schedule1:2026-10-18T12:00:00Z", payload={"instruction": "fixture"})
    assert first.job_id == again.job_id
    with pytest.raises(PlatformError, match="IDEMPOTENCY_CONFLICT"):
        await jobs.enqueue(ctx, kind="schedule-run", key="schedule1:2026-10-18T12:00:00Z", payload={"instruction": "changed"})
    claimed = await jobs.claim("worker1")
    assert claimed.personal_user_id == "alice" and claimed.scope is None
    assert await jobs.claim("worker2") is None
    await jobs.checkpoint(claimed, "worker1", {"phase": "staged"})
    await jobs.complete(claimed, "worker1", {"state": "succeeded"})
    with pytest.raises(JobLeaseLostError):
        await jobs.complete(claimed, "worker1", {})
    assert await jobs.claim("worker1") is None
    assert await jobs.list(await authority.context("bob"), "schedule-run") == []


@pytest.mark.asyncio
async def test_crashed_model_run_is_unknown_and_delivery_retries_saved_body(authority):
    async with authority.engine.begin() as db:
        await db.run_sync(durable_jobs.create)
    ctx = await setup_quota(authority)
    jobs = authority.jobs
    run = await jobs.enqueue(ctx, kind="schedule-run", key="once-1", payload={"model_input": "fixture"})
    old = await jobs.claim("worker1")
    async with authority.engine.begin() as db:
        await db.execute(update(durable_jobs).where(durable_jobs.c.id == run.job_id).values(lease_expires_at=now() - timedelta(seconds=1)))
    assert await jobs.claim("worker2") is None
    assert (await jobs.list(ctx, "schedule-run"))[0].error["code"] == "OUTCOME_UNKNOWN"
    with pytest.raises(JobLeaseLostError):
        await jobs.complete(old, "worker1", {})
    sent = await jobs.enqueue(ctx, kind="delivery", key="run1:discord:owner", payload={"body": "saved answer", "destination": "verified-owner"})
    claim = await jobs.claim("worker1")
    await jobs.fail(claim, "worker1", "TRANSPORT_UNAVAILABLE", retry_after=0)
    retry = await jobs.claim("worker2")
    assert retry.job_id == sent.job_id and retry.payload == claim.payload and retry.fencing_token > claim.fencing_token


@pytest.mark.asyncio
async def test_job_context_rechecks_tenant_revision_and_execution_purpose(authority):
    async with authority.engine.begin() as db:
        await db.run_sync(durable_jobs.create)
    ctx = await setup_quota(authority)
    jobs = authority.jobs
    job = await jobs.enqueue(ctx, kind="schedule-run", key="context-v1", payload={"instruction": "fixture"})
    execution = await jobs.context_for(job)
    assert execution.purpose == "schedule" and execution.billing_subject_id == "alice"
    assert execution.workspace_id == "personal:alice"
    with pytest.raises(PlatformError, match="AUTHORIZATION_REVOKED"):
        await jobs.context_for(job.model_copy(update={"tenant_id": "foreign"}))
    await authority.set_eligibility(await authority.context("admin"), "alice", False)
    with pytest.raises(PlatformError):
        await jobs.context_for(job)
