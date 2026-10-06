"""Live read-only request question acceptance. Never approves plans or external writes.

Credentials come from the local private accounts file; no secret values are saved in evidence.
A provider-backed answer is polled and an optional administrator DB read verifies exact run provenance.
"""
import argparse
import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://127.0.0.1:8020')
parser.add_argument('--ticket', required=True)
parser.add_argument('--timeout', type=int, default=160)
parser.add_argument('--docker-db-container', default='vinhomes-postgres-1')
parser.add_argument('--docker-db-name', default='vinhomes_docker_complete')
parser.add_argument('--question-id', help='Verify an existing acceptance question without invoking the provider again.')
parser.add_argument('--output', default='.codex-artifacts/operations-ui-2026-10-06/session-runtime-acceptance.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
secret = root/'services/vinhomes-api/.local-connected'
accounts = {}
for line in (secret/'accounts.txt').read_text(encoding='utf-8-sig').splitlines():
    role, _, value = line.partition(':')
    if ' / ' in value:
        accounts[role.strip()] = tuple(part.strip() for part in value.split(' / ', 1))


def call(client, method, path, body=None):
    response = client.request(method, args.base+path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}; {response.text[:200]}')
    return response.json()


result = {'base': args.base, 'ticket_id': args.ticket, 'started_at': datetime.now(timezone.utc).isoformat()}
with httpx.Client(timeout=40) as manager:
    call(manager, 'POST', '/auth/login', {'identifier': accounts['management'][0], 'password': accounts['management'][1]})
    endpoint = f'/tickets/{args.ticket}/session'
    detail = call(manager, 'GET', endpoint)
    session = detail.get('session') or {}
    if session.get('status') in ('completed', 'failed', 'cancelled'):
        raise RuntimeError('Use an active request for a read-only follow-up.')
    members = (detail.get('room') or {}).get('members') or []
    if not members:
        raise RuntimeError('The request has no specialist to ask.')
    agents = call(manager, 'GET', f"/rooms/{session['channel_id']}/agents")['items']
    agent = next((a for a in agents if a['name'] in members and a['published'] and a['status'] == 'active'), None)
    if not agent:
        raise RuntimeError('No published active participant in this request.')
    result['session_id'] = session['id']
    result['agent'] = {'id': agent['id'], 'name': agent['name']}
    result['supervisor_autoapproves'] = detail.get('supervisorApprovesPlans')
    sources = call(manager, 'GET', endpoint+'/sources')['items']
    result['sources'] = [{'id': s['id'], 'title': s['title'], 'enabled': s['enabled']} for s in sources]
    if any(s['enabled'] for s in sources):
        raise RuntimeError('Refuse to change existing source consent; use a request with all external sources off.')
    before = call(manager, 'GET', endpoint+'/external-calls')['items']
    request_id = 'ui-session-runtime-'+str(uuid.uuid4())
    question = ('Kiểm tra kết nối giao diện: hãy đọc tiêu đề và mô tả yêu cầu hiện tại, tóm tắt vấn đề cư dân báo trong 2 câu. '
                'Chỉ đọc, không tạo hoặc sửa lịch, tệp, tin nhắn ngoài, phương án hay phân công. Nếu thiếu dữ liệu hãy nói rõ.')
    payload = {'text': question, 'agent_id': agent['id'], 'client_message_id': request_id}
    if args.question_id:
        created = {'id': args.question_id}
        result['same_question_replayed'] = None
    else:
        created = call(manager, 'POST', endpoint+'/questions', payload)
        replay = call(manager, 'POST', endpoint+'/questions', payload)
        result['same_question_replayed'] = replay.get('replayed') is True and replay['id'] == created['id']
    result['question_id'] = created['id']
    deadline = time.monotonic()+args.timeout
    status = 'queued'
    while time.monotonic() < deadline:
        detail = call(manager, 'GET', endpoint)
        item = next((q for q in (detail.get('room') or {}).get('questions', []) if q['id'] == created['id']), None)
        status = item['status'] if item else 'missing'
        if status not in ('queued', 'running'):
            break
        time.sleep(2)
    result['question_status'] = status
    messages = call(manager, 'GET', f"/rooms/{session['channel_id']}/messages?limit=100")['items']
    # All room history pages are needed when the deployed room already contains older conversations.
    while messages and len(messages) % 100 == 0:
        page = call(manager, 'GET', f"/rooms/{session['channel_id']}/messages?limit=100&afterSeq={messages[-1]['seq']}")['items']
        messages.extend(page)
        if len(page) < 100:
            break
    answer = next((m for m in messages if m.get('reply_to_id') == created['id'] and m.get('sender_agent_id') == agent['id']), None)
    result['answer'] = answer['body']['text'] if answer else None
    result['answer_persisted'] = answer is not None and answer['body'].get('sessionId') == session['id']
    result['external_write_count_delta'] = len(call(manager, 'GET', endpoint+'/external-calls')['items'])-len(before)
    result['sources_unchanged_off'] = all(not s['enabled'] for s in call(manager, 'GET', endpoint+'/sources')['items'])

    # Read-only SQL provenance from the exact deployed database; psql inherits no credential output.
    question_uuid = str(uuid.UUID(created['id']))
    query = f"""select row_to_json(p) from (select r.id::text as run_id,r.status,r.actor_user_id,tm.team_id::text as team_id,
        r.version_id::text as version_id,mm.status as question_status,b.checkpoint_namespace,
        (select count(*) from audit_events e where e.target_type='agent_run' and e.target_id=r.id::text
          and e.event_type='agent.tool_called' and e.payload->>'status'='AWAITING_CONFIRMATION') as pending_write_calls,
        (select count(*) from messages m where m.sender_user_id=mm.requested_by and m.client_message_id=(select client_message_id from messages where id=mm.message_id)) as question_rows
        from message_mentions mm join agent_runs r on r.id=mm.resolved_run_id
        join team_members tm on tm.id=r.team_member_id join runtime_session_bindings b on b.id=r.binding_id
        where mm.message_id='{question_uuid}'::uuid) p"""
    read = subprocess.run(['docker', 'exec', args.docker_db_container, 'psql', '-U', 'vinhomes_seed', '-d', args.docker_db_name, '-At', '-c', query],
                          capture_output=True, text=True, timeout=20)
    if read.returncode:
        result['provenance_error'] = 'Read-only Docker database probe failed.'
    else:
        result['run_provenance'] = json.loads(read.stdout.strip()) if read.stdout.strip() else {}
result['finished_at'] = datetime.now(timezone.utc).isoformat()
result['passed'] = (result['question_status'] == 'done' and result['answer_persisted'] and result['same_question_replayed'] is not False
                    and result['external_write_count_delta'] == 0 and result['sources_unchanged_off']
                    and result.get('run_provenance', {}).get('team_id') == result['session_id']
                    and result.get('run_provenance', {}).get('checkpoint_namespace') == 'session-questions'
                    and result.get('run_provenance', {}).get('pending_write_calls') == 0
                    and result.get('run_provenance', {}).get('question_rows') == 1)
output = root/args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True), flush=True)
if not result['passed']:
    raise SystemExit(1)
