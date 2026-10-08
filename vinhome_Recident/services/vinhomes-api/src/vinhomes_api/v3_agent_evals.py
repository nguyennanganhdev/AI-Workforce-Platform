"""Agent evaluation V1: six approved cases (four must pass), run end to end in the evaluation sandbox, scored in three layers.

Management prepares a suite (generated or written by hand), approves it, starts a run and reads the report.
A worker (agent-coordination, `python -m agent_eval`) claims the run under a lease, drives the sandbox stack
and sends back each case's trace, nine code checks, judgement and metrics. The verdict is computed here
from what it sent, under the run's snapshot: a pass/fail from the worker or the browser is never taken.
A passing run does not publish anything; it becomes the evidence of a pending review that management
still publishes, and only once the configuration hash still matches.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ._vendor.agent_eval.contracts import (CHECK_KEYS, PASS_MINIMUM, SUITE_SIZE, EvalCase, RequiredMetric, SuiteScope, Trace, case_verdict,
                                           run_passed, validate_suite)
from .v3_agent_reviews import Member, can_author_unit, room_agent, room_catalogue
from .v3_audit import audit
from .v3_models import resolve_model
from .v3_security import digest

router = APIRouter(tags=['Agent evaluation'])
internal = APIRouter(prefix='/internal/agent-eval/v1', tags=['Agent evaluation worker'])
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
HASH = '^[a-f0-9]{64}$'
LEASE_SECONDS = 60
CHECKS_VERSION = 'checks-9-v1'
FINAL = ('passed', 'failed', 'error')
# The library metrics a run must pass, per deployment. Empty by default: the Ragas thresholds are not yet
# calibrated on Vietnamese answers, so they are recorded as advisory until a profile makes them required.
METRIC_PROFILES = {
    'none': (),
    'ragas-rag-v1': (RequiredMetric('faithfulness', 0.8), RequiredMetric('answer_relevancy', 0.7),
                     RequiredMetric('context_precision', 0.7)),
}


def canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def metric_profile() -> tuple[str, tuple[RequiredMetric, ...]]:
    name = os.getenv('VINHOMES_API_EVAL_METRIC_PROFILE', 'none').strip() or 'none'
    if name not in METRIC_PROFILES:
        raise HTTPException(503, 'Unknown evaluation metric profile')
    return name, METRIC_PROFILES[name]


async def environment(db, *, lock: bool = False) -> dict | None:
    return (await db.execute(text("select * from vh_agent_eval_environments where name='default' and status='ready'"
                                  + (' for update' if lock else '')))).mappings().first()


async def collaborators(room_id: str, agent_id: str, scope: Member, catalog: dict) -> tuple[list[dict], list[dict]]:
    """The specialists published beside the agent in its room: the only other agents a case may name.
    One the sandbox cannot reproduce (a tool no longer registered, an external connection, a tool the sandbox
    lacks) is left out and named with the reason, so the run's snapshot says who was not there."""
    catalogue = await room_catalogue(room_id, scope, lock=False)
    offered = {(t['server_id'], t['name']) for t in catalog.get('tools', [])}
    kept, excluded = [], []
    for a in catalogue['items']:
        if a['id'] == agent_id or not a['published'] or a['purpose'] != 'specialist' or not a.get('latest_version'):
            continue
        configuration, reason, tools = a['latest_version']['config'], None, []
        try:
            tools = await tool_descriptors(scope[0], configuration.get('mcp_tools', []))
        except HTTPException:
            reason = 'có công cụ không còn đăng ký'
        if reason is None and any(t['provenance'] == 'custom' for t in tools):
            reason = 'dùng kết nối ngoài (MCP) chưa có kết nối thử riêng'
        if reason is None and any((t['server_id'], t['name']) not in offered for t in tools):
            reason = 'sandbox chưa có công cụ của agent này'
        if reason:
            excluded.append({'agent_id': a['id'], 'name': a['name'], 'reason': reason})
        else:
            kept.append({'agent_id': a['id'], 'name': a['name'], 'version_id': a['latest_version']['id'],
                         'configuration': configuration, 'tools': tools})
    return kept, excluded


async def tool_descriptors(db, grants: list[dict]) -> list[dict]:
    found = []
    for grant in grants:
        row = (await db.execute(text('select t.server_id,t.name,t.description,t.input_schema,t.effect,s.provenance from mcp_tools t '
                                     'join mcp_servers s on s.id=t.server_id and s.tenant_id=t.tenant_id where t.server_id=:server and t.name=:name'),
                                {'server': grant['server_id'], 'name': grant['name']})).mappings().first()
        if row is None:
            raise HTTPException(409, f"Tool {grant['server_id']}/{grant['name']} is no longer registered")
        found.append(dict(row))
    return found


def scope_of(agent_id: str, agent_tools: list[dict], others: list[dict], catalog: dict) -> SuiteScope:
    tools = {(t['server_id'], t['name']) for t in agent_tools}
    tools |= {(t['server_id'], t['name']) for o in others for t in o['configuration'].get('mcp_tools', [])}
    return SuiteScope(agent_id, frozenset({agent_id, *(o['agent_id'] for o in others)}), frozenset(tools),
                      frozenset((d['document_id'], d.get('version')) for d in catalog.get('documents', [])),
                      frozenset(f['fixture_profile_id'] for f in catalog.get('fixtures', [])))


