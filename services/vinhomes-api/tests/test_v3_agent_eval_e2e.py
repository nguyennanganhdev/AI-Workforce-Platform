"""End to end: the real worker (agent-coordination/src/agent_eval) between two real API processes.

The source API runs on the module's migrated database; the sandbox API on a second database made by
scripts/provision_eval_sandbox.py's own seed, with a role of its own. Only the judge model is stood in for,
and Reception is the demo route's canned reply (no Reception or Supervisor runs here): the cases expect a
plain reply. The first run finds the sandbox role able to reach the source database and ends unsafe; once
CONNECT is revoked from PUBLIC on the source, the second run plays all four cases: three pass, and the in-scope
case fails because no Supervisor routes to the agent here, so the run is no pass and nothing can be published.
"""
import asyncio
import importlib.util
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient
from test_resident_contract import PROJECT, SERVICE, TENANT, database_url, env_file, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client
from test_v3_coordination import register_tools
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

sys.path.insert(0, str(PROJECT / 'agent-coordination/src'))
from agent_eval.llm import ModelConfig  # noqa: E402
from agent_eval.worker import Settings, Worker  # noqa: E402

ROOM = '/rooms/management-room/agents'
TOOL = {'server_id': 'technical-tools', 'name': 'technical.get_active_outage'}
RUBRIC = {f'score{i}_description': f'mức {i}' for i in range(1, 6)}
JUDGE = {c: {'score': 5, 'reason': 'Trả lời đúng phạm vi, có căn cứ.', 'evidence_refs': ['final_response']}
         for c in ('bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao')}


def provisioning():
    spec = importlib.util.spec_from_file_location('provision_eval_sandbox', SERVICE / 'scripts/provision_eval_sandbox.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def sandbox_db(database):
    admin_url = env_file('migration.env').get('DATABASE_URL')
    suffix = uuid4().hex[:12]
    name, role, password = f'resident_contract_test_eval_{suffix}', f'evaltest_role_{suffix}', secrets.token_hex(16)
    tenant = uuid4()

    async def setup():
        admin = await asyncpg.connect(admin_url)
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.close()
        db = await asyncpg.connect(database_url(admin_url, name))
        try:
            for entry in json.loads((PROJECT / 'server/drizzle/meta/_journal.json').read_text())['entries']:
                await db.execute((PROJECT / 'server/drizzle' / (entry['tag'] + '.sql')).read_text(encoding='utf-8').replace('--> statement-breakpoint', ''))
            await db.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS")
            grants = (SERVICE / 'scripts/grant_v3_api_role.sql').read_text(encoding='utf-8')
            await db.execute(grants.replace('vinhomes_v3_api', role).replace('DATABASE vinhomes_v3', f'DATABASE "{name}"'))
            await db.execute(f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC')
            async with db.transaction():
                await db.execute("select set_config('app.tenant_id',$1,true)", str(tenant))
                await db.execute("insert into tenants(id,code,name,status) values($1,'agent-eval','Sandbox','active')", tenant)
                await db.execute('insert into vh_agent_eval_sandbox(tenant_id,source_database,fixture_version) values($1,$2,$3)',
                                 tenant, urlsplit(database['admin']).path.lstrip('/'), 'e2e')
                room = await provisioning().seed(db, tenant)
                # The demo route's canned Reception reply is sent as this agent (seed_v3_faker.sql has it for the demo tenant).
                await db.execute("insert into agents(id,tenant_id,name,type,configuration,purpose,status) values('demo-reception',$1,'Reception demo','built_in','{}','reception','draft')", tenant)
                await db.execute("insert into mcp_servers(id,title,vendor,url,provenance,tenant_id) values('technical-tools','T','Q','internal:x','first-party',$1)", tenant)
                await db.execute("insert into mcp_tools(server_id,name,description,input_schema,effect,tenant_id) values($1,$2,'Tra mất nước',$3,'read',$4)",
                                 TOOL['server_id'], TOOL['name'], json.dumps({'type': 'object', 'required': ['building_id']}), tenant)
        finally:
            await db.close()
        return room

    room = asyncio.run(setup())
    parts = urlsplit(database_url(admin_url, name))
    runtime = urlunsplit(parts._replace(netloc=f'{role}:{quote(password)}@{parts.hostname}:{parts.port}')).replace('postgresql:', 'postgresql+asyncpg:')
    yield {'runtime': runtime, 'tenant': tenant, 'room': room, 'name': name}

    async def cleanup():
        admin = await asyncpg.connect(admin_url)
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'DROP ROLE IF EXISTS {role}')
        await admin.close()
    asyncio.run(cleanup())


class Bridge(httpx.AsyncBaseTransport):
    """The worker's HTTP calls, to the two in-process APIs and the stand-in judge model."""

    def __init__(self, apis: dict[str, TestClient]):
        self.apis = apis

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == 'models.test':
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(JUDGE)}}], 'usage': {'prompt_tokens': 50, 'completion_tokens': 20}})
        client = self.apis[request.url.host]
        reply = await asyncio.to_thread(client.request, request.method, request.url.raw_path.decode(), content=request.content,
                                        headers={k: v for k, v in request.headers.items() if k.lower() in ('authorization', 'content-type')})
        return httpx.Response(reply.status_code, headers={'content-type': reply.headers.get('content-type', 'application/json')}, content=reply.content)


