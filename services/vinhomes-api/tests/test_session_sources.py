"""Actor-scoped request sources, pinned explicit turns and one-shot external write decisions."""
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import database as database
from test_v3_agent_database import demo_client
from test_v3_coordination import publish_specialist, verified_team, app, TOKEN, SERVICE, BASE
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings


def test_session_sources_actor_binding_read_only_automation_and_per_call_write(database, monkeypatch):
    from vinhomes_api import v3_connections
    called = []
    async def host(path, payload, **kwargs):
        if path == '/tools':
            return {'tools': [{'name': 'create_event', 'description': 'Tạo lịch kiểm tra thiết bị với nội dung và thời gian đã chọn',
                              'effect': 'write', 'inputSchema': {'type': 'object'}}]}
        if path == '/call':
            called.append(payload)
            return {'text': 'Đã tạo lịch kiểm tra.', 'isError': False}
        return {'ok': True}
    monkeypatch.setattr(v3_connections, 'host', host)
    with demo_client(database, 'management') as manager:
        made = manager.post('/rooms/management-room/connections', json={'title': 'Lịch bảo trì '+uuid4().hex[:8],
                            'url': 'https://calendar.example/mcp', 'allowed_tools': ['create_event']})
        assert made.status_code == 201, made.text
        server = made.json()['id']
    tool = server + '.create_event'
    agent, version = publish_specialist(database, 'Agent lịch '+uuid4().hex, ['technical'], ({'server_id': server, 'name': tool},))
    with app(database) as resident:
        team = verified_team(resident, database, 'Kiểm tra máy nước nóng '+uuid4().hex[:6])
        admitted = resident.post(BASE+f'/teams/{team}/members', headers=SERVICE, json={'agent_version_id': version})
        assert admitted.status_code == 200, admitted.text
        member = admitted.json()['member_id']
        automated = resident.post(BASE+f'/teams/{team}/members/{member}/runs', headers=SERVICE, json={'operation_id': uuid4().hex}).json()['run_id']
        release = resident.get(BASE+f'/teams/{team}/members/{member}/release', headers=SERVICE)
        assert release.status_code == 200 and not release.json()['tool_descriptors']
        assert resident.post(BASE+'/tools/call', headers=SERVICE, json={'run_id': automated, 'tool': tool, 'arguments': {}}).json()['status'] == 'FORBIDDEN'
    ticket = str(sql(database, 'select ticket_id from agent_teams where id=$1', UUID(team))[0]['ticket_id'])
    endpoint = f'/tickets/{ticket}/session'
    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as manager:
        sources = manager.get(endpoint+'/sources')
        assert sources.status_code == 200, sources.text
        assert next(s for s in sources.json()['items'] if s['id'] == server)['enabled'] is False
        asked = manager.post(endpoint+'/questions', json={'text': 'Tạo lịch kiểm tra lúc 18 giờ', 'agent_id': agent, 'client_message_id': uuid4().hex})
        assert asked.status_code == 201, asked.text
        question = asked.json()['id']
        assert any(str(q['message_id']) == question for q in manager.get(BASE+'/session-mentions', headers=SERVICE).json()['items'])
        assert not any(q['message_id'] == question for q in manager.get(BASE+'/mentions', headers=SERVICE).json()['items'])
        turn_path = BASE+f'/teams/{team}/mentions/{question}/turn'
        turn = manager.post(turn_path, headers=SERVICE)
        assert turn.status_code == 200, turn.text
        assert not turn.json()['tools']
        run = turn.json()['run_id']
        args = {'title': 'Kiểm tra căn hộ', 'starts_at': '2026-10-08T18:00:00+07:00'}
        call = {'run_id': run, 'tool': tool, 'arguments': args}
        assert manager.post(BASE+'/tools/call', headers=SERVICE, json=call).json()['status'] == 'FORBIDDEN'
        assert not called
        enabled = manager.put(endpoint+'/sources', json={'server_id': server, 'enabled': True})
        assert enabled.status_code == 200, enabled.text
        pinned = manager.post(turn_path, headers=SERVICE)
        assert pinned.status_code == 200 and pinned.json()['run_id'] == run
        assert pinned.json()['tools'][0]['name'] == tool.replace('.', '__')
        waiting = manager.post(BASE+'/tools/call', headers=SERVICE, json=call)
        assert waiting.status_code == 200, waiting.text
        assert waiting.json()['status'] == 'AWAITING_CONFIRMATION' and not called
        confirmation = waiting.json()['data']['confirmation']['id']
        row = sql(database, 'select actor_user_id,session_id,request_message_id,arguments,status from vh_external_call_confirmations where id=$1', UUID(confirmation))[0]
        assert row['actor_user_id'] == 'local-v3-management' and row['session_id'] == UUID(team) and row['request_message_id'] == UUID(question) and row['status'] == 'pending'
        with demo_client(database, 'admin') as admin:
            assert admin.get(endpoint+'/external-calls').status_code == 403
            assert admin.put(endpoint+'/sources', json={'server_id': server, 'enabled': True}).status_code == 403
        with demo_client(database, 'technical') as staff:
            assert staff.post(endpoint+f'/external-calls/{confirmation}/decision', json={'decision': 'approve'}).status_code in (403, 404)
        # Disabling the actor's consent after generation invalidates the pending confirmation.
        assert manager.put(endpoint+'/sources', json={'server_id': server, 'enabled': False}).status_code == 200
        decision = endpoint+f'/external-calls/{confirmation}/decision'
        assert manager.post(decision, json={'decision': 'approve'}).status_code == 403 and not called
        assert manager.put(endpoint+'/sources', json={'server_id': server, 'enabled': True}).status_code == 200
        done = manager.post(decision, json={'decision': 'approve'})
        assert done.status_code == 200, done.text
        assert done.json()['status'] == 'succeeded' and len(called) == 1 and called[0]['arguments'] == args
        assert manager.post(decision, json={'decision': 'approve'}).status_code == 409 and len(called) == 1
        outcome = manager.post(BASE+f'/teams/{team}/mentions/{question}/outcome', headers=SERVICE,
                               json={'status': 'done', 'run_id': run, 'content': 'Đã tạo lịch kiểm tra theo xác nhận của bạn.'})
        assert outcome.status_code == 200, outcome.text
        detail = manager.get(endpoint)
        assert detail.status_code == 200 and any(r['text'] == 'Đã tạo lịch kiểm tra theo xác nhận của bạn.' for r in detail.json()['room']['replies'])
        assert next(c for c in manager.get(endpoint+'/external-calls').json()['items'] if str(c['id']) == confirmation)['status'] == 'succeeded'
