"""What the platform administrator reads: the management units, the models at work, the audit trail.

Accounts are managed by the password-login module.
"""
import csv
import io
import json
from datetime import date, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from pydantic import BaseModel, Field, field_validator

from .v3_auth import scoped_connection
from .v3_audit import audit

router = APIRouter(prefix='/admin', tags=['Platform administration'])
Admin = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]


def admin(scope) -> None:
    if not scope[2]:
        raise HTTPException(403, 'Platform admin required')


class UnitCreate(BaseModel):
    code: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{1,59}$')
    name: str = Field(min_length=2, max_length=160)
    building_ids: list[UUID] = Field(min_length=1, max_length=100)
    category_ids: list[UUID] = Field(min_length=1, max_length=30)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Tên đơn vị phải có ít nhất 2 ký tự.')
        return value

    @field_validator('building_ids', 'category_ids')
    @classmethod
    def unique_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Không được chọn trùng mục.')
        return value


@router.get('/unit-options')
async def unit_options(scope: Admin):
    admin(scope)
    buildings = await scope[0].execute(text("select id,code,name from buildings where status='active' order by name"))
    categories = await scope[0].execute(text("select id,code,name from service_categories where enabled order by name"))
    return {'buildings': [dict(r) for r in buildings.mappings()],
            'categories': [dict(r) for r in categories.mappings()]}


@router.post('/units', status_code=201)
async def create_unit(body: UnitCreate, scope: Admin):
    admin(scope)
    db, actor, _ = scope
    # Serializes coverage allocation between administrators, including zone/site coverage.
    await db.execute(text("select pg_advisory_xact_lock(hashtext(current_setting('app.tenant_id')||'-management-coverage'))"))
    if (await db.execute(text('select 1 from management_units where code=:code'), {'code': body.code})).first():
        raise HTTPException(409, 'Mã đơn vị đã được sử dụng.')
    buildings = (await db.execute(text('select id from buildings where id=any(:ids) and status=\'active\''),
                                 {'ids': body.building_ids})).scalars().all()
    categories = (await db.execute(text('select id from service_categories where id=any(:ids) and enabled'),
                                  {'ids': body.category_ids})).scalars().all()
    if len(buildings) != len(body.building_ids) or len(categories) != len(body.category_ids):
        raise HTTPException(422, 'Tòa nhà hoặc dịch vụ không thuộc tổ chức này hoặc đã ngừng hoạt động.')
    covered = (await db.execute(text('''select b.name,mu.name as unit_name from buildings b
        join access_scopes s on s.tenant_id=b.tenant_id and
          (s.kind='tenant' or (s.kind='building' and s.building_id=b.id)
            or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id))
        join management_coverage mc on mc.scope_id=s.id and mc.tenant_id=s.tenant_id
        join management_units mu on mu.id=mc.management_unit_id and mu.tenant_id=mc.tenant_id
        where b.id=any(:buildings) and mc.service_category_id=any(:categories)
          and mu.status='active' and (mc.valid_to is null or mc.valid_to>now()) limit 1'''),
        {'buildings': buildings, 'categories': categories})).mappings().first()
    if covered:
        raise HTTPException(409, f"{covered['name']} đã có {covered['unit_name']} phụ trách dịch vụ được chọn.")
    unit, workspace = uuid4(), uuid4()
    room = 'bql-' + str(unit)
    tenant = "nullif(current_setting('app.tenant_id',true),'')::uuid"
    await db.execute(text(f"insert into management_units(id,tenant_id,code,name,status) values(:id,{tenant},:code,:name,'active')"),
                     {'id': unit, 'code': body.code, 'name': body.name})
    await db.execute(text(f"insert into access_scopes(tenant_id,kind,management_unit_id) values({tenant},'management',:id)"), {'id': unit})
    for building in buildings:
        scope_id = (await db.execute(text("select id from access_scopes where kind='building' and building_id=:id"), {'id': building})).scalar_one_or_none()
        if scope_id is None:
            scope_id = (await db.execute(text(f"insert into access_scopes(tenant_id,kind,building_id) values({tenant},'building',:id) returning id"), {'id': building})).scalar_one()
        for category in categories:
            await db.execute(text(f'''insert into management_coverage(tenant_id,management_unit_id,scope_id,service_category_id,valid_from)
                values({tenant},:unit,:scope,:category,now())'''), {'unit': unit, 'scope': scope_id, 'category': category})
    await db.execute(text(f"insert into workspaces(id,tenant_id,management_unit_id,code,name,status) values(:id,{tenant},:unit,:code,:name,'active')"),
                     {'id': workspace, 'unit': unit, 'code': body.code, 'name': body.name})
    await db.execute(text(f"insert into workspace_members(tenant_id,workspace_id,user_id,status,joined_at) values({tenant},:workspace,:actor,'active',now())"),
                     {'workspace': workspace, 'actor': actor})
    await db.execute(text(f"insert into channels(id,tenant_id,workspace_id,name,description,kind,created_by,is_dispatch_default) values(:id,{tenant},:workspace,:name,'Phòng điều phối yêu cầu của cư dân','management',:actor,true)"),
                     {'id': room, 'workspace': workspace, 'name': body.name, 'actor': actor})
    await db.execute(text(f"insert into channel_memberships(tenant_id,channel_id,user_id) values({tenant},:room,:actor)"), {'room': room, 'actor': actor})
    await audit(db, actor, 'management_unit.created', 'management_unit', str(unit),
                {'code': body.code, 'buildings': buildings, 'categories': categories, 'room': room})
    return {'id': unit, 'workspace_id': workspace, 'room_id': room}


