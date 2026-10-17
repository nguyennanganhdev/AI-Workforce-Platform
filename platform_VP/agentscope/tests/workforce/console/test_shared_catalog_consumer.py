"""C02 consumer integration against the producer's persisted SQLite authority."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException

pytest.importorskip("agentscope.app.vin_platform")

from test_vin_model_resolver_contract import real_authority as real_authority
from agentscope.app._agent_spec import AgentSpec, SpecTool
from agentscope.app._router import _workspace as routes
from agentscope.app._router._schema._workspace import AddSkillRequest
from agentscope.app._service._agent_readiness import resource_manifest
from agentscope.app._service._agent_studio import skill_catalog, tool_catalog, tool_runner
from agentscope.app._service._catalog_resources import resolve_catalog_resource
from agentscope.app._service._toolkit import get_toolkit
from agentscope.app._service._eval_sandbox import EvalSandbox
from agentscope.app.storage import AgentRecord, MCPRecord, SkillRecord, SessionConfig, SessionRecord
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.mcp import HttpMCPConfig, MCPClient


@pytest_asyncio.fixture
async def shared(real_authority):
    storage, authority, admin, _ = real_authority
    mcp = MCPRecord(id="shared-mcp", user_id="service", client=MCPClient(
        name="shared", is_stateful=False,
        mcp_config=HttpMCPConfig(url="https://offline.invalid/mcp", headers={"Authorization": "offline-sentinel"})),
        discovered_tools=[{"name": "lookup", "read_only": True, "requires_consent": False}])
    skill = SkillRecord(id="shared-skill", user_id="service", name="safe-skill", markdown="# Reviewed")

    async def get_record(owner, ident):
        assert owner == "service", "Resolver must retain the service owner"
        return {mcp.id: mcp, skill.id: skill}.get(ident)

    storage.get_mcp = AsyncMock(side_effect=get_record)
    storage.get_skill = AsyncMock(side_effect=get_record)
    storage.list_mcps = AsyncMock(side_effect=AssertionError("owned-only MCP fallback"))
    storage.list_skills = AsyncMock(side_effect=AssertionError("owned-only skill fallback"))
    storage.list_knowledge_bases = AsyncMock(return_value=[])
    grants = []
    for kind, record in [("mcp", mcp), ("skill", skill)]:
        ident = await authority.publish_catalog(admin, CatalogEntry(kind=kind, resource_id=record.id,
            owner_id="service", name=record.name, tool_names=["lookup"] if kind == "mcp" else []))
        grants.append(await authority.grant(admin, ResourceGrant(catalog_id=ident,
            subject_kind="user", subject_id="resident-a", permissions=["view", "bind", "execute"])))
    yield storage, authority, admin, grants, mcp, skill
    storage.list_mcps.assert_not_awaited()
    storage.list_skills.assert_not_awaited()


@pytest.mark.asyncio
async def test_builder_and_studio_read_shared_resources_under_resolved_owner(shared):
    storage, _, _, _, _, _ = shared
    tools, skills = await tool_catalog(storage, "resident-a"), await skill_catalog(storage, "resident-a")
    assert list(tools) == ["shared-mcp:lookup"]
    assert list(skills) == ["shared-skill"]
    assert "offline-sentinel" not in json.dumps([tools, skills])
    assert not await tool_catalog(storage, "resident-b")
    assert not await skill_catalog(storage, "resident-b")


@pytest.mark.asyncio
async def test_readiness_and_eval_recheck_revoked_grants_before_connector_call(shared):
    storage, authority, admin, grants, _, _ = shared
    spec = AgentSpec(name="Private", tools=[SpecTool(tool_id="shared-mcp:lookup", mcp_id="shared-mcp",
        tool_name="lookup", requires_consent=False)])
    agent = AgentRecord(id="private-a", user_id="resident-a", data={"name": "Private", "context_config": {}, "react_config": {}})
    agent.data.spec = {**spec.model_dump(), "skills": [{"skill_id": "shared-skill"}]}
    agent.data.lifecycle_state, agent.data.published_version = "published", 1
    access = SimpleNamespace()
    assert (await resource_manifest(storage, "resident-a", agent, access=access))["ready"]
    for grant in grants:
        await authority.revoke_grant(admin, grant)
    manifest = await resource_manifest(storage, "resident-a", agent, access=access)
    assert not manifest["ready"]
    assert not manifest["tools"][0]["available"]
    assert not manifest["skills"][0]["available"]
    with patch("agentscope.app._service._eval_sandbox.call_tool", new=AsyncMock()) as call:
        with pytest.raises(HTTPException) as denied:
            await tool_runner(storage, "resident-a", spec)("lookup", {})
        assert denied.value.status_code == 404
        call.assert_not_awaited()


@pytest.mark.asyncio
async def test_workspace_projection_does_not_serialize_mcp_credentials(shared):
    storage, _, _, _, mcp, _ = shared
    workspace = SimpleNamespace(list_mcps=AsyncMock(return_value=[mcp.client]))
    service = SimpleNamespace(resolve=AsyncMock(return_value=workspace))
    views = await routes.list_mcps("private-a", "session-a", "resident-a", service, storage)
    payload = json.dumps([item.model_dump() for item in views])
    assert "lookup" in payload
    assert "offline-sentinel" not in payload and "offline.invalid" not in payload
    assert "headers" not in payload and "mcp_config" not in payload


@pytest.mark.asyncio
async def test_customer_cannot_bypass_readonly_catalog_by_importing_workspace_config(shared):
    storage, _, _, _, mcp, _ = shared
    service = SimpleNamespace(resolve=AsyncMock())
    for action in [
        routes.add_mcp(mcp.client, "a", "s", "resident-a", storage, service),
        routes.add_skill(AddSkillRequest(skill_path="/offline"), "a", "s", "resident-a", service, storage),
    ]:
        with pytest.raises(HTTPException) as denied:
            await action
        assert denied.value.status_code == 403
    service.resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_authority_does_not_fall_back_to_private_library(monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = SimpleNamespace(get_mcp=AsyncMock())
    with pytest.raises(HTTPException) as denied:
        await resolve_catalog_resource(storage, "resident-a", "mcp", "shared-mcp")
    assert denied.value.status_code == 503
    storage.get_mcp.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_drops_revoked_snapshots_and_uses_authoritative_config(shared):
    storage, authority, admin, grants, mcp, skill = shared
    cached = mcp.client.model_copy(deep=True)
    cached.mcp_config.url = "https://tampered.invalid/mcp"
    workspace = SimpleNamespace(list_mcps=AsyncMock(return_value=[cached]),
        list_skills=AsyncMock(return_value=[SimpleNamespace(name=skill.name)]))
    agent = AgentRecord(id="a", user_id="resident-a", data={"name": "Private", "context_config": {}, "react_config": {}})
    agent.data.tool_bindings = [{"mcp_id": mcp.id, "tool_name": "lookup"}]
    session = SessionRecord(user_id="resident-a", agent_id=agent.id, config=SessionConfig(workspace_id="private"))
    with patch("agentscope.app._service._toolkit.Toolkit", side_effect=lambda **kw: SimpleNamespace(**kw)):
        async def assemble():
            return await get_toolkit(storage=storage, workspace=workspace, workspace_manager=None,
                scheduler_manager=None, background_task_manager=None, message_bus=None, middlewares=[],
                user_id="resident-a", agent_record=agent, session_record=session,
                resource_access_service=None, team_role="worker")

        before = await assemble()
        assert before.mcps[0].mcp_config.url == "https://offline.invalid/mcp"
        assert len(before.skills_or_loaders) == 1
        for grant in grants:
            await authority.revoke_grant(admin, grant)
        after = await assemble()
        assert not after.mcps and not after.skills_or_loaders


@pytest.mark.asyncio
async def test_pr99_sandbox_rechecks_shared_grant_before_fixture_and_each_tool(shared):
    storage, authority, admin, grants, mcp, _ = shared

    async def revalidate():
        return await resolve_catalog_resource(storage, "resident-a", "mcp", mcp.id, permission="execute")

    sandbox = EvalSandbox(mcp, {"grant_path": "/offline-grant"}, ["lookup"], revalidate=revalidate)
    sandbox.tickets = [{"ticket_id": "offline-ticket", "external_request_id": "offline-request"}]
    with patch("agentscope.app.workforce.integrations.unified._grants.scoped_client", new=AsyncMock(return_value=mcp.client)):
        _, run = await sandbox.case(0)
    await authority.revoke_grant(admin, grants[0])
    with patch("agentscope.app._service._eval_sandbox.call_tool", new=AsyncMock()) as call:
        with pytest.raises(HTTPException):
            await run("lookup", {})
        call.assert_not_awaited()
    with patch("agentscope.app._service._eval_sandbox.httpx.AsyncClient") as http:
        with pytest.raises(HTTPException):
            await sandbox.prepare(1)
        http.assert_not_called()
