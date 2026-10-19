"""Self-registered accounts cannot run code on, or reach into, the platform host."""

import pytest
from fastapi import HTTPException

from agentscope.app.vin_platform import PlatformError
from agentscope.app.vin_platform._egress import assert_public_credential, assert_public_endpoint
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
from resource_access_policy_test import _FakeStorage
from vin_fixtures import authority  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://localhost/v1", "http://169.254.169.254/latest",
                                 "https://10.0.0.5/v1", "http://[::1]:11434", "http://0.0.0.0", "file:///etc/passwd"])
async def test_internal_endpoints_are_refused(url):
    with pytest.raises(PlatformError, match="ENDPOINT_NOT_ALLOWED"):
        await assert_public_endpoint(url)


@pytest.mark.asyncio
async def test_public_literal_endpoint_and_bare_host_are_accepted():
    await assert_public_endpoint("https://8.8.8.8/v1")
    await assert_public_credential({"type": "xai_credential", "api_host": "1.1.1.1", "base_url": ""})


@pytest.mark.asyncio
async def test_unresolvable_compose_service_name_is_refused():
    with pytest.raises(PlatformError, match="ENDPOINT_UNRESOLVABLE|ENDPOINT_NOT_ALLOWED"):
        await assert_public_endpoint("http://redis.invalid:6379")


def _storage(authority, monkeypatch):
    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "true")
    storage = _FakeStorage()
    storage.vin_platform_service = authority
    authority.storage = storage
    return storage


@pytest.mark.asyncio
async def test_customer_mcp_must_be_remote_http_on_a_public_host(authority, monkeypatch):
    from agentscope.app._service._catalog_resources import assert_customer_mcp, is_operator

    storage = _storage(authority, monkeypatch)
    assert not await is_operator(storage, "alice")
    stdio = MCPClient(name="shell", is_stateful=True, mcp_config=StdioMCPConfig(command="sh", args=["-c", "id"]))
    with pytest.raises(HTTPException) as denied:
        await assert_customer_mcp(storage, "alice", stdio)
    assert (denied.value.status_code, denied.value.detail) == (403, "STDIO_MCP_NOT_ALLOWED")
    internal = MCPClient(name="inside", is_stateful=False, mcp_config=HttpMCPConfig(url="http://127.0.0.1:8000/mcp"))
    with pytest.raises(HTTPException) as denied:
        await assert_customer_mcp(storage, "alice", internal)
    assert denied.value.detail == "ENDPOINT_NOT_ALLOWED"
    public = MCPClient(name="remote", is_stateful=False, mcp_config=HttpMCPConfig(url="https://8.8.8.8/mcp"))
    await assert_customer_mcp(storage, "alice", public)


@pytest.mark.asyncio
async def test_customer_provider_with_internal_base_url_is_refused(authority, monkeypatch):
    from agentscope.app._router._credential import _public_endpoints

    storage = _storage(authority, monkeypatch)
    with pytest.raises(HTTPException) as denied:
        await _public_endpoints(storage, "alice", {"type": "openai_credential", "base_url": "http://169.254.169.254/v1"})
    assert (denied.value.status_code, denied.value.detail) == (422, "ENDPOINT_NOT_ALLOWED")
    await _public_endpoints(storage, "alice", {"type": "openai_credential", "api_key": "k"})


@pytest.mark.asyncio
async def test_single_tenant_deployment_keeps_local_tools(monkeypatch):
    from agentscope.app._service._catalog_resources import is_operator

    monkeypatch.setenv("VIN_PLATFORM_ENABLED", "false")
    assert await is_operator(_FakeStorage(), "anyone")
