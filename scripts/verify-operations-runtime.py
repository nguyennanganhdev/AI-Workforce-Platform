"""Verify deployed models, real private answers and owner isolation without logging credentials.

Registry configuration is opt-in. Normal runs preserve all selected models and role defaults.
"""
import argparse
import json
import time
import uuid
from pathlib import Path
import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://localhost:3022')
parser.add_argument('--configure-models', action='store_true')
parser.add_argument('--follow-up', action='store_true', help='Ask in the two previously created acceptance chats.')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
secret = root / 'services/vinhomes-api/.local-connected'
admin = {line.partition(':')[0].strip().lower(): line.partition(':')[2].strip()
         for line in (secret/'initial-admin.txt').read_text(encoding='utf-8-sig').splitlines() if ':' in line}
accounts = {}
for line in (secret/'accounts.txt').read_text(encoding='utf-8-sig').splitlines():
    role, _, record = line.partition(':')
    if ' / ' in record:
        accounts[role.strip()] = tuple(part.strip() for part in record.split(' / ', 1))
out = root / '.codex-artifacts/operations-ui-2026-10-06'
out.mkdir(parents=True, exist_ok=True)

def call(client, method, path, body=None):
    response = client.request(method, args.base+'/api/business'+path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}; {response.text[:250]}')
    return response.json()

result = {'answers': []}
previous = json.loads((out/'runtime-acceptance.json').read_text(encoding='utf-8')) if args.follow_up else None
with httpx.Client(timeout=65, headers={'Origin': args.base}) as administrator, httpx.Client(timeout=65, headers={'Origin': args.base}) as manager:
    call(administrator, 'POST', '/auth/login', {'identifier': admin['login'], 'password': admin['password']})
    registry = call(administrator, 'GET', '/admin/model-registry')
    if args.configure_models:
        result['checks'] = []
        for name, kind, dimension, roles in [
            ('gpt-6-luna', 'chat', None, ['reception', 'supervisor']),
            ('gpt-5.5', 'chat', None, ['specialist', 'factory']),
            ('text-embedding-3-large', 'embedding', 1536, ['embedding']),
        ]:
            model = next((m for m in registry['items'] if m['name'] == name and m['kind'] == kind), None)
            if not model:
                model = call(administrator, 'POST', '/admin/model-registry', {
                    'name': name, 'kind': kind, 'provider': 'openai',
                    'credential_env': 'OPENAI_API_KEY' if kind == 'chat' else 'EMBEDDING_API_KEY',
                    'base_url_env': 'OPENAI_BASE_URL' if kind == 'chat' else 'EMBEDDING_BASE_URL', 'dimension': dimension})
            check = call(administrator, 'POST', f"/admin/model-registry/{model['id']}/check")
            result['checks'].append({'name': name, **check})
            if not check['ok']:
                raise RuntimeError(f'Model check failed: {name}')
            if kind == 'chat':
                call(administrator, 'PATCH', f"/admin/model-registry/{model['id']}", {'allowed': True})
            for role in roles:
                call(administrator, 'PUT', '/admin/model-defaults/'+role, {'model_id': model['id']})
        registry = call(administrator, 'GET', '/admin/model-registry')
    result['models'] = [{'name': m['name'], 'kind': m['kind'], 'allowed': m['allowed'], 'check_status': m['check_status']} for m in registry['items']]
    result['defaults'] = registry['defaults']
    call(manager, 'POST', '/auth/login', {'identifier': accounts['management'][0], 'password': accounts['management'][1]})
    room = call(manager, 'GET', '/rooms')['items'][0]['id']
    agents = call(manager, 'GET', f'/rooms/{room}/agents')['items']
    active = [a for a in agents if a.get('published') and a['status'] == 'active']
    adviser = next((a for a in active if 'Tri thức' in a['name']), active[0])
    for mode in ('manual', 'automatic'):
        if previous:
            chat = call(manager, 'GET', '/personal-chats/'+next(a['chat_id'] for a in previous['answers'] if a['mode'] == mode))
            if chat['room_id'] != room or not chat['id'].startswith('personal-'):
                raise RuntimeError('Refusing to modify a chat outside this acceptance run.')
        else:
            chat = call(manager, 'POST', '/personal-chats', {'room_id': room, 'request_id': str(uuid.uuid4()),
                        'name': f'Kiểm tra nghiệm thu UI — {mode} — 06/10/2026'})
        text = 'Cư dân ở tòa S1.01. Phí gửi xe máy cư dân là bao nhiêu? Tra nguồn tri thức được cấp và nói rõ nếu không tìm thấy.'
        payload = {'text': text, 'client_message_id': str(uuid.uuid4())}
        if mode == 'manual':
            payload['mention_agent_id'] = adviser['id']
        try:
            created = call(manager, 'POST', f"/personal-chats/{chat['id']}/messages", payload)
            deadline = time.monotonic()+100
            while time.monotonic() < deadline:
                detail = call(manager, 'GET', f"/personal-chats/{chat['id']}")
                answer = next((m for m in detail['messages'] if m.get('sender_agent_id') and m.get('reply_to_id') == created['id']), None)
                if answer:
                    item = {'mode': mode, 'chat_id': chat['id'], 'status': 'answered', 'answer': answer['body']['text'],
                            'sources': answer.get('used_sources'), 'route': answer.get('route')}
                    break
                question = next(m for m in detail['messages'] if m['id'] == created['id'])
                if question.get('mention_status') == 'failed':
                    item = {'mode': mode, 'chat_id': chat['id'], 'status': 'failed'}
                    break
                time.sleep(2)
            else:
                item = {'mode': mode, 'chat_id': chat['id'], 'status': 'timed_out'}
        except RuntimeError as error:
            item = {'mode': mode, 'chat_id': chat['id'], 'status': 'failed', 'error': str(error)}
        denied = administrator.get(args.base+f"/api/business/personal-chats/{chat['id']}")
        item['admin_read_status'] = denied.status_code
        result['answers'].append(item)
        print(json.dumps(item, ensure_ascii=True), flush=True)
    graph = call(manager, 'GET', f'/rooms/{room}/agent-graph')
    result['graph_summary'] = graph['summary']
    result['graph_agents'] = len(graph['metrics'])
(out/'runtime-acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
if any(answer['status'] != 'answered' or answer['admin_read_status'] != 404 for answer in result['answers']):
    raise SystemExit(1)
