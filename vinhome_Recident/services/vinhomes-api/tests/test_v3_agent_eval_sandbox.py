"""The sandbox's routes on a database that holds the sandbox marker (its own test database, like a real sandbox).

The resident's message goes through the production route; in demo mode that route answers with its canned
Reception reply, which is enough to read back a trace. The gateway keeps full tool calls only here.
"""
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_coordination import register_tools
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

SANDBOX = '/internal/agent-eval/sandbox/v1'
AUTH = {'Authorization': 'Bearer ' + 's' * 40}
COORDINATION = 'c' * 40
TOOL = {'server_id': 'technical-tools', 'name': 'technical.get_active_outage'}


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv('VINHOMES_API_EVAL_SANDBOX_TOKEN', 's' * 40)


@contextmanager
def sandbox(database):
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True,
                          coordination_service_token=COORDINATION)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000)) as c:
        yield c


@pytest.fixture(scope='module')
def marked(database):
    """The marker and one fixture resident: what scripts/provision_eval_sandbox.py writes."""
    sql(database, "insert into vh_agent_eval_sandbox(tenant_id,source_database,fixture_version) values($1,'vinhomes_source_test','fx-1')", TENANT)
    home = sql(database, "select r.unit_id,u.building_id from unit_residents r join units u on u.id=r.unit_id where r.user_id='local-v3-resident' limit 1")[0]
    sql(database, "insert into vh_agent_eval_fixtures(tenant_id,id,user_id,unit_id,building_id,description) values($1,'resident-a','local-v3-resident',$2,$3,'Cư dân mẫu')",
        TENANT, home['unit_id'], home['building_id'])
    register_tools(database)
    return {**home, 'database': database}


def test_catalog_and_attestation_describe_the_sandbox(marked):
    with sandbox(marked['database']) as c:
        assert c.get(SANDBOX + '/catalog').status_code == 401
        catalog = c.get(SANDBOX + '/catalog', headers=AUTH).json()
        assert catalog['fixtures'][0]['fixture_profile_id'] == 'resident-a' and catalog['fixture_version'] == 'fx-1'
        assert {(t['server_id'], t['name']) for t in catalog['tools']} >= {(TOOL['server_id'], TOOL['name'])}
        facts = c.get(SANDBOX + '/attestation', headers=AUTH).json()
        assert facts['rolsuper'] is False and facts['rolbypassrls'] is False and facts['source_database'] == 'vinhomes_source_test'
        assert facts['tenant_id'] == str(TENANT) and facts['database'].startswith('resident_contract_test_')


def test_install_makes_the_copies_the_only_published_specialists(marked):
    database = marked['database']
    with sandbox(database) as c:
        bad = c.post(SANDBOX + '/install', headers=AUTH, json={'run_id': str(uuid4()), 'agents': [
            {'source_id': 'a1', 'name': 'A', 'configuration': {'instructions': 'x', 'mcp_tools': [{'server_id': 'nowhere', 'name': 'x'}]}}]})
        assert bad.status_code == 409 and 'environment_unsupported' in bad.json()['detail']
        body = {'run_id': str(uuid4()), 'agents': [
            {'source_id': 'source-agent', 'name': 'Agent kỹ thuật', 'configuration': {'instructions': 'Phân tích sự cố.', 'description': 'Kỹ thuật',
             'service_categories': ['technical'], 'mcp_tools': [TOOL], 'model_id': 'not-in-this-database'}}]}
        first = c.post(SANDBOX + '/install', headers=AUTH, json=body).json()
        copy = first['agents']['source-agent']
        second = c.post(SANDBOX + '/install', headers=AUTH, json=body).json()
        assert second['agents']['source-agent'] == copy and second['versions']['source-agent'] != first['versions']['source-agent']
    published = sql(database, "select a.id from agent_releases r join agents a on a.id=r.agent_id where r.status='published' and r.revoked_at is null "
                              "and a.purpose='specialist' and a.workspace_id=(select workspace_id from channels where id=$1)", first['room_id'])
    assert [p['id'] for p in published] == [copy]
    # A Supervisor session runs a version only with an approved review of the same configuration.
    approved = sql(database, "select 1 from vh_agent_reviews r join agent_versions v on v.agent_id=r.agent_id and v.config_hash=r.config_hash "
                             "where r.agent_id=$1 and r.status='approved' and v.id=$2", copy, UUID(second['versions']['source-agent']))
    assert len(approved) == 1
    stored = sql(database, 'select configuration from agents where id=$1', copy)[0]['configuration']
    assert 'not-in-this-database' not in stored


def test_a_fixture_conversation_runs_through_the_resident_route_and_reads_back_as_a_trace(marked):
    with sandbox(marked['database']) as c:
        assert c.post(SANDBOX + '/conversations', headers=AUTH, json={'fixture_profile_id': 'someone-real', 'title': 'x'}).status_code == 404
        channel = c.post(SANDBOX + '/conversations', headers=AUTH, json={'fixture_profile_id': 'resident-a', 'title': 'Ca 1'}).json()['channel_id']
        said = c.post(f'{SANDBOX}/conversations/{channel}/messages', headers=AUTH, json={'text': 'Nhà tôi mất nước', 'client_message_id': 'k1'})
        assert said.status_code == 201, said.text
        read = c.get(f'{SANDBOX}/conversations/{channel}/trace', headers=AUTH).json()
        trace = read['trace']
        assert [m['role'] for m in trace['messages']][0] == 'resident'
        assert trace['final_response'] and trace['terminal_state'] == 'reply_only' and trace['ticket_ids'] == []
        assert trace['context']['resident_id'] == 'local-v3-resident' and trace['context']['unit_id'] == str(marked['unit_id'])
        assert read['progress']['awaiting_reception'] is False
        assert c.post(f'{SANDBOX}/conversations/{channel}/close', headers=AUTH).json() == {'tickets': [], 'teams': []}
        # Only fixture residents' conversations are reachable.
        assert c.get(f'{SANDBOX}/conversations/{uuid4()}/trace', headers=AUTH).status_code == 404


