import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agentscope.app._agent_spec import SpecTool
from agentscope.app.workforce.integrations.unified._readiness import bindable_members, route_readiness
from agentscope.app._service._agent_studio import materialize
from tests.workforce.console.test_p0_publish import evaluated_spec, agent_record


def setup_team():
    spec, report = evaluated_spec()
    spec.tools = [SpecTool(tool_id="m:lookup", mcp_id="m", tool_name="lookup", read_only=True),
                  SpecTool(tool_id="m:dispatch", mcp_id="m", tool_name="dispatch")]
    # Generate fresh report for exactly the tool-bound spec.
    from agentscope.app._agent_spec import spec_hash
    from agentscope.app._service._publish_gate import seal_report
    report["spec_hash"] = spec_hash(spec); report = seal_report(spec, report)
    record = agent_record(spec, report)
    mcp = SimpleNamespace(id="m", enabled=True, client=SimpleNamespace(name="vinhomes", confirm_tools=[]),
                          discovered_tools=[{"name": "lookup", "read_only": True}, {"name": "dispatch", "read_only": False}])
    storage = SimpleNamespace(get_agent=AsyncMock(return_value=record), list_mcps=AsyncMock(return_value=[mcp]),
        list_sessions=AsyncMock(return_value=[SimpleNamespace(origin=SimpleNamespace(type="user"), team_id=None)]))
    route = {"route_id": "r", "manager_account_id": "u", "tools": [
                {"name": "lookup", "mcp_id": "m", "read_only": True},
                {"name": "dispatch", "mcp_id": "m", "read_only": False}],
             "config": {"member_agents": {record.id: {"tools": ["lookup", "dispatch"], "coordinator": True}}}}
    return storage, route, record


@pytest.mark.asyncio
async def test_ready_team_requires_owned_published_evaluated_invitable_agent_and_all_tools():
    storage, route, record = setup_team()
    assert (await route_readiness(storage, route))["ready"]
    for modify, code in [
        (lambda r: setattr(r, "user_id", "other"), "AGENT_NOT_OWNED"),
        (lambda r: setattr(r.data, "lifecycle_state", "draft"), "AGENT_NOT_PUBLISHED"),
        (lambda r: setattr(r.data.invite_config, "invitable", False), "AGENT_NOT_INVITABLE"),
        (lambda r: setattr(r.data, "evaluation", {"passed": True, "score": 1.}), "AGENT_EVALUATION_REQUIRED"),
        (lambda r: setattr(r.data, "tool_bindings", []), "AGENT_TOOL_BINDING_MISSING"),
    ]:
        changed = record.model_copy(deep=True); modify(changed)
        storage.get_agent.return_value = changed
        result = await route_readiness(storage, route)
        assert not result["ready"] and code in [issue["code"] for issue in result["issues"]]
    storage.get_agent.return_value = record
    storage.list_sessions.return_value = [SimpleNamespace(origin=SimpleNamespace(type="team"), team_id="old-team")]
    assert "AGENT_PRIMARY_SESSION_MISSING" in [issue["code"] for issue in (await route_readiness(storage, route))["issues"]]


@pytest.mark.asyncio
async def test_empty_roster_missing_tool_and_wrong_scope_are_not_ready():
    storage, route, record = setup_team()
    empty = copy.deepcopy(route); empty["config"]["member_agents"] = {}
    assert "TEAM_NOT_BOUND" in [i["code"] for i in (await route_readiness(storage, empty))["issues"]]
    result = await route_readiness(storage, route, status="revoked")
    assert not result["ready"]
    storage.list_mcps.return_value = []
    result = await route_readiness(storage, route)
    assert "TOOL_NOT_REGISTERED" in [i["code"] for i in result["issues"]]


@pytest.mark.asyncio
async def test_write_owner_is_explicit_and_bindings_are_derived_from_published_spec():
    storage, route, record = setup_team()
    members = await bindable_members(storage, route, [record.id], record.id)
    assert members[record.id]["tools"] == ["dispatch", "lookup"]
    route["config"]["member_agents"] = members
    assert (await route_readiness(storage, route))["ready"]
    members[record.id].pop("coordinator")
    result = await route_readiness(storage, route)
    assert "WRITE_TOOL_REQUIRES_COORDINATOR" in [i["code"] for i in result["issues"]]
    with pytest.raises(ValueError, match="TEAM_MEMBERS_INVALID"):
        await bindable_members(storage, route, [record.id, record.id], record.id)
