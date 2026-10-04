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
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_audit import audit
from .v3_auth import scoped_connection

router = APIRouter(prefix='/admin/connections', tags=['External connections of agents'])
Admin = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
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
    if reply.status_code in (422, 502) and isinstance(body.get('error'), str):
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
        "select s.id,s.title,s.url,s.workspace_id,s.credential_id,c.encrypted_value as sealed from mcp_servers s "
        "left join credentials c on c.id=s.credential_id and c.revoked_at is null "
        "where s.id=:id and s.provenance='custom'" + (' for update of s' if lock else '')), {'id': connection_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Connection not found')
    return row


async def listed(row) -> list[dict]:
    """What the server offers now, with the name each tool would carry in the catalogue."""
    tools = (await host('/tools', {'url': row['url'], 'sealed': row['sealed']}))['tools']
    return [{'name': f"{row['id']}.{t['name']}", 'tool': t['name'], 'description': t.get('description') or '',
             'input_schema': t.get('inputSchema') or {'type': 'object'}, 'destructive': bool(t.get('destructive')),
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
        "s.tools_refreshed_at,s.last_error,s.created_at,"
        "coalesce((select jsonb_agg(jsonb_build_object('name',t.name,'description',t.description) order by t.name) "
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


@router.post('', status_code=201)
async def create(body: NewConnection, scope: Admin):
    admin(scope)
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
    return {'id': code}


@router.post('/{connection_id}/check')
async def check(connection_id: str, scope: Admin):
    """List the server's tools. A failure is an answer, kept on the connection, not an error of this API."""
    admin(scope)
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
            'tools': [{k: t[k] for k in ('name', 'tool', 'description', 'destructive', 'usable')} | {'allowed': t['name'] in allowed} for t in tools]}


class AllowedTools(BaseModel):
    model_config = ConfigDict(extra='forbid')
    names: list[str] = Field(max_length=50)


@router.put('/{connection_id}/tools')
async def allow(connection_id: str, body: AllowedTools, scope: Admin):
    """Set which of the server's tools agents may be granted. Descriptions come from the server, now."""
    admin(scope)
    db = scope[0]
    row = await connection(db, connection_id, lock=True)
    offered = {t['name']: t for t in await listed(row)}
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
            f"values(:server,:name,:description,cast(:schema as jsonb),'read',false,{TENANT}) "
            f"on conflict(server_id,name) do update set description=excluded.description,input_schema=excluded.input_schema"),
            {'server': connection_id, 'name': name, 'description': offered[name]['description'][:4000], 'schema': json.dumps(offered[name]['input_schema'])})
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
    await db.execute(text('delete from mcp_tools where server_id=:id'), {'id': connection_id})
    await db.execute(text('delete from mcp_servers where id=:id'), {'id': connection_id})
    if row['credential_id']:
        await db.execute(text('update credentials set revoked_at=now() where id=:id and revoked_at is null'), {'id': row['credential_id']})
    await audit(db, scope[1], 'connection.removed', 'mcp_server', connection_id, {'url': row['url']})
    return {'id': connection_id, 'status': 'removed'}
