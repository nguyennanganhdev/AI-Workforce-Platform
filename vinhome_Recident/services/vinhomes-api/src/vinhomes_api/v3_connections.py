"""External MCP connections an administrator sets up for management's agents.

A connection is a row of the tool catalogue (`mcp_servers`, provenance `custom`) with the workspace it
serves and a sealed token (`credentials`, kind `mcp`). Its tools reach an agent only after the
administrator allowed them one by one: an allowed tool is a `mcp_tools` row with effect `read`, which
is what the agent editor offers and what the tool gateway runs. The tool host seals the token and
speaks MCP; this API never stores or returns a token in clear.

A remote server's own "read only" claim is not believed (the platform's rule, plugins/mcp.ts): the
administrator decides. Only a tool the server itself marks destructive is refused outright.
"""
import json
import os
import re
import unicodedata
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.exc import IntegrityError

from .v3_audit import audit
from .v3_auth import scoped_connection, resident_connection
from .v3_room_agents import managed_room
from .v3_security import digest

router = APIRouter(prefix='/admin/connections', tags=['External connections of agents'])
Admin = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
Member = Annotated[tuple[AsyncConnection, str], Depends(resident_connection)]
room_router = APIRouter(tags=['Unit external connections'])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
# A model's tool name is `<connection>__<tool>`, at most 64 of [A-Za-z0-9_-]; `__` is the separator.
TOOL_NAME = re.compile(r'^[A-Za-z0-9_-]+$')


async def host(path: str, payload: dict, *, timeout: float = 25) -> dict:
    """Ask the tool host. Its refusals (a URL it will not reach, a server that failed) are sentences
    meant for the administrator and are passed on; anything else is an outage."""
    url, token = os.getenv('VINHOMES_API_TECHNICAL_TOOLS_URL', '').rstrip('/'), os.getenv('VINHOMES_API_TECHNICAL_TOOLS_TOKEN', '')
    if not url or len(token) < 32:
        raise HTTPException(503, 'The tool host is not configured')
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            reply = await client.post(url + '/connections' + path, headers={'Authorization': 'Bearer ' + token}, json=payload)
            body = reply.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'The tool host did not answer') from None
    if reply.status_code in (400, 422, 502) and isinstance(body.get('error'), str):
        raise HTTPException(reply.status_code, body['error'])
    if reply.status_code != 200:
        raise HTTPException(503, 'External connections are not configured on the tool host')
    return body


def admin(scope) -> None:
    if not scope[2]:
        raise HTTPException(403, 'Platform admin required')


def code_of(title: str) -> str:
    """A short ASCII name for the connection: the model reads it in front of every tool it offers."""
    plain = unicodedata.normalize('NFD', title.replace('đ', 'd').replace('Đ', 'D'))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in plain if not unicodedata.combining(c)).lower())[:20] or 'ketnoi'


