"""Read-only BQL capabilities with short-lived, explicitly bound area grants."""
import base64
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

TOOLS = ('vh_management_ticket_list', 'vh_management_ticket_summary', 'vh_management_sla_report',
         'vh_management_workload', 'vh_management_knowledge_search', 'vh_management_capabilities')
router = APIRouter(prefix='/platform', tags=['Platform BQL management'])


def _secret():
    return os.environ['VINHOMES_API_PLATFORM_MCP_TOKEN'].encode()


def _pack(data):
    return base64.urlsafe_b64encode(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).decode().rstrip('=')


def sign_grant(binding_id, tools, ttl=900):
    body = _pack({'binding': str(binding_id), 'tools': list(tools), 'exp': int(time.time()) + ttl, 'kind': 'management-v1'})
    signature = hmac.new(_secret(), ('management-v1:' + body).encode(), hashlib.sha256).hexdigest()
    return 'vhmgr_' + body + '.' + signature


def verify_grant(token):
    try:
        if not token.startswith('vhmgr_') or len(token) > 8192:
            return None
        body, signature = token[6:].split('.')
        expected = hmac.new(_secret(), ('management-v1:' + body).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if data.get('kind') != 'management-v1' or not isinstance(data.get('exp'), int) or not time.time() < data['exp'] <= time.time() + 901:
            return None
        UUID(data['binding'])
        if not isinstance(data.get('tools'), list) or not data['tools'] or any(t not in TOOLS for t in data['tools']):
            return None
        return data
    except (ValueError, TypeError, KeyError):
        return None


async def find_management_grant(db, token):
    data = verify_grant(token)
    if data is None:
        return None
    row = (await db.execute(text('''select b.* from platform_management_bindings b
        join management_units m on m.id=b.management_unit_id and m.tenant_id=b.tenant_id
        join sites s on s.id=b.site_id and s.tenant_id=b.tenant_id
        left join zones z on z.id=b.zone_id and z.tenant_id=b.tenant_id and z.site_id=b.site_id
        where b.id=:id and b.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
          and b.active and m.status='active' and s.status='active'
          and (b.zone_id is null or z.status='active') '''), {'id': UUID(data['binding'])})).mappings().first()
    return {**dict(row), 'kind': 'management', 'tools': data['tools']} if row else None


class GrantRequest(BaseModel):
    platform_tenant: str = Field(min_length=1, max_length=255)
    platform_domain: str = Field(min_length=1, max_length=200)
    platform_area: str = Field(min_length=1, max_length=200)
    platform_user: str = Field(min_length=1, max_length=200)
    tools: list[str] = Field(min_length=1, max_length=len(TOOLS))


@router.post('/management-grants')
async def issue_management_grant(body: GrantRequest, request: Request):
    supplied = request.headers.get('authorization', '').encode()
    if not hmac.compare_digest(supplied, b'Bearer ' + _secret()):
        raise HTTPException(401, 'Control-plane credential required')
    if any(t not in TOOLS for t in body.tools) or len(set(body.tools)) != len(body.tools):
        raise HTTPException(422, 'Only management read tools can be granted')
    async with request.app.state.engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {'tenant': str(request.app.state.settings.tenant_id)})
        row = (await db.execute(text('''select id from platform_management_bindings
            where tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid and active
              and platform_tenant=:platform_tenant and platform_domain=:platform_domain
              and platform_area=:platform_area and platform_user=:platform_user'''), body.model_dump(exclude={'tools'}))).first()
        if row is None:
            raise HTTPException(403, 'No active operator binding for this BQL account and area')
        return {'bearer_token': sign_grant(row.id, body.tools), 'expires_in': 900, 'tools': body.tools}


async def scope(db, tool):
    from .platform_access import ACCESS
    from .platform_work import Refused
    access = ACCESS.get() or {}
    current = await find_management_grant(db, access.get('token', ''))
    if current is None or tool not in current['tools']:
        raise Refused('Không có grant BQL đúng khu và công cụ.', 'MANAGEMENT_SCOPE_FORBIDDEN')
    return current


def period(from_date, to_date):
    from .platform_work import Refused
    try:
        start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    except ValueError:
        raise Refused('Ngày báo cáo cần định dạng YYYY-MM-DD.', 'INVALID_PERIOD') from None
    if not 0 < (end - start).days <= 93:
        raise Refused('Khoảng báo cáo phải từ 1 đến 93 ngày, ngày kết thúc không bao gồm.', 'INVALID_PERIOD')
    vn = timezone(timedelta(hours=7))
    return {'start': datetime.combine(start, datetime.min.time(), vn),
            'end': datetime.combine(end, datetime.min.time(), vn)}


