"""Schedules of management's agents: at a set time, an instruction is put to an agent in the room.

The schedule service (server/src/room-routines) keeps the schedule with the platform's own routine
store (its floor of fifteen minutes, its cap per person, one firing per due minute). This API decides
who may schedule what, and it is where a firing happens: the instruction is posted in the room as the
schedule's owner, mentioning the agent, and the Supervisor answers that mention like any other. What
becomes of the mention closes the run.
"""
import hmac
import os
import re
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .v3_audit import audit
from .v3_room_agents import Scope, managed_room
from .v3_rooms import RoomMessage, post_message

router = APIRouter(tags=['Schedules of agents'])
internal = APIRouter(prefix='/internal/routines/v1', tags=['Schedules of agents: firing'])
TIMEZONE = 'Asia/Ho_Chi_Minh'
# The platform's cap (routines/store.ts), checked here first so the refusal is in the room's language.
MAX_ENABLED = 20
CRON = re.compile(r'^(\d{1,2}) (\d{1,2}) \* \* (\*|\d(?:,\d)*)$')
PUBLISHED = '''exists(select 1 from channel_agents ca join agents a on a.id=ca.agent_id and a.tenant_id=ca.tenant_id
    join agent_versions v on v.agent_id=a.id and v.tenant_id=a.tenant_id
    join agent_releases rel on rel.version_id=v.id and rel.tenant_id=v.tenant_id and rel.status='published' and rel.revoked_at is null
    where ca.channel_id=:room and ca.agent_id=:agent and a.status='active'
      and v.version_no=(select max(v2.version_no) from agent_versions v2 where v2.agent_id=a.id))'''
# The platform's sweep closes a run nobody finished with this sentence (routines/sweep.ts).
ABANDONED = 'the server never finished this run'


async def service(path: str, payload: dict) -> dict:
    """Ask the schedule service. Its refusals (a room the owner is not in, the cap) are sentences and
    are passed on; anything else is an outage."""
    url, token = os.getenv('VINHOMES_API_ROUTINES_URL', '').rstrip('/'), os.getenv('VINHOMES_API_ROUTINES_TOKEN', '')
    if not url or len(token) < 32:
        raise HTTPException(503, 'Lịch chạy chưa được bật trên hệ thống này.')
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            reply = await client.post(url + path, headers={'Authorization': 'Bearer ' + token}, json=payload)
            body = reply.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Dịch vụ lịch chạy không trả lời.') from None
    if reply.status_code in (404, 422) and isinstance(body.get('error'), str):
        raise HTTPException(reply.status_code, body['error'])
    if reply.status_code not in (200, 201):
        raise HTTPException(503, 'Dịch vụ lịch chạy không trả lời.')
    return body


class Timing(BaseModel):
    """What a schedule asks and when."""
    model_config = ConfigDict(extra='forbid')
    instruction: str = Field(min_length=1, max_length=2000)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    # 0 is Sunday, 6 is Saturday. Empty: every day.
    days: list[int] = Field(default_factory=list, max_length=7)

    @field_validator('instruction')
    @classmethod
    def said(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('instruction must not be blank')
        return value.strip()

    @field_validator('days')
    @classmethod
    def weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value) or len(set(value)) != len(value):
            raise ValueError('days are 0 (Sunday) to 6 (Saturday), each at most once')
        return sorted(value)

    @property
    def cron(self) -> str:
        return f"{self.minute} {self.hour} * * {','.join(str(day) for day in self.days) or '*'}"


class Schedule(Timing):
    agent_id: str = Field(min_length=1, max_length=160)


