"""Persisted unit skills and graph metrics from actual agent runs."""
import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from .v3_agent_reviews import Member, TENANT
from .v3_auth import _actor_id
from .v3_room_agents import managed_room
from .v3_audit import audit

router = APIRouter(tags=['Agent skills and graph'])
class SkillInput(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    description: str = Field(default='',max_length=2000)
    instructions: str = Field(min_length=1,max_length=20000)

@router.post('/rooms/{room_id}/agent-skills',status_code=201)
async def create_skill(room_id:str,body:SkillInput,scope:Member):
    room = await managed_room(scope,room_id,lock=False)
    if (await scope[0].execute(text('select 1 from platform_admins where user_id=:actor'), {'actor':scope[1]})).first():
        raise HTTPException(403,'Admin cannot author unit skills')
    row=(await scope[0].execute(text(f'insert into vh_agent_skills(tenant_id,workspace_id,created_by,name,description,instructions) values({TENANT},:workspace,:actor,:name,:description,:instructions) returning id,name,description,instructions'), {'workspace':room['workspace_id'],'actor':scope[1],**body.model_dump()})).mappings().one()
    await audit(scope[0],scope[1],'agent.skill_created','agent_skill',str(row['id']),{'name':body.name,'roomId':room_id})
    return dict(row)

@router.put('/rooms/{room_id}/agent-skills/{skill_id}')
async def update_skill(room_id:str,skill_id:str,body:SkillInput,scope:Member):
    room=await managed_room(scope,room_id,lock=False)
    row=(await scope[0].execute(text('update vh_agent_skills set name=:name,description=:description,instructions=:instructions,updated_at=now() where id=cast(:id as uuid) and workspace_id=:workspace and created_by=:actor returning id'), {'id':skill_id,'workspace':room['workspace_id'],'actor':scope[1],**body.model_dump()})).first()
    if not row: raise HTTPException(404,'Own unit skill required')
    await audit(scope[0],scope[1],'agent.skill_updated','agent_skill',skill_id,body.model_dump())
    return {'id':skill_id}

async def graph_snapshot(db,actor,room_id):
    room=await managed_room((db,actor),room_id,lock=False)
    rows=await db.execute(text("""select a.id,
      count(distinct coalesce(tm.team_id::text,r.channel_id)) filter(where r.created_at >= date_trunc('day',now() at time zone 'Asia/Ho_Chi_Minh') at time zone 'Asia/Ho_Chi_Minh') as today,
      count(distinct coalesce(tm.team_id::text,r.channel_id)) filter(where r.status='running'
        and (r.team_member_id is null or (tm.status='active' and at.channel_id=:room
          and at.status not in ('completed','cancelled','failed')
          and t.status not in ('closed','cancelled') and t.reopen_count=at.ticket_generation))) as running,
      count(distinct coalesce(tm.team_id::text,r.channel_id)) as seven_days,
      avg(extract(epoch from r.finished_at-r.started_at)) filter(where r.status='succeeded' and r.finished_at is not null and r.started_at is not null) as response_seconds
      from agents a join channel_agents ca on ca.agent_id=a.id and ca.channel_id=:room
      left join agent_runs r on r.agent_id=a.id and r.created_at>=now()-interval '7 days'
      left join team_members tm on tm.id=r.team_member_id and tm.tenant_id=r.tenant_id
      left join agent_teams at on at.id=tm.team_id and at.tenant_id=tm.tenant_id
      left join tickets t on t.id=at.ticket_id and t.tenant_id=at.tenant_id
      where a.workspace_id=:workspace group by a.id"""),{'room':room_id,'workspace':room['workspace_id']})
    metrics={r['id']:{'today':r['today'],'running':r['running'],'seven_days':r['seven_days'],**({'response_seconds':float(r['response_seconds'])} if r['response_seconds'] is not None else {})} for r in rows.mappings()}
    models=(await db.execute(text("""select a.id,coalesce(m.name,d.name) as name from agents a
      join channel_agents ca on ca.agent_id=a.id and ca.channel_id=:room
      left join lateral(select v.config from agent_releases rel
        join agent_versions v on v.id=rel.version_id and v.tenant_id=rel.tenant_id
        where rel.agent_id=a.id and rel.tenant_id=a.tenant_id and rel.status='published' and rel.revoked_at is null
        order by v.version_no desc limit 1) published on true
      left join admin_model_registry m on m.id::text=(case when published.config is not null then published.config else a.configuration end)->>'model_id'
      left join admin_role_models role on role.role=case when a.purpose='supervisor' then 'supervisor' else 'specialist' end
      left join admin_model_registry d on d.id=role.model_id"""),{'room':room_id})).mappings().all()
    for model in models:
        if model['name'] and model['id'] in metrics: metrics[model['id']]['model_name']=model['name']
    sessions=(await db.execute(text("""select distinct tm.agent_id,at.id,t.title,
      concat_ws(', ',case when ap.code is not null then 'Căn '||ap.code end,case when b.code is not null then 'tòa '||b.code end) as location
      from agent_runs r join team_members tm on tm.id=r.team_member_id
      join agent_teams at on at.id=tm.team_id and at.channel_id=:room
      join tickets t on t.id=at.ticket_id
      left join units ap on ap.id=t.unit_id and ap.tenant_id=t.tenant_id
      left join buildings b on b.id=t.building_id and b.tenant_id=t.tenant_id
      where r.status='running' and tm.status='active'
        and at.status not in ('completed','cancelled','failed')
        and t.status not in ('closed','cancelled') and t.reopen_count=at.ticket_generation
      order by t.title limit 100"""),{'room':room_id})).mappings().all()
    waiting=(await db.execute(text("""select count(*) from agent_teams at
      join tickets t on t.id=at.ticket_id and t.tenant_id=at.tenant_id
      join lateral(select status from vh_ticket_plans p where p.ticket_id=at.ticket_id order by created_at desc limit 1) p on true
      where at.channel_id=:room and at.status not in ('completed','cancelled','failed')
        and t.status not in ('closed','cancelled') and t.reopen_count=at.ticket_generation
        and exists(select 1 from team_members live where live.team_id=at.id and live.tenant_id=at.tenant_id and live.status='active')
        and p.status='management_pending'"""),{'room':room_id})).scalar_one()
    summary=(await db.execute(text("""select count(distinct at.id) filter(where at.status in ('running','waiting')
        and t.status not in ('closed','cancelled') and t.reopen_count=at.ticket_generation
        and exists(select 1 from team_members live where live.team_id=at.id and live.tenant_id=at.tenant_id and live.status='active')) as running_sessions,
      count(distinct at.id) filter(where at.created_at >= date_trunc('day',now() at time zone 'Asia/Ho_Chi_Minh') at time zone 'Asia/Ho_Chi_Minh') as received_today
      from agent_teams at left join tickets t on t.id=at.ticket_id and t.tenant_id=at.tenant_id
      where at.channel_id=:room"""),{'room':room_id})).mappings().one()
    response=(await db.execute(text("""select avg(extract(epoch from r.finished_at-r.started_at)) from agent_runs r
      join channel_agents ca on ca.agent_id=r.agent_id and ca.channel_id=:room
      where r.status='succeeded' and r.started_at is not null and r.finished_at is not null and r.created_at>=now()-interval '7 days'"""),{'room':room_id})).scalar_one()
    return {'metrics':metrics,'sessions':[dict(s) for s in sessions],'summary':{**dict(summary),'waiting':waiting,**({'response_seconds':float(response)} if response is not None else {})}}

@router.get('/rooms/{room_id}/agent-graph')
async def graph(room_id:str,scope:Member):
    return await graph_snapshot(scope[0],scope[1],room_id)

@router.get('/rooms/{room_id}/agent-graph/events')
async def graph_events(room_id:str,request:Request):
    settings=request.app.state.settings
    actor=await _actor_id(request,settings)
    engine=request.app.state.engine
    if not engine or not settings.tenant_id: raise HTTPException(503,'Graph data is unavailable')
    async def snapshot():
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id',:actor,true)"),{'tenant':str(settings.tenant_id),'actor':actor})
            active=(await db.execute(text("select 1 from users u join tenant_memberships m on m.user_id=u.id where u.id=:actor and u.status='active' and m.status='active'"),{'actor':actor})).first()
            if not active: raise HTTPException(403,'Active membership required')
            return await graph_snapshot(db,actor,room_id)
    first=await snapshot()
    async def events():
        current=first
        while not await request.is_disconnected():
            yield 'data: '+json.dumps(jsonable_encoder(current))+'\n\n'
            await asyncio.sleep(5)
            try: current=await snapshot()
            except HTTPException: break
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

from .v3_agent_reviews import Admin
@router.get('/admin/agent-skills')
async def shared_skills(scope:Admin):
    if not scope[2]: raise HTTPException(403,'Platform admin required')
    rows=await scope[0].execute(text('select id,name,description,instructions from vh_agent_skills where workspace_id is null order by name'))
    return {'items':[dict(r) for r in rows.mappings()]}

@router.post('/admin/agent-skills',status_code=201)
async def publish_shared_skill(body:SkillInput,scope:Admin):
    if not scope[2]: raise HTTPException(403,'Platform admin required')
    row=(await scope[0].execute(text(f'insert into vh_agent_skills(tenant_id,created_by,name,description,instructions) values({TENANT},:actor,:name,:description,:instructions) returning id'),{'actor':scope[1],**body.model_dump()})).scalar_one()
    await audit(scope[0],scope[1],'agent.shared_skill_published','agent_skill',str(row),body.model_dump())
    return {'id':row}
