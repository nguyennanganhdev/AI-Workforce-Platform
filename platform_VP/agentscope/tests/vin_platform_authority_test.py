"""Authority invariants using real SQL transactions, not mocked reservations."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from agentscope.app.vin_platform import PlatformError, QuotaPolicy
from agentscope.app.vin_platform import _tables as t
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.app.vin_platform._domain import DomainAdapter


from vin_fixtures import authority as authority  # noqa: F401


def limits(**kwargs):
    return QuotaPolicy(daily_tokens=kwargs.pop("daily_tokens", 1000), monthly_tokens=kwargs.pop("monthly_tokens", 2000),
        models=["test-model"], enabled=True, **kwargs)


async def setup_quota(service, **kwargs):
    admin = await service.context("admin")
    await service.set_policy(admin, "role:VIN_USER", limits(**kwargs))
    return await service.context("alice")


@pytest.mark.asyncio
async def test_quota_reserves_before_io_and_is_idempotently_settled(authority):
    ctx = await setup_quota(authority)
    ident = await authority.quota.reserve(ctx, budget=600, purpose="chat", model="test-model")
    with pytest.raises(PlatformError, match="QUOTA_EXCEEDED"):
        await authority.quota.reserve(ctx, budget=500, purpose="chat", model="test-model")
    await authority.quota.settle("vin", ident, 250)
    await authority.quota.settle("vin", ident, 250)
    with pytest.raises(PlatformError, match="SETTLEMENT_CONFLICT"):
        await authority.quota.settle("vin", ident, 0)
    usage = await authority.quota.usage(ctx)
    assert all(r["used"] == 250 and r["reserved"] == 0 for r in usage["buckets"])


@pytest.mark.asyncio
async def test_unknown_usage_holds_budget_but_releases_concurrency(authority):
    ctx = await setup_quota(authority, max_concurrency=1)
    ident = await authority.quota.reserve(ctx, budget=300, purpose="chat", model="test-model")
    await authority.quota.settle("vin", ident, None)
    assert (await authority.quota.usage(ctx))["pending_reconciliation"] == 1
    second = await authority.quota.reserve(ctx, budget=300, purpose="chat", model="test-model")
    with pytest.raises(PlatformError, match="CONCURRENCY"):
        await authority.quota.reserve(ctx, budget=1, purpose="chat", model="test-model")
    await authority.quota.settle("vin", ident, 100)
    await authority.quota.settle("vin", second, 100)
    await authority.quota.reserve(ctx, budget=300, purpose="chat", model="test-model")


@pytest.mark.asyncio
async def test_concurrent_reservations_do_not_overspend(authority):
    ctx = await setup_quota(authority, max_concurrency=10)
    async def attempt():
        try:
            await authority.quota.reserve(ctx, budget=600, purpose="chat", model="test-model")
            return True
        except PlatformError:
            return False
    assert sum(await asyncio.gather(*[attempt() for _ in range(5)])) == 1


@pytest.mark.asyncio
async def test_rollover_retains_original_reservations(authority):
    ctx = await setup_quota(authority, max_concurrency=3)
    before = datetime(2026, 10, 31, 16, 59, tzinfo=UTC)
    first = await authority.quota.reserve(ctx, budget=900, purpose="chat", model="test-model", now=before)
    await authority.quota.reserve(ctx, budget=900, purpose="chat", model="test-model", now=before + timedelta(minutes=2))
    await authority.quota.settle("vin", first, 800)
    rows = (await authority.quota.usage(ctx))["buckets"]
    assert any(r["window"] == "day:2026-10-31" and r["used"] == 800 for r in rows)
    assert any(r["window"] == "day:2026-11-01" and r["reserved"] == 900 for r in rows)


@pytest.mark.asyncio
async def test_group_pool_and_override_cannot_escape_pool(authority):
    admin = await authority.context("admin")
    await authority.add_membership(admin, "alice", "residents")
    await authority.add_membership(admin, "bob", "residents")
    await authority.set_policy(admin, "group:residents", limits())
    await authority.set_policy(admin, "pool:residents", limits(daily_tokens=700, max_concurrency=10))
    alice, bob = await authority.context("alice"), await authority.context("bob")
    await authority.quota.reserve(alice, budget=600, purpose="chat", model="test-model")
    with pytest.raises(PlatformError, match="QUOTA_EXCEEDED"):
        await authority.quota.reserve(bob, budget=200, purpose="chat", model="test-model")


@pytest.mark.asyncio
async def test_revoke_eligibility_and_stale_context_block_new_work(authority):
    ctx = await setup_quota(authority)
    await authority.set_eligibility(await authority.context("admin"), "alice", False)
    with pytest.raises(PlatformError, match="REVOKED"):
        await authority.quota.reserve(ctx, budget=1, purpose="chat", model="test-model")
    with pytest.raises(PlatformError, match="ELIGIBILITY"):
        await authority.quota.reserve(await authority.context("alice"), budget=1, purpose="chat", model="test-model")


@pytest.mark.asyncio
async def test_catalog_requires_explicit_grants_and_revoke(authority):
    admin, alice = await authority.context("admin"), await authority.context("alice")
    ident = await authority.publish_catalog(admin, CatalogEntry(kind="knowledge_base", resource_id="kb-vin",
        owner_id="admin", name="Approved resident rules"))
    assert await authority.catalog(alice) == []
    grant = await authority.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="role", subject_id="VIN_USER",
        permissions=["view", "bind"]))
    assert (await authority.catalog(alice))[0]["resource_id"] == "kb-vin"
    assert await authority.catalog(alice, permission="manage") == []
    await authority.revoke_grant(admin, grant)
    assert await authority.catalog(alice) == []


@pytest.mark.asyncio
async def test_cross_tenant_admin_cannot_publish_foreign_owner(authority):
    with pytest.raises(PlatformError, match="OWNER_NOT_FOUND"):
        await authority.publish_catalog(await authority.context("other"), CatalogEntry(
            kind="agent", resource_id="secret-agent", owner_id="alice", name="bad"))


@pytest.mark.asyncio
async def test_secret_storage_is_encrypted_purpose_scoped_and_not_public(authority):
    sentinel = "fake-sensitive-value-for-test-only"
    ref = await authority.secret_put(await authority.context("admin"), sentinel, "channel")
    async with authority.engine.connect() as db:
        raw = (await db.execute(select(t.secrets.c.ciphertext))).scalar_one()
    assert sentinel not in raw
    assert await authority.secret_get("vin", ref, "channel") == sentinel
    with pytest.raises(PlatformError):
        await authority.secret_get("foreign", ref, "channel")
    with pytest.raises(PlatformError):
        await authority.secret_get("vin", ref, "domain-client")


@pytest.mark.asyncio
async def test_durable_job_cas_and_fencing(authority):
    ctx = await setup_quota(authority)
    await authority.automation_put(ctx, "job1", "schedule", {"run_at": "2026-11-01T00:00:00Z"})
    token = await authority.claim(ctx, "job1")
    with pytest.raises(PlatformError, match="LEASE_NOT_AVAILABLE"):
        await authority.claim(ctx, "job1")
    with pytest.raises(PlatformError, match="LEASE_LOST"):
        await authority.complete_claim(ctx, "job1", "wrong-token", {})
    await authority.complete_claim(ctx, "job1", token, {"state": "succeeded"})
    assert (await authority.automation_list(ctx, "schedule"))[0]["data"]["state"] == "succeeded"
    assert await authority.automation_list(await authority.context("bob"), "schedule") == []


@pytest.mark.asyncio
async def test_storage_quota_counts_actual_bytes_and_releases_once(authority):
    ctx = await setup_quota(authority, storage_bytes=100, max_file_bytes=80)
    await authority.reserve_upload(ctx, "doc1", 70)
    with pytest.raises(PlatformError, match="STORAGE_QUOTA"):
        await authority.reserve_upload(ctx, "doc2", 40)
    await authority.settle_upload(ctx, "doc1", stored=True)
    await authority.settle_upload(ctx, "doc1", stored=False)
    await authority.settle_upload(ctx, "doc1", stored=False)
    await authority.reserve_upload(ctx, "doc3", 70)


@pytest.mark.asyncio
async def test_missing_policy_fails_closed(authority):
    with pytest.raises(PlatformError, match="QUOTA_POLICY_REQUIRED"):
        await authority.quota.reserve(await authority.context("alice"), budget=10, purpose="chat", model="test-model")


@pytest.mark.asyncio
async def test_embedding_has_own_cap_and_also_counts_against_total_day(authority):
    ctx = await setup_quota(authority, embedding_daily_tokens=900)
    chat = await authority.quota.reserve(ctx, budget=800, purpose="chat", model="test-model")
    await authority.quota.settle("vin", chat, 800)
    with pytest.raises(PlatformError, match="QUOTA_EXCEEDED"):
        await authority.quota.reserve(ctx, budget=300, purpose="embedding", model="test-model")
    embedding = await authority.quota.reserve(ctx, budget=200, purpose="embedding", model="test-model")
    await authority.quota.settle("vin", embedding, 100)
    rows = (await authority.quota.usage(ctx))["buckets"]
    assert next(r for r in rows if r["window"].startswith("embedding-day:"))["used"] == 100
    assert next(r for r in rows if r["window"].startswith("day:"))["used"] == 900


@pytest.mark.asyncio
async def test_unapproved_domain_urls_fail_closed(authority):
    from agentscope.app.vin_platform._domain import validate_url
    for url in ["http://external.invalid/", "https://user:pass@example.com/", "file:///etc/passwd"]:
        with pytest.raises(PlatformError):
            validate_url(url)
    with pytest.raises(PlatformError, match="DOMAIN_NOT_CONFIGURED"):
        await DomainAdapter(authority).start(await authority.context("alice"), "vinhomes")