class Enabled(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


def schedule_of(cron: str) -> dict[str, Any] | None:
    """The time and days of a schedule this API made; None for any other expression."""
    match = CRON.match(cron)
    if not match:
        return None
    return {'minute': int(match[1]), 'hour': int(match[2]),
            'days': [] if match[3] == '*' else [int(day) for day in match[3].split(',')]}


async def within_cap(db, owner: str) -> None:
    count = (await db.execute(text('select count(*) from routines where owner_user_id=:owner and enabled'), {'owner': owner})).scalar_one()
    if count >= MAX_ENABLED:
        raise HTTPException(409, f'Người đặt lịch đã có {MAX_ENABLED} lịch đang bật. Tắt bớt một lịch trước.')


async def routine_in(db, room_id: str, routine_id: str) -> dict[str, Any]:
    row = (await db.execute(text('select id,owner_user_id,agent_id,enabled from routines where id=:id and channel_id=:room'),
                            {'id': routine_id, 'room': room_id})).mappings().first()
    if not row:
        raise HTTPException(404, 'Schedule not found')
    return dict(row)


@router.get('/rooms/{room_id}/routines', summary='Schedules of the agents in a room I manage')
async def schedules(room_id: str, scope: Scope) -> dict[str, object]:
    await managed_room(scope, room_id, lock=False)
    rows = (await scope[0].execute(text('''
        select r.id,r.agent_id,a.name as agent_name,r.owner_user_id,u.name as owner_name,r.instruction,r.cron,
               r.enabled,r.next_run_at,run.status::text as last_status,run.started_at as last_run_at,run.error as last_error
        from routines r join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id
        join users u on u.id=r.owner_user_id
        left join lateral (select status,started_at,error from routine_runs rr
            where rr.routine_id=r.id and rr.tenant_id=r.tenant_id order by rr.started_at desc,rr.id desc limit 1) run on true
        where r.channel_id=:room order by r.created_at desc,r.id'''), {'room': room_id})).mappings().all()
    items = []
    for row in rows:
        item = {**row, 'schedule': schedule_of(row['cron'])}
        if (item['last_error'] or '').startswith(ABANDONED):
            item['last_error'] = 'Agent không trả lời trong 10 phút.'
        items.append(item)
    return {'items': items, 'timezone': TIMEZONE}


@router.post('/rooms/{room_id}/routines', status_code=201, summary='Schedule an instruction for a published agent of the room')
async def schedule(room_id: str, body: Schedule, scope: Scope) -> dict[str, object]:
    db, actor = scope
    # Not locked: the schedule service writes a row that refers to this room while this request is open.
    await managed_room(scope, room_id, lock=False)
    if not (await db.execute(text('select 1 from channel_memberships where channel_id=:room and user_id=:actor'),
                             {'room': room_id, 'actor': actor})).first():
        raise HTTPException(403, 'Chỉ thành viên của phòng đặt được lịch.')
    if not (await db.execute(text('select ' + PUBLISHED), {'room': room_id, 'agent': body.agent_id})).scalar_one():
        raise HTTPException(422, 'Agent chưa có bản phát hành trong phòng này.')
    await within_cap(db, actor)
    made = await service('', {'ownerUserId': actor, 'agentId': body.agent_id, 'channelId': room_id,
                               'instruction': body.instruction, 'cron': body.cron, 'timezone': TIMEZONE})
    await audit(db, actor, 'routine.created', 'routine', made['id'], {'room': room_id, 'agent': body.agent_id, 'cron': body.cron})
    return {'id': made['id'], 'next_run_at': made['nextRunAt']}


@router.put('/rooms/{room_id}/routines/{routine_id}', summary='Change what a schedule of the room asks and when')
async def change(room_id: str, routine_id: str, body: Timing, scope: Scope) -> dict[str, object]:
    db, actor = scope
    await managed_room(scope, room_id, lock=False)
    routine = await routine_in(db, room_id, routine_id)
    # Any manager of the room may change it; the schedule stays its owner's and keeps its agent.
    changed = await service(f'/{routine_id}/update', {'ownerUserId': routine['owner_user_id'], 'instruction': body.instruction, 'cron': body.cron})
    await audit(db, actor, 'routine.changed', 'routine', routine_id, {'room': room_id, 'cron': body.cron})
    return {'id': routine_id, 'next_run_at': changed['nextRunAt']}


@router.put('/rooms/{room_id}/routines/{routine_id}/enabled', summary='Switch a schedule of the room on or off')
async def switch(room_id: str, routine_id: str, body: Enabled, scope: Scope) -> dict[str, object]:
    db, actor = scope
    await managed_room(scope, room_id, lock=False)
    routine = await routine_in(db, room_id, routine_id)
    if body.enabled and not routine['enabled']:
        await within_cap(db, routine['owner_user_id'])
    # Any manager of the room may switch it; the schedule stays its owner's.
    await service(f'/{routine_id}/enabled', {'ownerUserId': routine['owner_user_id'], 'enabled': body.enabled})
    await audit(db, actor, 'routine.switched', 'routine', routine_id, {'room': room_id, 'enabled': body.enabled})
    return {'id': routine_id, 'enabled': body.enabled}


@router.delete('/rooms/{room_id}/routines/{routine_id}', summary='Remove a schedule of the room')
async def remove(room_id: str, routine_id: str, scope: Scope) -> dict[str, object]:
    db, actor = scope
    await managed_room(scope, room_id, lock=False)
    routine = await routine_in(db, room_id, routine_id)
    await service(f'/{routine_id}/remove', {'ownerUserId': routine['owner_user_id']})
    await audit(db, actor, 'routine.removed', 'routine', routine_id, {'room': room_id, 'agent': routine['agent_id']})
    return {'removed': True}


async def run_closed(db, body: dict[str, Any], status: str, error: str | None = None) -> None:
    """A scheduled mention carries its run; what became of the mention is what became of the run.
    A run closes once: one the sweep already gave up on stays as it was closed."""
    if body.get('routineRunId'):
        await db.execute(text('''update routine_runs set status=cast(:status as routine_run_status),finished_at=now(),error=:error
            where id=:run and status is null'''), {'run': body['routineRunId'], 'status': status, 'error': error})


async def schedule_service_scope(request: Request):
    """The schedule service's sweep, with the token the two services share; no acting user."""
    token, offered = os.getenv('VINHOMES_API_ROUTINES_TOKEN', ''), request.headers.get('authorization', '')
    if len(token) < 32:
        raise HTTPException(503, 'The schedule service is not configured')
    if not offered.startswith('Bearer ') or not hmac.compare_digest(offered[7:].encode(), token.encode()):
        raise HTTPException(401, 'Invalid schedule service credential')
    settings, engine = request.app.state.settings, request.app.state.engine
    if engine is None:
        raise HTTPException(503, 'Database unavailable')
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id','',true)"),
                             {'tenant': str(settings.tenant_id)})
            yield db
    except IntegrityError as exc:
        raise HTTPException(409, 'V3 constraint conflict; reload the resource and retry') from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, 'V3 database is unavailable or missing required tables') from exc


