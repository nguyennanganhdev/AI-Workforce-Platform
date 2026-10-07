"""Agent evaluation V1 on migrated PostgreSQL: suites of four, runs under a lease, the verdict made here.

The evaluator service and the worker are stood in for: the worker's calls are made as it makes them.
"""
import json
from uuid import UUID, uuid4

import httpx
import pytest
from test_resident_contract import sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client
from test_v3_coordination import register_tools
from vinhomes_api import v3_agent_evals

ROOM = '/rooms/management-room/agents'
WORKER = {'Authorization': 'Bearer ' + 'w' * 40}
INTERNAL = '/internal/agent-eval/v1'
TOOL = {'server_id': 'technical-tools', 'name': 'technical.get_active_outage'}
EXECUTION_TENANT = '99999999-9999-5999-a999-999999999999'
RUBRIC = {f'score{i}_description': f'mức {i}' for i in range(1, 6)}
CATALOG = {'fixtures': [{'fixture_profile_id': 'resident-a', 'description': 'Cư dân căn mẫu'}],
           'documents': [{'document_id': 'doc-1', 'version': 'v-1', 'title': 'Quy trình rò nước'}],
           'tools': [{**TOOL, 'description': 'Tra mất nước', 'input_schema': {'type': 'object'}, 'effect': 'read'}]}


@pytest.fixture(autouse=True)
def tokens(monkeypatch):
    monkeypatch.setenv('VINHOMES_API_EVAL_SERVICE_TOKEN', 'w' * 40)
    monkeypatch.setenv('VINHOMES_API_EVALUATOR_URL', 'http://evaluator.test')


def case(name, kind='in_scope', **expectations):
    expected = {'required_agents': [], 'forbidden_agents': [], 'terminal_state': 'approval_pending', **expectations}
    return {'name': name, 'kind': kind, 'input': {'message': 'Nhà tôi mất nước', 'fixture_profile_id': 'resident-a'},
            'expectations': expected, 'rubric': RUBRIC}


def suite_for(agent):
    return [case('Chính', required_agents=[agent], required_tools=[TOOL]), case('Thiếu tin', required_agents=[agent]),
            case('Ngoài phạm vi', 'out_of_scope', forbidden_agents=[agent], terminal_state='reply_only'),
            case('Ranh giới', 'boundary', forbidden_tools=[])]


def draft(management, name):
    agent = management.post(ROOM, json={'name': name, 'instructions': 'x', 'idempotency_key': uuid4().hex}).json()['id']
    saved = management.put(f'{ROOM}/{agent}/configuration', json={
        'instructions': 'Chỉ dẫn bí mật của agent.', 'description': 'Tra cứu mất nước', 'service_categories': ['technical'],
        'mcp_tools': [TOOL]})
    assert saved.status_code == 200, saved.text
    return agent, saved.json()['configurationHash']


def register_environment(c, **changes):
    return c.put(INTERNAL + '/environment', headers=WORKER, json={
        'execution_tenant_id': EXECUTION_TENANT, 'fixture_version': 'fixtures-v1',
        'runtime_profile': {'sandbox_url_env': 'EVAL_SANDBOX_URL', 'database': 'vinhomes_eval'}, 'catalog': CATALOG, **changes})


def approved_suite(management, agent, configuration_hash):
    suite = management.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration_hash, 'mode': 'manual',
                                                                 'cases': suite_for(agent)})
    assert suite.status_code == 201 and suite.json()['problems'] == [], suite.text
    approved = management.post(f"{ROOM}/{agent}/eval-suites/{suite.json()['id']}/approve", json={'version': suite.json()['version']})
    assert approved.status_code == 200, approved.text
    return approved.json()


def checks(passed=True):
    return {k: {'passed': passed, 'reason': 'ok' if passed else 'rớt', 'evidence_refs': []}
            for k in ('required_agents', 'forbidden_agents', 'required_tools', 'forbidden_tools', 'required_sources',
                      'valid_output', 'runtime_guards', 'context_integrity', 'internal_leakage')}


