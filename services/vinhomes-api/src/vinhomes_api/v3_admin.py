"""What the platform administrator reads: the management units, the models at work, the audit trail.

Read only. Accounts are managed by the password-login module and external connections by
v3_connections; creating a management unit is still the provisioning script's job.
"""
import asyncio
import os
from datetime import datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection

router = APIRouter(prefix='/admin', tags=['Platform administration'])
Admin = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]


def admin(scope) -> None:
    if not scope[2]:
        raise HTTPException(403, 'Platform admin required')


@router.get('/units')
async def units(scope: Admin):
    """Each management unit with the buildings it covers, its groups and how many people and agents work in it."""
    admin(scope)
    rows = await scope[0].execute(text('''select mu.id,mu.code,mu.name,mu.status,
        coalesce((select jsonb_agg(distinct b.name order by b.name) from buildings b
          join management_coverage mc on mc.tenant_id=b.tenant_id and mc.management_unit_id=mu.id
            and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
          join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
            and (s.kind='tenant' or (s.kind='building' and s.building_id=b.id)
              or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id))
          where b.tenant_id=mu.tenant_id and b.status='active'),'[]'::jsonb) as buildings,
        coalesce((select jsonb_agg(jsonb_build_object('id',w.id,'name',w.name,
            'members',(select count(*) from workspace_members m where m.workspace_id=w.id and m.tenant_id=w.tenant_id and m.status='active'),
            'agents',(select count(distinct r.agent_id) from agent_releases r join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id
              where a.workspace_id=w.id and r.tenant_id=w.tenant_id and r.status='published' and r.revoked_at is null),
            'connections',(select count(*) from mcp_servers c where c.tenant_id=w.tenant_id and c.provenance='custom'
              and (c.workspace_id is null or c.workspace_id=w.id))) order by w.name)
          from workspaces w where w.management_unit_id=mu.id and w.tenant_id=mu.tenant_id and w.status='active'),'[]'::jsonb) as groups,
        (select count(*) from staff_profiles sp where sp.management_unit_id=mu.id and sp.tenant_id=mu.tenant_id) as staff,
        (select count(*) from tickets t where t.management_unit_id=mu.id and t.tenant_id=mu.tenant_id
          and t.status not in ('closed','cancelled')) as open_tickets
        from management_units mu order by mu.name'''))
    return {'items': [dict(r) for r in rows.mappings()]}


async def health(client: httpx.AsyncClient, url: str | None) -> dict | None:
    """A service's own word on what it runs, or None when it does not answer. Never a key or an address."""
    if not url:
        return None
    try:
        reply = await client.get(url.rstrip('/') + '/health')
        body = reply.json()
        return body if reply.status_code == 200 and isinstance(body, dict) else None
    except (httpx.HTTPError, ValueError):
        return None


@router.get('/models')
async def models(request: Request, scope: Admin):
    """Which model each role runs on, as the running services report it. Models are set in the
    deployment's settings (one provider, key and address per role); this screen does not change them."""
    admin(scope)
    reception_url = request.app.state.settings.reception_url
    coordination_url = os.getenv('VINHOMES_API_COORDINATION_URL', '').strip() or None
    factory_url = os.getenv('FACTORY_SERVICE_URL', '').strip() or None
    async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
        reception, coordination, factory = await asyncio.gather(
            health(client, reception_url), health(client, coordination_url), health(client, factory_url))
    embedding = (await scope[0].execute(text(
        'select provider,model_name,dimension from embedding_models where active order by updated_at desc limit 1'))).mappings().first()

    def role(code, configured, answer, model=None, provider=None):
        return {'role': code, 'configured': bool(configured), 'running': answer is not None,
                'model': model, 'provider': provider}

    c = coordination or {}
    return {'items': [
        role('reception', reception_url, reception, (reception or {}).get('model'), (reception or {}).get('provider')),
        role('supervisor', coordination_url, coordination, c.get('model'), c.get('provider')),
        role('specialist', coordination_url, coordination, c.get('specialist_model')),
        role('factory', factory_url, factory),
        {'role': 'embedding', 'configured': embedding is not None, 'running': None,
         'model': f"{embedding['model_name']} · {embedding['dimension']} chiều" if embedding else None,
         'provider': embedding['provider'] if embedding else None},
    ]}


@router.get('/audit-events')
async def audit_events(scope: Admin, kind: str = Query('', max_length=60, pattern=r'^[a-z_.]*$'),
                       before: datetime | None = None, limit: int = Query(50, ge=1, le=100)):
    """The trail, newest first. `kind` is the first part of an event type (agent, connection, team, ...)."""
    admin(scope)
    rows = await scope[0].execute(text('''select e.id,e.created_at,e.event_type,e.initiator_kind,e.target_type,e.target_id,e.payload,
          coalesce(u.name, case when e.initiator_kind='agent' then (select a.name from agents a where a.id=e.initiator_id and a.tenant_id=e.tenant_id) end,
            e.initiator_id) as actor
        from audit_events e left join users u on u.id=e.actor_user_id
        where (:kind='' or e.event_type like :prefix) and (cast(:before as timestamptz) is null or e.created_at<cast(:before as timestamptz))
        order by e.created_at desc limit :limit'''), {'kind': kind, 'prefix': kind.replace('_', r'\_') + '%', 'before': before, 'limit': limit})
    kinds = await scope[0].execute(text("select distinct split_part(event_type,'.',1) from audit_events order by 1"))
    return {'items': [dict(r) for r in rows.mappings()], 'kinds': list(kinds.scalars())}
