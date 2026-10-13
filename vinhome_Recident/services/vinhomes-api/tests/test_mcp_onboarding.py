"""MCP discovery must authenticate without requiring a configured outbound platform."""

import pytest
from fastapi.testclient import TestClient

from vinhomes_api.main import create_app
from vinhomes_api.platform import Bridge
from vinhomes_api.v3_config import V3Settings

TOKEN = "onboarding-test-token-0123456789abcdef"
SETTINGS = V3Settings("127.0.0.1", 8000, None, None, None)
ACCEPT = {"Accept": "application/json, text/event-stream"}
HELLO = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
               "clientInfo": {"name": "onboarding-test", "version": "1"}},
}


@pytest.fixture(autouse=True)
def platform_not_configured(monkeypatch):
    for suffix in ("URL", "CUSTOMER_KEY", "PROVIDER_KEY", "SIGNING_KEY_ID", "SIGNING_SECRET", "MCP_TOKEN"):
        monkeypatch.delenv("VINHOMES_API_PLATFORM_" + suffix, raising=False)


def test_no_token_keeps_mcp_disabled():
    with TestClient(create_app(SETTINGS)) as client:
        assert client.post("/mcp", json=HELLO, headers=ACCEPT).status_code == 404


def test_short_token_fails_closed(monkeypatch):
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", "short")
    with pytest.raises(ValueError, match="at least 32 characters"):
        create_app(SETTINGS)


def test_onboarding_requires_bearer_and_discovers_tools_with_bridge_off(monkeypatch):
    monkeypatch.setenv("VINHOMES_API_PLATFORM_MCP_TOKEN", TOKEN)
    assert Bridge.from_env() is None
    with TestClient(create_app(SETTINGS)) as client:
        for authorization in (None, TOKEN, "ApiKey " + TOKEN, "Bearer wrong", "Bearer " + TOKEN + "x"):
            headers = {**ACCEPT, **({"Authorization": authorization} if authorization else {})}
            response = client.post("/mcp", json=HELLO, headers=headers)
            assert response.status_code == 401
            assert response.headers["WWW-Authenticate"] == "Bearer"
            assert TOKEN not in response.text

        headers = {**ACCEPT, "Authorization": "Bearer " + TOKEN}
        response = client.post("/mcp", json=HELLO, headers=headers)
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "vinhomes"
        assert "mcp-session-id" not in response.headers
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
        assert response.status_code == 200
        tools = response.json()["result"]["tools"]
        assert len(tools) == 23
        assert {"vh_ticket_get", "vh_knowledge_search", "vh_work_order_dispatch"} <= {tool["name"] for tool in tools}
        assert all("ticket_id" in tool["inputSchema"]["required"] for tool in tools)
    assert Bridge.from_env() is None