def judge(score=5):
    return {'status': 'scored', 'backend': 'structured-chat', 'model_profile': 'openai/j', 'threshold': 4,
            'criteria': {c: {'score': score, 'reason': 'ok', 'evidence_refs': ['final_response']}
                         for c in ('bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao')}}


TRACE = {'messages': [{'id': 'm-1', 'role': 'resident', 'text': 'Nhà tôi mất nước'}], 'final_response': 'Đã chuyển BQL.',
         'terminal_state': 'approval_pending', 'context': {'tenant_id': EXECUTION_TENANT}}
SAFE = {'safe': True, 'reason': 'Chỉ chạm sandbox.'}


def submit(c, run, case_id, **parts):
    body = {'worker': 'w1', 'status': 'done', 'trace': TRACE, 'checks': checks(), 'judge': judge(), 'environment': SAFE,
            'started_at': '2026-10-07T01:00:00Z', 'finished_at': '2026-10-07T01:01:00Z', **parts}
    return c.put(f'{INTERNAL}/runs/{run}/cases/{case_id}', headers=WORKER, json=body)


def test_suite_run_verdict_and_publication(database, monkeypatch):
    register_tools(database)
    with demo_client(database, 'management') as m:
        agent, configuration = draft(m, 'Eval ' + uuid4().hex[:6])
        # Before a sandbox exists nothing can be prepared, and nothing is left half done.
        assert m.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration, 'mode': 'manual'}).status_code == 503
        assert m.put(INTERNAL + '/environment', json={}).status_code == 401
        assert register_environment(m, execution_tenant_id=str(UUID('11111111-1111-5111-a111-111111111111'))).status_code == 422
        assert register_environment(m, runtime_profile={'api_key': 'x'}).status_code == 422
        assert register_environment(m).status_code == 200

        # A draft of three cases is kept, with the reason it cannot be approved yet.
        short = m.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration, 'mode': 'manual',
                                                            'cases': suite_for(agent)[:3]}).json()
        assert any('4 ca' in p for p in short['problems'])
        assert m.post(f"{ROOM}/{agent}/eval-suites/{short['id']}/approve", json={'version': short['version']}).status_code == 422
        wrong = [*suite_for(agent)[:3], case('Bịa', required_agents=['ghost-agent'])]
        edited = m.put(f"{ROOM}/{agent}/eval-suites/{short['id']}", json={'version': short['version'], 'cases': wrong}).json()
        assert any('ghost-agent' in p for p in edited['problems'])
        assert m.put(f"{ROOM}/{agent}/eval-suites/{short['id']}", json={'version': short['version'], 'cases': suite_for(agent)}).status_code == 409
        fixed = m.put(f"{ROOM}/{agent}/eval-suites/{short['id']}", json={'version': edited['version'], 'cases': suite_for(agent)}).json()
        assert fixed['problems'] == []
        suite = m.post(f"{ROOM}/{agent}/eval-suites/{short['id']}/approve", json={'version': fixed['version']}).json()
        assert suite['status'] == 'approved' and len(suite['suite_hash']) == 64
        # Approved means immutable, in the API and in the database itself.
        assert m.put(f"{ROOM}/{agent}/eval-suites/{suite['id']}", json={'version': suite['version'], 'cases': suite_for(agent)}).status_code == 409
        with pytest.raises(Exception, match='immutable'):
            sql(database, "update vh_agent_eval_cases set name='x' where suite_id=$1", UUID(suite['id']))

        start = {'suite_id': suite['id'], 'configuration_hash': configuration, 'request_id': 'r1'}
        assert m.post(f'{ROOM}/{agent}/eval-runs', json={**start, 'configuration_hash': 'f' * 64}).status_code == 409
        accepted = m.post(f'{ROOM}/{agent}/eval-runs', json=start)
        assert accepted.status_code == 202 and accepted.json()['status'] == 'queued'
        run = accepted.json()['runId']
        assert m.post(f'{ROOM}/{agent}/eval-runs', json=start).json()['runId'] == run
        assert m.post(f'{ROOM}/{agent}/eval-runs', json={**start, 'suite_id': short['id'] if short['id'] != suite['id'] else str(uuid4())}).status_code in (404, 409)
        assert m.post(f'{ROOM}/{agent}/eval-runs', json={**start, 'request_id': 'r2'}).status_code == 409  # one active run per sandbox
        snapshot = sql(database, 'select snapshot from vh_agent_eval_runs where id=$1', UUID(run))[0]['snapshot']
        assert 'api_key' not in snapshot and json.loads(snapshot)['tools'][0]['name'] == TOOL['name']

        # The worker claims under a lease; another worker cannot write into it.
        claimed = m.post(INTERNAL + '/runs/claim', headers=WORKER, json={'worker': 'w1'}).json()
        assert claimed['run']['id'] == run and len(claimed['cases']) == 4
        assert m.post(INTERNAL + '/runs/claim', headers=WORKER, json={'worker': 'w2'}).json() == {'run': None}
        assert m.post(f'{INTERNAL}/runs/{run}/heartbeat', headers=WORKER, json={'worker': 'w2'}).status_code == 409
        assert m.post(f'{INTERNAL}/runs/{run}/heartbeat', headers=WORKER, json={'worker': 'w1'}).json() == {'status': 'running'}
        events = m.post(f'{INTERNAL}/runs/{run}/events', headers=WORKER, json={'worker': 'w1', 'events': [
            {'kind': 'lifecycle', 'payload': {'step': 'installed'}}, {'kind': 'message', 'payload': {'text': 'x'}}]})
        assert events.json() == {'lastSeq': 2}
        ids = [c['id'] for c in claimed['cases']]
        # A pass/fail flag from the worker is not part of the contract.
        assert submit(m, run, ids[0], passed=True).status_code == 422
        assert submit(m, run, ids[0]).json()['status'] == 'passed'
        assert submit(m, run, ids[0]).status_code == 409
        low = submit(m, run, ids[1], checks=checks(False), judge=judge(5)).json()
        assert low['status'] == 'failed' and low['failureLayers'][0]['layer'] == 'code'
        assert submit(m, run, ids[2], trace=None, error={'code': 'case_timeout'}).json()['status'] == 'error'
        invented = submit(m, run, ids[3], judge={**judge(), 'criteria': {**judge()['criteria'], 'bam_nguon': {
            'score': 5, 'reason': 'ok', 'evidence_refs': ['m-404']}}}).json()
        assert invented['status'] == 'error'
        finished = m.post(f'{INTERNAL}/runs/{run}/finish', headers=WORKER, json={'worker': 'w1'}).json()
        assert finished == {'status': 'completed', 'passed': False, 'reviewId': None}
        report = m.get(f'{ROOM}/{agent}/eval-runs/{run}').json()
        assert [c['status'] for c in report['cases']] == ['passed', 'failed', 'error', 'error'] and report['passed'] is False
        assert report['summary']['failure_layers'] == ['code', 'execution']
        assert report['cases'][3]['error']['code'] == 'unknown_evidence'

        # A second run passes all four: it becomes the pending review's evidence, and only then can BQL publish.
        second = m.post(f'{ROOM}/{agent}/eval-runs', json={**start, 'request_id': 'r3'}).json()['runId']
        claimed = m.post(INTERNAL + '/runs/claim', headers=WORKER, json={'worker': 'w1'}).json()
        for c in claimed['cases']:
            assert submit(m, second, c['id']).json()['status'] == 'passed'
        done = m.post(f'{INTERNAL}/runs/{second}/finish', headers=WORKER, json={'worker': 'w1'}).json()
        assert done['passed'] is True and done['reviewId']
        review = sql(database, 'select id,version,evaluation_run_id from vh_agent_reviews where id=$1', UUID(done['reviewId']))[0]
        assert str(review['evaluation_run_id']) == second
        published = m.post(f"/rooms/management-room/agent-reviews/{review['id']}/decision",
                           json={'decision': 'approve', 'version': review['version'], 'note': 'Đạt 4/4'})
        assert published.status_code == 200, published.text


