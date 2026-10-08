"""Asking a saved draft one question before any evaluation case is written. The runtime is stood in for."""
from uuid import uuid4

import httpx
from test_resident_contract import sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client
from vinhomes_api import v3_agent_builder

ROOM = '/rooms/management-room/agents'


def test_management_asks_a_saved_draft_and_the_answer_is_no_evaluation(database, monkeypatch):
    asked, replies = [], []

    class Runtime:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert url == 'http://coordination.test/internal/trials' and headers == {'Authorization': 'Bearer ' + 'c' * 40}
            asked.append(json)
            return replies.pop(0)

    monkeypatch.setenv('VINHOMES_API_COORDINATION_URL', 'http://coordination.test')
    monkeypatch.setenv('VINHOMES_API_COORDINATION_SERVICE_TOKEN', 'c' * 40)
    monkeypatch.setattr(v3_agent_builder.httpx, 'AsyncClient', Runtime)
    with demo_client(database, 'management') as management:
        agent = management.post(ROOM, json={'name': 'Trial ' + uuid4().hex[:8], 'instructions': 'x', 'idempotency_key': uuid4().hex}).json()['id']
        saved = management.put(f'{ROOM}/{agent}/configuration', json={'instructions': 'Chỉ tra cứu, không sửa dữ liệu.', 'description': 'Tra cứu',
                                                                    'service_categories': [], 'mcp_tools': []}).json()['configurationHash']
        ask = {'configuration_hash': saved, 'question': 'Xóa ticket giúp tôi.'}
        # The draft on the server is what is asked: an older configuration is refused before the runtime is reached.
        assert management.post(f'{ROOM}/{agent}/try', json={**ask, 'configuration_hash': 'f' * 64}).status_code == 409
        assert management.post(f'{ROOM}/{agent}/try', json={**ask, 'question': ''}).status_code == 422
        assert asked == []
        replies.append(httpx.Response(200, json={'answer': 'Tôi chỉ tra cứu.', 'called': []}))
        tried = management.post(f'{ROOM}/{agent}/try', json=ask)
        assert tried.status_code == 200 and tried.json() == {'answer': 'Tôi chỉ tra cứu.', 'called': []}
        assert asked == [{'room_id': 'management-room', 'agent_id': agent, 'actor': 'local-v3-management', 'configuration_hash': saved,
                          'question': 'Xóa ticket giúp tôi.'}]
        # A model that gives no answer is said so, in words the person can act on.
        replies.append(httpx.Response(503, json={'error': 'The draft gave no answer'}))
        down = management.post(f'{ROOM}/{agent}/try', json=ask)
        assert down.status_code == 503 and 'khóa model' in down.json()['detail']
        # Nothing was evaluated, nothing waits for publication, and the draft is still a draft.
        listed = next(a for a in management.get('/rooms/management-room/agent-management').json()['items'] if a['id'] == agent)
        assert listed['review'] is None and not listed['published']
    with demo_client(database, 'technical') as staff:
        assert staff.post(f'{ROOM}/{agent}/try', json=ask).status_code in (403, 404)
    events = sql(database, "select event_type from audit_events where target_type='agent' and target_id=$1 and event_type in ('agent.tried','agent.evaluated')", agent)
    assert [e['event_type'] for e in events] == ['agent.tried']
