"""Schedules of management's agents: who may set one, and what a firing does in the room.

The schedule service (the platform's routine store and sweep) is stood in for here: it keeps rows through
its own connection while the API's request is still open, as the real one does.
"""
import asyncio
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from test_resident_contract import TENANT, sql
from test_resident_contract import (
    database as database,  # noqa: PLC0414 -- pytest fixture export
)
from test_v3_agent_database import demo_client
from test_v3_coordination import BASE, SERVICE, TOKEN, publish_specialist
from vinhomes_api import v3_routines
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings

ROOM = '/rooms/management-room/routines'
HOST = {'Authorization': 'Bearer ' + 'h' * 40}


def schedule_service(database, monkeypatch):
    seen = []

    class Host:
        def __init__(self, **options): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *error): return False
        async def post(self, url, headers, json):
            assert headers == HOST
            path = url.removeprefix('http://routines.test/internal/routines/v1')
            seen.append((path, json))
            if path == '':
                made = 'routine_' + uuid4().hex
                await asyncio.to_thread(sql, database, "insert into routines(id,owner_user_id,agent_id,channel_id,instruction,cron,timezone,next_run_at,tenant_id) "
                              "values($1,$2,$3,$4,$5,$6,$7,now()+interval '1 day',$8) returning id", made, json['ownerUserId'], json['agentId'],
                    json['channelId'], json['instruction'], json['cron'], json['timezone'], TENANT)
                return httpx.Response(201, json={'id': made, 'nextRunAt': '2026-10-06T01:00:00.000Z'})
            made = path.split('/')[1]
            if path.endswith('/enabled'):
                await asyncio.to_thread(sql, database, 'update routines set enabled=$2 where id=$1 and owner_user_id=$3 returning id', made, json['enabled'], json['ownerUserId'])
            else:
                await asyncio.to_thread(sql, database, 'delete from routine_runs where routine_id=$1 returning id', made)
                await asyncio.to_thread(sql, database, 'delete from routines where id=$1 and owner_user_id=$2 returning id', made, json['ownerUserId'])
            return httpx.Response(200, json={'ok': True})

    monkeypatch.setenv('VINHOMES_API_ROUTINES_URL', 'http://routines.test/internal/routines/v1')
    monkeypatch.setenv('VINHOMES_API_ROUTINES_TOKEN', 'h' * 40)
    monkeypatch.setattr(v3_routines.httpx, 'AsyncClient', Host)
    return seen


def due_run(database, routine):
    """What the sweep does when a schedule is due: it opens a run and hands its id to the API."""
    run = 'routine_run_' + uuid4().hex
    sql(database, 'insert into routine_runs(id,routine_id,scheduled_for,tenant_id) values($1,$2,now(),$3) returning id', run, routine, TENANT)
    return run