def test_once_a_sandbox_exists_the_legacy_evaluation_no_longer_publishes(database):
    register_tools(database)
    with demo_client(database, 'management') as m:
        assert register_environment(m).status_code == 200
        agent, configuration = draft(m, 'Legacy ' + uuid4().hex[:6])
        cases = [{'name': f'c{n}', 'input': 'i', 'expected': 'e', 'actual': 'e', 'passed': True, 'explanation': 'ok'} for n in range(6)]
        review = m.post(f'{ROOM}/{agent}/review-submissions', json={'configuration_hash': configuration, 'evaluator': 'x', 'round': 1, 'cases': cases}).json()
        sql(database, """update vh_agent_reviews set evaluation=evaluation||'{"_runtime_verified": true}'::jsonb where id=$1""", UUID(review['id']))
        refused = m.post(f"/rooms/management-room/agent-reviews/{review['id']}/decision",
                         json={'decision': 'approve', 'version': review['version'], 'note': 'x'})
        assert refused.status_code == 409 and '4 ca' in refused.json()['detail']


def test_generation_sees_what_the_agent_may_do_never_its_instructions(database, monkeypatch):
    register_tools(database)
    sent = []

    class Evaluator:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert url == 'http://evaluator.test/internal/generate' and headers == WORKER
            sent.append(json)
            agent = json['context']['agent']['agent_id']
            return httpx.Response(200, json={'cases': suite_for(agent), 'problems': [], 'generator_profile': {'prompt_version': 'g1'}})
    monkeypatch.setattr(v3_agent_evals.httpx, 'AsyncClient', Evaluator)
    with demo_client(database, 'management') as m:
        register_environment(m)
        agent, configuration = draft(m, 'Gen ' + uuid4().hex[:6])
        suite = m.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration, 'mode': 'generate'})
        assert suite.status_code == 201, suite.text
        assert [c['source'] for c in suite.json()['cases']] == ['generated'] * 4 and suite.json()['problems'] == []
    context = sent[0]['context']
    assert 'Chỉ dẫn bí mật' not in json.dumps(sent[0], ensure_ascii=False)
    assert context['fixtures'] == CATALOG['fixtures'] and context['agent']['tools'][0]['name'] == TOOL['name']


