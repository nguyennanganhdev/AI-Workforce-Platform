"""BQL-owned Factory construction. Credentials and the tool catalogue stay server-side."""
import json
import os
import re
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from .v3_agent_reviews import Member, room_agent, room_catalogue, submit, EvaluationRecord, can_author_unit
from .v3_coordination import Scope as RuntimeScope
from .v3_security import digest
from .v3_audit import audit
from .v3_models import resolve_model

router = APIRouter(tags=['BQL agent builder'])


def re_safe_code(code: str) -> bool:
    return bool(re.fullmatch(r'[A-Z_]{1,80}', code))


def factory_refusal(body: object) -> str:
    """What management reads when the Factory refuses a description: its open questions, one per line."""
    issues = body.get('issues', []) if isinstance(body, dict) else []
    issues = [i for i in issues if isinstance(i, dict)] if isinstance(issues, list) else []
    said = [' '.join(str(i.get('message', '')).split())[:300] for i in issues[:4]]
    said = [m for m in said if m]
    if any(i.get('code') == 'NEEDS_INPUT' for i in issues):
        return '\n'.join(['Factory cần biết thêm trước khi soạn chỉ dẫn. Bổ sung vào ô Nhiệm vụ rồi tạo lại:',
                          *('- ' + m for m in said)])
    if any(i.get('code') == 'BLOCKED_RESOURCE' for i in issues):
        return '\n'.join(['Nhóm chưa có công cụ cho một phần của nhiệm vụ này. Bỏ phần đó khỏi ô Nhiệm vụ, hoặc nhờ quản trị viên thêm công cụ rồi tạo lại:',
                          *('- ' + m for m in said)])
    return 'Factory chưa soạn được chỉ dẫn từ nhiệm vụ này: ' + ('; '.join(said) or 'đối chiếu nhiệm vụ với các công cụ của nhóm.')


class EvaluationCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=2000)
    expected: str = Field(min_length=1, max_length=2000)
    ticket: dict = Field(default_factory=dict)
    must: list[str] = Field(default_factory=list, max_length=20)
    must_not: list[str] = Field(default_factory=list, max_length=20)
    must_call: list[str] = Field(default_factory=list, max_length=20)
    must_not_call: list[str] = Field(default_factory=list, max_length=20)
    tool_results: dict = Field(default_factory=dict)


class Evaluate(BaseModel):
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')
    request_id: str = Field(min_length=1, max_length=120)
    cases: list[EvaluationCaseInput] = Field(min_length=6, max_length=12)


class EvaluationView(BaseModel):
    actor: str = Field(min_length=1, max_length=160)
    room_id: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')


@router.post('/internal/coordination/v1/agent-evaluations/view')
async def evaluation_view(body: EvaluationView, db: RuntimeScope):
    agent = await room_agent((db, body.actor), body.room_id, body.agent_id, lock=False)
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Configuration changed')
    if agent['status'] != 'draft' and not agent['configuration'].get('revision_of'):
        raise HTTPException(409, 'Draft or draft revision required')
    descriptors = []
    for granted in agent['configuration'].get('mcp_tools', []):
        tool = (await db.execute(text("select t.description,t.input_schema from mcp_tools t join mcp_servers s on s.id=t.server_id where t.server_id=:server and t.name=:name and (t.effect='read' or s.provenance='custom') and not t.destructive and s.status='active'"),
                                {'server': granted['server_id'], 'name': granted['name']})).mappings().first()
        if tool is None:
            raise HTTPException(409, 'A configured tool is not available for evaluation')
        descriptors.append({'name': granted['name'].replace('.', '__'), 'description': tool['description'], 'parameters': tool['input_schema']})
    from .v3_models import resolve_model
    model_config = await resolve_model(db, 'specialist', agent['configuration'].get('model_id'))
    return {'model_config': model_config, 'instructions': await instructions_with_skills(db, agent['configuration'], agent['workspace_id']), 'model_id': agent['configuration'].get('model_id'), 'tools': descriptors,
            'configuration_hash': body.configuration_hash}