FILTER = "t.tenant_id=:tenant_id and t.site_id=:site_id and (cast(:zone_id as uuid) is null or t.zone_id=:zone_id) and t.management_unit_id=:management_unit_id and t.created_at>=:start and t.created_at<:end"


async def tickets(db, from_date, to_date, status=None, offset=0, limit=20):
    s = await scope(db, TOOLS[0]); params = {**s, **period(from_date, to_date), 'status': status, 'offset': offset, 'limit': limit}
    where = FILTER + ' and (cast(:status as text) is null or t.status=:status)'
    total = await db.scalar(text('select count(*) from tickets t where ' + where), params)
    rows = (await db.execute(text('''select t.id,t.code,t.title,t.status,t.priority,t.is_emergency,t.version,
        t.created_at,t.updated_at,t.response_due_at,t.resolution_due_at from tickets t where ''' + where +
        ' order by t.created_at desc,t.id limit :limit offset :offset'), params)).mappings().all()
    return {'status': 'ok', 'items': [dict(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit,
            'next_offset': offset + limit if offset + limit < total else None, 'observed_at': time.time()}


async def summary(db, from_date, to_date):
    s = await scope(db, TOOLS[1]); params = {**s, **period(from_date, to_date)}
    rows = (await db.execute(text('select t.status,count(*) as tickets from tickets t where ' + FILTER + ' group by t.status order by t.status'), params)).mappings().all()
    return {'status': 'ok', 'groups': [dict(r) for r in rows], 'total': sum(r['tickets'] for r in rows), 'observed_at': time.time()}


async def sla(db, from_date, to_date):
    s = await scope(db, TOOLS[2]); params = {**s, **period(from_date, to_date)}
    row = (await db.execute(text('''select count(*) as total,
        count(*) filter(where t.first_response_at>t.response_due_at or (t.first_response_at is null and t.response_due_at<now())) as response_overdue,
        count(*) filter(where t.resolved_at>t.resolution_due_at or (t.resolved_at is null and t.status not in ('closed','cancelled') and t.resolution_due_at<now())) as resolution_overdue,
        count(*) filter(where t.response_due_at is null or t.resolution_due_at is null) as missing_deadlines
        from tickets t where ''' + FILTER), params)).mappings().one()
    return {'status': 'ok', **dict(row), 'observed_at': time.time(), 'definition': 'Ticket deadline snapshot; not a recomputation of every SLA cycle.'}


async def workload(db, from_date, to_date):
    s = await scope(db, TOOLS[3]); params = {**s, **period(from_date, to_date)}
    rows = (await db.execute(text('''select t.assigned_team_id,count(*) as open_tickets from tickets t where ''' + FILTER +
        " and t.status not in ('closed','cancelled','resolved') group by t.assigned_team_id order by count(*) desc"), params)).mappings().all()
    return {'status': 'ok', 'groups': [dict(r) for r in rows], 'observed_at': time.time(), 'definition': 'Open tickets by assigned team, limited to tickets created in the requested period.'}


async def knowledge(db, query, include_unverified=False, limit=8):
    s = await scope(db, TOOLS[4])
    rows = (await db.execute(text('''select d.id,d.title,d.code,d.version_id,d.unverified,d.category,c.ordinal,c.text_content
        from vh_knowledge_documents d join vh_knowledge_chunks c on c.document_id=d.id and c.tenant_id=d.tenant_id
        where d.tenant_id=:tenant_id and d.site_id=:site_id and (cast(:zone_id as uuid) is null or d.zone_id is null or d.zone_id=:zone_id)
          and (d.building_ids is null or not exists(select 1 from unnest(d.building_ids) x
              left join buildings b on b.id=x and b.tenant_id=d.tenant_id where b.site_id is distinct from :site_id
                or (cast(:zone_id as uuid) is not null and b.zone_id is distinct from :zone_id)))
          and (:include_unverified or not d.unverified)
          and c.search_tsv @@ plainto_tsquery('simple',:query)
        order by ts_rank(c.search_tsv,plainto_tsquery('simple',:query)) desc,d.id,c.ordinal limit :limit'''),
        {**s, 'query': query, 'include_unverified': include_unverified, 'limit': limit})).mappings().all()
    return {'status': 'ok', 'items': [dict(r) for r in rows], 'reference_only': include_unverified, 'observed_at': time.time()}


async def capabilities(db):
    await scope(db, TOOLS[5])
    return {'status': 'ok', 'management_read_tools': list(TOOLS), 'ticket_actions': ['dispatch', 'reschedule', 'cancel', 'add_note'],
            'ticket_actions_require': 'Separate ticket/workflow/tool grant and action-specific consent',
            'travel': 'mock_only', 'unsupported_writes': ['card_issue', 'visitor_registration', 'amenity_booking', 'payment'],
            'fallback': 'Return a proposed plan and hand over to the responsible human; never claim an unsupported action completed.'}
