"""The evaluation sandbox's side: what the evaluation worker may do in the sandbox stack, and nothing else.

These routes answer only in a database whose own tenant holds the sandbox marker (vh_agent_eval_sandbox),
with VINHOMES_API_EVAL_SANDBOX_TOKEN set. A production database has no marker, so in production every
route here answers 404 even with a valid token. The sandbox is a separate database of the same
PostgreSQL cluster (scripts/provision_eval_sandbox.py): its roles cannot connect to the production database,
which the attestation route reports and the worker checks before every case.

The worker installs copies of the agents under test, speaks as a synthetic fixture resident through the
same resident route functions production uses (Reception, Supervisor and the specialists then run as
they do in production), reads what was recorded and closes the conversation's work afterwards.
"""
import hashlib
import hmac
import json
import os
import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .v3_security import digest

router = APIRouter(prefix='/internal/agent-eval/sandbox/v1', tags=['Agent evaluation sandbox'])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
# A failed specialist run whose answer could not be read as the agent output format.
OUTPUT_ERRORS = ('invalid_model_output', 'invalid_agent_output', 'ValidationError', 'model_returned_no_answer')
# Pause reasons that are a fault of the run, not a decision to hand the request to people.
FAULT_PAUSES = re.compile(r'model_unavailable|model_timeout|invalid|error|failed|turn|step|budget|limit', re.I)


async def is_sandbox(db) -> bool:
    return (await db.execute(text(f'select 1 from vh_agent_eval_sandbox where tenant_id={TENANT}'))).first() is not None


async def sandbox_scope(request: Request):
    token, offered = os.getenv('VINHOMES_API_EVAL_SANDBOX_TOKEN', ''), request.headers.get('authorization', '')
    if len(token) < 32:
        raise HTTPException(404, 'Not found')
    if not offered.startswith('Bearer ') or not hmac.compare_digest(offered[7:].encode(), token.encode()):
        raise HTTPException(401, 'Invalid sandbox credential')
    engine, settings = request.app.state.engine, request.app.state.settings
    if engine is None or not settings.tenant_id:
        raise HTTPException(503, 'Database unavailable')
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id','',true)"), {'tenant': str(settings.tenant_id)})
            if not await is_sandbox(db):
                raise HTTPException(404, 'Not found')
            yield db
    except IntegrityError as exc:
        raise HTTPException(409, 'Sandbox constraint conflict') from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, 'Database unavailable') from exc


Sandbox = Annotated[Any, Depends(sandbox_scope, scope='function')]


async def as_fixture(db, user_id: str) -> None:
    await db.execute(text("select set_config('app.user_id',:user,true)"), {'user': user_id})