async def context_of(scope: Member, room_id: str, agent: dict) -> tuple[dict, SuiteScope, list[dict], list[dict], list[dict]]:
    """What the cases may use, and the generation context the model sees: never the instructions."""
    db = scope[0]
    env = await environment(db)
    if env is None:
        raise HTTPException(503, 'Môi trường đánh giá chưa sẵn sàng. Báo quản trị viên khởi động sandbox đánh giá.')
    configuration = agent['configuration']
    tools = await tool_descriptors(db, configuration.get('mcp_tools', []))
    catalog = env['catalog'] or {}
    others, excluded = await collaborators(room_id, agent['id'], scope, catalog)
    public = lambda t: {k: t[k] for k in ('server_id', 'name', 'description', 'input_schema')}
    context = {
        'agent': {'agent_id': agent['id'], 'name': agent['name'], 'description': configuration.get('description', ''),
                  'service_categories': configuration.get('service_categories', []), 'tools': [public(t) for t in tools]},
        'collaborators': [{'agent_id': o['agent_id'], 'name': o['name'], 'description': o['configuration'].get('description', ''),
                           'service_categories': o['configuration'].get('service_categories', []),
                           'tools': [{'server_id': t['server_id'], 'name': t['name']} for t in o['configuration'].get('mcp_tools', [])]}
                          for o in others],
        'sources': catalog.get('documents', []), 'fixtures': catalog.get('fixtures', []),
        'fixture_version': env['fixture_version'],
    }
    return context, scope_of(agent['id'], tools, others, catalog), tools, others, excluded


def stored_case(row) -> dict:
    return {'name': row['name'], 'kind': row['kind'], 'source': row['source'], 'input': row['input'],
            'expectations': row['expectations'], 'rubric': row['rubric'], 'metric_policy': row['metric_policy']}


async def suite_view(db, suite_id) -> dict:
    suite = (await db.execute(text('select * from vh_agent_eval_suites where id=:id'), {'id': suite_id})).mappings().first()
    if suite is None:
        raise HTTPException(404, 'Evaluation suite not found')
    cases = (await db.execute(text('select * from vh_agent_eval_cases where suite_id=:id order by ordinal'), {'id': suite_id})).mappings().all()
    return {**{k: v for k, v in suite.items() if k != 'generation_context'},
            'cases': [{'id': c['id'], 'ordinal': c['ordinal'], **stored_case(c)} for c in cases]}


async def own_suite(scope: Member, room_id: str, agent_id: str, suite_id: UUID, *, lock: bool = False) -> dict:
    suite = (await scope[0].execute(text('select * from vh_agent_eval_suites where id=:id and agent_id=:agent and room_id=:room'
                                         + (' for update' if lock else '')),
                                    {'id': suite_id, 'agent': agent_id, 'room': room_id})).mappings().first()
    if suite is None:
        raise HTTPException(404, 'Evaluation suite not found')
    return dict(suite)


def parsed(cases: list[dict]) -> list[EvalCase]:
    """Each case in the stored shape; a case that does not even parse cannot be kept as a draft."""
    out = []
    for number, raw in enumerate(cases, 1):
        try:
            out.append(EvalCase.model_validate(raw))
        except ValidationError as error:
            first = error.errors()[0]
            raise HTTPException(422, f'Ca {number}: {".".join(str(p) for p in first["loc"])} {first["msg"]}') from None
    if len(out) > SUITE_SIZE:
        raise HTTPException(422, f'Một bộ đánh giá có đúng {SUITE_SIZE} ca')
    return out


async def write_cases(db, suite_id, cases: list[EvalCase]) -> None:
    await db.execute(text('delete from vh_agent_eval_cases where suite_id=:id'), {'id': suite_id})
    for ordinal, case in enumerate(cases, 1):
        await db.execute(text(f"""insert into vh_agent_eval_cases(tenant_id,suite_id,ordinal,name,kind,source,input,expectations,rubric,metric_policy)
            values({TENANT},:suite,:ordinal,:name,:kind,:source,cast(:input as jsonb),cast(:expectations as jsonb),cast(:rubric as jsonb),cast(:policy as jsonb))"""),
            {'suite': suite_id, 'ordinal': ordinal, 'name': case.name, 'kind': case.kind, 'source': case.source,
             'input': case.input.model_dump_json(), 'expectations': case.expectations.model_dump_json(),
             'rubric': case.rubric.model_dump_json(), 'policy': json.dumps(case.metric_policy)})


def evaluator() -> tuple[str, str]:
    url, token = os.getenv('VINHOMES_API_EVALUATOR_URL', '').rstrip('/'), os.getenv('VINHOMES_API_EVAL_SERVICE_TOKEN', '')
    if not url or len(token) < 32:
        raise HTTPException(503, 'The evaluator service is not configured')
    return url, token


def public_profile(model: dict | None) -> dict | None:
    return {k: model[k] for k in ('model_id', 'provider', 'model_name')} if model else None


class SuiteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    configuration_hash: str = Field(pattern=HASH)
    mode: Literal['generate', 'manual']
    cases: list[dict] = Field(default_factory=list, max_length=SUITE_SIZE)


