"""Explicit management questions in a request, with actor-scoped external source consent."""
import json
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .v3_auth import scoped_connection
from .v3_audit import audit
from .v3_mutations import management_access, visible_ticket
from .v3_session import _session
from .v3_coordination import Scope as RuntimeScope, TENANT, FINAL, RUNTIME_BACKEND, POLICY_VERSION, team_authority, specialist_member
from .v3_room_agents import managed_room
from .v3_room_files import for_agent

router = APIRouter(tags=['Request session external sources'])
runtime_router = APIRouter(prefix='/internal/coordination/v1', tags=['Explicit request question runtime'])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection, scope='function')]


async def management_session(scope, ticket_id, *, lock=False):
    ticket = await visible_ticket(scope, ticket_id, lock=lock)
    if not await management_access((scope[0], scope[1], False), ticket):
        raise HTTPException(403, 'Management grant for this request required')
    session = await _session(scope[0], ticket_id, lock=lock)
    if not session:
        raise HTTPException(404, 'Request has no coordination session')
    await managed_room((scope[0], scope[1]), session['channel_id'], lock=False)
    return session


async def question_authority(db, team_id, message_id, *, actor=None, agent_id=None, lock=False):
    team = await team_authority(db, team_id)
    if team['status'] in FINAL:
        raise HTTPException(409, 'Request session has finished')
    question = (await db.execute(text('''select mm.*,m.channel_id,m.body from message_mentions mm
        join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        where mm.message_id=:message and m.body->>'sessionId'=:team
          and m.body->>'kind'='session_question' and m.body->>'sourceConsentScope'='actor_session' '''
        + (' for update of mm' if lock else '')), {'message': message_id, 'team': str(team_id)})).mappings().first()
    if not question or (actor and question['requested_by'] != actor) or (agent_id and question['agent_id'] != agent_id):
        raise HTTPException(403, 'Question is not bound to this actor and request')
    actor = question['requested_by']
    session = await management_session((db, actor, False), team['ticket_id'])
    if session['id'] != team['id'] or question['channel_id'] != team['channel_id']:
        raise HTTPException(409, 'Question belongs to an obsolete request session')
    if not (await db.execute(text(f'''select 1 from users u join tenant_memberships tm on tm.user_id=u.id
        where u.id=:actor and u.status='active' and tm.status='active' and tm.tenant_id={TENANT}'''), {'actor': actor})).first():
        raise HTTPException(403, 'Requesting manager is inactive')
    member_id = (await db.execute(text('''select id from team_members where team_id=:team and agent_id=:agent
        and member_kind='specialist' and status='active' '''), {'team': team_id, 'agent': question['agent_id']})).scalar_one_or_none()
    if not member_id:
        raise HTTPException(403, 'Agent no longer participates in this request')
    member = await specialist_member(db, team, member_id)
    return team, dict(question), member


async def session_source_enabled(db, actor, team_id, connection_id):
    return (await db.execute(text('''select enabled from vh_session_sources
        where team_id=:team and actor_user_id=:actor and server_id=:server for share'''),
        {'team': team_id, 'actor': actor, 'server': connection_id})).scalar_one_or_none() is True


async def session_call_context(db, actor, channel_id, agent_id, run_id):
    bound = (await db.execute(text('''select cast(m.body->>'sessionId' as uuid) as team_id,mm.message_id
        from message_mentions mm join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        join agent_runs r on r.id=mm.resolved_run_id and r.tenant_id=mm.tenant_id
        where r.id=:run and r.actor_user_id=:actor and r.agent_id=:agent and r.channel_id=:channel
          and mm.requested_by=:actor and mm.agent_id=:agent and m.body->>'sourceConsentScope'='actor_session'
          and r.team_member_id is not null'''), {'run': run_id, 'actor': actor, 'agent': agent_id, 'channel': channel_id})).mappings().first()
    if not bound:
        raise HTTPException(403, 'External call requires an explicit management question in this request')
    await question_authority(db, bound['team_id'], bound['message_id'], actor=actor, agent_id=agent_id)
    return dict(bound)


