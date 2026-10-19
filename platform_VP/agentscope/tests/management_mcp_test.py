import asyncio
from types import SimpleNamespace

import httpx
from unittest.mock import AsyncMock
from agentscope.app._service._skill_packages import archive_bytes, cache_archive
from agentscope.app.storage import SkillRecord
from agentscope.mcp import MCPClient, HttpMCPConfig
from fastapi import HTTPException


def _record(name):
    return SimpleNamespace(enabled=True, discovered_tools=[{'name': name, 'read_only': True}],
        client=MCPClient(name='domain', is_stateful=False, mcp_config=HttpMCPConfig(url='https://domain.example/mcp',
            headers={'Authorization': 'Bearer fixture-control'})))


def test_test_pack_grant_uses_the_configured_demo_binding_and_never_mutates_the_catalog_client(monkeypatch):
    from agentscope.app._service import _management_mcp as module
    original_http = httpx.AsyncClient
    captured = []
    name = 'vh_management_ticket_summary'
    record = _record(name)

    async def handler(request):
        import json
        payload = json.loads(request.content)
        assert request.url.path == '/api/business/platform/management-grants'
        assert request.headers['Authorization'] == 'Bearer fixture-control'
        captured.append(payload)
        return httpx.Response(200, json={'bearer_token': 'fixture-short-lived'})

    monkeypatch.setenv('VINHOMES_TEST_BINDING', 'default/vinhomes/demo-area/demo-user')
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kwargs: original_http(**kwargs, transport=httpx.MockTransport(handler)))
    resolver = AsyncMock(return_value=record)
    monkeypatch.setattr('agentscope.app._service._catalog_resources.resolve_catalog_resource', resolver)
    agent = SimpleNamespace(data=SimpleNamespace(spec={'tools': [{'mcp_id': 'm', 'tool_name': name}]}))
    result = asyncio.run(module.manager_clients(object(), 'any-customer', agent, [record.client]))
    assert captured == [{'platform_tenant': 'default', 'platform_domain': 'vinhomes', 'platform_area': 'demo-area',
                         'platform_user': 'demo-user', 'tools': [name]}]
    resolver.assert_awaited_once()
    assert resolver.await_args.kwargs['permission'] == 'execute'
    assert len(result) == 1 and result[0].enable_tools == [name]
    assert result[0].mcp_config.headers['Authorization'] == 'Bearer fixture-short-lived'
    assert record.client.mcp_config.headers['Authorization'] == 'Bearer fixture-control'


def test_unconfigured_test_pack_refuses_instead_of_using_a_customer_identity(monkeypatch):
    from agentscope.app._service import _management_mcp as module
    monkeypatch.delenv('VINHOMES_TEST_BINDING', raising=False)
    agent = SimpleNamespace(data=SimpleNamespace(spec={'tools': [{'mcp_id': 'm', 'tool_name': 'vh_management_sla_report'}]}))
    try:
        asyncio.run(module.manager_clients(object(), 'u', agent, []))
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError('test pack ran without its binding')


def test_skill_cache_checks_integrity_and_size_without_hub():
    record=SkillRecord(name='fixture',user_id='u')
    asyncio.run(cache_archive(record,b'fixture-archive','tar'))
    assert archive_bytes(record)==b'fixture-archive'
    record.archive_sha256='wrong'
    try:
        archive_bytes(record)
    except HTTPException as error:
        assert error.status_code==409
    else:
        raise AssertionError('Corrupt cache accepted')
    try:
        asyncio.run(cache_archive(record,b'x'*2_000_001,'zip'))
    except HTTPException as error:
        assert error.status_code==413
    else:
        raise AssertionError('Oversized archive accepted')