@router.post('/rooms/{room_id}/agents/{agent_id}/evaluate')
async def evaluate_agent(room_id: str, agent_id: str, body: Evaluate, scope: Member):
    # The runtime verifies this same configuration in a separate transaction. Do not hold
    # row locks across that HTTP call; submit() locks and rechecks the hash afterwards.
    agent = await room_agent(scope, room_id, agent_id, lock=False)
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Evaluation belongs to a different configuration')
    if len({c.name for c in body.cases}) != len(body.cases):
        raise HTTPException(422, 'Evaluation case names must be distinct')
    # Browser-authored assertions are literals, not executable regular expressions.
    # The script evaluator still owns its curated regex datasets.
    import re
    cases = [c.model_dump() for c in body.cases]
    for case in cases:
        case['must'] = [re.escape(p) for p in (case['must'] or [case['expected']])]
        case['must_not'] = [re.escape(p) for p in case['must_not']]
        if any(len(p) > 500 for p in case['must'] + case['must_not']):
            raise HTTPException(422, 'Evaluation assertion is too long')
    url, token = os.getenv('VINHOMES_API_COORDINATION_URL', '').rstrip('/'), os.getenv('VINHOMES_API_COORDINATION_SERVICE_TOKEN', '')
    if not url or len(token) < 32:
        raise HTTPException(503, 'The evaluation runtime is not configured')
    try:
        async with httpx.AsyncClient(timeout=250, follow_redirects=False) as client:
            reply = await client.post(url + '/internal/evaluations', headers={'Authorization': 'Bearer ' + token}, json={
                'room_id': room_id, 'agent_id': agent_id, 'actor': scope[1], 'request_id': body.request_id,
                'configuration_hash': body.configuration_hash, 'cases': cases})
            if reply.status_code == 409:
                raise HTTPException(409, 'This evaluation is running or was interrupted. Check the runtime before starting another round')
            if reply.status_code != 200:
                raise HTTPException(503, 'Evaluation runtime did not complete this round')
            records = reply.json()['cases']
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Evaluation is unavailable; the agent was not published') from None
    passed = all(c['passed'] for c in records) and len(records) == len(cases)
    review = None
    if passed:
        record = EvaluationRecord(configuration_hash=body.configuration_hash, evaluator='coordination-openbot-assertions', round=1, cases=records)
        review = await submit(room_id, agent_id, record, scope)
        # Only this authenticated runtime result may attest a BQL publication. A person
        # posting passed=true records to the legacy submission API cannot forge this flag.
        await scope[0].execute(text("update vh_agent_reviews set evaluation=evaluation||cast(:proof as jsonb) where id=:id"),
            {'id': review['id'], 'proof': json.dumps({'_runtime_verified': True, '_evaluation_request_id': body.request_id})})
    await audit(scope[0], scope[1], 'agent.evaluated', 'agent', agent_id, {'passed': passed, 'requestId': body.request_id})
    return {'passed': passed, 'cases': records, 'review': review, 'toolsMode': 'case-fixtures-no-side-effects'}


class Trial(BaseModel):
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')
    question: str = Field(min_length=1, max_length=2000)


@router.post('/rooms/{room_id}/agents/{agent_id}/try')
async def try_agent(room_id: str, agent_id: str, body: Trial, scope: Member):
    """One question to the saved draft, to read how it replies before writing evaluation cases.
    Nothing is recorded as an evaluation and nothing is published; tools answer that they found nothing."""
    agent = await room_agent(scope, room_id, agent_id, lock=False)
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Cấu hình đã đổi. Lưu cấu hình rồi hỏi thử lại.')
    if agent['status'] != 'draft' and not agent['configuration'].get('revision_of'):
        raise HTTPException(409, 'Chỉ hỏi thử được bản nháp. Sửa và lưu cấu hình để có bản nháp mới.')
    url, token = os.getenv('VINHOMES_API_COORDINATION_URL', '').rstrip('/'), os.getenv('VINHOMES_API_COORDINATION_SERVICE_TOKEN', '')
    if not url or len(token) < 32:
        raise HTTPException(503, 'The evaluation runtime is not configured')
    try:
        async with httpx.AsyncClient(timeout=130, follow_redirects=False) as client:
            reply = await client.post(url + '/internal/trials', headers={'Authorization': 'Bearer ' + token}, json={
                'room_id': room_id, 'agent_id': agent_id, 'actor': scope[1], 'configuration_hash': body.configuration_hash,
                'question': body.question})
            said = reply.json() if reply.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        said = None
    if not said or not isinstance(said.get('answer'), str):
        raise HTTPException(503, 'Bản nháp chưa trả lời được. Nếu lặp lại, báo quản trị viên kiểm tra khóa model.')
    await audit(scope[0], scope[1], 'agent.tried', 'agent', agent_id, {'tools': said.get('called', [])})
    return {'answer': said['answer'], 'called': said.get('called', [])}