async def session_confirmation_authority(db, actor, room_id, agent_id, connection_id, session_id, request_message_id):
    team, question, member = await question_authority(db, session_id, request_message_id, actor=actor, agent_id=agent_id)
    if team['channel_id'] != room_id or not question['resolved_run_id']:
        raise HTTPException(403, 'Confirmation is not bound to this request question')
    run = (await db.execute(text('''select id from agent_runs where id=:run and actor_user_id=:actor
        and channel_id=:channel and agent_id=:agent and team_member_id=:member and version_id=:version'''),
        {'run': question['resolved_run_id'], 'actor': actor, 'channel': room_id, 'agent': agent_id,
         'member': member['id'], 'version': member['version_id']})).first()
    if not run or not await session_source_enabled(db, actor, session_id, connection_id):
        raise HTTPException(403, 'Nguồn ngoài đã tắt cho câu hỏi của bạn trong yêu cầu này')
    return {'id': member['version_id'], 'config': member['config']}


@router.get('/tickets/{ticket_id}/session/sources')
async def sources(ticket_id: UUID, scope: Scope):
    session = await management_session(scope, ticket_id)
    rows = await scope[0].execute(text('''select s.id,s.title,s.status,s.suspension_reason,
        coalesce(x.enabled,false) as enabled,coalesce((select jsonb_agg(jsonb_build_object('name',t.name,
        'description',t.description,'effect',t.effect)) from mcp_tools t where t.server_id=s.id),'[]'::jsonb) as tools
        from mcp_servers s left join vh_session_sources x on x.server_id=s.id and x.team_id=:team and x.actor_user_id=:actor
        where s.provenance='custom' and (s.workspace_id is null or s.workspace_id=:workspace) order by s.created_at'''),
        {'team': session['id'], 'actor': scope[1], 'workspace': session['workspace_id']})
    return {'items': [dict(r) for r in rows.mappings()]}


class Selection(BaseModel):
    server_id: str = Field(min_length=1, max_length=160)
    enabled: bool


@router.put('/tickets/{ticket_id}/session/sources')
async def select_source(ticket_id: UUID, body: Selection, scope: Scope):
    session = await management_session(scope, ticket_id, lock=True)
    if session['status'] in FINAL:
        raise HTTPException(409, 'Request session has finished')
    server = (await scope[0].execute(text('''select id,status from mcp_servers where id=:server
        and provenance='custom' and (workspace_id is null or workspace_id=:workspace)'''),
        {'server': body.server_id, 'workspace': session['workspace_id']})).mappings().first()
    if not server:
        raise HTTPException(404, 'Nguồn ngoài không thuộc đơn vị này')
    if body.enabled and server['status'] != 'active':
        raise HTTPException(409, 'Kết nối đang tạm ngưng hoặc chờ duyệt')
    await scope[0].execute(text('''insert into vh_session_sources(team_id,actor_user_id,server_id,enabled)
        values(:team,:actor,:server,:enabled) on conflict (tenant_id,team_id,actor_user_id,server_id)
        do update set enabled=excluded.enabled,updated_at=now()'''),
        {'team': session['id'], 'actor': scope[1], 'server': body.server_id, 'enabled': body.enabled})
    await audit(scope[0], scope[1], 'session.source_selected', 'agent_team', str(session['id']),
                {'connection': body.server_id, 'enabled': body.enabled})
    return {'server_id': body.server_id, 'enabled': body.enabled}


@router.get('/tickets/{ticket_id}/session/external-calls')
async def calls(ticket_id: UUID, scope: Scope):
    session = await management_session(scope, ticket_id)
    rows = await scope[0].execute(text('''select c.id,c.agent_id,c.tool_name,c.arguments,
        case when c.status='pending' and c.expires_at<=now() then 'expired' else c.status end as status,
        c.result,c.created_at,c.expires_at,s.title as connection_title,t.description
        from vh_external_call_confirmations c join mcp_servers s on s.id=c.connection_id
        left join mcp_tools t on t.server_id=c.connection_id and t.name=c.tool_name
        where c.session_id=:team and c.actor_user_id=:actor order by c.created_at desc limit 50'''),
        {'team': session['id'], 'actor': scope[1]})
    return {'items': [dict(r) for r in rows.mappings()]}


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'cancel']


