"""Admin UI producer contract: tenant boundary, pagination, CAS and KB review."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from vin_fixtures import authority as authority, seed_admin_catalog  # noqa: F401
from agentscope.app.vin_platform import PlatformError, QuotaPolicy
from agentscope.app.vin_platform._contracts import CatalogEntry, DocumentReview
from agentscope.app.vin_platform._router import router, caller


@pytest.mark.asyncio
async def test_admin_lists_are_complete_filtered_paged_and_tenant_scoped(authority):
    ids = await seed_admin_catalog(authority)
    admin = await authority.context("admin")
    foreign = await authority.context("other")
    await authority.set_policy(foreign, "user:foreign", QuotaPolicy(daily_tokens=1, monthly_tokens=2))
    app = FastAPI()
    app.include_router(router)
    current = admin
    async def who():
        return authority, current
    app.dependency_overrides[caller] = who
    @app.exception_handler(PlatformError)
    async def error(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": exc.code}, status_code=exc.status)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as http:
        page = (await http.get("/admin/vin/quota-policies?limit=1")).json()
        assert page["total"] == 3 and page["next_offset"] == 1 and len(page["items"]) == 1
        group = (await http.get("/admin/vin/quota-policies?subject_kind=group")).json()
        assert group["items"][0]["subject"] == "group:pilot" and group["items"][0]["revision"] == 1
        inactive = (await http.get("/admin/vin/catalog?kind=knowledge_base&active=false&environment=production")).json()
        assert inactive["total"] == 1 and inactive["items"][0]["catalog_id"] == ids["catalog_id"]
        assert (await http.get("/admin/vin/catalog?environment=sandbox")).json()["total"] == 0
        for path, params, ident in (("grants", "subject_kind=group&subject_id=pilot", ids["grant_id"]),
                                    ("memberships", "user_id=alice&group_id=pilot", ids["membership_id"])):
            data = (await http.get(f"/admin/vin/{path}?{params}")).json()
            assert data["total"] == 1 and data["items"][0]["id"] == ident and data["items"][0]["revision"] == 1
        accounts = (await http.get("/admin/vin/accounts?user_id=alice&eligible=true")).json()
        assert accounts["total"] == 1 and accounts["items"][0]["revision"] == 1
        assert "password" not in str(accounts)
        assert (await http.get("/admin/vin/grants?limit=101")).status_code == 422
        current = await authority.context("alice")
        for path in ("quota-policies", "catalog", "grants", "memberships", "accounts"):
            assert (await http.get("/admin/vin/" + path)).status_code == 403
        current = foreign
        assert (await http.get("/admin/vin/catalog")).json()["total"] == 0
        assert (await http.delete(f'/admin/vin/grants/{ids["grant_id"]}?expected_revision=1')).status_code == 409


@pytest.mark.asyncio
async def test_admin_cas_override_reset_and_revoke(authority):
    ids = await seed_admin_catalog(authority)
    admin = await authority.context("admin")
    policy = QuotaPolicy(daily_tokens=100, monthly_tokens=1000, models=["test-model"], enabled=True)
    async def change():
        try:
            return await authority.set_policy(admin, "user:alice", policy, expected_revision=1)
        except PlatformError as exc:
            return exc.code
    results = await asyncio.gather(change(), change())
    assert sorted(map(str, results)) == ["2", "REVISION_CONFLICT"]
    with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
        await authority.administration.remove_policy(admin, "user:alice", 1)
    await authority.administration.remove_policy(admin, "user:alice", 2)
    limits, _ = await authority.quota.policy(await authority.context("alice"))
    assert limits.daily_tokens == 500  # group policy resumes after removing override
    with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
        await authority.set_policy(admin, "user:alice", policy, expected_revision=1)
    assert await authority.set_policy(admin, "user:alice", policy, expected_revision=3) == 4
    for method, collection, ident in ((authority.revoke_grant, "grants", ids["grant_id"]),
                                       (authority.revoke_membership, "memberships", ids["membership_id"])):
        await method(admin, ident, expected_revision=1)
        with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
            await method(admin, ident, expected_revision=1)
        page = await authority.administration.page(admin, collection, active=False)
        assert page["items"][0]["revision"] == 2
    await authority.set_eligibility(admin, "alice", False, expected_revision=1)
    with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
        await authority.set_eligibility(admin, "alice", True, expected_revision=1)
    personal_admin = admin.model_copy(update={"workspace_id": "personal:admin"})
    with pytest.raises(PlatformError, match="CAPABILITY_DENIED"):
        await authority.administration.accounts(personal_admin)


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", ["sql", "redis"])
async def test_library_review_cas_and_safe_metadata(authority, adapter, tmp_path):
    from agentscope.app.storage import AsyncSQLAlchemyStorage, KnowledgeBaseRecord, KnowledgeBaseData, KnowledgeDocumentRecord, KnowledgeDocumentData, EmbeddingModelConfig
    from storage_redis_knowledge_base_test import make_storage
    storage = make_storage() if adapter == "redis" else AsyncSQLAlchemyStorage("sqlite+aiosqlite:///" + str(tmp_path / "kb.db"))
    if adapter == "sql":
        await storage.__aenter__()
    authority.storage = storage
    try:
        admin = await authority.context("admin")
        kb = KnowledgeBaseRecord(id="library", user_id="admin", data=KnowledgeBaseData(name="Vin",
            retrieval_mode="lexical", collection_name="", embedding_model_config=EmbeddingModelConfig(
                type="lexical", credential_id="", model="lexical-no-embedding", dimensions=1)))
        await storage.upsert_knowledge_base("admin", kb)
        doc = KnowledgeDocumentRecord(id="doc", user_id="admin", knowledge_base_id="library", status="ready",
            data=KnowledgeDocumentData(filename="policy.md", size=25, blob_uri="private://SENTINEL",
                text_content="SENTINEL private document", version="v1", review_status="candidate"))
        await storage.upsert_knowledge_document("admin", doc)
        catalog = await authority.publish_catalog(admin, CatalogEntry(kind="knowledge_base", resource_id="library", owner_id="admin", name="Vin"))
        page = await authority.administration.documents(admin, catalog, review_status="candidate")
        view = page["items"][0]
        assert page["total"] == 1 and "SENTINEL" not in str(page)
        review = DocumentReview(status="approved", expected_revision=view["revision"])
        approved = await authority.administration.review(admin, catalog, "doc", review)
        assert approved["review_status"] == "approved" and approved["reviewed_by"] == "admin"
        assert approved["revision"] != view["revision"]
        with pytest.raises(PlatformError, match="REVISION_CONFLICT"):
            await authority.administration.review(admin, catalog, "doc", review)
        with pytest.raises(PlatformError, match="RESOURCE_NOT_FOUND"):
            await authority.administration.documents(await authority.context("other"), catalog)
        with pytest.raises(PlatformError, match="CAPABILITY_DENIED"):
            await authority.administration.review(await authority.context("alice"), catalog, "doc", review)
        latest = await storage.get_knowledge_document("admin", "library", "doc")
        changed = latest.model_copy(deep=True)
        changed.data.version = "v2"
        await storage.upsert_knowledge_document("admin", changed)
        assert not await storage.replace_knowledge_document(latest, doc)
        assert (await storage.get_knowledge_document("admin", "library", "doc")).data.version == "v2"
    finally:
        if adapter == "sql":
            await storage.__aexit__(None, None, None)