@internal.post('/runs/{run_id}/fire', summary='Carry out one due run: post its instruction in the room')
async def fire(run_id: str, request: Request, db: Annotated[Any, Depends(schedule_service_scope, scope='function')]) -> dict[str, object]:
    run = (await db.execute(text('''select rr.status,r.owner_user_id,r.agent_id,r.channel_id,r.instruction
        from routine_runs rr join routines r on r.id=rr.routine_id and r.tenant_id=rr.tenant_id
        where rr.id=:run for update of rr'''), {'run': run_id})).mappings().first()
    if not run:
        raise HTTPException(404, 'Run not found')
    if run['status'] is not None:
        return {'posted': False}
    scope, refusal = (db, run['owner_user_id']), None
    # The owner's authority is read again now, not remembered from the day the schedule was made.
    active = (await db.execute(text('''select 1 from users u join tenant_memberships m on m.user_id=u.id
        where u.id=:actor and u.status='active' and m.status='active'
          and m.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid'''), {'actor': run['owner_user_id']})).first()
    try:
        await managed_room(scope, run['channel_id'])
    except HTTPException:
        active = None
    if not active:
        refusal = 'Người đặt lịch không còn quyền quản lý phòng này.'
    elif not (await db.execute(text('select ' + PUBLISHED), {'room': run['channel_id'], 'agent': run['agent_id']})).scalar_one():
        refusal = 'Agent không còn bản phát hành đang dùng trong phòng này.'
    if refusal:
        await run_closed(db, {'routineRunId': run_id}, 'failed', refusal)
        return {'posted': False, 'reason': refusal}
    message = await post_message(run['channel_id'], RoomMessage(text=run['instruction'], client_message_id='routine:' + run_id,
        mention_agent_id=run['agent_id']), request, scope, routine_run_id=run_id)
    return {'posted': True, 'message_id': str(message['id'])}
