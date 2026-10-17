import asyncio
from types import SimpleNamespace
from contextlib import asynccontextmanager

import httpx
from agentscope.app._service._management_mcp import manager_clients
from agentscope.app._service._skill_packages import archive_bytes, cache_archive
from agentscope.app.storage import SkillRecord
from agentscope.mcp import MCPClient, HttpMCPConfig
from fastapi import HTTPException


def test_management_client_uses_current_auth_area_and_never_mutates_ticket_client(monkeypatch):
    from agentscope.app._service import _management_mcp as module
    original_http = httpx.AsyncClient
    captured = []
    name = 'vh_management_ticket_summary'
    record = SimpleNamespace(enabled=True, discovered_tools=[{'name':name,'read_only':True}],
        client=MCPClient(name='domain',is_stateful=False,mcp_config=HttpMCPConfig(url='https://domain.example/mcp',
            headers={'Authorization':'Bearer fixture-control'})))

    async def handler(request):
        import json
        payload = json.loads(request.content)
        assert request.url.path == '/api/business/platform/management-grants'
        assert request.headers['Authorization'] == 'Bearer fixture-control'
        assert payload['platform_area'] == 'current-op2' and payload['platform_user'] == '600f652c-a100-4a35-a98f-c751c8f4c2d5'
        captured.append(payload)
        return httpx.Response(200,json={'bearer_token':'fixture-short-lived'})

    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs: original_http(**kwargs,transport=httpx.MockTransport(handler)))
    class DB:
        async def execute(self,*args):
            assert isinstance(args[1]['id'], str), 'auth_users.id is a string column'
            return SimpleNamespace(mappings=lambda:SimpleNamespace(first=lambda:{'tenant_id':'t','domain_id':'d','area_id':'current-op2','role':'AREA_MANAGER','status':'active'}))
    class Engine:
        @asynccontextmanager
        async def connect(self):
            yield DB()
    class Storage:
        async def get_mcp(self,*args):
            return record
    agent=SimpleNamespace(data=SimpleNamespace(spec={'tools':[{'mcp_id':'m','tool_name':name}]}))
    result=asyncio.run(manager_clients(Storage(),SimpleNamespace(_require_engine=lambda:Engine()),
        '600f652c-a100-4a35-a98f-c751c8f4c2d5',agent,[record.client]))
    assert len(result)==1 and captured
    assert result[0].enable_tools==[name]
    assert result[0].mcp_config.headers['Authorization']=='Bearer fixture-short-lived'
    assert record.client.mcp_config.headers['Authorization']=='Bearer fixture-control'


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