@router.post('/tickets/{ticket_id}/session/external-calls/{confirmation_id}/decision')
async def decide(ticket_id: UUID, confirmation_id: UUID, scope: Scope, body: Decision):
    session = await management_session(scope, ticket_id)
    if not (await scope[0].execute(text('''select 1 from vh_external_call_confirmations
        where id=:id and session_id=:team and actor_user_id=:actor'''),
        {'id': confirmation_id, 'team': session['id'], 'actor': scope[1]})).first():
        raise HTTPException(404, 'Không tìm thấy xác nhận của bạn trong yêu cầu này')
    from .v3_connections import execute_external_call
    return await execute_external_call(scope[0], scope[1], session['channel_id'], confirmation_id, body.decision)


@runtime_router.get('/session-mentions')
async def inbox(db: RuntimeScope):
    rows = await db.execute(text('''select mm.message_id,mm.agent_id,m.channel_id,mm.tenant_id,
        cast(m.body->>'sessionId' as uuid) as team_id from message_mentions mm
        join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
        where mm.status in ('queued','running') and m.body->>'kind'='session_question'
          and m.body->>'sourceConsentScope'='actor_session' order by mm.created_at limit 100'''))
    items = []
    for row in rows.mappings():
        try:
            await question_authority(db, row['team_id'], row['message_id'])
        except HTTPException as error:
            if error.status_code not in (403, 404, 409):
                raise
            await db.execute(text("update message_mentions set status='refused' where message_id=:message and status in ('queued','running')"), {'message': row['message_id']})
            await db.execute(text("update agent_runs set status='failed',finished_at=now(),updated_at=now() where id=(select resolved_run_id from message_mentions where message_id=:message) and status='running'"), {'message': row['message_id']})
            continue
        items.append(dict(row))
    return {'items': items}