class Construction(BaseModel):
    role: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=2000)
    service_categories: list[str] = Field(default_factory=list, max_length=10)
    configuration_hash: str = Field(pattern='^[a-f0-9]{64}$')
    request_id: str = Field(min_length=1, max_length=120)
    revision_of: UUID | None = None
    model_id: str | None = Field(default=None, max_length=160)
    skill_ids: list[UUID] | None = Field(default=None, max_length=30)


@router.post('/rooms/{room_id}/agents/{agent_id}/construct')
async def construct(room_id: str, agent_id: str, body: Construction, scope: Member):
    # The Factory takes up to a minute and a half. No row lock is held across that call: a locked
    # room makes every other read of it wait. The agent is locked and checked again before the write.
    agent = await room_agent(scope, room_id, agent_id, lock=False)
    if not await can_author_unit(scope[0], scope[1], agent['workspace_id']):
        raise HTTPException(403, 'Only management of this unit can construct its agent')
    configuration = agent['configuration']
    old = configuration.get('factory')
    if old and old.get('request_id') == body.request_id:
        if old.get('input') != body.model_dump(mode='json'):
            raise HTTPException(409, 'Construction id already used for different content')
        return {'configurationHash': digest(configuration), 'configuration': configuration}
    if digest(configuration) != body.configuration_hash:
        raise HTTPException(409, 'Agent configuration changed; reload before construction')
    if agent['status'] != 'draft' and not body.revision_of:
        raise HTTPException(409, 'Start a revision of the active agent before construction')
    if body.revision_of:
        latest = (await scope[0].execute(text('select id from agent_versions where agent_id=:id order by version_no desc limit 1'), {'id': agent_id})).scalar_one_or_none()
        if latest != body.revision_of:
            raise HTTPException(409, 'The base version changed')
    if (await scope[0].execute(text("select 1 from vh_agent_reviews where agent_id=:id and status='pending'"), {'id': agent_id})).first():
        raise HTTPException(409, 'Decide the pending review first')
    catalogue = await room_catalogue(room_id, scope, lock=False)
    codes = {c['code'] for c in catalogue['categories']}
    if not set(body.service_categories) <= codes:
        raise HTTPException(422, 'Unknown service category')
    # Freeze selected capabilities before asking the Factory; later edits to shared skills
    # do not silently change the draft that this request constructs.
    model_id = body.model_id if 'model_id' in body.model_fields_set else configuration.get('model_id')
    if model_id and not await resolve_model(scope[0], 'specialist', model_id):
        raise HTTPException(422, 'Model is not available for this unit')
    skill_ids = [str(s) for s in body.skill_ids] if body.skill_ids is not None else configuration.get('skill_ids', [])
    skill_snapshots = []
    for skill_id in skill_ids:
        skill = (await scope[0].execute(text('select id,name,instructions from vh_agent_skills where id=cast(:id as uuid) and (workspace_id is null or workspace_id=:workspace)'), {'id': skill_id, 'workspace': agent['workspace_id']})).mappings().first()
        if not skill:
            raise HTTPException(422, 'Skill outside this unit')
        skill_snapshots.append({'id': str(skill['id']), 'name': skill['name'], 'instructions': skill['instructions']})
    tools = [{'kind': 'tool', 'ref': f"{t['server_id']}/{t['name']}", 'name': t['name'], 'title': t['name'],
              'description': t['description'], 'inputSchema': t['input_schema'], 'outputSchema': None,
              'effect': t['effect'], 'destructive': False} for t in catalogue['tools']]
    request = {'name': agent['name'], 'role': body.role, 'description': body.description}
    url, token = os.getenv('FACTORY_SERVICE_URL', '').rstrip('/'), os.getenv('FACTORY_SERVICE_TOKEN', '')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or len(token) < 32:
        raise HTTPException(503, 'Agent Factory is not configured')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1', 'factory'):
        raise HTTPException(503, 'Factory requires HTTPS or the private configured service host')
    headers = {'Authorization': 'Bearer ' + token}
    payload = {'request': request, 'catalogue': {'tools': tools, 'defaultToolRefs': []}}
    factory_model = await resolve_model(scope[0], 'factory')
    try:
        async with httpx.AsyncClient(timeout=95, follow_redirects=False) as client:
            reply = await client.post(url + '/v1/constructions', json={**payload, **({'model_config': factory_model} if factory_model else {})}, headers=headers)
            if reply.status_code == 422:
                refusal = reply.json()
                issues = refusal.get('issues', []) if isinstance(refusal, dict) else []
                if (isinstance(issues, list) and issues
                        and all(isinstance(i, dict) and i.get('code') == 'NEEDS_INPUT'
                                and isinstance(i.get('message'), str) and i['message'].strip() for i in issues)):
                    # Clarification is a normal step of construction, not a saved artifact.
                    return {'needsInput': True, 'questions': [
                        ' '.join(i['message'].split())[:300] for i in issues[:4]]}
                raise HTTPException(422, factory_refusal(refusal))
            if reply.status_code != 200 or len(reply.content) > 1024 * 1024:
                code = reply.json().get('code', '') if len(reply.content) < 4096 else ''
                safe_code = code if isinstance(code, str) and re_safe_code(code) else 'UNAVAILABLE'
                raise HTTPException(503, f'Factory construction did not complete ({safe_code})')
            artifact = reply.json()
            verified = await client.post(url + '/v1/verify', json={**payload, 'artifact': artifact}, headers=headers)
            if verified.status_code != 200:
                raise HTTPException(502, 'Factory artifact failed integrity verification')
            artifact = verified.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Factory is unavailable; no agent was published') from None
    agent = await room_agent(scope, room_id, agent_id)
    if digest(agent['configuration']) != body.configuration_hash:
        raise HTTPException(409, 'Agent configuration changed; reload before construction')
    if (await scope[0].execute(text("select 1 from vh_agent_reviews where agent_id=:id and status='pending'"), {'id': agent_id})).first():
        raise HTTPException(409, 'Decide the pending review first')
    known = {t['ref']: t for t in tools}
    resources = artifact['spec']['resources']
    if any(r['kind'] != 'tool' or r['ref'] not in known for r in resources):
        raise HTTPException(502, 'Factory selected a resource outside the authorized catalogue')
    instructions = artifact['systemPrompt']
    if not isinstance(instructions, str) or not 1 <= len(instructions) <= 50000:
        raise HTTPException(422, 'Generated instructions exceed this runtime limit')
    configuration = {'instructions': instructions, 'description': body.description,
        'service_categories': body.service_categories, 'knowledge_namespace_ids': [], 'framework_version': 'factory-compiler-2',
        'revision_of': str(body.revision_of) if body.revision_of else None,
        'model_id': model_id, 'skill_ids': skill_ids, 'skill_snapshots': skill_snapshots,
        'mcp_tools': [{'server_id': r['ref'].split('/', 1)[0], 'name': known[r['ref']]['name']} for r in resources],
        'factory': {'request_id': body.request_id, 'input': body.model_dump(mode='json'), 'artifact': artifact}}
    await scope[0].execute(text('update agents set configuration=cast(:config as jsonb) where id=:id'), {'id': agent_id, 'config': json.dumps(configuration)})
    await audit(scope[0], scope[1], 'agent.factory_constructed', 'agent', agent_id, {'specHash': artifact['specHash'], 'roomId': room_id})
    return {'configurationHash': digest(configuration), 'configuration': configuration}


async def instructions_with_skills(db, configuration, workspace_id):
    instruction = configuration.get('instructions', '')
    if 'skill_snapshots' in configuration:
        for skill in configuration['skill_snapshots']:
            instruction += '\n\nKỹ năng: ' + skill['name'] + '\n' + skill['instructions']
        return instruction
    for skill_id in configuration.get('skill_ids', []):
        skill = (await db.execute(text('select name,instructions from vh_agent_skills where id=cast(:id as uuid) and (workspace_id is null or workspace_id=:workspace)'), {'id': skill_id, 'workspace': workspace_id})).mappings().first()
        if not skill:
            raise HTTPException(409, 'A configured skill is no longer available')
        instruction += '\n\nKỹ năng: ' + skill['name'] + '\n' + skill['instructions']
    return instruction
