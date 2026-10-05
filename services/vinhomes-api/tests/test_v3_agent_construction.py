"""The management construction route treats clarification as a normal Factory step."""
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinhomes_api import v3_agent_builder as builder
from vinhomes_api.v3_auth import resident_connection
from vinhomes_api.v3_security import digest


@pytest.fixture
def construction_client(monkeypatch):
    configuration = {'instructions': 'Draft pending construction.'}
    db = AsyncMock()
    db.execute.return_value.first = lambda: None
    app = FastAPI()
    app.include_router(builder.router)
    app.dependency_overrides[resident_connection] = lambda: (db, 'manager')
    monkeypatch.setattr(builder, 'room_agent', AsyncMock(return_value={
        'name': 'Agent vệ sinh', 'status': 'draft', 'configuration': configuration}))
    monkeypatch.setattr(builder, 'room_catalogue', AsyncMock(return_value={'categories': [], 'tools': []}))
    monkeypatch.setenv('FACTORY_SERVICE_URL', 'http://factory:4010')
    monkeypatch.setenv('FACTORY_SERVICE_TOKEN', 'test-service-token-' + 'x' * 32)
    real_client = httpx.AsyncClient
    calls = []
    replies = []

    def refusal(request):
        calls.append(request)
        if replies:
            status, body = replies.pop(0)
            return httpx.Response(status, json=body)
        return httpx.Response(422, json={'code': 'NEEDS_INPUT', 'issues': [
            {'code': 'NEEDS_INPUT', 'message': 'Agent lấy dữ liệu từ đâu?'},
            {'code': 'NEEDS_INPUT', 'message': 'Agent trả về gì?'}]})

    monkeypatch.setattr(builder.httpx, 'AsyncClient', lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(refusal)))
    payload = {'role': 'Chuyên viên BQL', 'description': 'Hỗ trợ vệ sinh',
               'configuration_hash': digest(configuration), 'request_id': 'clarification-1'}
    with TestClient(app) as client:
        yield client, payload, db, calls, replies


def test_missing_information_returns_questions_without_writing_a_configuration(construction_client):
    client, payload, db, calls, _ = construction_client
    response = client.post('/rooms/bql-sapphire/agents/draft/construct', json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == {'needsInput': True, 'questions': ['Agent lấy dữ liệu từ đâu?', 'Agent trả về gì?']}
    assert len(calls) == 1  # No artifact verification for an unanswered question.
    assert all('update agents' not in str(call.args[0]) for call in db.execute.call_args_list)


@pytest.mark.parametrize('issues', [
    [{'code': 'NEEDS_INPUT'}],
    [{'code': 'NEEDS_INPUT', 'message': '   '}],
    [{'code': 'NEEDS_INPUT', 'message': 'Nguồn dữ liệu?'},
     {'code': 'BLOCKED_RESOURCE', 'message': 'No authorized tool.'}],
    'malformed',
])
def test_malformed_or_blocked_requests_are_not_reported_as_clarification(construction_client, issues):
    client, payload, db, _, replies = construction_client
    replies.append((422, {'issues': issues}))
    response = client.post('/rooms/bql-sapphire/agents/draft/construct', json=payload)
    assert response.status_code == 422
    assert 'needsInput' not in response.json()
    assert all('update agents' not in str(call.args[0]) for call in db.execute.call_args_list)


def test_clarification_can_be_answered_then_verified_and_saved(construction_client, monkeypatch):
    client, payload, db, calls, replies = construction_client
    assert client.post('/rooms/bql-sapphire/agents/draft/construct', json=payload).json()['needsInput']
    monkeypatch.setattr(builder, 'audit', AsyncMock())
    monkeypatch.setattr(builder, 'room_catalogue', AsyncMock(return_value={
        'categories': [], 'tools': [{'server_id': 'reports', 'name': 'reports.read',
                                  'description': 'Read report', 'input_schema': {'type': 'object'}}]}))
    artifact = {'specHash': 'a' * 64, 'systemPrompt': 'Read the approved report and summarize actual results.',
                'spec': {'resources': [{'kind': 'tool', 'ref': 'reports/reports.read'}]}}
    replies.extend([(200, artifact), (200, artifact)])
    response = client.post('/rooms/bql-sapphire/agents/draft/construct', json={
        **payload, 'request_id': 'answered-2', 'description': 'Read report data from the approved reporting tool and return a summary.'})
    assert response.status_code == 200, response.text
    configuration = response.json()['configuration']
    assert configuration['instructions'] == artifact['systemPrompt']
    assert configuration['mcp_tools'] == [{'server_id': 'reports', 'name': 'reports.read'}]
    assert calls[-1].url.path == '/v1/verify'
    assert sum('update agents' in str(call.args[0]) for call in db.execute.call_args_list) == 1