@router.get('/units')
async def units(scope: Admin):
    """Each management unit with the buildings it covers, its groups and how many people work in it."""
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
            'members',(select count(*) from workspace_members m where m.workspace_id=w.id and m.tenant_id=w.tenant_id and m.status='active')) order by w.name)
          from workspaces w where w.management_unit_id=mu.id and w.tenant_id=mu.tenant_id and w.status='active'),'[]'::jsonb) as groups,
        (select count(*) from staff_profiles sp where sp.management_unit_id=mu.id and sp.tenant_id=mu.tenant_id) as staff,
        (select count(*) from tickets t where t.management_unit_id=mu.id and t.tenant_id=mu.tenant_id
          and t.status not in ('closed','cancelled')) as open_tickets
        from management_units mu order by mu.name'''))
    return {'items': [dict(r) for r in rows.mappings()]}


@router.get('/audit-events')
async def audit_events(scope: Admin, kind: str = Query('', max_length=60, pattern=r'^[a-z_.-]*$'),
                       before: datetime | None = None, before_id: UUID | None = None, limit: int = Query(50, ge=1, le=100),
                       first: date | None = Query(None, alias='from'), last: date | None = Query(None, alias='to'),
                       actor: str = Query('',max_length=160), action: str = Query('',max_length=120),
                       search: str = Query('',max_length=160), result: str = Query('',pattern=r'^(|success|failed|recorded)$')):
    admin(scope)
    if first and last and last<first: raise HTTPException(422,'Ngày kết thúc phải từ ngày bắt đầu trở đi.')
    if before_id and not before: raise HTTPException(422,'Mốc sự kiện cần đi cùng thời gian phân trang.')
    rows = await scope[0].execute(text("""select e.id,e.created_at,e.event_type,e.initiator_kind,e.target_type,e.target_id,e.payload,
          coalesce(u.name,
            case when e.initiator_kind='system' then 'Hệ thống' when e.initiator_kind='agent' then 'Agent' else 'Người dùng' end) as actor,
          coalesce(e.payload->>'title',e.payload->>'name',e.payload->>'connection_title',
            (select t.title from tickets t where e.target_type='ticket' and t.id::text=e.target_id and t.tenant_id=e.tenant_id),
            (select v.name from users v where e.target_type='account' and v.id=e.target_id),
            (select mu.name from management_units mu where e.target_type='management_unit' and mu.id::text=e.target_id and mu.tenant_id=e.tenant_id),e.target_type) as target_label,
          case when e.payload->>'ok'='false' or e.payload->>'success'='false' or e.payload->>'status'='failed' or e.event_type like '%.failed' then 'failed'
            when e.payload->>'ok'='true' or e.payload->>'success'='true' then 'success' else 'recorded' end as result
        from audit_events e left join users u on u.id=e.actor_user_id
        where (:kind='' or e.event_type like :prefix)
          and (cast(:before as timestamptz) is null or e.created_at<cast(:before as timestamptz)
            or (e.created_at=cast(:before as timestamptz) and cast(:before_id as uuid) is not null and e.id<cast(:before_id as uuid)))
          and (cast(:first as date) is null or e.created_at>=(cast(cast(:first as date) as timestamp) at time zone 'Asia/Ho_Chi_Minh'))
          and (cast(:last as date) is null or e.created_at<(cast(cast(:last as date)+1 as timestamp) at time zone 'Asia/Ho_Chi_Minh'))
          and (:actor='' or coalesce(u.name,e.initiator_id,'') ilike :actor_match)
          and (:action='' or e.event_type=:action)
          and (:search='' or e.payload::text ilike :search_match or e.target_id ilike :search_match or e.event_type ilike :search_match)
          and (:result='' or (case when e.payload->>'ok'='false' or e.payload->>'success'='false' or e.payload->>'status'='failed' or e.event_type like '%.failed' then 'failed' when e.payload->>'ok'='true' or e.payload->>'success'='true' then 'success' else 'recorded' end)=:result)
        order by e.created_at desc,e.id desc limit :limit"""),
        {'kind':kind,'prefix':kind.replace('_',r'\_')+'%','before':before,'before_id':before_id,'limit':limit,'first':first,'last':last,
         'actor':actor,'actor_match':'%'+actor+'%','action':action,'search':search,'search_match':'%'+search+'%','result':result})
    kinds = await scope[0].execute(text("select distinct split_part(event_type,'.',1) from audit_events order by 1"))
    actions = await scope[0].execute(text('select distinct event_type from audit_events order by 1'))
    return {'items':[dict(r) for r in rows.mappings()],'kinds':list(kinds.scalars()),'actions':list(actions.scalars())}


# More than this is not a file somebody reads: a shorter span is asked for, rather than a cut one handed over.
EXPORT_ROWS = 50_000


def cell(value) -> str:
    """A spreadsheet runs a cell that starts with = + - or @ as a formula; such a cell is written as text."""
    written = '' if value is None else str(value)
    return "'" + written if written[:1] in ('=', '+', '-', '@') else written


@router.get('/audit-events/export')
async def audit_export(scope: Admin, first: date = Query(..., alias='from'), last: date = Query(..., alias='to'),
                       kind: str = Query('', max_length=60, pattern=r'^[a-z_.-]*$'),
                       actor: str = Query('',max_length=160), action: str = Query('',max_length=120),
                       search: str = Query('',max_length=160), result: str = Query('',pattern=r'^(|success|failed|recorded)$')):
    """The trail of a span of days (Việt Nam time, both days included) as a CSV file, oldest first.
    Taking a copy of the trail is itself recorded in it."""
    admin(scope)
    if last < first:
        raise HTTPException(422, 'Ngày kết thúc phải từ ngày bắt đầu trở đi.')
    # Midnight in Việt Nam, as a moment: the date is read as a local time there, not as one of the database's own zone.
    span = """e.created_at>=(cast(cast(:first as date) as timestamp) at time zone 'Asia/Ho_Chi_Minh')
        and e.created_at<(cast(cast(:last as date)+1 as timestamp) at time zone 'Asia/Ho_Chi_Minh') and (:kind='' or e.event_type like :prefix)
        and (:actor='' or e.initiator_id ilike :actor_match or exists(select 1 from users actor_user where actor_user.id=e.actor_user_id and actor_user.name ilike :actor_match))
        and (:action='' or e.event_type=:action)
        and (:search='' or e.payload::text ilike :search_match or e.target_id ilike :search_match or e.event_type ilike :search_match)
        and (:result='' or (case when e.payload->>'ok'='false' or e.payload->>'success'='false' or e.payload->>'status'='failed' or e.event_type like '%.failed' then 'failed' when e.payload->>'ok'='true' or e.payload->>'success'='true' then 'success' else 'recorded' end)=:result)"""
    asked = {'first':first,'last':last,'kind':kind,'prefix':kind.replace('_',r'\_')+'%','actor':actor,'actor_match':'%'+actor+'%','action':action,'search':search,'search_match':'%'+search+'%','result':result}
    count = (await scope[0].execute(text('select count(*) from audit_events e where ' + span), asked)).scalar_one()
    if count > EXPORT_ROWS:
        raise HTTPException(413, f'Khoảng này có {count} sự kiện, nhiều hơn mức {EXPORT_ROWS} của một tệp. Chọn khoảng ngắn hơn.')
    rows = await scope[0].execute(text("""select to_char(e.created_at at time zone 'Asia/Ho_Chi_Minh','YYYY-MM-DD HH24:MI:SS') as at,
          e.event_type,e.initiator_kind,e.target_type,e.target_id,e.payload,
          coalesce(u.name, e.initiator_id) as actor
        from audit_events e left join users u on u.id=e.actor_user_id where """ + span + ' order by e.created_at,e.id'), asked)
    out = io.StringIO()
    sheet = csv.writer(out)
    sheet.writerow(['Thời điểm (giờ Việt Nam)', 'Sự kiện', 'Người hoặc agent', 'Loại người thực hiện', 'Loại đối tượng', 'Đối tượng', 'Chi tiết'])
    for row in rows.mappings():
        sheet.writerow([cell(value) for value in (row['at'], row['event_type'], row['actor'], row['initiator_kind'], row['target_type'],
                                                  row['target_id'], json.dumps(row['payload'], ensure_ascii=False))])
    await audit(scope[0], scope[1], 'audit.exported', 'audit_events', f'{first}..{last}', {'kind': kind, 'rows': count})
    # The byte order mark is what makes a spreadsheet read the Vietnamese text as UTF-8.
    return Response('﻿' + out.getvalue(), media_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="nhat-ky-{first}-{last}.csv"', 'Cache-Control': 'no-store'})


@router.get('/overview')
async def overview(scope: Admin):
    """Tenant-wide figures, including empty dates rather than inventing chart activity."""
    admin(scope)
    db = scope[0]
    counts = (await db.execute(text("""select
        (select count(*) from tickets where status not in ('closed','cancelled')) as open_tickets,
        (select count(*) from tickets where status not in ('closed','cancelled') and resolution_due_at<now()) as overdue_tickets,
        (select count(*) from tenant_memberships where status='pending') as pending_accounts"""))).mappings().one()
    chart = await db.execute(text("""select d::date as date,count(t.id) as count
        from generate_series((now() at time zone 'Asia/Ho_Chi_Minh')::date-13,
          (now() at time zone 'Asia/Ho_Chi_Minh')::date,interval '1 day') d
        left join tickets t on (t.created_at at time zone 'Asia/Ho_Chi_Minh')::date=d::date
        group by d order by d"""))
    pending = await db.execute(text("""select u.name,u.email from tenant_memberships m join users u on u.id=m.user_id
        where m.status='pending' order by m.created_at limit 5"""))
    return {**dict(counts),'requests_per_day':[dict(r) for r in chart.mappings()],
            'pending_accounts_preview':[dict(r) for r in pending.mappings()]}