def test_the_gateway_keeps_full_calls_only_in_the_sandbox(marked):
    database = marked['database']
    run = uuid4()
    with sandbox(database) as c:
        refused = c.post('/internal/coordination/v1/tools/call', headers={'Authorization': 'Bearer ' + COORDINATION},
                         json={'run_id': str(run), 'tool': TOOL['name'], 'arguments': {'building_id': str(marked['building_id'])}})
        assert refused.json()['status'] == 'FORBIDDEN'
    kept = sql(database, 'select server_id,tool,arguments,status from vh_agent_eval_tool_traces where agent_run_id=$1', run)
    assert len(kept) == 1 and kept[0]['server_id'] == TOOL['server_id'] and kept[0]['status'] == 'FORBIDDEN'
    assert UUID(str(marked['building_id'])).hex in kept[0]['arguments'].replace('-', '')


def test_a_copy_names_its_model_by_provider_and_name_and_an_unknown_one_is_unsupported(marked):
    database = marked['database']
    copy = {'source_id': 'model-agent', 'name': 'M', 'configuration': {'instructions': 'x', 'mcp_tools': []}}
    with sandbox(database) as c:
        missing = c.post(SANDBOX + '/install', headers=AUTH, json={'run_id': str(uuid4()), 'agents': [{**copy, 'model': {'provider': 'openai', 'model_name': 'gpt-unknown'}}]})
        assert missing.status_code == 409 and 'model openai/gpt-unknown' in missing.json()['detail']
        admin = sql(database, 'select user_id from platform_admins order by user_id limit 1')[0]['user_id']
        model = sql(database, "insert into admin_model_registry(tenant_id,name,provider,kind,credential_env,created_by,check_status) "
                              "values($1,'gpt-known','openai','chat','OPENAI_API_KEY',$2,'ok') returning id", TENANT, admin)[0]['id']
        found = c.post(SANDBOX + '/install', headers=AUTH, json={'run_id': str(uuid4()), 'agents': [{**copy, 'model': {'provider': 'openai', 'model_name': 'gpt-known'}}]})
        assert found.status_code == 200, found.text
    stored = sql(database, 'select configuration from agents where id=$1', found.json()['agents']['model-agent'])[0]['configuration']
    assert str(model) in stored


def test_a_question_back_and_a_question_passed_to_management_are_where_the_conversation_stands(marked):
    database = marked['database']
    with sandbox(database) as c:
        channel = c.post(SANDBOX + '/conversations', headers=AUTH, json={'fixture_profile_id': 'resident-a', 'title': 'Ca hỏi lại'}).json()['channel_id']
        c.post(f'{SANDBOX}/conversations/{channel}/messages', headers=AUTH, json={'text': 'Nhà tôi mất điện', 'client_message_id': 'q1'})
        # Reception's own question, marked the way its intake rules mark it (v3_reception_runtime.write_reply).
        sql(database, """update messages set body=jsonb_build_object('text','Sự cố ở thiết bị nào? Chưa rõ thì cứ nói chưa rõ nhé.','clarification','item')
            where channel_id=$1 and sender_kind='agent' returning id""", channel)
        assert c.get(f'{SANDBOX}/conversations/{channel}/trace', headers=AUTH).json()['trace']['terminal_state'] == 'information_requested'
        # The same conversation once Reception passed the question to management: a person answers, no Supervisor works on it.
        sql(database, "update messages set body=jsonb_build_object('text','Mình đã chuyển câu hỏi của bạn đến Ban quản lý.') where channel_id=$1 and sender_kind='agent' returning id", channel)
        asked = sql(database, "select id from messages where channel_id=$1 and sender_kind='user'", channel)[0]['id']
        room = sql(database, "select c.id,c.workspace_id,(select id from agents where purpose='supervisor' and workspace_id=c.workspace_id limit 1) as supervisor "
                             "from channels c where c.kind='management' and c.workspace_id is not null limit 1")[0]
        sql(database, """insert into agent_teams(tenant_id,workspace_id,channel_id,request_message_id,supervisor_agent_id,status,shared_state)
            values($1,$2,$3,$4,$5,'queued','{"request": {"kind": "inquiry"}}') returning id""", TENANT, room['workspace_id'], room['id'], asked, room['supervisor'])
        read = c.get(f'{SANDBOX}/conversations/{channel}/trace', headers=AUTH).json()
        assert read['trace']['terminal_state'] == 'approval_pending' and read['progress']['working'] is False
        # A Supervisor that paused to hand the request to people is not working on it, though its session row says running.
        sql(database, "update agent_teams set status='running',shared_state='{\"runtime\": {\"phase\": \"paused\", \"pauseReason\": \"planner:cần người trực xử lý\"}}' "
                      "where request_message_id=$1 returning id", asked)
        handed = c.get(f'{SANDBOX}/conversations/{channel}/trace', headers=AUTH).json()
        assert handed['trace']['terminal_state'] == 'approval_pending' and handed['progress']['working'] is False
        assert c.post(f'{SANDBOX}/conversations/{channel}/close', headers=AUTH).json()['teams'] != []
