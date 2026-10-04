"""The knowledge base as a gateway tool of management's agents.

The search service is stood in for here, and it does what the real one does first: it hands the caller's
credential back to this API and asks who is searching.
"""
import asyncio
import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_coordination import BASE, SERVICE, TOKEN, publish_specialist
from vinhomes_api import v3_agent_knowledge
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings
from vinhomes_api.v3_tool_gateway import catalogue

AUTHORIZATION = '/internal/reception/v1/knowledge-authorization'


def test_a_granted_agent_searches_for_a_building_its_unit_covers_and_the_search_service_is_told_whose_run_it_is(database, monkeypatch):
    for t in catalogue():
        sql(database, "insert into mcp_servers(id,title,vendor,url,tenant_id) values($1,$1,'first-party','internal:tools',$2) on conflict(id) do nothing returning id", t['server_id'], TENANT)
        sql(database, "insert into mcp_tools(server_id,name,description,input_schema,effect,tenant_id) values($1,$2,$3,cast($4 as jsonb),$5,$6) on conflict(server_id,name) do nothing returning name",
            t['server_id'], t['name'], t['description'], json.dumps(t['input_schema']), t['effect'], TENANT)
    base = sql(database, """insert into knowledge_bases(tenant_id,domain_id,code,name,status)
        select tenant_id,domain_id,$1,'Test','active' from sites limit 1 returning id""", 'agents-' + uuid4().hex[:8])[0]['id']
    agent, _ = publish_specialist(database, 'Room rules ' + uuid4().hex[:8], [], tools=({'server_id': 'knowledge', 'name': 'knowledge.search'},))
    plain, _ = publish_specialist(database, 'Room plain ' + uuid4().hex[:8], [])
    asked, client = [], {}

    class SearchService:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert url == 'http://knowledge.test/internal/knowledge/search'
            # Its first act: who is this? The API is asked on another connection while the tool call is still open.
            verdict = await asyncio.to_thread(client['c'].post, AUTHORIZATION, headers=headers,
                                              json={'knowledgeBaseId': str(base), 'scopeId': json['scopeId']})
            asked.append((json, verdict.status_code, verdict.json()))
            if verdict.status_code != 200:
                return httpx.Response(verdict.status_code, json={'error': {'code': 'forbidden', 'message': 'Knowledge access denied.'}})
            return httpx.Response(200, json={'retrievalRunId': str(uuid4()), 'policyVersion': 'test', 'insufficientSources': False,
                                             'hits': [{'rank': 1, 'title': 'Nội quy tòa nhà', 'text': 'Giờ yên tĩnh từ 22:00 đến 06:00.'}]})

    monkeypatch.setenv('VINHOMES_API_KNOWLEDGE_URL', 'http://knowledge.test')
    monkeypatch.setattr(v3_agent_knowledge.httpx, 'AsyncClient', SearchService)
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as c:
        client['c'] = c

        def turn(who):
            message = c.post('/rooms/management-room/messages', json={'text': 'Giờ yên tĩnh là mấy giờ?', 'mention_agent_id': who,
                                                                      'client_message_id': str(uuid4())}).json()['id']
            path = BASE + f'/room-mentions/{message}/{who}'
            return path, c.post(path + '/turn', headers=SERVICE).json()

        path, started = turn(agent)
        assert [t['name'] for t in started['tools']] == ['knowledge__search']
        run = started['run_id']
        call = lambda run_id, **arguments: c.post(BASE + '/tools/call', headers=SERVICE,
            json={'run_id': run_id, 'tool': 'knowledge.search', 'arguments': arguments}).json()

        found = call(run, query='  Giờ yên tĩnh là mấy giờ?  ')
        assert found['status'] == 'OK' and found['data']['data']['hits'][0]['text'] == 'Giờ yên tĩnh từ 22:00 đến 06:00.', found
        sent, status, verdict = asked[-1]
        covered = sql(database, """select s.id,b.id as building from access_scopes s join buildings b on b.id=s.building_id
            join management_coverage mc on mc.scope_id=s.id where s.kind='building' limit 1""")[0]
        unit_scope = sql(database, "select id from access_scopes where kind='management'")[0]['id']
        assert sent == {'query': 'Giờ yên tĩnh là mấy giờ?', 'scopeId': str(covered['id']), 'topK': 5} and status == 200
        context = verdict['context']
        assert (context['userId'], context['roleCodes'], context['agentRunId'], context['targetScopeId']) == \
            ('local-v3-management', ['management'], run, str(covered['id']))
        # The building's own ancestors, and the unit's scope so documents published for management apply.
        assert str(unit_scope) in context['ancestorScopeIds'] and str(covered['id']) not in context['ancestorScopeIds']

        # A building the unit does not cover is refused before anything is searched, by the gateway and by the authority.
        elsewhere = sql(database, """select s.id,b.id as building from access_scopes s join buildings b on b.id=s.building_id
            where s.kind='building' and s.id not in (select scope_id from management_coverage) limit 1""")[0]
        searches = len(asked)
        assert call(run, query='x', building_id=str(elsewhere['building']))['status'] == 'FORBIDDEN' and len(asked) == searches
        credential = {'Authorization': 'Bearer ' + v3_agent_knowledge.credential(TOKEN, run)}
        assert c.post(AUTHORIZATION, headers=credential, json={'knowledgeBaseId': str(base), 'scopeId': str(elsewhere['id'])}).status_code == 403
        assert c.post(AUTHORIZATION, headers=credential, json={'knowledgeBaseId': str(uuid4()), 'scopeId': str(covered['id'])}).status_code == 403
        # A credential nobody made, or one made for a run under another key, names no run.
        for forged in ('run.' + run + '.' + '0' * 64, v3_agent_knowledge.credential('another-key', run)):
            assert c.post(AUTHORIZATION, headers={'Authorization': 'Bearer ' + forged},
                          json={'knowledgeBaseId': str(base), 'scopeId': str(covered['id'])}).status_code == 401
        assert call(run, query='')['status'] == 'INVALID_INPUT'

        # An agent whose pinned version does not hold the tool cannot use it, nor borrow the authority.
        _, other = turn(plain)
        assert call(other['run_id'], query='x')['status'] == 'FORBIDDEN'
        assert c.post(AUTHORIZATION, headers={'Authorization': 'Bearer ' + v3_agent_knowledge.credential(TOKEN, other['run_id'])},
                      json={'knowledgeBaseId': str(base), 'scopeId': str(covered['id'])}).status_code == 403

        # With more than one building in its coverage the agent has to say which one.
        zone = sql(database, """select s.id from access_scopes s join buildings b on b.zone_id=s.zone_id
            where s.kind='zone' and b.id=$1""", covered['building'])[0]['id']
        sql(database, """insert into management_coverage(tenant_id,management_unit_id,scope_id,service_category_id,valid_from)
            select tenant_id,management_unit_id,$1,service_category_id,now()-interval '1 day' from management_coverage limit 1 returning id""", zone)
        vague = call(run, query='Giờ yên tĩnh?')
        assert vague['status'] == 'TOOL_ERROR' and vague['errors'][0]['code'] == 'BUILDING_REQUIRED' and str(covered['building']) in vague['errors'][0]['message']
        assert call(run, query='Giờ yên tĩnh?', building_id=str(covered['building']))['status'] == 'OK'
        sql(database, 'delete from management_coverage where scope_id=$1 returning id', zone)

        # Once the run is over its credential opens nothing.
        assert c.post(path + '/outcome', headers=SERVICE, json={'run_id': run, 'status': 'done', 'content': 'Từ 22:00 đến 06:00.'}).status_code == 200
        assert c.post(AUTHORIZATION, headers=credential, json={'knowledgeBaseId': str(base), 'scopeId': str(covered['id'])}).status_code == 403
    audited = sql(database, "select payload->>'status' as status from audit_events where event_type='agent.tool_called' and target_id=$1 order by created_at", run)
    assert [a['status'] for a in audited] == ['OK', 'FORBIDDEN', 'INVALID_INPUT', 'TOOL_ERROR', 'OK']
