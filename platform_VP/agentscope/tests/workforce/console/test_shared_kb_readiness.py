"""Shared Knowledge uses the same resolver during authoring and runtime."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app._agent_spec import AgentSpec, SpecKnowledge, SpecPatchError
from agentscope.app._service._agent_readiness import resource_manifest
from agentscope.app._service._agent_studio import apply_bindings, knowledge_catalog
from agentscope.app.storage import AgentData, AgentRecord, ChatModelConfig, SessionConfig, SessionRecord


def agent():
    return AgentRecord(id="agent-a", user_id="resident-a", data=AgentData(
        name="Personal agent", system_prompt="Use approved Knowledge",
        context_config=ContextConfig(), react_config=ReActConfig(), lifecycle_state="published",
        published_version=1, resource_workspace_id="published-a",
        spec=AgentSpec(name="Personal agent", knowledge=[SpecKnowledge(kb_id="vin-kb", name="Vin rules")]).model_dump(mode="json"),
    ))


def resources():
    kb = SimpleNamespace(id="vin-kb", user_id="service-owner")
    document = SimpleNamespace(status="ready", data=SimpleNamespace(review_status="approved", effective_from=None, effective_until=None))
    storage = SimpleNamespace(
        list_knowledge_bases=AsyncMock(side_effect=AssertionError("owned-only fallback")),
        list_knowledge_documents=AsyncMock(return_value=[document]),
    )
    access = SimpleNamespace(resolve_knowledge_base=AsyncMock(return_value=kb))
    return storage, access


@pytest.mark.asyncio
async def test_readiness_reads_shared_documents_under_resolved_service_owner():
    storage, access = resources()
    manifest = await resource_manifest(storage, "resident-a", agent(), access=access)
    assert manifest["ready"]
    assert manifest["knowledge"][0]["ready_documents"] == 1
    access.resolve_knowledge_base.assert_awaited_once_with("resident-a", "vin-kb")
    storage.list_knowledge_documents.assert_awaited_once_with("service-owner", "vin-kb")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 404])
async def test_revoked_shared_knowledge_blocks_new_runtime_without_reading_old_owner(status):
    storage, access = resources()
    access.resolve_knowledge_base.side_effect = HTTPException(status, "unavailable")
    manifest = await resource_manifest(storage, "resident-a", agent(), access=access)
    assert not manifest["ready"]
    assert manifest["knowledge"][0]["available"] is False
    storage.list_knowledge_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_policy_store_outage_is_not_treated_as_an_empty_ready_manifest():
    storage, access = resources()
    access.resolve_knowledge_base.side_effect = HTTPException(503, "policy store unavailable")
    with pytest.raises(HTTPException) as raised:
        await resource_manifest(storage, "resident-a", agent(), access=access)
    assert raised.value.status_code == 503
    storage.list_knowledge_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_authoring_catalog_uses_public_views_without_exposing_owner_or_provider_fields():
    storage, access = resources()
    access.list_resource = AsyncMock(return_value=[SimpleNamespace(
        id="vin-kb", name="Vin rules", description="Approved rules", updated_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        owner_id="service-owner", embedding_model_config={"secret_ref": "offline-sentinel"},
    )])
    catalog = await knowledge_catalog(storage, "resident-a", access=access)
    assert catalog["vin-kb"]["revision"] == "2026-10-18T00:00:00+00:00"
    assert set(catalog["vin-kb"]) == {"kb_id", "name", "description", "revision"}


@pytest.mark.asyncio
async def test_staged_publication_accepts_entitled_shared_kb_and_rechecks_revocation():
    storage, access = resources()
    record = agent()
    primary = SessionRecord(id="primary-a", user_id="resident-a", agent_id=record.id,
        config=SessionConfig(workspace_id="workspace-a", chat_model_config=ChatModelConfig(
            type="openai_credential", credential_id="service-provider", model="offline", parameters={})))
    storage.list_sessions = AsyncMock(return_value=[primary])
    storage.upsert_session = AsyncMock(side_effect=AssertionError("stage must not activate"))
    workspace = SimpleNamespace(set_mcp_declarations=AsyncMock())
    manager = SimpleNamespace(get_workspace=AsyncMock(return_value=workspace))
    spec = AgentSpec.model_validate(record.data.spec)
    await apply_bindings(storage, manager, "resident-a", record, spec, stage=True, access=access)
    assert primary.config.workspace_id == "workspace-a"
    access.resolve_knowledge_base.assert_awaited_once_with("resident-a", "vin-kb")
    access.resolve_knowledge_base.side_effect = HTTPException(404, "resource revoked")
    with pytest.raises(HTTPException):
        await apply_bindings(storage, manager, "resident-a", record, spec, stage=True, access=access)
    storage.upsert_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_vin_authoring_without_resolver_never_silently_uses_owned_only_resources():
    storage, _ = resources()
    storage.vin_platform_service = object()
    with pytest.raises(SpecPatchError):
        await knowledge_catalog(storage, "resident-a")
    manifest = await resource_manifest(storage, "resident-a", agent())
    assert not manifest["ready"]
    storage.list_knowledge_bases.assert_not_awaited()
    storage.list_knowledge_documents.assert_not_awaited()
