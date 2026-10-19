"""Consumer contract: bootstrap discovery credentials never execute a customer tool."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from vin_fixtures import authority as authority  # noqa: F401
from test_vin_model_resolver_contract import real_authority as real_authority  # noqa: F401
from agentscope.app._service._customer_mcp import CustomerMCPTool, customer_tools, granted_client
from agentscope.app.storage import MCPRecord
from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._contracts import CatalogEntry, ResourceGrant
from agentscope.mcp import HttpMCPConfig, MCPClient

TICKET = "11111111-1111-4111-8111-111111111111"


@pytest_asyncio.fixture
async def connector(real_authority):
    storage, service, admin, _ = real_authority
    descriptor = {"name": "vh_ticket_get", "read_only": True, "input_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}}}
    record = MCPRecord(id="customer-domain", user_id="admin", tags=["vin-customer-domain:vinhomes"],
        client=MCPClient(name="vinhomes", is_stateful=False, mcp_config=HttpMCPConfig(url="http://domain.invalid/mcp", headers={"Authorization": "bootstrap-sentinel"})),
        discovered_tools=[descriptor])
    storage.get_mcp = AsyncMock(return_value=record)
    ident = await service.publish_catalog(admin, CatalogEntry(kind="mcp", resource_id=record.id, owner_id="admin", name="Vinhomes", tool_names=[descriptor["name"]]))
    grant = await service.grant(admin, ResourceGrant(catalog_id=ident, subject_kind="user", subject_id="alice", permissions=["view", "bind", "execute"]))
    service.automation_list = AsyncMock(return_value=[{"data": {"type": "customer-case", "case_id": "case-a"}}])
    adapter = SimpleNamespace(provider=AsyncMock(return_value=SimpleNamespace(api_base_url="http://domain.invalid/platform/customer")),
        get_case=AsyncMock(return_value={"id": "case-a", "data": {"domain": {"tickets": [{"id": TICKET}]}}}),
        ticket_grant=AsyncMock(return_value={"bearer_token": "ticket-sentinel"}))
    with patch("agentscope.app._service._customer_mcp.DomainAdapter", return_value=adapter):
        yield storage, service, admin, record, grant, adapter


@pytest.mark.asyncio
async def test_own_ticket_gets_fresh_grant_without_changing_shared_discovery_auth(connector):
    storage, _, _, record, _, adapter = connector
    for _ in range(2):
        client = await granted_client(storage, "alice", record.id, "vh_ticket_get", {"ticket_id": TICKET})
        assert client.mcp_config.headers == {"Authorization": "Bearer ticket-sentinel"}
        assert client.enable_tools == ["vh_ticket_get"] and not client.is_stateful
    assert adapter.ticket_grant.await_count == 2
    assert record.client.mcp_config.headers == {"Authorization": "bootstrap-sentinel"}
    assert adapter.ticket_grant.call_args.args[0].initiator_user_id == "alice"


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,name,code", [({}, "vh_ticket_get", "CUSTOMER_TICKET_REQUIRED"),
    ({"ticket_id": "bad"}, "vh_ticket_get", "CUSTOMER_TICKET_REQUIRED"),
    ({"ticket_id": TICKET}, "vh_management_ticket_list", "CUSTOMER_TOOL_NOT_DELEGATED"),
    ({"ticket_id": TICKET}, "vh_ticket_close", "CUSTOMER_TOOL_NOT_DELEGATED")])
async def test_invalid_ticket_or_management_or_consent_tools_never_obtain_grant(connector, arguments, name, code):
    storage, _, _, record, _, adapter = connector
    with pytest.raises(PlatformError) as denied:
        await granted_client(storage, "alice", record.id, name, arguments)
    assert denied.value.code == code
    adapter.ticket_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_owner_and_revoked_catalog_denied_before_domain(connector):
    storage, service, admin, record, grant, adapter = connector
    for user in ("bob", "alice"):
        if user == "alice":
            await service.revoke_grant(admin, grant)
        tool = CustomerMCPTool(storage, user, record, record.discovered_tools[0])
        result = await tool(ticket_id=TICKET)
        assert "CUSTOMER_MCP_UNAVAILABLE" in str(result.content)
    adapter.ticket_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_unbound_ticket_wrong_origin_and_revoked_link_fail_closed(connector):
    storage, _, _, record, _, adapter = connector
    adapter.get_case.return_value["data"]["domain"]["tickets"] = []
    with pytest.raises(PlatformError, match="CUSTOMER_TICKET_NOT_FOUND"):
        await granted_client(storage, "alice", record.id, "vh_ticket_get", {"ticket_id": TICKET})
    record.client.mcp_config.url = "http://other.invalid/mcp"
    with pytest.raises(PlatformError, match="CUSTOMER_CONNECTOR_ORIGIN_MISMATCH"):
        await granted_client(storage, "alice", record.id, "vh_ticket_get", {"ticket_id": TICKET})
    record.client.mcp_config.url = "http://domain.invalid/mcp"
    adapter.get_case.side_effect = PlatformError("LINK_REVOKED", 403)
    with pytest.raises(PlatformError, match="LINK_REVOKED"):
        await granted_client(storage, "alice", record.id, "vh_ticket_get", {"ticket_id": TICKET})
    adapter.ticket_grant.assert_not_awaited()


@pytest.mark.asyncio
async def test_selected_domain_tools_replace_raw_clients_and_sanitize_transport_errors(connector):
    storage, _, _, record, _, _ = connector
    other = MCPClient(name="other", is_stateful=False, mcp_config=HttpMCPConfig(url="http://other.invalid/mcp"))
    remaining, tools = await customer_tools(storage, "alice", [record.client, other], {record.name: record})
    assert remaining == [other] and [tool.name for tool in tools] == ["vh_ticket_get"]
    with patch.object(MCPClient, "get_tool", new=AsyncMock(side_effect=RuntimeError("ticket-sentinel bootstrap-sentinel"))):
        result = await tools[0](ticket_id=TICKET)
    encoded = json.dumps(result.model_dump(mode="json"))
    assert "DOMAIN_TOOL_TEMPORARILY_UNAVAILABLE" in encoded and "sentinel" not in encoded