@router.post('/rooms/{room_id}/agents/{agent_id}/eval-suites', status_code=201)
async def create_suite(room_id: str, agent_id: str, body: SuiteCreate, scope: Member):
    # Generation waits up to two minutes on the model: no row lock is held across it.
    agent = await room_agent(scope, room_id, agent_id, lock=False)
    if not await can_author_unit(scope[0], scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can prepare its evaluation')
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Cấu hình đã đổi. Tải lại rồi chuẩn bị bộ đánh giá.')
    context, suite_scope, *_ = await context_of(scope, room_id, agent)
    generator = None
    if body.mode == 'generate':
        url, token = evaluator()
        model = await resolve_model(scope[0], 'evaluator')
        try:
            async with httpx.AsyncClient(timeout=150, follow_redirects=False) as client:
                reply = await client.post(url + '/internal/generate', headers={'Authorization': 'Bearer ' + token},
                                          json={'context': context, **({'model_config': model} if model else {})})
            if reply.status_code != 200:
                raise HTTPException(503, 'Model sinh ca chưa trả lời. Thử lại sau hoặc tự soạn bộ ca.')
            answer = reply.json()
            raw_cases, generator = answer['cases'], answer['generator_profile']
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, 'Dịch vụ đánh giá không phản hồi. Thử lại sau.') from None
        try:
            cases = parsed([{**c, 'source': 'generated'} for c in raw_cases[:SUITE_SIZE]])
        except HTTPException:
            raise HTTPException(502, 'Model sinh ca trả về ca không dùng được. Sinh lại hoặc tự soạn.') from None
    else:
        cases = parsed([{**c, 'source': c.get('source', 'manual')} for c in body.cases])
    _, problems = validate_suite([c.model_dump(mode='json') for c in cases], suite_scope)
    agent = await room_agent(scope, room_id, agent_id)
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Cấu hình đã đổi trong lúc chuẩn bị. Tải lại rồi thử lại.')
    revision = (await scope[0].execute(text('select coalesce(max(revision),0)+1 from vh_agent_eval_suites where agent_id=:id'),
                                       {'id': agent_id})).scalar_one()
    suite_id = (await scope[0].execute(text(f"""insert into vh_agent_eval_suites(tenant_id,room_id,agent_id,revision,configuration_hash,status,
            generation_context,generator_profile,problems,created_by)
        values({TENANT},:room,:agent,:revision,:hash,'draft',cast(:context as jsonb),cast(:generator as jsonb),cast(:problems as jsonb),:actor) returning id"""),
        {'room': room_id, 'agent': agent_id, 'revision': revision, 'hash': body.configuration_hash, 'context': json.dumps(context),
         'generator': json.dumps(generator), 'problems': json.dumps(problems), 'actor': scope[1]})).scalar_one()
    await write_cases(scope[0], suite_id, cases)
    await audit(scope[0], scope[1], 'agent.evaluation_suite_prepared', 'agent', agent_id, {'suiteId': str(suite_id), 'mode': body.mode, 'revision': revision})
    return await suite_view(scope[0], suite_id)


@router.get('/rooms/{room_id}/agents/{agent_id}/eval-suites')
async def list_suites(room_id: str, agent_id: str, scope: Member):
    await room_agent(scope, room_id, agent_id, lock=False)
    ids = (await scope[0].execute(text("select id from vh_agent_eval_suites where agent_id=:id and room_id=:room and status<>'archived' "
                                       'order by revision desc limit 10'), {'id': agent_id, 'room': room_id})).scalars().all()
    env = await environment(scope[0])
    return {'items': [await suite_view(scope[0], i) for i in ids],
            'environment': {'ready': env is not None, 'fixtures': (env['catalog'] or {}).get('fixtures', []) if env else [],
                            'documents': (env['catalog'] or {}).get('documents', []) if env else []}}


class SuiteEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    cases: list[dict] = Field(max_length=SUITE_SIZE)