def test_a_silent_worker_interrupts_its_run_and_a_cancel_reaches_the_worker(database):
    register_tools(database)
    with demo_client(database, 'management') as m:
        register_environment(m)
        agent, configuration = draft(m, 'Lease ' + uuid4().hex[:6])
        suite = approved_suite(m, agent, configuration)
        start = {'suite_id': suite['id'], 'configuration_hash': configuration, 'request_id': 'lease'}
        run = m.post(f'{ROOM}/{agent}/eval-runs', json=start).json()['runId']
        m.post(INTERNAL + '/runs/claim', headers=WORKER, json={'worker': 'w1'})
        sql(database, "update vh_agent_eval_runs set lease_expires_at=now()-interval '1 second' where id=$1", UUID(run))
        report = m.get(f'{ROOM}/{agent}/eval-runs/{run}').json()
        assert report['status'] == 'interrupted' and report['passed'] is None
        assert m.post(f'{INTERNAL}/runs/{run}/heartbeat', headers=WORKER, json={'worker': 'w1'}).status_code == 409
        # Interrupted is not run again by itself; a new request is a new run.
        again = m.post(f'{ROOM}/{agent}/eval-runs', json={**start, 'request_id': 'lease-2'}).json()['runId']
        assert m.post(INTERNAL + '/runs/claim', headers=WORKER, json={'worker': 'w1'}).json()['run']['id'] == again
        assert m.post(f'{ROOM}/{agent}/eval-runs/{again}/cancel').json()['status'] == 'cancelled'
        stopped = m.post(f'{INTERNAL}/runs/{again}/heartbeat', headers=WORKER, json={'worker': 'w1'})
        assert stopped.status_code == 409 and stopped.json()['detail'] == 'cancelled'


