"""Durable free-room mentions. A personal runtime binding carries the requesting user.

This is a conversation, not a fabricated ticket or a work assignment. Every turn and
publication rechecks membership, management authority and the pinned release.
"""
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from .v3_coordination import Scope, TENANT, RUNTIME_BACKEND, POLICY_VERSION
from .v3_room_agents import managed_room
from .v3_audit import audit

router = APIRouter(prefix='/internal/coordination/v1', tags=['Room conversation runtime'])


async def mention_authority(db, message: UUID, agent: str, *, lock=False):
    row = (await db.execute(text('''select mm.*,m.channel_id,m.body,c.workspace_id
        from message_mentions mm join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        join channels c on c.id=m.channel_id and c.tenant_id=m.tenant_id and c.deleted_at is null
        where mm.message_id=:message and mm.agent_id=:agent''' + (' for update of mm' if lock else '')),
        {'message': message, 'agent': agent})).mappings().first()
    if not row:
        raise HTTPException(404, 'Mention not found')
    await managed_room((db, row['requested_by']), row['channel_id'], lock=lock)
    active = (await db.execute(text('''select 1 from users u join tenant_memberships m on m.user_id=u.id
        where u.id=:actor and u.status='active' and m.status='active'
        and m.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid'''), {'actor': row['requested_by']})).first()
    if not active:
        raise HTTPException(403, 'Requesting user is inactive')
    return dict(row)


@router.get('/room-mentions')
async def inbox(db: Scope):
    rows = await db.execute(text('''select mm.message_id,mm.agent_id,m.channel_id,mm.tenant_id
        from message_mentions mm join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        where mm.status in ('queued','running') and coalesce(m.body->>'sessionId','')=''
        order by mm.created_at limit 100'''))
    return {'items': [dict(r) for r in rows.mappings()]}


@router.post('/room-mentions/{message_id}/{agent_id}/turn')
async def turn(message_id: UUID, agent_id: str, db: Scope):
    mention = await mention_authority(db, message_id, agent_id, lock=True)
    if mention['status'] not in ('queued', 'running'):
        raise HTTPException(409, 'Mention has finished')
    version = (await db.execute(text('''select v.*,a.name from agents a
        join channel_agents ca on ca.agent_id=a.id and ca.tenant_id=a.tenant_id and ca.channel_id=:channel
        join agent_versions v on v.agent_id=a.id and v.tenant_id=a.tenant_id
        join agent_releases rel on rel.version_id=v.id and rel.tenant_id=v.tenant_id
          and rel.status='published' and rel.revoked_at is null
        where a.id=:agent and a.status='active' and a.workspace_id=:workspace
          and ((cast(:run as uuid) is not null and v.id=(select version_id from agent_runs where id=:run))
            or (cast(:run as uuid) is null and v.version_no=(select max(last.version_no) from agent_versions last where last.agent_id=a.id)))'''),
        {'channel': mention['channel_id'], 'agent': agent_id, 'workspace': mention['workspace_id'], 'run': mention['resolved_run_id']})).mappings().first()
    if not version:
        # Commit a definite refusal; no canned agent answer is produced.
        await db.execute(text("update message_mentions set status='refused' where message_id=:message and agent_id=:agent"), {'message': message_id, 'agent': agent_id})
        return {'refused': True, 'reason': 'No active published version in this room'}
    principal = (await db.execute(text(f'''insert into execution_principals(tenant_id,kind,user_id,status)
        values({TENANT},'user',:actor,'active') on conflict (tenant_id,user_id) where kind='user'
        do update set user_id=excluded.user_id returning id,status,authz_version'''), {'actor': mention['requested_by']})).mappings().one()
    if principal['status'] != 'active':
        raise HTTPException(403, 'Execution principal is inactive')
    backend = (await db.execute(text('select id from runtime_backends where code=:code and enabled'), {'code': RUNTIME_BACKEND})).scalar_one_or_none()
    if not backend:
        raise HTTPException(503, 'Runtime backend unavailable')
    await db.execute(text(f'''insert into runtime_identities(tenant_id,backend_id,principal_id,runtime_user_key,status)
        values({TENANT},:backend,:principal,:actor,'active') on conflict (backend_id,principal_id) do nothing'''),
        {'backend': backend, 'principal': principal['id'], 'actor': mention['requested_by']})
    key = f'room-mention:{message_id}:{agent_id}'
    binding = (await db.execute(text(f'''insert into runtime_session_bindings(tenant_id,identity_id,backend_id,
        customer_user_id,channel_id,agent_id,agent_version_id,audience_kind,started_by_user_id,
        runtime_session_key,checkpoint_namespace,status,policy_version)
        select {TENANT},i.id,:backend,:actor,:channel,:agent,:version,'personal',:actor,:key,'room-mentions','active',:policy
        from runtime_identities i where i.backend_id=:backend and i.principal_id=:principal
        on conflict (backend_id,runtime_session_key) do nothing returning id'''),
        {'backend': backend, 'actor': mention['requested_by'], 'channel': mention['channel_id'], 'agent': agent_id,
         'version': version['id'], 'key': key, 'policy': POLICY_VERSION, 'principal': principal['id']})).scalar_one_or_none()
    if binding is None:
        binding = (await db.execute(text("select id from runtime_session_bindings where backend_id=:backend and runtime_session_key=:key and status='active'"), {'backend': backend, 'key': key})).scalar_one_or_none()
        if binding is None:
            raise HTTPException(409, 'Room runtime binding is inactive')
    run = (await db.execute(text(f'''insert into agent_runs(tenant_id,channel_id,agent_id,version_id,actor_user_id,
        idempotency_key,status,started_at,trace_id,binding_id,authority_principal_id,policy_version,authority_version)
        values({TENANT},:channel,:agent,:version,:actor,:key,'running',now(),:trace,:binding,:principal,:policy,:authz)
        on conflict (tenant_id,idempotency_key) do update set idempotency_key=excluded.idempotency_key returning id'''),
        {'channel': mention['channel_id'], 'agent': agent_id, 'version': version['id'], 'actor': mention['requested_by'],
         'key': key, 'trace': str(uuid4()), 'binding': binding, 'principal': principal['id'], 'policy': POLICY_VERSION, 'authz': principal['authz_version']})).scalar_one()
    await db.execute(text("update message_mentions set status='running',resolved_run_id=:run where message_id=:message and agent_id=:agent"),
        {'run': run, 'message': message_id, 'agent': agent_id})
    tools = []
    for grant in version['config'].get('mcp_tools', []):
        tool = (await db.execute(text("select description,input_schema from mcp_tools where server_id=:server and name=:name and effect='read' and not destructive"),
            {'server': grant['server_id'], 'name': grant['name']})).mappings().first()
        if not tool:
            raise HTTPException(409, 'Published tool no longer available')
        tools.append({'name': grant['name'].replace('.', '__'), 'description': tool['description'], 'parameters': tool['input_schema']})
    history = (await db.execute(text("select body->>'text' as text,sender_kind from messages where channel_id=:channel and visibility='room' and seq<(select seq from messages where id=:message) order by seq desc limit 20"),
        {'channel': mention['channel_id'], 'message': message_id})).mappings().all()
    return {'run_id': str(run), 'instructions': version['instructions'], 'tools': tools,
        'instruction': mention['body']['text'], 'messages': [dict(r) for r in reversed(history)]}