@runtime_router.post('/teams/{team_id}/mentions/{message_id}/turn')
async def turn(team_id: UUID, message_id: UUID, db: RuntimeScope):
    team, question, member = await question_authority(db, team_id, message_id, lock=True)
    if question['status'] not in ('queued', 'running'):
        raise HTTPException(409, 'Question has finished')
    actor = question['requested_by']
    principal = (await db.execute(text(f'''insert into execution_principals(tenant_id,kind,user_id,status)
        values({TENANT},'user',:actor,'active') on conflict (tenant_id,user_id) where kind='user'
        do update set user_id=excluded.user_id returning id,status,authz_version'''), {'actor': actor})).mappings().one()
    if principal['status'] != 'active':
        raise HTTPException(403, 'Execution principal is inactive')
    backend = (await db.execute(text('select id from runtime_backends where code=:code and enabled'), {'code': RUNTIME_BACKEND})).scalar_one_or_none()
    if not backend:
        raise HTTPException(503, 'Runtime backend unavailable')
    await db.execute(text(f'''insert into runtime_identities(tenant_id,backend_id,principal_id,runtime_user_key,status)
        values({TENANT},:backend,:principal,:actor,'active') on conflict (backend_id,principal_id) do nothing'''),
        {'backend': backend, 'principal': principal['id'], 'actor': actor})
    key = f'session-question:{team_id}:{message_id}'
    binding = (await db.execute(text(f'''insert into runtime_session_bindings(tenant_id,identity_id,backend_id,
        customer_user_id,channel_id,agent_id,agent_version_id,audience_kind,started_by_user_id,
        runtime_session_key,checkpoint_namespace,status,policy_version)
        select {TENANT},i.id,:backend,:actor,:channel,:agent,:version,'personal',:actor,:key,'session-questions','active',:policy
        from runtime_identities i where i.backend_id=:backend and i.principal_id=:principal
        on conflict (backend_id,runtime_session_key) do nothing returning id'''),
        {'backend': backend, 'actor': actor, 'channel': team['channel_id'], 'agent': member['agent_id'],
         'version': member['version_id'], 'key': key, 'policy': POLICY_VERSION, 'principal': principal['id']})).scalar_one_or_none()
    if binding is None:
        binding = (await db.execute(text("select id from runtime_session_bindings where backend_id=:backend and runtime_session_key=:key and status='active'"), {'backend': backend, 'key': key})).scalar_one_or_none()
        if binding is None:
            raise HTTPException(409, 'Question runtime binding is inactive')
    run = (await db.execute(text(f'''insert into agent_runs(tenant_id,channel_id,agent_id,version_id,actor_user_id,
        team_member_id,idempotency_key,status,started_at,trace_id,binding_id,authority_principal_id,policy_version,authority_version)
        values({TENANT},:channel,:agent,:version,:actor,:member,:key,'running',now(),:trace,:binding,:principal,:policy,:authz)
        on conflict (tenant_id,idempotency_key) do update set idempotency_key=excluded.idempotency_key returning id'''),
        {'channel': team['channel_id'], 'agent': member['agent_id'], 'version': member['version_id'], 'actor': actor,
         'member': member['id'], 'key': key, 'trace': str(uuid4()), 'binding': binding, 'principal': principal['id'],
         'policy': POLICY_VERSION, 'authz': principal['authz_version']})).scalar_one()
    await db.execute(text("update message_mentions set status='running',resolved_run_id=:run where message_id=:message and agent_id=:agent"),
                     {'run': run, 'message': message_id, 'agent': member['agent_id']})
    tools = []
    for grant in member['config'].get('mcp_tools', []):
        tool = (await db.execute(text('''select t.description,t.input_schema,t.effect,s.provenance from mcp_tools t
            join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id where t.server_id=:server and t.name=:name
            and (t.effect='read' or s.provenance='custom') and not t.destructive and s.status='active' '''),
            {'server': grant['server_id'], 'name': grant['name']})).mappings().first()
        if not tool:
            continue
        if tool['provenance'] == 'custom' and not await session_source_enabled(db, actor, team_id, grant['server_id']):
            continue
        tools.append({'name': grant['name'].replace('.', '__'), 'description': tool['description'], 'parameters': tool['input_schema']})
    from .v3_agent_builder import instructions_with_skills
    from .v3_models import resolve_model
    instructions = await instructions_with_skills(db, member['config'], team['workspace_id'])
    instructions += '\nThao tác ghi vào nguồn ngoài luôn dừng chờ Ban quản lý cho phép từng lần. Khi công cụ trả AWAITING_CONFIRMATION, nói rõ đang chờ xác nhận; chưa khẳng định thao tác đã được thực hiện.'
    history = (await db.execute(text("""select body->>'text' as text,sender_kind from messages
        where channel_id=:channel and body->>'sessionId'=:team and seq<(select seq from messages where id=:message)
        order by seq desc limit 20"""), {'channel': team['channel_id'], 'team': str(team_id), 'message': message_id})).mappings().all()
    attached, images = await for_agent(db, team['channel_id'], message_id, pictures=True)
    ticket = (await db.execute(text('select t.title,t.description,u.code as unit_code,t.priority from tickets t left join units u on u.id=t.unit_id and u.tenant_id=t.tenant_id where t.id=:id'), {'id': team['ticket_id']})).mappings().one()
    return {'run_id': str(run), 'instructions': instructions, 'tools': tools,
            'model_config': await resolve_model(db, 'specialist', member['config'].get('model_id')),
            'instruction': '\n\n'.join(p for p in (question['body']['text'].split(': ', 1)[-1], attached) if p),
            'ticket': dict(ticket), 'messages': [dict(m) for m in reversed(history)], 'images': images}