async def connection(db, connection_id: str, *, lock: bool = False):
    row = (await db.execute(text(
        "select s.id,s.title,s.url,s.workspace_id,s.credential_id,s.status,s.suspension_reason,c.encrypted_value as sealed from mcp_servers s "
        "left join credentials c on c.id=s.credential_id and c.revoked_at is null "
        "where s.id=:id and s.provenance='custom'" + (' for update of s' if lock else '')), {'id': connection_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Connection not found')
    return row


async def listed(row) -> list[dict]:
    """What the server offers now, with the name each tool would carry in the catalogue."""
    tools = (await host('/tools', {'url': row['url'], 'sealed': row['sealed']}))['tools']
    return [{'name': f"{row['id']}.{t['name']}", 'tool': t['name'], 'description': t.get('description') or '',
             'effect': 'read' if t.get('effect') == 'read' else 'write', 'input_schema': t.get('inputSchema') or {'type': 'object'}, 'destructive': bool(t.get('destructive')),
             'usable': bool(TOOL_NAME.match(t['name'])) and '__' not in t['name'] and len(row['id']) + 2 + len(t['name']) <= 64}
            for t in tools]


async def users_of(db, connection_id: str, names: list[str]) -> list[str]:
    """Published agents whose pinned version was granted one of these tools. A turn of theirs is refused
    once the tool is gone, so the tool stays until they are revoked or republished without it."""
    rows = await db.execute(text(
        "select distinct a.name from agent_releases r join agent_versions v on v.id=r.version_id and v.tenant_id=r.tenant_id "
        "join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id, jsonb_array_elements(coalesce(v.config->'mcp_tools','[]'::jsonb)) g "
        "where r.status='published' and r.revoked_at is null and g->>'server_id'=:server and g->>'name'=any(:names) order by a.name"),
        {'server': connection_id, 'names': names})
    return list(rows.scalars())


@router.get('')
async def connections(scope: Admin):
    admin(scope)
    rows = await scope[0].execute(text(
        "select s.id,s.title,s.url,s.workspace_id,w.name as workspace,s.credential_id is not null as has_token,"
        "s.tools_refreshed_at,s.last_error,s.created_at,s.status,s.suspension_reason,s.added_by,(select name from users where id=s.added_by) as added_by_name,"
        "coalesce((select jsonb_agg(jsonb_build_object('id',used.id,'name',used.name) order by used.name) from "
        "(select distinct a.id,a.name from agent_releases r join agent_versions v on v.id=r.version_id and v.tenant_id=r.tenant_id "
        "join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id where r.tenant_id=s.tenant_id "
        "and r.status='published' and r.revoked_at is null "
        "and v.config->'mcp_tools' @> jsonb_build_array(jsonb_build_object('server_id',s.id))) used), '[]'::jsonb) as usage_agents,"
        "coalesce((select jsonb_agg(jsonb_build_object('name',t.name,'description',t.description,'effect',t.effect) order by t.name) "
        "from mcp_tools t where t.server_id=s.id and t.tenant_id=s.tenant_id),'[]'::jsonb) as tools "
        "from mcp_servers s left join workspaces w on w.id=s.workspace_id and w.tenant_id=s.tenant_id "
        "where s.provenance='custom' order by s.created_at"))
    workspaces = await scope[0].execute(text("select id,name from workspaces where status='active' order by name"))
    return {'items': [dict(r) for r in rows.mappings()], 'workspaces': [dict(w) for w in workspaces.mappings()]}


class NewConnection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=2, max_length=80)
    url: str = Field(min_length=8, max_length=500)
    token: str | None = Field(default=None, max_length=4000)
    # The group whose agents may use it; none means every group of this organisation.
    workspace_id: UUID | None = None
    allowed_tools: list[str] = Field(default_factory=list, max_length=50)
    read_tools: list[str] = Field(default_factory=list, max_length=50)


@router.post('', status_code=201)
async def create(body: NewConnection, scope: Admin):
    admin(scope)
    return await create_connection(body, scope, legacy_read=True)


async def create_connection(body: NewConnection, scope, *, legacy_read=False):
    db = scope[0]
    await host('/check', {'url': body.url})
    if body.workspace_id and not (await db.execute(text("select 1 from workspaces where id=:id and status='active'"), {'id': body.workspace_id})).first():
        raise HTTPException(422, 'Unknown group')
    code, n = code_of(body.title), 1
    while (await db.execute(text('select 1 from mcp_servers where id=:id'), {'id': code if n == 1 else f'{code}{n}'})).first():
        n += 1
    code = code if n == 1 else f'{code}{n}'
    credential = None
    if body.token and body.token.strip():
        sealed = (await host('/seal', {'token': body.token}))['sealed']
        credential = (await db.execute(text(
            f"insert into credentials(kind,provider,key_id,metadata,encrypted_value,tenant_id,workspace_id,scope_kind) "
            f"values('mcp',:code,'shared','{{}}'::jsonb,:sealed,{TENANT},:workspace,:scope) returning id"),
            {'code': code, 'sealed': sealed, 'workspace': body.workspace_id, 'scope': 'workspace' if body.workspace_id else 'tenant'})).scalar_one()
    await db.execute(text(
        f"insert into mcp_servers(id,title,vendor,url,provenance,credential_id,auth_scheme,added_by,tenant_id,workspace_id) "
        f"values(:id,:title,'custom',:url,'custom',:credential,:scheme,:actor,{TENANT},:workspace)"),
        {'id': code, 'title': body.title.strip(), 'url': body.url, 'credential': credential,
         'scheme': 'deployment-token' if credential else 'none', 'actor': scope[1], 'workspace': body.workspace_id})
    await audit(db, scope[1], 'connection.created', 'mcp_server', code, {'url': body.url, 'workspaceId': body.workspace_id, 'hasToken': bool(credential)})
    if body.allowed_tools:
        await allow_tools(code, AllowedTools(names=[code + '.' + name for name in body.allowed_tools], read_names=[code + '.' + name for name in body.read_tools] if legacy_read else None), scope, legacy_read=legacy_read)
    policy = (await db.execute(text('select require_approval from vh_connection_policy'))).scalar_one_or_none()
    if policy and not (len(scope) > 2 and scope[2]):
        await db.execute(text("update mcp_servers set status='pending' where id=:id"), {'id': code})
    return {'id': code}


@router.post('/{connection_id}/check')
async def check(connection_id: str, scope: Admin):
    admin(scope)
    return await check_connection(connection_id, scope)


async def check_connection(connection_id: str, scope):
    row = await connection(scope[0], connection_id)
    try:
        tools, error = await listed(row), None
    except HTTPException as refused:
        if refused.status_code not in (422, 502):
            raise
        tools, error = [], str(refused.detail)
    await scope[0].execute(text('update mcp_servers set tools_refreshed_at=now(),last_error=:error where id=:id'), {'error': error, 'id': connection_id})
    allowed = set((await scope[0].execute(text('select name from mcp_tools where server_id=:id'), {'id': connection_id})).scalars())
    return {'ok': error is None, 'error': error,
            'tools': [{k: t[k] for k in ('name', 'tool', 'description', 'destructive', 'usable', 'effect')} | {'allowed': t['name'] in allowed} for t in tools]}


class AllowedTools(BaseModel):
    model_config = ConfigDict(extra='forbid')
    names: list[str] = Field(max_length=50)
    read_names: list[str] | None = Field(default=None, max_length=50)


@router.put('/{connection_id}/tools')
async def allow(connection_id: str, body: AllowedTools, scope: Admin):
    admin(scope)
    return await allow_tools(connection_id, body, scope, legacy_read=True)


async def allow_tools(connection_id: str, body: AllowedTools, scope, *, legacy_read=False):
    db = scope[0]
    row = await connection(db, connection_id, lock=True)
    offered = {t['name']: t for t in await listed(row)}
    if body.read_names is not None and (not legacy_read or not set(body.read_names) <= set(body.names)):
        raise HTTPException(422, 'Only admin may classify an allowed tool as read')
    for name in body.names:
        tool = offered.get(name)
        if tool is None:
            raise HTTPException(422, 'The server does not offer one of these tools')
        if tool['destructive'] or not tool['usable']:
            raise HTTPException(422, 'A tool the server marks destructive, or whose name an agent cannot call, cannot be allowed')
    current = set((await db.execute(text('select name from mcp_tools where server_id=:id'), {'id': connection_id})).scalars())
    removed = sorted(current - set(body.names))
    if removed and (agents := await users_of(db, connection_id, removed)):
        raise HTTPException(409, {'code': 'CONNECTION_IN_USE', 'agents': agents})
    await db.execute(text('delete from mcp_tools where server_id=:id and name=any(:names)'), {'id': connection_id, 'names': removed})
    for name in body.names:
        await db.execute(text(
            f"insert into mcp_tools(server_id,name,description,input_schema,effect,destructive,tenant_id) "
            f"values(:server,:name,:description,cast(:schema as jsonb),:effect,false,{TENANT}) "
            f"on conflict(server_id,name) do update set description=excluded.description,input_schema=excluded.input_schema,effect=excluded.effect"),
            {'server': connection_id, 'name': name, 'effect': ('read' if body.read_names is None or name in body.read_names else 'write') if legacy_read else offered[name]['effect'], 'description': offered[name]['description'][:4000], 'schema': json.dumps(offered[name]['input_schema'])})
    await db.execute(text('update mcp_servers set tools_refreshed_at=now(),last_error=null where id=:id'), {'id': connection_id})
    await audit(db, scope[1], 'connection.tools_allowed', 'mcp_server', connection_id, {'allowed': sorted(body.names), 'removed': removed})
    return {'id': connection_id, 'allowed': sorted(body.names)}


@router.delete('/{connection_id}')
async def remove(connection_id: str, scope: Admin):
    admin(scope)
    db = scope[0]
    row = await connection(db, connection_id, lock=True)
    names = list((await db.execute(text('select name from mcp_tools where server_id=:id'), {'id': connection_id})).scalars())
    if names and (agents := await users_of(db, connection_id, names)):
        raise HTTPException(409, {'code': 'CONNECTION_IN_USE', 'agents': agents})
    history = (await db.execute(text('select exists(select 1 from vh_external_call_confirmations where connection_id=:id)'), {'id': connection_id})).scalar_one()
    if history:
        raise HTTPException(409, 'Kết nối đã có lịch sử xác nhận công cụ. Hãy tạm ngưng kết nối để giữ lịch sử kiểm toán.')
    linked_accounts = (await db.execute(text('select exists(select 1 from mcp_user_credentials where server_id=:id)'), {'id': connection_id})).scalar_one()
    if linked_accounts:
        raise HTTPException(409, 'Kết nối còn tài khoản xác thực đã liên kết. Hãy tạm ngưng kết nối để giữ thông tin liên quan.')
    try:
        await db.execute(text('delete from mcp_tools where server_id=:id'), {'id': connection_id})
        await db.execute(text('delete from mcp_servers where id=:id'), {'id': connection_id})
    except IntegrityError as refused:
        # Transaction rollback also restores the tools deleted above when a newer
        # reference appears while this request waits for the connection row lock.
        if getattr(refused.orig, 'sqlstate', None) == '23503':
            raise HTTPException(409, 'Kết nối còn dữ liệu liên quan. Hãy tạm ngưng kết nối để giữ lịch sử kiểm toán.') from None
        raise
    if row['credential_id']:
        await db.execute(text('update credentials set revoked_at=now() where id=:id and revoked_at is null'), {'id': row['credential_id']})
    await audit(db, scope[1], 'connection.removed', 'mcp_server', connection_id, {'url': row['url']})
    return {'id': connection_id, 'status': 'removed'}

class ConnectionPolicy(BaseModel):
    require_approval: bool = False


@router.get('/policy')
async def get_policy(scope: Admin):
    admin(scope)
    value = (await scope[0].execute(text('select require_approval from vh_connection_policy'))).scalar_one_or_none()
    return {'require_approval': bool(value)}


@router.put('/policy')
async def put_policy(body: ConnectionPolicy, scope: Admin):
    admin(scope)
    await scope[0].execute(text(f'insert into vh_connection_policy(tenant_id,require_approval) values({TENANT},:value) on conflict(tenant_id) do update set require_approval=excluded.require_approval,updated_at=now()'), {'value': body.require_approval})
    await audit(scope[0], scope[1], 'connection.policy_changed', 'connection_policy', 'tenant', body.model_dump())
    return body.model_dump()


class ConnectionStatus(BaseModel):
    status: Literal['active', 'suspended']
    reason: str = Field(default='', max_length=2000)


@router.patch('/{connection_id}/status')
async def status_connection(connection_id: str, body: ConnectionStatus, scope: Admin):
    admin(scope)
    if body.status == 'suspended' and not body.reason.strip():
        raise HTTPException(422, 'Lý do tạm ngưng là bắt buộc')
    await connection(scope[0], connection_id, lock=True)
    await scope[0].execute(text('update mcp_servers set status=:status,suspension_reason=:reason where id=:id'), {'status': body.status, 'reason': body.reason.strip() or None, 'id': connection_id})
    await audit(scope[0], scope[1], 'connection.status_changed', 'mcp_server', connection_id, body.model_dump())
    return {'id': connection_id, **body.model_dump()}


async def unit_connection(room_id: str, connection_id: str, scope, *, lock=False):
    room = await managed_room(scope, room_id, lock=False)
    row = await connection(scope[0], connection_id, lock=lock)
    if row['workspace_id'] not in (None, room['workspace_id']):
        raise HTTPException(404, 'Connection not found')
    return row


@room_router.get('/rooms/{room_id}/connections')
async def unit_connections(room_id: str, scope: Member):
    room = await managed_room(scope, room_id, lock=False)
    rows = await scope[0].execute(text("select s.id,s.title,s.status,s.suspension_reason,s.created_at,s.tools_refreshed_at,s.last_error,s.added_by=:actor as own,coalesce((select jsonb_agg(jsonb_build_object('name',t.name,'description',t.description,'effect',t.effect)) from mcp_tools t where t.server_id=s.id),'[]'::jsonb) as tools from mcp_servers s where s.provenance='custom' and (s.workspace_id is null or s.workspace_id=:workspace) order by s.created_at desc"), {'workspace': room['workspace_id'], 'actor': scope[1]})
    return {'items': [dict(r) for r in rows.mappings()]}


@room_router.post('/rooms/{room_id}/connections/discover')
async def discover_connection(room_id: str, body: NewConnection, scope: Member):
    await managed_room(scope, room_id, lock=False)
    sealed = (await host('/seal', {'token': body.token}))['sealed'] if body.token else None
    offered = await listed({'id': 'preview', 'url': body.url, 'sealed': sealed})
    return {'tools': [{k: t[k] for k in ('tool', 'description', 'effect', 'destructive', 'usable')} for t in offered]}


@room_router.post('/rooms/{room_id}/connections', status_code=201)
async def create_unit_connection(room_id: str, body: NewConnection, scope: Member):
    room = await managed_room(scope, room_id, lock=False)
    if body.workspace_id and body.workspace_id != room['workspace_id']:
        raise HTTPException(403, 'Connection must belong to this unit')
    if body.read_tools:
        raise HTTPException(422, 'A unit cannot classify remote tools as read')
    body.workspace_id = room['workspace_id']
    return await create_connection(body, scope)


@room_router.post('/rooms/{room_id}/connections/{connection_id}/check')
async def check_unit_connection(room_id: str, connection_id: str, scope: Member):
    await unit_connection(room_id, connection_id, scope)
    return await check_connection(connection_id, scope)


@room_router.put('/rooms/{room_id}/connections/{connection_id}/tools')
async def allow_unit_connection(room_id: str, connection_id: str, body: AllowedTools, scope: Member):
    row = await unit_connection(room_id, connection_id, scope)
    room = await managed_room(scope, room_id, lock=False)
    if row['workspace_id'] != room['workspace_id']:
        raise HTTPException(403, 'Only own unit connections can be changed')
    return await allow_tools(connection_id, body, scope)


async def external_authority(db, actor, room_id, agent_id, connection_id, tool_name, *, version_id=None, session_id=None, request_message_id=None):
    room = await managed_room((db, actor), room_id, lock=False)
    server = await connection(db, connection_id)
    if server['status'] != 'active':
        raise HTTPException(403, 'Kết nối đang tạm ngưng hoặc chờ duyệt')
    if server['workspace_id'] not in (None, room['workspace_id']) or (server['credential_id'] and not server['sealed']):
        raise HTTPException(403, 'Connection is not available for this unit')
    personal = (await db.execute(text("select 1 from channels where id=:room and kind='personal'"), {'room': room_id})).first()
    if personal and (await db.execute(text('select enabled from vh_private_chat_sources where channel_id=:room and server_id=:server'), {'room': room_id, 'server': connection_id})).scalar_one_or_none() is not True:
        raise HTTPException(403, 'Nguồn ngoài đã tắt trong cuộc trò chuyện này')
    if (session_id is None) != (request_message_id is None):
        raise HTTPException(422, 'Session and question pins must be supplied together')
    if session_id is not None:
        from .v3_session_sources import session_confirmation_authority
        version = await session_confirmation_authority(db, actor, room_id, agent_id, connection_id, session_id, request_message_id)
    else:
        version = (await db.execute(text("select v.id,v.config from agents a join channel_agents ca on ca.agent_id=a.id and ca.channel_id=:room join agent_releases r on r.agent_id=a.id and r.status='published' and r.revoked_at is null join agent_versions v on v.id=r.version_id where a.id=:agent and a.workspace_id=:workspace and a.status='active' order by v.version_no desc limit 1"), {'room': room_id, 'agent': agent_id, 'workspace': room['workspace_id']})).mappings().first()
    if not version or (version_id and version['id'] != version_id) or not any(g.get('server_id') == connection_id and g.get('name') == tool_name for g in version['config'].get('mcp_tools', [])):
        raise HTTPException(403, 'Tool not granted to the current published agent')
    tool = (await db.execute(text('select effect,destructive,description from mcp_tools where server_id=:server and name=:name'), {'server': connection_id, 'name': tool_name})).mappings().first()
    if not tool or tool['destructive']:
        raise HTTPException(403, 'Tool is not available')
    return server, tool, version


async def prepare_external_call(db, actor, room_id, agent_id, connection_id, tool_name, arguments, *, session_id=None, request_message_id=None):
    server, tool, version = await external_authority(db, actor, room_id, agent_id, connection_id, tool_name, session_id=session_id, request_message_id=request_message_id)
    if len(json.dumps(arguments)) > 32000:
        raise HTTPException(422, 'Tool arguments are too large')
    if tool['effect'] == 'read':
        answer = await host('/call', {'url': server['url'], 'sealed': server['sealed'], 'tool': tool_name.removeprefix(connection_id + '.'), 'arguments': arguments})
        await audit(db, actor, 'external-source-used', 'mcp_server', connection_id, {'agentId': agent_id, 'tool': tool_name, 'effect': 'read', 'channelId': room_id})
        return {'result': answer}
    row = (await db.execute(text(f"insert into vh_external_call_confirmations(tenant_id,actor_user_id,channel_id,agent_id,version_id,connection_id,tool_name,arguments,arguments_hash,session_id,request_message_id) values({TENANT},:actor,:room,:agent,:version,:server,:tool,cast(:args as jsonb),:hash,:session,:message) returning id,expires_at"), {'actor': actor, 'room': room_id, 'agent': agent_id, 'version': version['id'], 'server': connection_id, 'tool': tool_name, 'args': json.dumps(arguments), 'hash': digest(arguments), 'session': session_id, 'message': request_message_id})).mappings().one()
    await audit(db, actor, 'external-write-requested', 'mcp_server', connection_id, {'agentId': agent_id, 'tool': tool_name, 'confirmationId': str(row['id']), 'channelId': room_id})
    return {'confirmation': {'id': row['id'], 'connection': server['title'], 'tool': tool_name.removeprefix(connection_id + '.'), 'description': tool['description'], 'arguments': arguments, 'expires_at': row['expires_at']}}


class ExternalDecision(BaseModel):
    decision: Literal['approve', 'cancel']


@room_router.get('/rooms/{room_id}/external-calls')
async def pending_calls(room_id: str, scope: Member):
    await managed_room(scope, room_id, lock=False)
    rows = await scope[0].execute(text("select c.id,c.agent_id,c.tool_name,c.arguments,case when c.status='pending' and c.expires_at<=now() then 'expired' else c.status end as status,c.result,c.created_at,c.expires_at,s.title as connection_title,t.description from vh_external_call_confirmations c join mcp_servers s on s.id=c.connection_id left join mcp_tools t on t.server_id=c.connection_id and t.name=c.tool_name where c.channel_id=:room and c.actor_user_id=:actor order by c.created_at desc limit 50"), {'room': room_id, 'actor': scope[1]})
    return {'items': [dict(r) for r in rows.mappings()]}


@room_router.post('/rooms/{room_id}/external-calls/{confirmation_id}/decision')
async def decide_external_call(room_id: str, confirmation_id: UUID, body: ExternalDecision, scope: Member):
    await managed_room(scope, room_id, lock=False)
    return await execute_external_call(scope[0], scope[1], room_id, confirmation_id, body.decision)


async def execute_external_call(db, actor, room_id, confirmation_id, decision):
    """Commit one-shot consumption before reaching the vendor; ambiguous effects never retry."""
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    async def identity(transaction):
        await transaction.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id',:actor,true)"), {'tenant': tenant, 'actor': actor})
    async with db.engine.begin() as consume:
        await identity(consume)
        item = (await consume.execute(text('select * from vh_external_call_confirmations where id=:id and actor_user_id=:actor and channel_id=:room and expires_at>now() for update'), {'id': confirmation_id, 'actor': actor, 'room': room_id})).mappings().first()
        if not item or item['status'] != 'pending':
            raise HTTPException(409, 'Confirmation is expired or already decided')
        if decision != 'cancel':
            await external_authority(consume, actor, room_id, item['agent_id'], item['connection_id'], item['tool_name'], version_id=item['version_id'], session_id=item['session_id'], request_message_id=item['request_message_id'])
        if digest(item['arguments']) != item['arguments_hash']:
            raise HTTPException(409, 'Confirmation content changed')
        await consume.execute(text('update vh_external_call_confirmations set status=:status,decided_at=now() where id=:id'), {'status': 'cancelled' if decision == 'cancel' else 'executing', 'id': confirmation_id})
        await audit(consume, actor, 'external-write-decided', 'mcp_server', item['connection_id'], {'decision': decision, 'confirmationId': str(confirmation_id), 'channelId': room_id})
    if decision == 'cancel':
        return {'status': 'cancelled'}
    result, state = None, 'uncertain'
    try:
        async with db.engine.begin() as execution:
            await identity(execution)
            # Holding the server lock prevents a new call from passing a committed suspension.
            await connection(execution, item['connection_id'], lock=True)
            server, _, _ = await external_authority(execution, actor, room_id, item['agent_id'], item['connection_id'], item['tool_name'], version_id=item['version_id'], session_id=item['session_id'], request_message_id=item['request_message_id'])
            result = await host('/call', {'url': server['url'], 'sealed': server['sealed'], 'tool': item['tool_name'].removeprefix(item['connection_id'] + '.'), 'arguments': item['arguments']})
            state = 'failed' if result.get('isError') else 'succeeded'
    except HTTPException as error:
        result = {'error': str(error.detail), 'retryable': False}
        state = 'uncertain' if error.status_code >= 500 else 'failed'
    async with db.engine.begin() as completion:
        await identity(completion)
        await completion.execute(text('update vh_external_call_confirmations set status=:status,result=cast(:result as jsonb) where id=:id'), {'id': confirmation_id, 'status': state, 'result': json.dumps(result)})
        await audit(completion, actor, 'external-source-used', 'mcp_server', item['connection_id'], {'agentId': item['agent_id'], 'tool': item['tool_name'], 'effect': 'write', 'status': state, 'confirmationId': str(confirmation_id), 'channelId': room_id})
    return {'status': state, 'result': result}


@router.post('/discover')
async def discover_admin_connection(body: NewConnection, scope: Admin):
    admin(scope)
    sealed = (await host('/seal', {'token': body.token}))['sealed'] if body.token else None
    tools = await listed({'id': 'preview', 'url': body.url, 'sealed': sealed})
    return {'tools': [{k: t[k] for k in ('tool', 'description', 'effect', 'destructive', 'usable')} for t in tools]}
