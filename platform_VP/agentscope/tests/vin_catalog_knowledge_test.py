"""Catalog read-only projections and private inline storage quota."""

from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from vin_platform_authority_test import authority as authority, setup_quota  # noqa: F401
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant


@pytest.mark.asyncio
async def test_catalog_permission_union_environment_and_capabilities(authority):
    admin, alice = await authority.context("admin"), await authority.context("alice")
    ident = await authority.publish_catalog(admin, CatalogEntry(kind="mcp", resource_id="mcp1", owner_id="admin", name="Domain"))
    for permissions in (["view"], ["bind", "execute"]):
        await authority.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="user", subject_id="alice", permissions=permissions))
    view = await authority.catalog(alice, "mcp")
    assert view[0]["permissions"] == ["bind", "execute", "view"]
    assert await authority.catalog(alice.model_copy(update={"environment": "sandbox"}), "mcp") == []
    caps = (await authority.capabilities(alice))["capabilities"]
    assert all(caps[k] for k in ("schedules.manage", "channels.manage", "providers.read", "mcps.read", "skills.read"))
    assert not any(caps[k] for k in ("management.read", "accounts.manage", "providers.manage", "catalog.manage"))


@pytest.mark.asyncio
async def test_existing_mcp_page_returns_granted_safe_readonly_metadata(authority):
    from agentscope.app._router._mcp import list_mcps
    from agentscope.app.storage import MCPRecord
    from agentscope.mcp import MCPClient, HttpMCPConfig
    record = MCPRecord(user_id="admin", id="mcp1", client=MCPClient(name="domain", is_stateful=False,
        mcp_config=HttpMCPConfig(url="https://example.invalid/mcp?secret=SENTINEL", headers={"Authorization": "Bearer SENTINEL"})),
        url="https://example.invalid/?secret=SENTINEL", last_sync_error="SENTINEL")
    storage = authority.storage
    storage.vin_platform_service = authority
    storage.get_mcp = AsyncMock(return_value=record)
    storage.list_mcps = AsyncMock(return_value=[])  # alice has no private MCP here
    admin = await authority.context("admin")
    ident = await authority.publish_catalog(admin, CatalogEntry(kind="mcp", resource_id="mcp1", owner_id="admin", name="Domain"))
    grant = await authority.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="user", subject_id="alice", permissions=["view", "bind"]))
    views = await list_mcps(user_id="alice", storage=storage)
    assert views[0].editable is False and "SENTINEL" not in views[0].model_dump_json()
    await authority.revoke_grant(admin, grant)
    assert await list_mcps(user_id="alice", storage=storage) == []


@pytest.mark.asyncio
async def test_private_reference_is_usable_and_bytes_are_accounted(authority):
    from agentscope.app._router._knowledge_references import create_reference, ReferenceRequest
    from agentscope.app.storage import KnowledgeBaseData, KnowledgeBaseRecord, EmbeddingModelConfig
    await setup_quota(authority, storage_bytes=80, max_file_bytes=80)
    storage = authority.storage
    storage.vin_platform_service = authority
    storage.get_knowledge_base = AsyncMock(return_value=KnowledgeBaseRecord(user_id="alice", id="kb", data=KnowledgeBaseData(
        name="private", retrieval_mode="lexical", collection_name="", embedding_model_config=EmbeddingModelConfig(
            type="lexical", credential_id="", model="lexical-no-embedding", dimensions=1))))
    storage.upsert_knowledge_document = AsyncMock()
    body = ReferenceRequest(filename="personal.txt", text="personal source information " * 2, source_ref="my-file")
    result = await create_reference("kb", body, user_id="alice", storage=storage)
    assert result["review_status"] == "approved"
    with pytest.raises(PlatformError, match="STORAGE_QUOTA"):
        await create_reference("kb", body, user_id="alice", storage=storage)
    storage.upsert_knowledge_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_cached_knowledge_rechecks_grant_and_document_provenance(authority):
    from agentscope.app.rag.knowledge_base_manager._authorized import AuthorizedKnowledge
    from agentscope.app.vin_platform._context import execution_scope
    admin, alice = await authority.context("admin"), await authority.context("alice")
    storage = authority.storage
    storage.vin_platform_service = authority
    record = SimpleNamespace(id="library", user_id="admin")
    storage.get_knowledge_base = AsyncMock(return_value=record)
    source = SimpleNamespace(id="approved", status="ready", data=SimpleNamespace(
        review_status="approved", effective_from=None, effective_until=None, source_ref="vin/policy", version="v2"))
    retired = SimpleNamespace(id="retired", status="ready", data=SimpleNamespace(
        review_status="retired", effective_from=None, effective_until=None))
    async def document(owner, kb, ident):
        assert (owner, kb) == ("admin", "library")
        return {"approved": source, "retired": retired}.get(ident)
    storage.get_knowledge_document = AsyncMock(side_effect=document)
    hits = [SimpleNamespace(document_id=ident, chunk=SimpleNamespace(metadata={})) for ident in ("approved", "retired", "foreign")]
    inner = SimpleNamespace(search=AsyncMock(return_value=hits), list_chunks=AsyncMock())
    cached = AuthorizedKnowledge(inner, storage, record)
    ident = await authority.publish_catalog(admin, CatalogEntry(kind="knowledge_base", resource_id="library", owner_id="admin", name="Vin"))
    grant = await authority.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="user", subject_id="alice", permissions=["view", "bind"]))
    with execution_scope(alice):
        result = await cached.search("policy")
        assert [item.document_id for item in result] == ["approved"]
        assert result[0].chunk.metadata["source_ref"] == "vin/policy"
        assert result[0].chunk.metadata["version"] == "v2"
        await authority.revoke_grant(admin, grant)
        with pytest.raises(PlatformError) as revoked:
            await cached.search("policy")
        assert revoked.value.status == 404
    inner.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_key_migration_dry_run_and_exact_match_only(authority, monkeypatch):
    from agentscope.app.storage import CredentialRecord
    sentinel = "offline-shared-key-never-a-real-key"
    monkeypatch.setenv("WORKFORCE_PLATFORM_OPENAI_API_KEY", sentinel)
    record = CredentialRecord(user_id="alice", id="stable-id", data={"type": "openai_credential", "api_key": sentinel})
    custom = CredentialRecord(user_id="alice", id="custom-id", data={"type": "openai_credential", "api_key": "private-other-key"})
    authority.storage.list_credentials = AsyncMock(side_effect=lambda user: [record, custom] if user == "alice" else [])
    authority.storage.replace_credential_data = AsyncMock(return_value=True)
    admin = await authority.context("admin")
    dry = await authority.migrate_credentials(admin)
    assert (dry["scanned"], dry["matched"], dry["rewritten"], dry["unmapped"]) == (2, 1, 0, 1)
    authority.storage.replace_credential_data.assert_not_called()
    applied = await authority.migrate_credentials(admin, dry_run=False)
    assert applied["rewritten"] == 1 and sentinel not in str(applied)
    args = authority.storage.replace_credential_data.call_args.args
    assert args[:2] == ("alice", "stable-id")
    assert args[-1]["api_key"] == "server-managed" and args[-1]["secret_ref"] == "vin:platform-openai"
