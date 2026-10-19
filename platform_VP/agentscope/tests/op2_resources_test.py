"""Owner-scoped readiness, reference retrieval and candidate review without models."""
from tests.personal_chat_test import personal_app, make_group
from agentscope.app.rag.knowledge_base_manager._lexical import LexicalKnowledge
from agentscope.message import UserMsg


def test_draft_cannot_start_direct_or_group_model_run(personal_app):
    app, client, storage = personal_app
    agent = client.portal.call(storage.get_agent, 'alice', 'alice-a')
    agent.data.spec = {'name': 'Draft agent'}
    client.portal.call(storage.upsert_agent, 'alice', agent)
    group = make_group(client)
    assert group['ready'] is False and group['readiness_issues']
    response = client.post('/chat/', json={'agent_id': group['agentId'], 'session_id': group['sessionId'],
                                          'input': UserMsg(name='BQL', content='Plan work').model_dump(mode='json')})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'AGENT_NOT_READY'


def test_lexical_references_need_review_and_cannot_cross_owner(personal_app):
    _, client, storage = personal_app
    response = client.post('/knowledge_bases/lexical', json={'name': 'Reference documents'})
    assert response.status_code == 201, response.text
    kb_id = response.json()['knowledge_base_id']
    response = client.post(f'/knowledge_bases/{kb_id}/references', json={
        'filename': 'Review workflow.md', 'text': 'A coordinator must review evidence before accepting a proposed maintenance plan.',
        'source_ref': 'repository://operator-guide'})
    assert response.status_code == 201, response.text
    doc_id = response.json()['document_id']
    kb = client.portal.call(storage.get_knowledge_base, 'alice', kb_id)
    runtime = LexicalKnowledge(storage, kb)
    assert client.portal.call(runtime.search, ['maintenance']) == []
    client.headers['X-User-ID'] = 'bob'
    assert client.post(f'/knowledge_bases/{kb_id}/references/{doc_id}/review', json={'status': 'approved'}).status_code == 404
    client.headers['X-User-ID'] = 'alice'
    assert client.post(f'/knowledge_bases/{kb_id}/references/{doc_id}/review', json={'status': 'approved'}).status_code == 200
    hits = client.portal.call(runtime.search, ['maintenance'])
    assert len(hits) == 1 and hits[0].chunk.metadata['source_ref'] == 'repository://operator-guide'
    assert client.post(f'/knowledge_bases/{kb_id}/references/{doc_id}/review', json={'status': 'retired'}).status_code == 200
    assert client.portal.call(runtime.search, ['maintenance']) == []


def test_local_skill_stays_candidate_until_owner_review(personal_app):
    _, client, storage = personal_app
    response = client.post('/skill', json={'name': 'evidence-review-v1', 'description': 'Review proposed plans',
                                         'markdown': 'Review source evidence and unresolved assumptions before accepting a proposed plan.'})
    assert response.status_code == 201, response.text
    skill_id = response.json()['id']
    assert response.json()['review_status'] == 'candidate' and not response.json()['enabled']
    client.headers['X-User-ID'] = 'bob'
    assert client.post(f'/skill/{skill_id}/review', json={'status': 'approved'}).status_code == 404
    client.headers['X-User-ID'] = 'alice'
    assert client.post(f'/skill/{skill_id}/review', json={'status': 'approved'}).json()['enabled'] is True
