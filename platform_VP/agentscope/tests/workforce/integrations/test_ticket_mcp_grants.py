"""Workflow grants stay in cloned transports, never in model input or shared clients."""
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from agentscope.app.workforce.integrations.unified._case import CaseRuntime, _Case
from agentscope.mcp import HttpMCPConfig, MCPClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_runtime_exchanges_bootstrap_for_ticket_scoped_grant():
    workflow, ticket, start = (str(uuid4()) for _ in range(3))
    original = MCPClient(name="vinhomes", is_stateful=False,
                         mcp_config=HttpMCPConfig(url="http://api:8000/mcp", headers={"Authorization": "Bearer bootstrap"}))
    record = SimpleNamespace(enabled=True, client=original, discovered_tools=[
        {"name": "vh_ticket_get", "input_schema": {"type": "object", "properties": {}}}])
    class Storage:
        async def get_mcp(self, *_):
            return record
    class Store:
        async def grant_context(self, current):
            assert current == workflow
            return {"ticket_id": ticket, "external_request_id": start}
    route = {"config": {"mcp_grants": {"vinhomes": {"path": "/platform/mcp-grants"}}},
             "tools": [{"name": "vh_ticket_get", "mcp_tool": "vh_ticket_get", "mcp_id": "mcp-1"}]}
    requests = []
    def exchange(request):
        requests.append(request)
        body = json.loads(request.content)
        assert str(request.url) == "http://api:8000/platform/mcp-grants"
        assert request.headers["Authorization"] == "Bearer bootstrap"
        assert body["ticket_id"] == ticket and body["external_request_id"] == start
        assert body["workflow_id"] == workflow and body["tools"] == ["vh_ticket_get"]
        return httpx.Response(200, json={"bearer_token": "ticket-only", "ticket_id": ticket,
            "workflow_id": workflow, "tools": body["tools"], "expires_at": "2099-01-01T00:00:00+00:00"})
    runtime = CaseRuntime(Store())
    runtime.bind(SimpleNamespace(state=SimpleNamespace(storage=Storage())))
    real_client = httpx.AsyncClient
    with patch("httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(exchange), **kwargs)):
        case = _Case(runtime.store, {"workflow_id": workflow, "session_id": "s"}, route)
        tools = await runtime._tools("manager", case, route)
    assert len(requests) == 1
    transport_client = tools[0]._mcp._client_gen.__self__
    assert transport_client.mcp_config.headers["Authorization"] == "Bearer ticket-only"
    assert original.mcp_config.headers["Authorization"] == "Bearer bootstrap"


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["https://attacker.test/grants", "//attacker.test/grants"])
async def test_grant_endpoint_cannot_export_bootstrap_to_another_origin(path):
    from agentscope.app.workforce.integrations.unified._grants import scoped_client
    client = MCPClient(name="vinhomes", is_stateful=False,
                       mcp_config=HttpMCPConfig(url="http://api:8000/mcp", headers={"Authorization": "Bearer bootstrap"}))
    with pytest.raises(ValueError):
        await scoped_client(client, {"path": path}, {"ticket_id": str(uuid4()),
            "external_request_id": str(uuid4())}, "workflow", ["vh_ticket_get"])