class Outcome(BaseModel):
    run_id: UUID
    status: str = Field(pattern='^(done|failed)$')
    content: str = Field(default='', max_length=20000)


@router.post('/room-mentions/{message_id}/{agent_id}/outcome')
async def outcome(message_id: UUID, agent_id: str, body: Outcome, db: Scope):
    mention = await mention_authority(db, message_id, agent_id, lock=True)
    if mention['resolved_run_id'] != body.run_id:
        raise HTTPException(409, 'Run does not belong to this mention')
    prior = (await db.execute(text("select body from messages where run_id=:run and reply_to_id=:message"), {'run': body.run_id, 'message': message_id})).mappings().first()
    if prior:
        if prior['body'] != {'text': body.content, 'source': 'room-agent'} or body.status != 'done':
            raise HTTPException(409, 'Outcome already recorded with different content')
        return {'status': 'done', 'replayed': True}
    if mention['status'] not in ('running', body.status):
        raise HTTPException(409, 'Mention has finished')
    if body.status == 'done':
        release = (await db.execute(text("select 1 from agent_runs r join agent_releases rel on rel.version_id=r.version_id and rel.tenant_id=r.tenant_id where r.id=:run and r.status='running' and rel.status='published' and rel.revoked_at is null"), {'run': body.run_id})).first()
        if not release or not body.content.strip():
            raise HTTPException(409, 'Release revoked or answer empty')
        seq = (await db.execute(text('update channels set next_message_seq=next_message_seq+1,last_message=:preview,last_message_at=now() where id=:room returning next_message_seq-1'), {'room': mention['channel_id'], 'preview': body.content[:200]})).scalar_one()
        await db.execute(text(f'''insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id,run_id)
            values({TENANT},:room,:seq,'agent',:agent,'room',cast(:body as jsonb),:reply,:run)'''),
            {'room': mention['channel_id'], 'seq': seq, 'agent': agent_id, 'body': json.dumps({'text': body.content, 'source': 'room-agent'}), 'reply': message_id, 'run': body.run_id})
    await db.execute(text("update message_mentions set status=:status where message_id=:message and agent_id=:agent"), {'message': message_id, 'agent': agent_id, 'status': body.status})
    await db.execute(text("update agent_runs set status=:status,finished_at=now() where id=:run"), {'run': body.run_id, 'status': 'succeeded' if body.status == 'done' else 'failed'})
    await db.execute(text("update runtime_session_bindings set status='closed' where id=(select binding_id from agent_runs where id=:run) and audience_kind='personal'"), {'run': body.run_id})
    await audit(db, mention['requested_by'], 'room.agent_answered', 'agent_run', str(body.run_id), {'status': body.status})
    return {'status': body.status, 'replayed': False}