def test_management_schedules_a_published_agent_and_a_firing_is_a_mention_in_the_room(database, monkeypatch):
    seen = schedule_service(database, monkeypatch)
    agent, _ = publish_specialist(database, 'Scheduled report ' + uuid4().hex[:8], [])
    weekday_mornings = {'agent_id': agent, 'instruction': 'Tóm tắt các yêu cầu hôm qua.', 'hour': 8, 'minute': 0, 'days': [5, 1, 2, 3, 4]}
    with demo_client(database, 'technical') as staff:
        assert staff.get(ROOM).status_code in (403, 404)
        assert staff.post(ROOM, json=weekday_mornings).status_code in (403, 404)
    with demo_client(database, 'management') as management:
        draft = management.post('/rooms/management-room/agents', json={'name': 'Draft ' + uuid4().hex[:8], 'instructions': 'x',
                                                                      'idempotency_key': uuid4().hex}).json()['id']
        unpublished = management.post(ROOM, json={**weekday_mornings, 'agent_id': draft})
        assert unpublished.status_code == 422 and 'phát hành' in unpublished.json()['detail']
        assert management.post(ROOM, json={**weekday_mornings, 'days': [7]}).status_code == 422
        assert seen == []
        made = management.post(ROOM, json=weekday_mornings)
        assert made.status_code == 201, made.text
        routine = made.json()['id']
        assert seen == [('', {'ownerUserId': 'local-v3-management', 'agentId': agent, 'channelId': 'management-room',
                               'instruction': 'Tóm tắt các yêu cầu hôm qua.', 'cron': '0 8 * * 1,2,3,4,5', 'timezone': 'Asia/Ho_Chi_Minh'})]
        listed = management.get(ROOM).json()
        row = next(i for i in listed['items'] if i['id'] == routine)
        assert listed['timezone'] == 'Asia/Ho_Chi_Minh' and row['schedule'] == {'minute': 0, 'hour': 8, 'days': [1, 2, 3, 4, 5]}
        assert (row['agent_id'], row['enabled'], row['last_status']) == (agent, True, None) and row['owner_name']

    settings = V3Settings('127.0.0.1', 8000, database['runtime'], TENANT, None, None, demo_mode=True, coordination_service_token=TOKEN)
    with TestClient(create_app(settings), client=('127.0.0.1', 50000), headers={'X-Demo-Actor': 'management'}) as c:
        fire = lambda run, headers=HOST: c.post(f'/internal/routines/v1/runs/{run}/fire', headers=headers)
        status = lambda run: sql(database, 'select status::text,error from routine_runs where id=$1', run)[0]
        first = due_run(database, routine)
        assert fire(first, {'Authorization': 'Bearer ' + 'x' * 40}).status_code == 401
        assert fire('routine_run_missing').status_code == 404
        posted = fire(first)
        assert posted.status_code == 200 and posted.json()['posted'], posted.text
        message = posted.json()['message_id']
        # Handing the same run over twice posts once.
        assert fire(first).json()['message_id'] == message
        in_room = [m for m in c.get('/rooms/management-room/messages?limit=100').json()['items'] if m['body'].get('routineRunId') == first]
        assert [(m['body']['text'], m['sender_user_id'], m['mention_status']) for m in in_room] == [('Tóm tắt các yêu cầu hôm qua.', 'local-v3-management', 'queued')]
        # The Supervisor answers the mention; the run is closed with what became of it.
        path = BASE + f'/room-mentions/{message}/{agent}'
        turn = c.post(path + '/turn', headers=SERVICE).json()
        assert turn['instruction'] == 'Tóm tắt các yêu cầu hôm qua.' and status(first)['status'] is None
        assert c.post(path + '/outcome', headers=SERVICE, json={'run_id': turn['run_id'], 'status': 'done', 'content': 'Hôm qua có 3 yêu cầu.'}).status_code == 200
        assert status(first)['status'] == 'succeeded'
        assert fire(first).json() == {'posted': False}

        second = due_run(database, routine)
        path = BASE + f"/room-mentions/{fire(second).json()['message_id']}/{agent}"
        run = c.post(path + '/turn', headers=SERVICE).json()['run_id']
        assert c.post(path + '/outcome', headers=SERVICE, json={'run_id': run, 'status': 'failed'}).status_code == 200
        assert status(second) == {'status': 'failed', 'error': 'Agent không trả lời được.'}
        row = next(i for i in c.get(ROOM).json()['items'] if i['id'] == routine)
        assert (row['last_status'], row['last_error']) == ('failed', 'Agent không trả lời được.')

        # A run the sweep gave up on reads as a sentence in the room's language.
        sql(database, "insert into routine_runs(id,routine_id,scheduled_for,status,finished_at,error,started_at,tenant_id) values($1,$2,now()+interval '1 minute',"
                      "'skipped',now(),'the server never finished this run; it may have restarted mid-turn',now()+interval '1 minute',$3) returning id",
            'routine_run_' + uuid4().hex, routine, TENANT)
        assert next(i for i in c.get(ROOM).json()['items'] if i['id'] == routine)['last_error'] == 'Agent không trả lời trong 10 phút.'

        # Once the agent's release is revoked nothing is posted, and the run says why.
        assert c.post(f'/rooms/management-room/agents/{agent}/release/revoke', json={'note': 'Ngừng dùng'}).status_code == 200
        third = due_run(database, routine)
        refused = fire(third).json()
        assert not refused['posted'] and 'phát hành' in refused['reason'] and status(third)['status'] == 'failed'

        assert c.put(f'{ROOM}/{routine}/enabled', json={'enabled': False}).status_code == 200
        assert not next(i for i in c.get(ROOM).json()['items'] if i['id'] == routine)['enabled']
        assert c.put(f'{ROOM}/routine_unknown/enabled', json={'enabled': False}).status_code == 404
        assert c.delete(f'{ROOM}/{routine}').status_code == 200
        assert all(i['id'] != routine for i in c.get(ROOM).json()['items'])
    assert [path for path, _ in seen[1:]] == [f'/{routine}/enabled', f'/{routine}/remove']
    events = sql(database, "select event_type from audit_events where target_type='routine' and target_id=$1 order by created_at", routine)
    assert [e['event_type'] for e in events] == ['routine.created', 'routine.switched', 'routine.removed']
