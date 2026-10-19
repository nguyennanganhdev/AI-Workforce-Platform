"""Customer workspace defaults and personal resource management; no provider I/O."""

from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from agentscope.app.storage import ChatModelConfig, CredentialRecord
from agentscope.app._router._workforce_console import _model_config
from agentscope.app._service._model import runtime_model_config
from vin_fixtures import authority  # noqa: F401


@pytest.mark.asyncio
async def test_leader_prefers_customer_provider_over_platform_catalog(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = SimpleNamespace(vin_platform_service=authority, list_credentials=AsyncMock(return_value=[
        CredentialRecord(id="personal", user_id="alice", data={
            "type": "openai_credential", "name": "Personal", "api_key": "offline-key",
        }),
    ]))
    config = await _model_config(storage, "alice", authority=authority)
    assert config.credential_id == "personal"


def test_customer_selected_model_can_skip_deployment_override(monkeypatch):
    monkeypatch.setenv("WORKFORCE_MODEL_NAME", "deployment-model")
    config = ChatModelConfig(type="openai_credential", credential_id="personal", model="customer-model", parameters={})
    assert runtime_model_config(config, private=True).model == "customer-model"


@pytest.mark.asyncio
async def test_customer_can_manage_personal_skills_mcps_and_hubs(authority):
    view = await authority.capabilities(await authority.context("alice"))
    for capability in ["skills.private.manage", "mcps.private.manage", "hubs.private.manage"]:
        assert view["capabilities"].get(capability) is True
    assert view["capabilities"]["catalog.manage"] is False


@pytest.mark.asyncio
async def test_existing_managed_config_constructs_model_with_customer_key(authority, monkeypatch):
    from resource_access_policy_test import _FakeStorage
    from agentscope.app._service import ResourceAccessService
    from agentscope.app._service._model import get_model
    from agentscope.app.vin_platform._resources import PersistedResourcePolicy
    monkeypatch.setenv("WORKFORCE_MODEL_NAME", "wrong-deployment-model")
    storage = _FakeStorage()
    authority.storage = storage
    storage.vin_platform_service = authority
    storage.credentials[("alice", "personal")] = CredentialRecord(id="personal", user_id="alice",
        data={"type": "openai_credential", "name": "Personal", "api_key": "offline-customer-key"})
    access = ResourceAccessService(storage, PersistedResourcePolicy(authority))
    model = await get_model("alice", ChatModelConfig(type="openai_credential", credential_id="vin-platform-openai",
        model="wrong-deployment-model", parameters={}), access)
    assert model.model == "gpt-4o-mini"
    assert model.client.api_key == "offline-customer-key"
    await model.client.close()


@pytest.mark.asyncio
async def test_private_skill_is_listed_approved_bound_and_owner_isolated(authority, monkeypatch):
    from fastapi import HTTPException
    from agentscope.app._router._skill import create_local_skill, review_skill, list_skills, LocalSkillRequest, SkillReviewRequest
    from agentscope.app._service._catalog_resources import list_catalog_resources, resolve_catalog_resource
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    rows = {}
    async def put(user, record): rows[(user, record.id)] = record
    async def load(user, ident): return rows.get((user, ident))
    async def listing(user): return [record for (owner, _), record in rows.items() if owner == user]
    storage = SimpleNamespace(vin_platform_service=authority, get_skill_by_name=AsyncMock(return_value=None),
        upsert_skill=put, get_skill=load, list_skills=listing)
    authority.storage = storage
    created = await create_local_skill(LocalSkillRequest(name="personal-skill", description="Personal procedure",
        markdown="# Procedure\n\nRead the request, verify the supplied information, and answer."), "alice", storage)
    approved = await review_skill(created.id, SkillReviewRequest(status="approved"),
        SimpleNamespace(user_id="alice", role="VIN_USER"), storage)
    assert approved.enabled
    assert (await list_skills("alice", storage))[0].editable
    assert (await list_catalog_resources(storage, "alice", "skill"))[0].id == created.id
    assert (await resolve_catalog_resource(storage, "alice", "skill", created.id)).enabled
    assert await list_skills("bob", storage) == []
    with pytest.raises(HTTPException):
        await resolve_catalog_resource(storage, "bob", "skill", created.id)
    with pytest.raises(HTTPException):
        await review_skill(created.id, SkillReviewRequest(status="revoked"),
            SimpleNamespace(user_id="bob", role="VIN_USER"), storage)
    await review_skill(created.id, SkillReviewRequest(status="revoked"),
        SimpleNamespace(user_id="alice", role="VIN_USER"), storage)
    assert await list_catalog_resources(storage, "alice", "skill") == []
    with pytest.raises(HTTPException, match="RESOURCE_REVOKED"):
        await resolve_catalog_resource(storage, "alice", "skill", created.id, permission="execute")