async def fixture(db, fixture_id: str) -> dict:
    row = (await db.execute(text('select * from vh_agent_eval_fixtures where id=:id'), {'id': fixture_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Unknown fixture profile')
    return dict(row)


async def conversation(db, channel_id: str) -> dict:
    """A reception chat opened by a fixture resident; never anyone else's conversation."""
    row = (await db.execute(text("""select c.id,f.id as fixture_id,f.user_id,f.unit_id,f.building_id from channels c
        join vh_agent_eval_fixtures f on f.user_id=c.created_by and f.tenant_id=c.tenant_id
        where c.id=:id and c.kind='reception'"""), {'id': channel_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Conversation of a fixture resident required')
    return dict(row)


async def management_room(db) -> dict:
    room = (await db.execute(text("""select c.id,c.workspace_id from channels c join agents a on a.workspace_id=c.workspace_id and a.tenant_id=c.tenant_id
        join channel_agents ca on ca.channel_id=c.id and ca.agent_id=a.id and ca.tenant_id=c.tenant_id
        where c.kind='management' and a.purpose='supervisor' and a.status='active' order by c.is_dispatch_default desc nulls last,c.id limit 1"""))).mappings().first()
    if room is None:
        raise HTTPException(409, 'The sandbox has no management room with a Supervisor')
    return dict(room)


@router.get('/catalog')
async def catalog(db: Sandbox):
    marker = (await db.execute(text('select * from vh_agent_eval_sandbox'))).mappings().one()
    fixtures = (await db.execute(text("""select f.id as fixture_profile_id,f.description,u.code as unit_code,b.code as building_code,b.name as building_name,
        f.user_id as resident_id,f.unit_id::text,f.building_id::text
        from vh_agent_eval_fixtures f join units u on u.id=f.unit_id and u.tenant_id=f.tenant_id
        join buildings b on b.id=f.building_id and b.tenant_id=f.tenant_id order by f.id"""))).mappings().all()
    documents = (await db.execute(text("""select d.id as document_id,d.active_version_id as version,d.title,d.code from knowledge_documents d
        where d.status='published' and d.active_version_id is not null order by d.title limit 500"""))).mappings().all()
    tools = (await db.execute(text("""select t.server_id,t.name,t.description,t.input_schema,t.effect from mcp_tools t
        join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id where s.status='active' and not t.destructive
        and s.provenance<>'custom' order by t.server_id,t.name"""))).mappings().all()
    return {'tenant_id': str(marker['tenant_id']), 'fixture_version': marker['fixture_version'],
            'fixtures': [dict(f) for f in fixtures],
            'documents': [{**dict(d), 'document_id': str(d['document_id']), 'version': str(d['version'])} for d in documents],
            'tools': [dict(t) for t in tools]}


@router.get('/attestation')
async def attestation(db: Sandbox):
    """Facts the worker checks before each case: whose database this is and that it cannot reach the source."""
    facts = (await db.execute(text(f"""select current_database() as database,current_user as role,s.source_database,
        r.rolsuper,r.rolbypassrls,{TENANT} as tenant_id,
        exists(select 1 from pg_database where datname=s.source_database) as source_exists,
        (select has_database_privilege(current_user,s.source_database,'CONNECT') from pg_database where datname=s.source_database) as source_connect,
        (select count(*) from tenants) as tenants,
        array(select datname from pg_database where not datistemplate and has_database_privilege(current_user,datname,'CONNECT') order by datname) as connectable
        from vh_agent_eval_sandbox s join pg_roles r on r.rolname=current_user"""))).mappings().one()
    return {**dict(facts), 'tenant_id': str(facts['tenant_id']), 'connectable': list(facts['connectable'])}


class AgentCopy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    configuration: dict
    model: dict | None = None  # {provider, model_name}: the sandbox's own registered model of that name


class Install(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: UUID
    agents: list[AgentCopy] = Field(min_length=1, max_length=20)


def copy_id(source_id: str) -> str:
    return 'eval-' + hashlib.sha256(source_id.encode()).hexdigest()[:20]


@router.post('/install')
async def install(body: Install, db: Sandbox):
    """The run's agents become the only published specialists of the sandbox room, each a new version."""
    room = await management_room(db)
    admin = (await db.execute(text('select user_id from platform_admins order by user_id limit 1'))).scalar_one()
    mapping, versions = {}, {}
    for copy in body.agents:
        configuration = {**copy.configuration, 'knowledge_namespace_ids': [], 'revision_of': None}
        for grant in configuration.get('mcp_tools', []):
            offered = (await db.execute(text("""select 1 from mcp_tools t join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id
                where t.server_id=:server and t.name=:name and s.status='active' and s.provenance<>'custom' and not t.destructive"""),
                {'server': grant['server_id'], 'name': grant['name']})).first()
            if offered is None:
                raise HTTPException(409, f"environment_unsupported: {grant['server_id']}/{grant['name']}")
        configuration.pop('model_id', None)
        if copy.model:
            model_id = (await db.execute(text("select id from admin_model_registry where provider=:provider and name=:name and kind='chat' "
                                              "and check_status='ok' and workspace_id is null limit 1"),
                                         {'provider': copy.model.get('provider'), 'name': copy.model.get('model_name')})).scalar_one_or_none()
            if model_id is None:
                raise HTTPException(409, f"environment_unsupported: model {copy.model.get('provider')}/{copy.model.get('model_name')}")
            configuration['model_id'] = str(model_id)
        agent_id = copy_id(copy.source_id)
        await db.execute(text(f"""insert into agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
            values(:id,{TENANT},:workspace,:name,'built_in',cast(:configuration as jsonb),'specialist','active')
            on conflict(id) do update set name=excluded.name,configuration=excluded.configuration,status='active',updated_at=now()"""),
            {'id': agent_id, 'workspace': room['workspace_id'], 'name': copy.name, 'configuration': json.dumps(configuration)})
        await db.execute(text(f"""insert into channel_agents(tenant_id,channel_id,agent_id) select {TENANT},:room,:agent
            where not exists(select 1 from channel_agents where channel_id=:room and agent_id=:agent)"""), {'room': room['id'], 'agent': agent_id})
        number = (await db.execute(text('select coalesce(max(version_no),0)+1 from agent_versions where agent_id=:id'), {'id': agent_id})).scalar_one()
        version_id = (await db.execute(text(f"""insert into agent_versions(tenant_id,agent_id,version_no,runtime,framework_version,instructions,config,config_hash,created_by)
            values({TENANT},:agent,:number,'agentscope',:framework,:instructions,cast(:config as jsonb),:hash,:actor) returning id"""),
            {'agent': agent_id, 'number': number, 'framework': configuration.get('framework_version', 'eval-copy'),
             'instructions': configuration.get('instructions', ''), 'config': json.dumps(configuration), 'hash': digest(configuration),
             'actor': admin})).scalar_one()
        await db.execute(text("update agent_releases set status='revoked',revoked_at=now(),updated_at=now() where agent_id=:id and status='published' and revoked_at is null"),
                         {'id': agent_id})
        await db.execute(text(f"""insert into agent_releases(tenant_id,agent_id,version_id,status,published_at) values({TENANT},:agent,:version,'published',now())"""),
                         {'agent': agent_id, 'version': version_id})
        # A Supervisor session only runs a version with an approved review of that same configuration.
        await db.execute(text(f"""insert into vh_agent_reviews(tenant_id,agent_id,submitted_by,config_hash,evaluation,status,decided_by,decision_note,decided_at)
            select {TENANT},:agent,:actor,:hash,cast(:evidence as jsonb),'approved',:actor,'Bản sao cho lần đánh giá trong sandbox',now()
            where not exists(select 1 from vh_agent_reviews where agent_id=:agent and config_hash=:hash and status='approved')"""),
            {'agent': agent_id, 'actor': admin, 'hash': digest(configuration), 'evidence': json.dumps({'evaluator': 'sandbox-install', 'run_id': str(body.run_id)})})
        mapping[copy.source_id], versions[copy.source_id] = agent_id, str(version_id)
    # Nothing else may answer in this room: a specialist left from another run would change the routing.
    await db.execute(text("""update agent_releases r set status='revoked',revoked_at=now(),updated_at=now() from agents a
        where a.id=r.agent_id and a.tenant_id=r.tenant_id and a.purpose='specialist' and r.status='published' and r.revoked_at is null
          and a.workspace_id=:workspace and not (a.id = any(:keep))"""), {'workspace': room['workspace_id'], 'keep': list(mapping.values())})
    await db.execute(text("update agents set status='draft',updated_at=now() where purpose='specialist' and workspace_id=:workspace and not (id = any(:keep))"),
                     {'workspace': room['workspace_id'], 'keep': list(mapping.values())})
    return {'agents': mapping, 'versions': versions, 'room_id': room['id']}


class Opening(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fixture_profile_id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)


@router.post('/conversations', status_code=201)
async def open_conversation(body: Opening, db: Sandbox):
    from .v3_resident import CreateChat, create_chat
    profile = await fixture(db, body.fixture_profile_id)
    await as_fixture(db, profile['user_id'])
    chat = await create_chat(CreateChat(title=body.title), (db, profile['user_id']))
    return {'channel_id': chat['id'], 'resident_id': profile['user_id']}


class Said(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=2000)
    client_message_id: str = Field(min_length=1, max_length=120)


@router.post('/conversations/{channel_id}/messages', status_code=201)
async def say(channel_id: str, body: Said, request: Request, background: BackgroundTasks, db: Sandbox):
    """The resident's words, through the production route: Reception is dispatched after this commits."""
    from .v3_resident import SendMessage, send_message
    chat = await conversation(db, channel_id)
    await as_fixture(db, chat['user_id'])
    return await send_message(channel_id, SendMessage(text=body.text, client_message_id=body.client_message_id),
                              request, (db, chat['user_id']), background)


@router.post('/conversations/{channel_id}/answers', status_code=201)
async def answer(channel_id: str, body: Said, db: Sandbox):
    """The resident's answer to the Supervisor's open question, through the production route."""
    from .v3_resident_interactions import Response, respond
    chat = await conversation(db, channel_id)
    await as_fixture(db, chat['user_id'])
    pending = (await db.execute(text("""select t.id,t.version from vh_reception_supervisor_pending p join tickets t on t.id=p.ticket_id and t.tenant_id=p.tenant_id
        where t.channel_id=:channel and p.pending_kind='information' and p.ticket_generation=t.reopen_count order by p.created_at desc limit 1"""),
        {'channel': channel_id})).mappings().first()
    if pending is None:
        raise HTTPException(409, 'No open Supervisor question in this conversation')
    request_id = UUID(hashlib.sha256(body.client_message_id.encode()).hexdigest()[:32])
    return await respond(pending['id'], Response(decision='information', note=body.text, ticket_version=pending['version'],
                                                 request_id=request_id), (db, chat['user_id']))


@router.get('/conversations/{channel_id}/trace')
async def read_trace(channel_id: str, db: Sandbox):
    chat = await conversation(db, channel_id)
    return await build_trace(db, chat)


@router.post('/conversations/{channel_id}/close')
async def close(channel_id: str, db: Sandbox):
    """Stops the sandbox's work on this conversation, so the next case starts on a quiet stack."""
    await conversation(db, channel_id)
    tickets = (await db.execute(text("update tickets set status='cancelled',updated_at=now() where channel_id=:channel and status not in ('closed','cancelled') returning id"),
                                {'channel': channel_id})).scalars().all()
    teams = (await db.execute(text("""update agent_teams set status='cancelled',finished_at=now(),updated_at=now()
        where status not in ('completed','failed','cancelled') and (ticket_id = any(:tickets) or request_message_id in
          (select id from messages where channel_id=:channel)) returning id"""), {'tickets': list(tickets), 'channel': channel_id})).scalars().all()
    await db.execute(text('delete from vh_reception_supervisor_pending where ticket_id = any(:tickets)'), {'tickets': list(tickets)})
    return {'tickets': [str(t) for t in tickets], 'teams': [str(t) for t in teams]}


def clip(value: str | None, limit: int = 20000) -> str:
    return (value or '')[:limit]


def message_text(body: dict) -> str:
    return body.get('text') if isinstance(body.get('text'), str) else json.dumps(body, ensure_ascii=False)[:2000]


async def build_trace(db, chat: dict) -> dict:
    """What happened in one fixture conversation, as the evaluator's Trace plus where it stands."""
    channel = chat['id']
    tenant = str((await db.execute(text(f'select {TENANT}'))).scalar_one())
    reception = (await db.execute(text("select id from agents where purpose='reception' order by created_at limit 1"))).scalar_one_or_none()
    rows = (await db.execute(text("""select id,seq,sender_kind,sender_user_id,sender_agent_id,visibility,body,reply_to_id from messages
        where channel_id=:channel order by seq"""), {'channel': channel})).mappings().all()
    messages, last_resident, replied, asked = [], None, set(), set()
    for m in rows:
        body = m['body'] or {}
        if body.get('type') == 'ticket_draft':
            continue
        if m['sender_kind'] == 'user':
            # An answer to the Supervisor goes to the Supervisor: Reception writes no reply to it.
            role, last_resident = 'resident', (None if 'supervisorResponse' in body else m['id'])
        elif body.get('source') == 'supervisor':
            role = 'supervisor'
        elif m['sender_kind'] == 'agent':
            role = 'reception' if m['sender_agent_id'] == reception else 'agent'
        else:
            role = 'system'
        if m['reply_to_id']:
            replied.add(m['reply_to_id'])
        if body.get('clarification'):
            asked.add(f"m-{m['seq']}")
        messages.append({'id': f"m-{m['seq']}", 'role': role, 'agent_id': m['sender_agent_id'], 'text': clip(message_text(body)),
                         'visible_to_resident': m['visibility'] in ('customer', 'room')})
    tickets = (await db.execute(text('select id,status,unit_id,building_id from tickets where channel_id=:channel order by created_at'),
                                {'channel': channel})).mappings().all()
    ticket_ids = [t['id'] for t in tickets]
    teams = (await db.execute(text("""select id,status,channel_id,shared_state from agent_teams where ticket_id = any(:tickets)
        or request_message_id in (select id from messages where channel_id=:channel) order by created_at"""),
        {'tickets': ticket_ids, 'channel': channel})).mappings().all()
    team_ids = [t['id'] for t in teams]
    members = (await db.execute(text("""select id,team_id,agent_id,status,created_at from team_members where team_id = any(:teams)
        and member_kind='specialist' order by created_at"""), {'teams': team_ids})).mappings().all()
    runs = (await db.execute(text("""select r.id,r.agent_id,r.status,r.error_code,r.binding_id,r.authority_principal_id,r.team_member_id,
        r.input_tokens,r.output_tokens from agent_runs r where r.team_member_id = any(:members) or r.channel_id=:channel
        or r.idempotency_key = any(:supervisor_keys) order by r.created_at"""),
        {'members': [m['id'] for m in members], 'channel': channel,
         'supervisor_keys': [f'supervisor-session:{t}' for t in team_ids]})).mappings().all()
    specialists = {m['id'] for m in members}  # the Supervisor is a member of its own session too
    specialist_runs = [r for r in runs if r['team_member_id'] in specialists]
    participants, outputs, issues = [], [], []
    for r in specialist_runs:
        state = {'succeeded': 'completed', 'queued': 'running', 'running': 'running'}.get(r['status'], 'failed')
        participants.append({'id': f"p-{r['id']}", 'agent_id': r['agent_id'], 'run_id': str(r['id']), 'status': state})
        if r['status'] == 'succeeded':
            outputs.append({'id': f"o-{r['id']}", 'agent_id': r['agent_id'], 'valid': True})
        elif r['status'] == 'failed' and (r['error_code'] or '') in OUTPUT_ERRORS:
            outputs.append({'id': f"o-{r['id']}", 'agent_id': r['agent_id'], 'valid': False, 'error': r['error_code']})
        elif r['status'] in ('failed', 'interrupted'):
            issues.append({'id': f"i-{r['id']}", 'kind': 'error', 'code': r['error_code'] or r['status'], 'message': f"lượt của {r['agent_id']}"})
    for r in runs:
        if r['team_member_id'] not in specialists and r['status'] in ('failed', 'interrupted'):
            issues.append({'id': f"i-{r['id']}", 'kind': 'timeout' if 'timeout' in (r['error_code'] or '') else 'error',
                           'code': r['error_code'] or r['status'], 'message': f"lượt của {r['agent_id']}"})
    routing = [{'id': f"r-{t['id']}", 'selected_agent_ids': [m['agent_id'] for m in members if m['team_id'] == t['id']]} for t in teams]
    paused, halted = [], set()
    for t in teams:
        reason = ((t['shared_state'] or {}).get('runtime') or {}).get('pauseReason')
        if reason:
            halted.add(t['id'])  # the Supervisor stopped and waits for a person, whatever the row's status says
        if reason and FAULT_PAUSES.search(reason):
            kind = 'turn_limit' if re.search('turn|limit|budget', reason) else 'loop' if 'step' in reason else 'error'
            issues.append({'id': f"i-team-{t['id']}", 'kind': kind, 'code': reason[:200], 'message': 'phiên Supervisor dừng'})
        elif reason:
            paused.append(reason)
        if t['status'] == 'failed':
            issues.append({'id': f"i-failed-{t['id']}", 'kind': 'error', 'code': 'session_failed', 'message': 'phiên Supervisor thất bại'})
    for m in (await db.execute(text("""select seq,sender_agent_id,body from messages where channel_id = any(:rooms) and body->>'sessionId' = any(:teams)
            order by seq"""), {'rooms': list({t['channel_id'] for t in teams}), 'teams': [str(t) for t in team_ids]})).mappings().all():
        kind = (m['body'] or {}).get('kind', '')
        if kind == 'specialist_reply' or kind.startswith('supervisor_'):
            messages.append({'id': f"room-{m['seq']}", 'role': 'agent' if kind == 'specialist_reply' else 'supervisor',
                             'agent_id': m['sender_agent_id'], 'text': clip(message_text(m['body'])), 'visible_to_resident': False})
    for t in teams:
        if ((t['shared_state'] or {}).get('request') or {}).get('kind') == 'inquiry':
            # On record for the judge: Reception's "passed to management" is a fact, not a promise.
            messages.append({'id': f"handover-{t['id']}", 'role': 'system', 'agent_id': None, 'visible_to_resident': False,
                             'text': 'Câu hỏi của cư dân đã được ghi vào phòng Ban quản lý và đang chờ người trả lời (không mở ticket, không gọi agent).'})
    run_agent = {r['id']: r['agent_id'] for r in runs}
    tool_calls = [{'id': f"t-{c['id']}", 'agent_id': c['agent_id'], 'server_id': c['server_id'] or 'unknown', 'name': c['tool'],
                   'arguments': c['arguments'] or {}, 'status': c['status'], 'result': c['result']}
                  for c in (await db.execute(text('select * from vh_agent_eval_tool_traces where agent_run_id = any(:runs) order by created_at'),
                                             {'runs': [r['id'] for r in runs]})).mappings().all()]
    hits = (await db.execute(text("""select rr.agent_run_id,rr.id as retrieval_run_id,h.chunk_id,h.rank,c.text_content,v.document_id,v.id as version_id,d.title
        from retrieval_runs rr join retrieval_hits h on h.retrieval_run_id=rr.id and h.tenant_id=rr.tenant_id and h.included
        join knowledge_chunks c on c.id=h.chunk_id and c.tenant_id=h.tenant_id
        join document_versions v on v.id=c.version_id and v.tenant_id=c.tenant_id
        join knowledge_documents d on d.id=v.document_id and d.tenant_id=v.tenant_id
        where rr.agent_run_id = any(:runs) order by rr.created_at,h.rank"""), {'runs': [r['id'] for r in runs]})).mappings().all()
    retrievals = [{'id': f"k-{h['retrieval_run_id']}-{h['rank']}", 'agent_id': run_agent.get(h['agent_run_id'], 'unknown'),
                   'document_id': str(h['document_id']), 'version': str(h['version_id']), 'chunk_id': str(h['chunk_id']),
                   'rank': h['rank'], 'content': clip(h['text_content']), 'retrieval_run_id': str(h['retrieval_run_id'])} for h in hits]
    said = [m for m in messages if m['visible_to_resident'] and m['role'] != 'resident']
    # A document is cited when an answer the resident reads names it by title.
    citations, seen = [], set()
    for h in hits:
        title = (h['title'] or '').strip()
        if len(title) >= 6 and (h['document_id'], h['version_id']) not in seen and any(title.casefold() in m['text'].casefold() for m in said):
            seen.add((h['document_id'], h['version_id']))
            citations.append({'id': f"c-{len(citations) + 1}", 'agent_id': run_agent.get(h['agent_run_id']),
                              'document_id': str(h['document_id']), 'version': str(h['version_id'])})
    first_ticket = tickets[0] if tickets else None
    principal = next((r for r in specialist_runs), None) or next((r for r in runs if r['agent_id'] == reception), None)
    context = {'tenant_id': tenant, 'resident_id': chat['user_id'],
               'unit_id': str(first_ticket['unit_id']) if first_ticket and first_ticket['unit_id'] else str(chat['unit_id']),
               'building_id': str(first_ticket['building_id']) if first_ticket and first_ticket['building_id'] else str(chat['building_id']),
               'principal_id': str(principal['authority_principal_id']) if principal else None,
               'binding_id': str(principal['binding_id']) if principal else None}
    pending = (await db.execute(text('select pending_kind from vh_reception_supervisor_pending where ticket_id = any(:tickets)'),
                                {'tickets': ticket_ids})).scalars().all()
    plans = (await db.execute(text('select status from vh_ticket_plans where ticket_id = any(:tickets)'), {'tickets': ticket_ids})).scalars().all()
    awaiting_reception = last_resident is not None and last_resident not in replied
    # A ticket handed over but not yet taken by a Supervisor session is still work in progress, not a reply.
    unrouted = any(t['status'] not in ('resolved', 'closed', 'cancelled') for t in tickets) and not teams
    # A question Reception passed to management waits for a person: no Supervisor session works on it.
    inquiry = lambda t: ((t['shared_state'] or {}).get('request') or {}).get('kind') == 'inquiry'
    handed_over = any(inquiry(t) and t['status'] in ('queued', 'running', 'waiting') for t in teams)
    working = (any(t['status'] in ('queued', 'running') and not inquiry(t) and t['id'] not in halted for t in teams) or unrouted) and not pending
    last_reply = next((m for m in reversed(said)), None)
    if awaiting_reception:
        terminal = None
    elif any(t['status'] in ('resolved', 'closed') for t in tickets) or any(t['status'] == 'completed' for t in teams):
        terminal = 'resolved'
    elif 'plan_approval' in pending or 'management_pending' in plans:
        terminal = 'approval_pending'
    elif 'resident_pending' in plans:
        # The plan exists but its request to the resident is not written yet: a moment later it is.
        terminal = None
    elif 'information' in pending:
        terminal = 'information_requested'
    elif working:
        terminal = None
    elif teams:
        # Handed to people (a session waiting for management, or no specialist offered): a human decides next.
        terminal = 'approval_pending' if any(t['status'] == 'waiting' for t in teams) or paused or handed_over else None
    elif last_reply and (last_reply['id'] in asked or re.search(r'\?(\s|$)', last_reply['text'])):
        terminal = 'information_requested'
    else:
        terminal = 'reply_only' if last_reply else None
    stalled = any(t['status'] in ('failed', 'cancelled') for t in teams) and terminal is None
    trace = {'messages': messages, 'participants': participants, 'routing': routing, 'tool_calls': tool_calls,
             'retrievals': retrievals, 'citations': citations, 'outputs': outputs, 'issues': issues, 'context': context,
             'ticket_ids': [str(t) for t in ticket_ids], 'final_response': last_reply['text'] if last_reply else None,
             'terminal_state': terminal}
    return {'trace': trace,
            'progress': {'awaiting_reception': awaiting_reception, 'working': working, 'stalled': stalled,
                         'pending': list(pending), 'paused': paused, 'team_status': [t['status'] for t in teams],
                         'ticket_status': [t['status'] for t in tickets]},
            'usage': {'input_tokens': sum(r['input_tokens'] or 0 for r in runs), 'output_tokens': sum(r['output_tokens'] or 0 for r in runs)},
            'refs': {'tenant_id': tenant, 'channel_id': channel, 'ticket_ids': [str(t) for t in ticket_ids],
                     'team_ids': [str(t) for t in team_ids], 'agent_run_ids': [str(r['id']) for r in runs],
                     'retrieval_run_ids': sorted({str(h['retrieval_run_id']) for h in hits})}}


async def record_tool_trace(db, run: dict | None, agent_run_id, server_id: str | None, tool: str, arguments: dict, status: str, result) -> None:
    """The gateway's call, in full, only in the sandbox: production keeps tool and status in its audit and nothing more."""
    if not await is_sandbox(db):
        return
    if server_id is None:
        # A refused call names no grant; the catalogue still tells which server offers a tool of that name.
        offering = (await db.execute(text('select distinct server_id from mcp_tools where name=:tool'), {'tool': tool})).scalars().all()
        server_id = offering[0] if len(offering) == 1 else None
    await db.execute(text(f"""insert into vh_agent_eval_tool_traces(tenant_id,agent_run_id,agent_id,server_id,tool,arguments,status,result)
        values({TENANT},:run,:agent,:server,:tool,cast(:arguments as jsonb),:status,cast(:result as jsonb))"""),
        {'run': agent_run_id, 'agent': run['agent_id'] if run else 'refused-runtime-call', 'server': server_id, 'tool': tool,
         'arguments': json.dumps(arguments, default=str), 'status': status, 'result': json.dumps(result, default=str)})