def case(name, kind, agent):
    expected = {'terminal_state': 'reply_only', 'ticket': 'forbidden', **({'forbidden_agents': [agent]} if kind == 'out_of_scope' else {}),
                **({'required_agents': [agent]} if kind == 'in_scope' else {})}
    return {'name': name, 'kind': kind, 'input': {'message': 'Cho tôi hỏi giờ mở cửa hồ bơi', 'fixture_profile_id': 'resident-a'},
            'expectations': expected, 'rubric': RUBRIC}


async def drain(worker):
    while await worker.once():
        pass


def test_the_worker_runs_a_suite_end_to_end_and_only_an_isolated_sandbox_passes(database, sandbox_db, monkeypatch):
    for variable, value in (('VINHOMES_API_EVAL_SERVICE_TOKEN', 'w' * 40), ('VINHOMES_API_EVAL_SANDBOX_TOKEN', 's' * 40),
                            ('VINHOMES_API_EVALUATOR_URL', 'http://evaluator.test')):
        monkeypatch.setenv(variable, value)
    register_tools(database)
    source_settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True)
    sandbox_settings = V3Settings('127.0.0.1', 8000, sandbox_db['runtime'], sandbox_db['tenant'], None, None, demo_mode=True)
    with TestClient(create_app(source_settings), client=('127.0.0.1', 50000)) as source, \
            TestClient(create_app(sandbox_settings), client=('127.0.0.1', 50000)) as sandbox, \
            demo_client(database, 'management') as m:
        judge = ModelConfig('openai', 'judge', 'https://models.test/v1', 'k' * 40)
        settings = Settings('http://source', 'w' * 40, 'http://sandbox', 's' * 40, 'e2e', settle_seconds=0, case_seconds=30,
                            fallback_model=judge)

        async def play():
            async with httpx.AsyncClient(transport=Bridge({'source': source, 'sandbox': sandbox})) as client:
                worker = Worker(settings, client, sleep=lambda _: asyncio.sleep(0))
                await worker.register()
                await drain(worker)
        asyncio.run(play())
        agent = m.post(ROOM, json={'name': 'E2E ' + uuid4().hex[:6], 'instructions': 'x', 'idempotency_key': uuid4().hex}).json()['id']
        configuration = m.put(f'{ROOM}/{agent}/configuration', json={'instructions': 'Trả lời thắc mắc về tiện ích.', 'description': 'Tiện ích',
                                                                    'service_categories': [], 'mcp_tools': [TOOL]}).json()['configurationHash']
        listed = m.get(f'{ROOM}/{agent}/eval-suites').json()['environment']
        assert listed['ready'] and [f['fixture_profile_id'] for f in listed['fixtures']] == ['resident-a', 'resident-b', 'resident-c']
        cases = [case('Hỏi tiện ích', 'in_scope', agent), case('Hỏi lại', 'boundary', agent), case('Hỏi phí', 'boundary', agent),
                 case('Ngoài phạm vi', 'out_of_scope', agent)]
        suite = m.post(f'{ROOM}/{agent}/eval-suites', json={'configuration_hash': configuration, 'mode': 'manual', 'cases': cases}).json()
        assert suite['problems'] == [], suite
        suite = m.post(f"{ROOM}/{agent}/eval-suites/{suite['id']}/approve", json={'version': suite['version']}).json()

        def evaluate(request_id):
            run = m.post(f'{ROOM}/{agent}/eval-runs', json={'suite_id': suite['id'], 'configuration_hash': configuration, 'request_id': request_id})
            assert run.status_code == 202, run.text
            asyncio.run(play())
            return m.get(f"{ROOM}/{agent}/eval-runs/{run.json()['runId']}").json()

        unsafe = evaluate('e2e-1')
        assert unsafe['status'] == 'failed' and unsafe['error']['code'] == 'environment_unsafe', unsafe
        assert 'kết nối được database nguồn' in unsafe['error']['message']
        # Isolate the source as --isolate-source does: its own role keeps CONNECT, PUBLIC loses it.
        source_name = urlsplit(database['admin']).path.lstrip('/')
        sql(database, f'REVOKE CONNECT ON DATABASE "{source_name}" FROM PUBLIC')
        report = evaluate('e2e-2')
        assert report['status'] == 'completed', report
        # No Supervisor runs here, so the in-scope case never sees the agent take part: it fails on the code check,
        # however well the judge scored the reply. The other three pass.
        assert [c['status'] for c in report['cases']] == ['failed', 'passed', 'passed', 'passed'],             [(c['status'], c['failure_layers'], c['error']) for c in report['cases']]
        first = report['cases'][0]
        assert first['checks']['required_agents']['passed'] is False and first['judge']['status'] == 'scored'
        assert first['failure_layers'] == [{'layer': 'code', 'kind': 'failed', 'detail': 'required_agents'}]
        assert first['terminal_state'] == 'reply_only' and first['environment']['safe'] is True
        assert first['trace']['context']['tenant_id'] == str(sandbox_db['tenant'])
        assert report['passed'] is False and report['summary']['passed'] == 3
        assert sql(database, 'select count(*) as n from vh_agent_eval_events where run_id=$1', UUID(report['id']))[0]['n'] > 0
        # 3/4 is not a pass: no review is opened, so there is nothing BQL could publish.
        assert sql(database, "select id from vh_agent_reviews where agent_id=$1", agent) == []