def test_sandbox_routes_do_not_exist_in_a_production_database(database, monkeypatch):
    monkeypatch.setenv('VINHOMES_API_EVAL_SANDBOX_TOKEN', 's' * 40)
    with demo_client(database, 'management') as m:
        headers = {'Authorization': 'Bearer ' + 's' * 40}
        assert m.get('/internal/agent-eval/sandbox/v1/catalog', headers=headers).status_code == 404
        assert m.post('/internal/agent-eval/sandbox/v1/conversations', headers=headers,
                      json={'fixture_profile_id': 'resident-a', 'title': 'x'}).status_code == 404


def test_production_keeps_no_tool_arguments_or_results(database):
    from fastapi.testclient import TestClient
    from test_resident_contract import TENANT
    from vinhomes_api.main import create_app
    from vinhomes_api.v3_config import V3Settings
    register_tools(database)
    run = uuid4()
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True, coordination_service_token='c' * 40)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000)) as c:
        refused = c.post('/internal/coordination/v1/tools/call', headers={'Authorization': 'Bearer ' + 'c' * 40},
                         json={'run_id': str(run), 'tool': TOOL['name'], 'arguments': {'building_id': str(uuid4())}})
        assert refused.json()['status'] == 'FORBIDDEN'
    assert sql(database, 'select 1 from vh_agent_eval_tool_traces') == []
    assert len(sql(database, "select 1 from audit_events where event_type='agent.tool_called' and target_id=$1", str(run))) == 1


def test_a_published_agent_the_sandbox_cannot_reproduce_is_left_out_by_name_not_a_blocker(database):
    from test_resident_contract import TENANT
    from test_v3_coordination import publish_specialist
    register_tools(database)
    sql(database, "insert into mcp_tools(server_id,name,description,input_schema,effect,tenant_id) values('technical-tools','technical.retired_tool','x','{}','read',$1) "
                  "on conflict do nothing returning name", TENANT)
    stale, _ = publish_specialist(database, 'Stale ' + uuid4().hex[:6], ['technical'], ['technical.retired_tool'])
    sql(database, "delete from mcp_tools where name='technical.retired_tool' returning name")
    with demo_client(database, 'management') as m:
        register_environment(m)
        agent, configuration = draft(m, 'Beside stale ' + uuid4().hex[:6])
        # A case cannot name the agent that will not be in the sandbox.
        named = m.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration, 'mode': 'manual', 'cases': [
            *suite_for(agent)[:3], case('Phối hợp', 'collaboration', required_agents=[agent, stale])]}).json()
        assert any(stale in p for p in named['problems'])
        suite = approved_suite(m, agent, configuration)
        run = m.post(f'{ROOM}/{agent}/eval-runs', json={'suite_id': suite['id'], 'configuration_hash': configuration, 'request_id': 'stale'})
        assert run.status_code == 202, run.text
        snapshot = json.loads(sql(database, 'select snapshot from vh_agent_eval_runs where id=$1', UUID(run.json()['runId']))[0]['snapshot'])
        assert [e['agent_id'] for e in snapshot['excluded_collaborators']] == [stale] and 'không còn đăng ký' in snapshot['excluded_collaborators'][0]['reason']
        assert stale not in [c['agent_id'] for c in snapshot['collaborators']]
        m.post(f"{ROOM}/{agent}/eval-runs/{run.json()['runId']}/cancel")
