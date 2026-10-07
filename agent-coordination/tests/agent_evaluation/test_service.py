"""The evaluator service: generation answers only the business API, with its own model or the fallback."""
import json

import httpx
from starlette.testclient import TestClient

from agent_eval.service import create_app
from agent_eval.worker import Settings

CONTEXT = {'agent': {'agent_id': 'target', 'name': 'A', 'tools': []}, 'collaborators': [], 'sources': [],
           'fixtures': [{'fixture_profile_id': 'resident-a'}]}


def answer(request):
    case = {'name': 'Ca', 'kind': 'boundary', 'message': 'm', 'follow_up_messages': [], 'fixture_profile_id': 'resident-a',
            'required_agents': [], 'forbidden_agents': [], 'required_tools': [], 'forbidden_tools': [], 'required_sources': [],
            'ticket': 'optional', 'terminal_state': 'reply_only', 'rubric': {f'score{i}_description': 'x' for i in range(1, 6)}}
    cases = [{**case, 'name': f'Ca {n}'} for n in range(6)]
    return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'cases': cases})}}]})


def test_generation_requires_the_service_token_and_a_model():
    settings = Settings('http://api.test', 'w' * 40)
    with TestClient(create_app(settings, transport=httpx.MockTransport(answer), run_worker=False)) as c:
        assert c.post('/internal/generate', json={'context': CONTEXT}).status_code == 401
        auth = {'Authorization': 'Bearer ' + 'w' * 40}
        assert c.post('/internal/generate', headers=auth, json={'context': CONTEXT}).status_code == 503
        model = {'provider': 'openai', 'model_name': 'gen', 'base_url': 'https://m.test/v1', 'api_key': 'k' * 40}
        made = c.post('/internal/generate', headers=auth, json={'context': CONTEXT, 'model_config': model})
        assert made.status_code == 200 and len(made.json()['cases']) == 6
        assert made.json()['generator_profile']['model_profile'] == 'openai/gen' and 'k' * 40 not in made.text
        leaked = {**CONTEXT, 'agent': {**CONTEXT['agent'], 'instructions': 'secret'}}
        assert c.post('/internal/generate', headers=auth, json={'context': leaked, 'model_config': model}).status_code == 422
