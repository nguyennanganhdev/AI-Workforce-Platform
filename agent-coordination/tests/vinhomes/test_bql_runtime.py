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


def test_a_trial_question_is_answered_once_and_is_no_evaluation(tmp_path, monkeypatch):
    asked = []
    async def answer(client, instructions, case, tools, defaults, **options):
        asked.append((instructions, case['instruction'], case['name']))
        if case['instruction'] == 'down':
            raise httpx.ConnectError('no model')
        return 'Tôi chỉ tra cứu.', ['reporting.filter_report_scope']
    monkeypatch.setattr('vinhomes.publish.answer', answer)
    monkeypatch.setenv('MANAGED_AGENT_TOKEN', 'test-bot-token')
    settings = Settings('http://backend', TOKEN, str(tmp_path / 'state.sqlite'), openbot=OpenBot('http://bot/ag-ui', 'test-model'))
    auth = {'Authorization': 'Bearer ' + TOKEN}
    body = {'room_id': 'room', 'agent_id': 'agent', 'actor': 'manager', 'configuration_hash': 'a' * 64, 'question': 'Bạn làm được gì?'}
    with TestClient(create_app(settings, transport=httpx.MockTransport(transport))) as c:
        assert c.post('/internal/trials', json=body).status_code == 401
        assert c.post('/internal/trials', json={**body, 'question': ''}, headers=auth).status_code == 422
        first = c.post('/internal/trials', json=body, headers=auth)
        assert first.status_code == 200 and first.json() == {'answer': 'Tôi chỉ tra cứu.', 'called': ['reporting.filter_report_scope']}
        # The saved draft's own instructions, and a thread of its own each time: nothing is replayed, nothing is stored.
        assert c.post('/internal/trials', json=body, headers=auth).status_code == 200
        assert [a[:2] for a in asked] == [('Only read', 'Bạn làm được gì?')] * 2 and asked[0][2] != asked[1][2]
        # A model that does not answer is said so; it is not an answer of the draft.
        assert c.post('/internal/trials', json={**body, 'question': 'down'}, headers=auth).status_code == 503


@pytest.mark.asyncio
async def test_photos_on_a_room_question_reach_the_bot_as_pictures_beside_the_text(tmp_path, monkeypatch):
    import json
    wires = []
    def bot(req):
        body = json.loads(req.content)
        wires.append(body)
        run = {'threadId': body['threadId'], 'runId': body['runId']}
        events = [{'type': 'RUN_STARTED', **run}, {'type': 'TEXT_MESSAGE_START', 'messageId': 'm', 'role': 'assistant'},
                  {'type': 'TEXT_MESSAGE_CONTENT', 'messageId': 'm', 'delta': 'Vết rò ở chân vòi.'},
                  {'type': 'TEXT_MESSAGE_END', 'messageId': 'm'}, {'type': 'RUN_FINISHED', **run}]
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                              content=''.join(f'data: {json.dumps(e)}\n\n' for e in events).encode())

    class Backend:
        outcomes = []
        def __init__(self, images): self.images = images
        async def room_turn(self, message, agent):
            return {'run_id': 'run-' + message, 'instructions': 'Read only', 'tools': [], 'instruction': 'Ảnh này rò ở đâu?', 'messages': [],
                    **({'images': self.images} if self.images is not None else {})}
        async def room_outcome(self, message, agent, result):
            self.outcomes.append(result)

    monkeypatch.setenv('MANAGED_AGENT_TOKEN', 'test-bot-token')
    settings = Settings('http://backend', TOKEN, openbot=OpenBot('http://bot/ag-ui', 'model'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(bot)) as client:
        for message, images in (('with', [{'name': 'vet-ro.png', 'mimeType': 'image/png', 'data': 'aGVsbG8='}]), ('without', None)):
            backend = Backend(images)
            runtime = Runtime(backend, Store(tmp_path / f'{message}.sqlite'), client=client, settings=settings)
            await runtime.answer_room({'tenant_id': 'tenant', 'message_id': message, 'agent_id': 'agent'})
            assert backend.outcomes[-1]['status'] == 'done' and backend.outcomes[-1]['content'] == 'Vết rò ở chân vòi.'
    shown, plain = (wire['messages'][0]['content'] for wire in wires)
    # The question as text, then each photo as the part the Bot turns into a picture for the model.
    assert [part['type'] for part in shown] == ['text', 'image'] and json.loads(shown[0]['text'])['instruction'] == 'Ảnh này rò ở đâu?'
    assert shown[1] == {'type': 'image', 'source': {'type': 'data', 'value': 'aGVsbG8=', 'mimeType': 'image/png'}}
    # A question with no photo is sent exactly as before: one string.
    assert isinstance(plain, str) and json.loads(plain)['instruction'] == 'Ảnh này rò ở đâu?'


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

@pytest.mark.asyncio
async def test_explicit_session_question_uses_actor_bound_turn_and_preserves_ticket_context(tmp_path, monkeypatch):
    generated = []
    class Backend:
        outcomes = []
        async def session_turn(self, team, message):
            assert (team, message) == ('team', 'question')
            return {'run_id': 'actor-run', 'instructions': 'Wait for each external write confirmation',
                    'tools': [{'name': 'calendar__create_event'}], 'instruction': 'Tạo lịch kiểm tra',
                    'ticket': {'title': 'Máy nước nóng không nóng', 'unit_code': '1201'}, 'messages': []}
        async def room_tool(self, run, tool, arguments):
            assert run == 'actor-run'
            return {'status': 'AWAITING_CONFIRMATION', 'data': {'confirmation': {'arguments': arguments}}}
        async def session_outcome(self, team, message, result):
            assert (team, message) == ('team', 'question')
            self.outcomes.append(result)
        async def room_turn(self, *args):
            raise AssertionError('Request question must not use the unbound room turn')
    async def answer(client, instructions, payload, tools, context, **kwargs):
        generated.append(payload)
        assert payload['ticket'] == {'title': 'Máy nước nóng không nóng', 'unit_code': '1201'}
        pending = await kwargs['invoke_tool']('calendar.create_event', {'title': 'Kiểm tra'})
        assert pending['status'] == 'AWAITING_CONFIRMATION'
        return 'Thao tác đang chờ bạn cho phép.', []
    monkeypatch.setattr('vinhomes.publish.answer', answer)
    monkeypatch.setenv('MANAGED_AGENT_TOKEN', 'test-token')
    backend = Backend()
    runtime = Runtime(backend, Store(tmp_path / 'session.sqlite'), settings=Settings('http://backend', TOKEN, openbot=OpenBot('http://bot', 'model')))
    item = {'kind': 'session-mention', 'tenant_id': 'tenant', 'team_id': 'team', 'message_id': 'question', 'agent_id': 'specialist'}
    await runtime.answer_room(item)
    await runtime.answer_room(item)
    assert len(generated) == 1
    assert backend.outcomes[-1] == {'run_id': 'actor-run', 'status': 'done', 'content': 'Thao tác đang chờ bạn cho phép.'}
