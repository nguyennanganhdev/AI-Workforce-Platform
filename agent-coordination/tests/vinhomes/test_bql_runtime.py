"""BQL evaluation retries and room turn recovery do not silently rebill a model."""
import httpx
import pytest
from starlette.testclient import TestClient
from vinhomes.runtime import Settings, Store, Runtime, create_app
from vinhomes.ports import OpenBot
from vinhomes.ports import ToolGateway
from vinhomes.publish import dotted

TOKEN = 'service-test-credential-0123456789abcdef'


@pytest.mark.asyncio
async def test_multi_segment_tool_names_reach_the_authorized_gateway():
    from types import SimpleNamespace
    import json
    sent = []
    def producer(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={'status': 'OK', 'data': {}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(producer)) as client:
        gateway = ToolGateway(client, 'http://gateway/call', TOKEN)
        reply = await gateway.execute_authorized(SimpleNamespace(source_run_id='run'), None,
            'security__camera__read', {'building_id': 'building'}, 'operation', 'run', 'call')
    assert dotted('security__camera__read') == 'security.camera.read'
    assert sent == [{'run_id': 'run', 'tool': 'security.camera.read', 'arguments': {'building_id': 'building'}}]
    assert reply['result']['status'] == 'OK'


def request():
    return {'room_id': 'room', 'agent_id': 'agent', 'actor': 'manager', 'request_id': 'round-1',
        'configuration_hash': 'a' * 64,
        'cases': [{'name': f'case-{i}', 'instruction': 'answer', 'expected': 'ok', 'must': ['ok']} for i in range(6)]}


def transport(req):
    if req.url.path.endswith('/agent-evaluations/view'):
        return httpx.Response(200, json={'instructions': 'Only read', 'tools': []})
    if req.url.path.endswith('/inbox'):
        return httpx.Response(200, json={'items': [], 'next_cursor': None})
    return httpx.Response(200, json={'items': []})


def test_evaluation_requires_service_and_replays_across_restart_without_model_calls(tmp_path, monkeypatch):
    calls = []
    async def answer(*args, **kwargs):
        calls.append(1)
        return 'ok', []
    monkeypatch.setattr('vinhomes.publish.answer', answer)
    monkeypatch.setenv('MANAGED_AGENT_TOKEN', 'test-bot-token')
    settings = Settings('http://backend', TOKEN, str(tmp_path / 'state.sqlite'),
        openbot=OpenBot('http://bot/ag-ui', 'test-model'))
    auth = {'Authorization': 'Bearer ' + TOKEN}
    body = request()
    with TestClient(create_app(settings, transport=httpx.MockTransport(transport))) as c:
        assert c.post('/internal/evaluations', json=body).status_code == 401
        assert c.post('/internal/evaluations', json={'cases': None}, headers=auth).status_code == 422
        assert c.post('/internal/evaluations', content='x' * 140000, headers=auth).status_code == 413
        result = c.post('/internal/evaluations', json=body, headers=auth)
        assert result.status_code == 200 and all(case['passed'] for case in result.json()['cases'])
        assert len(calls) == 6
        assert c.post('/internal/evaluations', json={**body, 'cases': [{**case, 'instruction': 'changed'} for case in body['cases']]}, headers=auth).status_code == 409
    with TestClient(create_app(settings, transport=httpx.MockTransport(transport))) as c:
        replay = c.post('/internal/evaluations', json=body, headers=auth)
        assert replay.json() == result.json() and len(calls) == 6


@pytest.mark.asyncio
async def test_interrupted_room_turn_is_failed_without_a_second_generation(tmp_path, monkeypatch):
    class Backend:
        outcomes = []
        async def room_turn(self, message, agent):
            return {'run_id': 'run', 'instructions': 'Read only', 'tools': [], 'instruction': 'question', 'messages': []}
        async def room_outcome(self, message, agent, result):
            self.outcomes.append(result)
    async def forbidden(*args, **kwargs):
        raise AssertionError('Interrupted turn must not call the model again')
    monkeypatch.setattr('vinhomes.publish.answer', forbidden)
    store = Store(tmp_path / 'state.sqlite')
    import json
    key = json.dumps(('tenant', 'message', 'agent'))
    await store.put_once('room_mention_intent', key, 'run')
    backend = Backend()
    runtime = Runtime(backend, store, settings=Settings('http://backend', TOKEN, openbot=OpenBot('http://bot', 'model')))
    item = {'tenant_id': 'tenant', 'message_id': 'message', 'agent_id': 'agent'}
    await runtime.answer_room(item)
    await runtime.answer_room(item)
    assert [r['status'] for r in backend.outcomes] == ['failed', 'failed']