class Outcome(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(pattern='^(done|failed)$')
    run_id: UUID
    content: str = Field(default='', max_length=20000)


@runtime_router.post('/teams/{team_id}/mentions/{message_id}/outcome')
async def outcome(team_id: UUID, message_id: UUID, body: Outcome, db: RuntimeScope):
    # A revoked question cannot publish a reply, but its exact actor-bound run may still be closed.
    if body.status == 'failed':
        bound = (await db.execute(text('''select r.id from agent_runs r join message_mentions mm on mm.resolved_run_id=r.id
            join messages m on m.id=mm.message_id and m.tenant_id=mm.tenant_id
            join team_members tm on tm.id=r.team_member_id and tm.tenant_id=r.tenant_id
            where r.id=:run and mm.message_id=:message and tm.team_id=:team
              and m.body->>'sessionId'=:team_text and m.body->>'sourceConsentScope'='actor_session'
              and r.actor_user_id=mm.requested_by and r.agent_id=mm.agent_id for update of r'''),
            {'run': body.run_id, 'message': message_id, 'team': team_id, 'team_text': str(team_id)})).first()
        if not bound:
            raise HTTPException(409, 'Run does not belong to this question')
        await db.execute(text("update message_mentions set status='failed' where message_id=:message and status in ('queued','running')"), {'message': message_id})
        await db.execute(text("update agent_runs set status='failed',finished_at=now(),updated_at=now() where id=:run and status='running'"), {'run': body.run_id})
        await db.execute(text("update runtime_session_bindings set status='closed' where id=(select binding_id from agent_runs where id=:run) and checkpoint_namespace='session-questions'"), {'run': body.run_id})
        return {'ok': True}
    team, question, member = await question_authority(db, team_id, message_id, lock=True)
    if question['resolved_run_id'] != body.run_id:
        raise HTTPException(409, 'Run does not belong to this question')
    if question['status'] == body.status:
        stored = (await db.execute(text('select body from messages where reply_to_id=:message and run_id=:run'), {'message': message_id, 'run': body.run_id})).scalar_one_or_none()
        if body.status == 'done' and (not stored or stored.get('text') != f"{team['ticket_code']}: {body.content}"):
            raise HTTPException(409, 'Outcome already recorded with different content')
        return {'ok': True, 'replayed': True}
    if question['status'] != 'running':
        raise HTTPException(409, 'Question has finished')
    if body.status == 'done' and body.content.strip():
        seq = (await db.execute(text('''update channels set next_message_seq=next_message_seq+1,
            last_message=:text,last_message_at=now() where id=:channel returning next_message_seq-1'''),
            {'channel': team['channel_id'], 'text': body.content[:200]})).scalar_one()
        await db.execute(text(f'''insert into messages(tenant_id,channel_id,seq,sender_kind,sender_agent_id,visibility,body,reply_to_id,run_id)
            values({TENANT},:channel,:seq,'agent',:agent,'room',cast(:body as jsonb),:reply,:run)'''),
            {'channel': team['channel_id'], 'seq': seq, 'agent': member['agent_id'], 'reply': message_id, 'run': body.run_id,
             'body': json.dumps({'text': f"{team['ticket_code']}: {body.content}", 'sessionId': str(team_id),
                                 'kind': 'specialist_reply', 'source': 'session-question'}, ensure_ascii=False)})
    await db.execute(text('update message_mentions set status=:status where message_id=:message'), {'status': body.status, 'message': message_id})
    await db.execute(text('update agent_runs set status=:status,finished_at=now(),updated_at=now() where id=:run'),
                     {'run': body.run_id, 'status': 'succeeded' if body.status == 'done' else 'failed'})
    await db.execute(text("update runtime_session_bindings set status='closed' where id=(select binding_id from agent_runs where id=:run) and checkpoint_namespace='session-questions'"), {'run': body.run_id})
    await audit(db, question['requested_by'], 'session.agent_answered', 'agent_run', str(body.run_id), {'teamId': str(team_id), 'messageId': str(message_id)})
    return {'ok': True}
