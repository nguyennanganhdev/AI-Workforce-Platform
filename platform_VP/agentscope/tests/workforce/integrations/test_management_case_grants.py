"""Manager case review preserves archived evidence when live grants end."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from agentscope.app.storage import SessionConfig, SessionRecord
from agentscope.app.workforce.integrations.unified._case import CaseRuntime
from agentscope.mcp import HttpMCPConfig, MCPClient


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 409])
async def test_manager_gets_read_grant_only_or_archived_evidence(status):
    workflow, ticket, start = (str(uuid4()) for _ in range(3))
    client = MCPClient(name="domain", is_stateful=False, mcp_config=HttpMCPConfig(url="http://domain:8000/mcp", headers={"Authorization": "Bearer fixture-bootstrap"}))
    record = SimpleNamespace(enabled=True, client=client, discovered_tools=[{"name": "read", "input_schema": {"type": "object"}}, {"name": "write", "input_schema": {"type": "object"}}])
    route = {"config": {"mcp_grants": {"domain": {"path": "/platform/mcp-grants"}}}, "tools": [
        {"name": "read", "mcp_tool": "read", "mcp_id": "m", "read_only": True},
        {"name": "write", "mcp_tool": "write", "mcp_id": "m", "read_only": False}]}
    session = SessionRecord(user_id="manager", agent_id="leader", config=SessionConfig(workspace_id="shadow"))
    session.state.middle_context["management_case_session_id"] = "case"
    store = SimpleNamespace(session=AsyncMock(return_value={"manager_account_id": "manager", "agent_id": "leader", "workflow_id": workflow, "route_id": "route", "session_id": "case"}),
                            grant_context=AsyncMock(return_value={"ticket_id": ticket, "external_request_id": start}),
                            labelled=AsyncMock(return_value={"E1": "Archived source"}))
    runtime = CaseRuntime(store)
    runtime.bind(SimpleNamespace(state=SimpleNamespace(storage=SimpleNamespace(get_session=AsyncMock(return_value=session), get_mcp=AsyncMock(return_value=record)))))
    requests = []

    def exchange(request):
        import json
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["tools"] == ["read"], "Manager review must never request write grants"
        if status == 409:
            return httpx.Response(409, json={"detail": "No active handover bound to these references"})
        return httpx.Response(200, json={"bearer_token": "fixture-scoped", "ticket_id": ticket, "workflow_id": workflow, "tools": ["read"], "expires_at": "2099-01-01T00:00:00+00:00"})

    original_http = httpx.AsyncClient
    with patch("agentscope.app.workforce.integrations.unified._contract.route_for_workflow", AsyncMock(return_value=route)), patch("httpx.AsyncClient", side_effect=lambda **kw: original_http(transport=httpx.MockTransport(exchange), **kw)):
        [middleware] = await runtime.middlewares("manager", "leader", session.id)
    names = {t.name for t in await middleware.list_tools()}
    assert names == ({"CaseEvidence", "read"} if status == 200 else {"CaseEvidence"})
    assert len(requests) == 1
    evidence = next(t for t in await middleware.list_tools() if t.name == "CaseEvidence")
    result = await evidence.call(cites=["E1"])
    assert "Archived source" in result.content[0].text
    assert client.mcp_config.headers["Authorization"] == "Bearer fixture-bootstrap"
    if status == 409:
        prompt = await middleware.on_system_prompt(None, "")
        assert "LIVE_CASE_TOOLS_UNAVAILABLE" in prompt


@pytest.mark.asyncio
async def test_operational_tools_still_fail_closed_when_domain_revokes_grant():
    from agentscope.app.workforce.integrations.unified._case import _Case
    from agentscope.app.workforce.integrations.unified._grants import WorkflowGrantUnavailable

    workflow, ticket, start = (str(uuid4()) for _ in range(3))
    client = MCPClient(name="domain", is_stateful=False, mcp_config=HttpMCPConfig(url="http://domain:8000/mcp"))
    mcp = SimpleNamespace(enabled=True, client=client, discovered_tools=[{"name": "write", "input_schema": {"type": "object"}}])
    route = {"config": {"mcp_grants": {"domain": {"path": "/platform/mcp-grants"}}}, "tools": [{"name": "write", "mcp_tool": "write", "mcp_id": "m"}]}
    store = SimpleNamespace(grant_context=AsyncMock(return_value={"ticket_id": ticket, "external_request_id": start}))
    runtime = CaseRuntime(store)
    runtime.bind(SimpleNamespace(state=SimpleNamespace(storage=SimpleNamespace(get_mcp=AsyncMock(return_value=mcp)))))
    original_http = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(409, json={"detail": "private details must not appear in error"}))
    with patch("httpx.AsyncClient", side_effect=lambda **kw: original_http(transport=transport, **kw)):
        with pytest.raises(WorkflowGrantUnavailable) as error:
            await runtime._tools("manager", _Case(store, {"workflow_id": workflow, "session_id": "case"}, route), route)
    assert "private details" not in str(error.value)
