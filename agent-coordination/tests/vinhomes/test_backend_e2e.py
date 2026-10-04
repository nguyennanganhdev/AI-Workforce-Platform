"""Real migrated business API + coordination runtime; only the model/OpenBot are stubbed.

Install services/vinhomes-api[test] in this test environment. PostgreSQL is created
and removed by the resident contract fixture, never by the live demo runtime.
"""
import asyncio
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

import httpx
import pytest

pytest.importorskip('vinhomes_api')
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'services/vinhomes-api/tests'))
from test_resident_contract import database as database, sql
from test_v3_coordination import app, hand_over, publish_specialist, BASE, TOKEN
from test_v3_agent_database import demo_client, operation
from tests.vinhomes.test_runtime import Providers
from vinhomes.backend import Backend
from vinhomes.ports import OpenBot
from vinhomes.runtime import Runtime, Settings, Store


def test_management_decision_reaches_the_actual_resident_conversation(database, tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'model-key')
    monkeypatch.setenv('MANAGED_AGENT_TOKEN', 'bot-token')
    publish_specialist(database, 'E2E technical ' + uuid4().hex[:8], ['technical'])
    providers = Providers()
    with app(database) as resident:
        handoff, chat = hand_over(resident, 'Vòi bếp rò nước')
        team, ticket = handoff['team']['id'], handoff['ticket']['id']

        def transport(request):
            if request.url.host == 'backend':
                reply = resident.request(request.method, request.url.path, params=request.url.params,
                                         headers=dict(request.headers), content=request.content)
                return httpx.Response(reply.status_code, content=reply.content, headers=dict(reply.headers))
            return providers(request)

        settings = Settings(backend_url='http://backend', service_token=TOKEN, model='gpt-5.4-mini',
                            openbot=OpenBot('http://127.0.0.1:4200/ag-ui', 'gpt-5.4-mini'))
        async def cycle():
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                runtime = Runtime(Backend(settings.backend_url, TOKEN, client), Store(tmp_path / 'state.sqlite'),
                                  client=client, settings=settings)
                await runtime.round()
                return next(s for s in runtime.store.sessions() if s.get('ticket_id') == ticket)

        state = asyncio.run(cycle())
        assert state['phase'] == 'waiting_management', state
        with demo_client(database, 'management') as management:
            plan = management.get(f'/tickets/{ticket}/session').json()['room']['plan']
            decision = management.post(f"/plans/{plan['id']}/management-decision", json={
                'decision': 'approve', 'version': plan['version'], 'note': 'Đồng ý'})
            assert decision.status_code == 200, decision.text
        state = asyncio.run(cycle())  # a fresh Runtime reads the persisted checkpoint
        assert state['phase'] == 'waiting_resident_plan', state
        assert asyncio.run(cycle())['phase'] == 'waiting_resident_plan'
        messages = sql(database, "select body from messages where channel_id=$1 and body->>'source'='supervisor'", chat)
        assert len(messages) == 1
        text = json.loads(messages[0]['body'])['text']
        assert text.endswith('Anh/chị có đồng ý với phương án này không?')
        assert 'Chi phí dự kiến: chưa có' in text
        assert not sql(database, 'select id from work_orders where ticket_id=$1', UUID(ticket))
        assert providers.decisions == ['tasks', 'run', 'complete_task', 'plan']
        [item] = resident.get(BASE + '/inbox', headers={'Authorization': 'Bearer ' + TOKEN}).json()['items']
        source = resident.post(f'/resident/chats/{chat}/messages', json={
            'text': 'Tôi đồng ý', 'client_message_id': str(uuid4())}).json()
        current = resident.get(BASE + f'/teams/{team}/view', headers={'Authorization': 'Bearer ' + TOKEN}).json()
        from datetime import datetime, UTC
        reply = {**item['message'], 'message_id': str(uuid4()), 'message_type': 'plan_approved',
                 'message': 'Tôi đồng ý', 'source_message_id': source['id'],
                 'ticket_version': current['ticket_version'], 'sent_at': datetime.now(UTC).isoformat()}
        operation(resident, 'respond_supervisor_interaction', {'message': reply})
        state = asyncio.run(cycle())
        assert state['phase'] == 'execution_ready' and state['pause_reason'] is None
        assert len(sql(database, 'select id from work_orders where ticket_id=$1', UUID(ticket))) == 1
        assert asyncio.run(cycle())['phase'] == 'execution_ready'
        assert len(sql(database, 'select id from work_orders where ticket_id=$1', UUID(ticket))) == 1