@router.put('/rooms/{room_id}/agents/{agent_id}/eval-suites/{suite_id}')
async def edit_suite(room_id: str, agent_id: str, suite_id: UUID, body: SuiteEdit, scope: Member):
    agent = await room_agent(scope, room_id, agent_id)
    if not await can_author_unit(scope[0], scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can edit its evaluation')
    suite = await own_suite(scope, room_id, agent_id, suite_id, lock=True)
    if suite['status'] != 'draft':
        raise HTTPException(409, 'Bộ đã duyệt không sửa được. Tạo bản mới để thay đổi.')
    if suite['version'] != body.version:
        raise HTTPException(409, 'Bộ đánh giá vừa được sửa ở nơi khác. Tải lại.')
    cases = parsed([{**c, 'source': c.get('source', 'manual')} for c in body.cases])
    _, suite_scope, *_ = await context_of(scope, room_id, agent)
    _, problems = validate_suite([c.model_dump(mode='json') for c in cases], suite_scope)
    await write_cases(scope[0], suite_id, cases)
    await scope[0].execute(text('update vh_agent_eval_suites set problems=cast(:problems as jsonb),version=version+1,updated_at=now() where id=:id'),
                           {'id': suite_id, 'problems': json.dumps(problems)})
    return await suite_view(scope[0], suite_id)


class SuiteApproval(BaseModel):
    version: int = Field(ge=0)


@router.post('/rooms/{room_id}/agents/{agent_id}/eval-suites/{suite_id}/approve')
async def approve_suite(room_id: str, agent_id: str, suite_id: UUID, body: SuiteApproval, scope: Member):
    agent = await room_agent(scope, room_id, agent_id)
    if not await can_author_unit(scope[0], scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can approve its evaluation')
    suite = await own_suite(scope, room_id, agent_id, suite_id, lock=True)
    if suite['status'] != 'draft' or suite['version'] != body.version:
        raise HTTPException(409, 'Bộ đánh giá đã đổi hoặc đã được duyệt. Tải lại.')
    view = await suite_view(scope[0], suite_id)
    cases = [{k: v for k, v in c.items() if k not in ('id', 'ordinal')} for c in view['cases']]
    _, suite_scope, *_ = await context_of(scope, room_id, agent)
    _, problems = validate_suite(cases, suite_scope)
    if problems:
        await scope[0].execute(text('update vh_agent_eval_suites set problems=cast(:p as jsonb),updated_at=now() where id=:id'),
                               {'id': suite_id, 'p': json.dumps(problems)})
        raise HTTPException(422, 'Chưa duyệt được: ' + ' '.join(problems))
    suite_hash = canonical({'cases': cases, 'generation_context': suite['generation_context']})
    await scope[0].execute(text("update vh_agent_eval_suites set status='approved',suite_hash=:hash,problems='[]'::jsonb,approved_by=:actor,"
                                'approved_at=now(),version=version+1,updated_at=now() where id=:id'),
                           {'id': suite_id, 'hash': suite_hash, 'actor': scope[1]})
    await audit(scope[0], scope[1], 'agent.evaluation_suite_approved', 'agent', agent_id, {'suiteId': str(suite_id), 'suiteHash': suite_hash})
    return await suite_view(scope[0], suite_id)


class RunStart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    suite_id: UUID
    configuration_hash: str = Field(pattern=HASH)
    request_id: str = Field(min_length=1, max_length=120)


@router.post('/rooms/{room_id}/agents/{agent_id}/eval-runs', status_code=202)
async def start_run(room_id: str, agent_id: str, body: RunStart, scope: Member):
    db = scope[0]
    agent = await room_agent(scope, room_id, agent_id)
    if not await can_author_unit(db, scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can evaluate its agent')
    request_hash = canonical({'suite_id': str(body.suite_id), 'configuration_hash': body.configuration_hash})
    old = (await db.execute(text('select id,status,request_hash from vh_agent_eval_runs where agent_id=:agent and request_id=:request'),
                            {'agent': agent_id, 'request': body.request_id})).mappings().first()
    if old:
        if old['request_hash'] != request_hash:
            raise HTTPException(409, 'Mã yêu cầu này đã dùng cho một lần đánh giá khác')
        return {'runId': old['id'], 'status': old['status']}
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Cấu hình đã đổi. Lưu nháp rồi chạy đánh giá.')
    if agent['status'] != 'draft' and not agent['configuration'].get('revision_of'):
        raise HTTPException(409, 'Chỉ đánh giá bản nháp hoặc bản sửa của agent.')
    suite = await own_suite(scope, room_id, agent_id, body.suite_id)
    if suite['status'] != 'approved':
        raise HTTPException(409, f'Duyệt bộ {SUITE_SIZE} ca trước khi chạy đánh giá.')
    view = await suite_view(db, body.suite_id)
    cases = [{k: v for k, v in c.items() if k not in ('id', 'ordinal')} for c in view['cases']]
    _, suite_scope, tools, others, excluded = await context_of(scope, room_id, agent)
    _, problems = validate_suite(cases, suite_scope)
    if problems:
        raise HTTPException(409, 'Bộ đã duyệt không còn khớp phạm vi hiện tại của agent: ' + ' '.join(problems))
    env = await environment(db, lock=True)
    every_tool = tools + [t for o in others for t in o['tools']]
    if any(t['provenance'] == 'custom' for t in tools):
        # A custom MCP server has no connection of its own in the sandbox: dropping its tools would
        # make a pass mean nothing, and calling the real server would leave the sandbox.
        raise HTTPException(409, 'Agent dùng kết nối ngoài (MCP) chưa có kết nối thử riêng trong sandbox; chưa đánh giá được.')
    offered = {(t['server_id'], t['name']) for t in (env['catalog'] or {}).get('tools', [])}
    missing = sorted(f"{t['server_id']}/{t['name']}" for t in tools if (t['server_id'], t['name']) not in offered)
    if missing:
        raise HTTPException(409, 'Sandbox chưa có công cụ: ' + ', '.join(missing))
    judge_model = await resolve_model(db, 'evaluator')
    model = await resolve_model(db, 'specialist', agent['configuration'].get('model_id'), agent['workspace_id']) if agent['configuration'].get('model_id') else None
    profile_name, required = metric_profile()
    snapshot = {
        'target': {'agent_id': agent_id, 'name': agent['name'], 'configuration': agent['configuration'],
                   'configuration_hash': body.configuration_hash, 'model': public_profile(model)},
        'collaborators': [{'agent_id': o['agent_id'], 'name': o['name'], 'version_id': str(o['version_id']),
                           'configuration': o['configuration'], 'model': public_profile(await resolve_model(
                               db, 'specialist', o['configuration']['model_id'], agent['workspace_id']) if o['configuration'].get('model_id') else None)}
                          for o in others],
        'excluded_collaborators': excluded,
        'tools': [{k: t[k] for k in ('server_id', 'name', 'description', 'input_schema', 'effect')} for t in every_tool],
        'suite': {'id': str(body.suite_id), 'revision': suite['revision'], 'suite_hash': suite['suite_hash']},
        'environment': {'id': str(env['id']), 'execution_tenant_id': str(env['execution_tenant_id']),
                        'fixture_version': env['fixture_version']},
        'evaluator': {'checks_version': CHECKS_VERSION, 'pass_rule': {'cases': SUITE_SIZE, 'minimum': PASS_MINIMUM}, 'judge_model': public_profile(judge_model), 'judge_threshold': 4,
                      'metric_profile': profile_name, 'required_metrics': [m.__dict__ for m in required],
                      'timeouts': {'case_seconds': 300, 'judge_seconds': 120, 'run_seconds': 1800}},
    }
    try:
        async with db.begin_nested():
            run_id = (await db.execute(text(f"""insert into vh_agent_eval_runs(tenant_id,suite_id,environment_id,room_id,agent_id,request_id,request_hash,
                    configuration_hash,suite_hash,snapshot_hash,snapshot,status,requested_by)
                values({TENANT},:suite,:env,:room,:agent,:request,:request_hash,:hash,:suite_hash,:snapshot_hash,cast(:snapshot as jsonb),'queued',:actor) returning id"""),
                {'suite': body.suite_id, 'env': env['id'], 'room': room_id, 'agent': agent_id, 'request': body.request_id,
                 'request_hash': request_hash, 'hash': body.configuration_hash, 'suite_hash': suite['suite_hash'],
                 'snapshot_hash': canonical(snapshot), 'snapshot': json.dumps(snapshot, default=str), 'actor': scope[1]})).scalar_one()
    except IntegrityError:
        # The same request sent twice waits on the environment lock, then meets its own run.
        again = (await db.execute(text('select id,status,request_hash from vh_agent_eval_runs where agent_id=:agent and request_id=:request'),
                                  {'agent': agent_id, 'request': body.request_id})).mappings().first()
        if again and again['request_hash'] == request_hash:
            return {'runId': again['id'], 'status': again['status']}
        raise HTTPException(409, 'Sandbox đang chạy một lần đánh giá khác. Chờ lần đó xong rồi chạy lại.') from None
    await audit(db, scope[1], 'agent.evaluation_requested', 'agent', agent_id, {'runId': str(run_id), 'suiteId': str(body.suite_id)})
    return {'runId': run_id, 'status': 'queued'}


RUN_FIELDS = ('id', 'suite_id', 'status', 'passed', 'summary', 'error', 'configuration_hash', 'suite_hash', 'snapshot_hash',
              'requested_by', 'created_at', 'started_at', 'finished_at')


def run_summary(run) -> dict:
    snapshot = run.get('snapshot') or {}
    return {**{k: run[k] for k in RUN_FIELDS if k in run}, 'suite_revision': snapshot.get('suite', {}).get('revision'),
            'judge_model': snapshot.get('evaluator', {}).get('judge_model'),
            'metric_profile': snapshot.get('evaluator', {}).get('metric_profile'),
            'fixture_version': snapshot.get('environment', {}).get('fixture_version')}


async def own_run(db, room_id: str, agent_id: str, run_id: UUID, *, lock: bool = False) -> dict:
    run = (await db.execute(text('select * from vh_agent_eval_runs where id=:id and agent_id=:agent and room_id=:room'
                                 + (' for update' if lock else '')), {'id': run_id, 'agent': agent_id, 'room': room_id})).mappings().first()
    if run is None:
        raise HTTPException(404, 'Evaluation run not found')
    return dict(run)


@router.get('/rooms/{room_id}/agents/{agent_id}/eval-runs')
async def list_runs(room_id: str, agent_id: str, scope: Member, limit: int = Query(20, ge=1, le=50)):
    await room_agent(scope, room_id, agent_id, lock=False)
    await expire_leases(scope[0])
    rows = (await scope[0].execute(text('select * from vh_agent_eval_runs where agent_id=:agent and room_id=:room order by created_at desc limit :limit'),
                                   {'agent': agent_id, 'room': room_id, 'limit': limit})).mappings().all()
    return {'items': [run_summary(dict(r)) for r in rows]}


@router.get('/rooms/{room_id}/agents/{agent_id}/eval-runs/{run_id}')
async def read_run(room_id: str, agent_id: str, run_id: UUID, scope: Member):
    await room_agent(scope, room_id, agent_id, lock=False)
    await expire_leases(scope[0])
    run = await own_run(scope[0], room_id, agent_id, run_id)
    results = (await scope[0].execute(text("""select r.*,c.name,c.kind,c.input,c.expectations from vh_agent_eval_case_results r
        join vh_agent_eval_cases c on c.id=r.case_id and c.tenant_id=r.tenant_id where r.run_id=:run order by r.ordinal"""), {'run': run_id})).mappings().all()
    return {**run_summary(run), 'cases': [dict(r) for r in results]}


@router.get('/rooms/{room_id}/agents/{agent_id}/eval-runs/{run_id}/events')
async def read_events(room_id: str, agent_id: str, run_id: UUID, scope: Member, after: int = Query(0, ge=0)):
    await room_agent(scope, room_id, agent_id, lock=False)
    await own_run(scope[0], room_id, agent_id, run_id)
    rows = (await scope[0].execute(text('select seq,case_id,kind,actor_ref,payload,occurred_at from vh_agent_eval_events '
                                        'where run_id=:run and seq>:after order by seq limit 200'), {'run': run_id, 'after': after})).mappings().all()
    return {'items': [dict(r) for r in rows]}


@router.post('/rooms/{room_id}/agents/{agent_id}/eval-runs/{run_id}/cancel')
async def cancel_run(room_id: str, agent_id: str, run_id: UUID, scope: Member):
    agent = await room_agent(scope, room_id, agent_id)
    if not await can_author_unit(scope[0], scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can stop its evaluation')
    run = await own_run(scope[0], room_id, agent_id, run_id, lock=True)
    if run['status'] not in ('queued', 'running'):
        raise HTTPException(409, 'Lần đánh giá đã kết thúc')
    # A running worker sees this on its next heartbeat and stops after the current step.
    await scope[0].execute(text("update vh_agent_eval_runs set status='cancelled',finished_at=now(),updated_at=now(),lease_owner=null where id=:id"), {'id': run_id})
    await audit(scope[0], scope[1], 'agent.evaluation_cancelled', 'agent', agent_id, {'runId': str(run_id)})
    return {'runId': run_id, 'status': 'cancelled'}


async def expire_leases(db) -> None:
    """A run whose worker stopped renewing its lease is interrupted, never run again on its own: its
    model calls and sandbox effects may have happened, and a second try would mix two executions."""
    await db.execute(text("""update vh_agent_eval_runs set status='interrupted',finished_at=now(),updated_at=now(),
        error=cast(:error as jsonb) where status='running' and lease_expires_at<now()"""),
        {'error': json.dumps({'code': 'worker_lease_expired', 'message': 'Worker mất kết nối; lần chạy dừng ở trạng thái không xác định.'})})


# The worker's side. One service token, one tenant per API process, like the Coordination runtime.

async def worker_scope(request: Request):
    token, offered = os.getenv('VINHOMES_API_EVAL_SERVICE_TOKEN', ''), request.headers.get('authorization', '')
    if len(token) < 32:
        raise HTTPException(503, 'Evaluation worker is not configured')
    if not offered.startswith('Bearer ') or not hmac.compare_digest(offered[7:].encode(), token.encode()):
        raise HTTPException(401, 'Invalid evaluation worker credential')
    engine, settings = request.app.state.engine, request.app.state.settings
    if engine is None or not settings.tenant_id:
        raise HTTPException(503, 'Database unavailable')
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id','',true)"), {'tenant': str(settings.tenant_id)})
            yield db, str(settings.tenant_id)
    except IntegrityError as exc:
        raise HTTPException(409, 'Evaluation constraint conflict') from exc
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(503, 'Database unavailable') from exc


Worker = Annotated[Any, Depends(worker_scope, scope='function')]


class EnvironmentRegistration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    execution_tenant_id: UUID
    fixture_version: str = Field(min_length=1, max_length=120)
    runtime_profile: dict
    catalog: dict


@internal.put('/environment')
async def register_environment(body: EnvironmentRegistration, scope: Worker):
    db, tenant = scope
    if str(body.execution_tenant_id) == tenant:
        raise HTTPException(422, 'The sandbox must run as a tenant of its own')
    serialized = json.dumps(body.runtime_profile)
    if any(word in serialized.lower() for word in ('password', 'secret', 'api_key', 'token')):
        raise HTTPException(422, 'A runtime profile holds references, never secrets')
    row = (await db.execute(text(f"""insert into vh_agent_eval_environments(tenant_id,name,status,execution_tenant_id,fixture_version,runtime_profile,catalog,catalog_updated_at)
        values({TENANT},'default','ready',:tenant,:fixtures,cast(:profile as jsonb),cast(:catalog as jsonb),now())
        on conflict(tenant_id,name) do update set execution_tenant_id=excluded.execution_tenant_id,fixture_version=excluded.fixture_version,
          runtime_profile=excluded.runtime_profile,catalog=excluded.catalog,catalog_updated_at=now(),updated_at=now()
        returning id,status"""), {'tenant': body.execution_tenant_id, 'fixtures': body.fixture_version, 'profile': serialized,
                                  'catalog': json.dumps(body.catalog)})).mappings().one()
    return dict(row)


class Claim(BaseModel):
    worker: str = Field(min_length=1, max_length=120)


@internal.post('/runs/claim')
async def claim(body: Claim, scope: Worker):
    db, _ = scope
    await expire_leases(db)
    run = (await db.execute(text("select * from vh_agent_eval_runs where status='queued' order by created_at limit 1 for update skip locked"))).mappings().first()
    if run is None:
        return {'run': None}
    run = dict(run)
    judge_model = await resolve_model(db, 'evaluator')
    if public_profile(judge_model) != run['snapshot']['evaluator']['judge_model']:
        await finish_failed(db, run['id'], 'judge_model_changed', 'Model giám khảo đã đổi sau khi yêu cầu đánh giá; chạy lại.')
        return {'run': None}
    cases = (await db.execute(text('select * from vh_agent_eval_cases where suite_id=:suite order by ordinal'), {'suite': run['suite_id']})).mappings().all()
    await db.execute(text("""update vh_agent_eval_runs set status='running',lease_owner=:worker,lease_expires_at=now()+make_interval(secs=>:lease),
        heartbeat_at=now(),started_at=now(),updated_at=now() where id=:id"""), {'id': run['id'], 'worker': body.worker, 'lease': LEASE_SECONDS})
    for case in cases:
        await db.execute(text(f"""insert into vh_agent_eval_case_results(tenant_id,run_id,case_id,ordinal,status)
            values({TENANT},:run,:case,:ordinal,'pending') on conflict do nothing"""), {'run': run['id'], 'case': case['id'], 'ordinal': case['ordinal']})
    # Keys travel in this answer only, like the Coordination runtime's model_config; the stored snapshot has none.
    return {'run': {'id': run['id'], 'snapshot': run['snapshot'], 'lease_seconds': LEASE_SECONDS},
            'cases': [{'id': c['id'], 'ordinal': c['ordinal'], **stored_case(c)} for c in cases],
            'judge_model': judge_model}


async def leased(db, run_id: UUID, worker: str) -> dict:
    run = (await db.execute(text('select * from vh_agent_eval_runs where id=:id for update'), {'id': run_id})).mappings().first()
    if run is None:
        raise HTTPException(404, 'Evaluation run not found')
    if run['status'] == 'cancelled':
        raise HTTPException(409, 'cancelled')
    if run['status'] != 'running' or run['lease_owner'] != worker:
        raise HTTPException(409, 'This worker does not hold the run')
    return dict(run)


@internal.post('/runs/{run_id}/heartbeat')
async def heartbeat(run_id: UUID, body: Claim, scope: Worker):
    db, _ = scope
    await leased(db, run_id, body.worker)
    await db.execute(text('update vh_agent_eval_runs set lease_expires_at=now()+make_interval(secs=>:lease),heartbeat_at=now(),updated_at=now() where id=:id'),
                     {'id': run_id, 'lease': LEASE_SECONDS})
    return {'status': 'running'}


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: UUID | None = None
    kind: Literal['lifecycle', 'message', 'routing', 'tool', 'retrieval', 'state', 'error']
    actor_ref: dict | None = None
    payload: dict


class Events(BaseModel):
    worker: str = Field(min_length=1, max_length=120)
    events: list[Event] = Field(min_length=1, max_length=200)


@internal.post('/runs/{run_id}/events')
async def append_events(run_id: UUID, body: Events, scope: Worker):
    db, _ = scope
    await leased(db, run_id, body.worker)
    seq = (await db.execute(text('select coalesce(max(seq),0) from vh_agent_eval_events where run_id=:run'), {'run': run_id})).scalar_one()
    for event in body.events:
        seq += 1
        await db.execute(text(f"""insert into vh_agent_eval_events(tenant_id,run_id,case_id,seq,kind,actor_ref,payload)
            values({TENANT},:run,:case,:seq,:kind,cast(:actor as jsonb),cast(:payload as jsonb))"""),
            {'run': run_id, 'case': event.case_id, 'seq': seq, 'kind': event.kind, 'actor': json.dumps(event.actor_ref),
             'payload': json.dumps(event.payload)})
    return {'lastSeq': seq}


class CaseSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    worker: str = Field(min_length=1, max_length=120)
    status: Literal['running', 'done']
    execution_refs: dict = Field(default_factory=dict)
    trace: dict | None = None
    checks: dict | None = None
    judge: dict | None = None
    metrics: list[dict] = Field(default_factory=list)
    environment: dict | None = None
    usage: dict = Field(default_factory=dict)
    error: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@internal.put('/runs/{run_id}/cases/{case_id}')
async def record_case(run_id: UUID, case_id: UUID, body: CaseSubmission, scope: Worker):
    db, _ = scope
    run = await leased(db, run_id, body.worker)
    row = (await db.execute(text("""select r.*,c.name,c.kind,c.source,c.input,c.expectations,c.rubric,c.metric_policy from vh_agent_eval_case_results r
        join vh_agent_eval_cases c on c.id=r.case_id and c.tenant_id=r.tenant_id where r.run_id=:run and r.case_id=:case for update of r"""),
        {'run': run_id, 'case': case_id})).mappings().first()
    if row is None:
        raise HTTPException(404, 'Case is not part of this run')
    if row['status'] in FINAL:
        raise HTTPException(409, 'Case result is already recorded')
    if body.status == 'running':
        await db.execute(text("update vh_agent_eval_case_results set status='running',started_at=coalesce(started_at,now()),updated_at=now() where id=:id"), {'id': row['id']})
        return {'status': 'running'}
    case = EvalCase.model_validate(stored_case(row))
    error = body.error
    trace = None
    if body.trace is not None:
        try:
            trace = Trace.model_validate(body.trace)
        except ValidationError:
            error = error or {'code': 'invalid_trace', 'message': 'Trace sai cấu trúc'}
    elif not error:
        error = {'code': 'missing_trace', 'message': 'Không thu được trace'}
    # Evidence the checks or the judge cite must exist in the trace they were made from.
    refs = (trace.refs() if trace else set()) | {f'check:{k}' for k in CHECK_KEYS}
    cited = {ref for r in (body.checks or {}).values() if isinstance(r, dict) for ref in r.get('evidence_refs', [])}
    cited |= {ref for a in ((body.judge or {}).get('criteria') or {}).values() if isinstance(a, dict) for ref in a.get('evidence_refs', [])}
    if trace and cited - refs:
        error = error or {'code': 'unknown_evidence', 'message': 'Kết quả trích bằng chứng không có trong trace'}
    required = tuple(RequiredMetric(**m) for m in run['snapshot']['evaluator']['required_metrics'])
    status, layers = case_verdict(case, checks=body.checks, judge=body.judge, metrics=body.metrics,
                                  environment=body.environment, error=error, required_metrics=required)
    latency = int((body.finished_at - body.started_at).total_seconds() * 1000) if body.started_at and body.finished_at else None
    await db.execute(text("""update vh_agent_eval_case_results set status=:status,execution_refs=cast(:refs as jsonb),trace=cast(:trace as jsonb),
        final_response=:final,terminal_state=:terminal,checks=cast(:checks as jsonb),judge=cast(:judge as jsonb),metrics=cast(:metrics as jsonb),
        environment=cast(:environment as jsonb),usage=cast(:usage as jsonb),failure_layers=cast(:layers as jsonb),error=cast(:error as jsonb),
        started_at=coalesce(:started,started_at),finished_at=coalesce(:finished,now()),latency_ms=:latency,updated_at=now() where id=:id"""),
        {'id': row['id'], 'status': status, 'refs': json.dumps(body.execution_refs), 'trace': json.dumps(body.trace),
         'final': trace.final_response if trace else None, 'terminal': trace.terminal_state if trace else None,
         'checks': json.dumps(body.checks), 'judge': json.dumps(body.judge), 'metrics': json.dumps(body.metrics),
         'environment': json.dumps(body.environment), 'usage': json.dumps(body.usage), 'layers': json.dumps(layers),
         'error': json.dumps(error), 'started': body.started_at, 'finished': body.finished_at, 'latency': latency if latency and latency >= 0 else None})
    return {'status': status, 'failureLayers': layers}


class Finish(BaseModel):
    model_config = ConfigDict(extra='forbid')
    worker: str = Field(min_length=1, max_length=120)
    error: dict | None = None


async def finish_failed(db, run_id, code: str, message: str) -> None:
    await db.execute(text("""update vh_agent_eval_runs set status='failed',finished_at=now(),updated_at=now(),lease_owner=null,
        error=cast(:error as jsonb) where id=:id"""), {'id': run_id, 'error': json.dumps({'code': code, 'message': message})})


@internal.post('/runs/{run_id}/finish')
async def finish(run_id: UUID, body: Finish, scope: Worker):
    db, _ = scope
    run = await leased(db, run_id, body.worker)
    results = (await db.execute(text('select status,failure_layers,usage,latency_ms from vh_agent_eval_case_results where run_id=:run order by ordinal'),
                                {'run': run_id})).mappings().all()
    statuses = [r['status'] for r in results]
    layers = sorted({layer['layer'] for r in results for layer in r['failure_layers']})
    summary = {'cases': len(statuses), 'passed': statuses.count('passed'), 'failed': statuses.count('failed'),
               'errors': statuses.count('error'), 'failure_layers': layers,
               'latency_ms': sum(r['latency_ms'] or 0 for r in results),
               'usage': {k: sum((r['usage'] or {}).get(k) or 0 for r in results) for k in ('input_tokens', 'output_tokens', 'judge_input_tokens', 'judge_output_tokens')}}
    if body.error or any(s not in FINAL for s in statuses) or len(statuses) != SUITE_SIZE:
        error = body.error or {'code': 'incomplete_run', 'message': f'Không đủ kết quả của {SUITE_SIZE} ca'}
        await db.execute(text("""update vh_agent_eval_runs set status='failed',summary=cast(:summary as jsonb),error=cast(:error as jsonb),
            finished_at=now(),updated_at=now(),lease_owner=null where id=:id"""), {'id': run_id, 'summary': json.dumps(summary), 'error': json.dumps(error)})
        await audit(db, run['requested_by'], 'agent.evaluation_finished', 'agent', run['agent_id'], {'runId': str(run_id), 'status': 'failed'})
        return {'status': 'failed', 'passed': None}
    passed = run_passed(statuses)
    await db.execute(text("""update vh_agent_eval_runs set status='completed',passed=:passed,summary=cast(:summary as jsonb),
        finished_at=now(),updated_at=now(),lease_owner=null where id=:id"""), {'id': run_id, 'passed': passed, 'summary': json.dumps(summary)})
    review = await attach_review(db, run, summary) if passed else None
    await audit(db, run['requested_by'], 'agent.evaluation_finished', 'agent', run['agent_id'],
                {'runId': str(run_id), 'status': 'completed', 'passed': passed})
    return {'status': 'completed', 'passed': passed, 'reviewId': review}


async def attach_review(db, run: dict, summary: dict):
    """The passing run becomes the evidence of the agent's pending review, if the configuration it
    evaluated is still the one stored. Publication itself stays management's step."""
    agent = (await db.execute(text('select configuration,status from agents where id=:id for update'), {'id': run['agent_id']})).mappings().one()
    if digest(agent['configuration']) != run['configuration_hash']:
        return None
    evidence = {'evaluator': 'agent-eval-v1', 'configuration_hash': run['configuration_hash'], 'run_id': str(run['id']),
                'suite_hash': run['suite_hash'], 'snapshot_hash': run['snapshot_hash'], 'summary': summary}
    pending = (await db.execute(text("select id from vh_agent_reviews where agent_id=:id and status='pending' for update"), {'id': run['agent_id']})).scalar_one_or_none()
    if pending:
        await db.execute(text('update vh_agent_reviews set evaluation=cast(:evidence as jsonb),evaluation_run_id=:run,config_hash=:hash,'
                              'version=version+1,updated_at=now() where id=:id'),
                         {'id': pending, 'evidence': json.dumps(evidence), 'run': run['id'], 'hash': run['configuration_hash']})
        return pending
    return (await db.execute(text(f"""insert into vh_agent_reviews(tenant_id,agent_id,submitted_by,config_hash,evaluation,status,evaluation_run_id)
        values({TENANT},:agent,:actor,:hash,cast(:evidence as jsonb),'pending',:run) returning id"""),
        {'agent': run['agent_id'], 'actor': run['requested_by'], 'hash': run['configuration_hash'],
         'evidence': json.dumps(evidence), 'run': run['id']})).scalar_one()


async def evaluation_gate(db) -> bool:
    """Once the tenant has a ready evaluation environment, only a V1 run is evidence for publication;
    before that the earlier server evaluation still is, so no unit is left unable to publish."""
    return await environment(db) is not None


async def run_evidence_problem(db, review_id) -> str | None:
    """Why this review may not be published by management, or None: it needs a completed run
    that passed at least four of its six cases on the configuration under review."""
    row = (await db.execute(text("""select r.config_hash,r.evaluation_run_id,run.status,run.passed,run.configuration_hash
        from vh_agent_reviews r left join vh_agent_eval_runs run on run.id=r.evaluation_run_id and run.tenant_id=r.tenant_id
        where r.id=:id"""), {'id': review_id})).mappings().one()
    if row['evaluation_run_id'] is None or row['status'] != 'completed' or row['passed'] is not True or row['configuration_hash'] != row['config_hash']:
        return f'Chạy đánh giá {SUITE_SIZE} ca trong sandbox và đạt ít nhất {PASS_MINIMUM} ca trước khi phát hành.'
    return None
