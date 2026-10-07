"""Suites: exactly four valid cases in scope, whether a person or the model wrote them."""
import copy
import json

import httpx
import pytest

from agent_eval.generator import SuiteScope, generate, validate_suite
from agent_eval.llm import ModelConfig

CONTEXT = {
    'agent': {'agent_id': 'target', 'name': 'Agent kỹ thuật', 'description': 'Xử lý sự cố kỹ thuật',
              'service_categories': ['technical'],
              'tools': [{'server_id': 'technical-tools', 'name': 'technical.asset.read', 'description': 'Tra tài sản',
                         'input_schema': {'type': 'object'}}]},
    'collaborators': [{'agent_id': 'cleaning', 'name': 'Agent vệ sinh', 'description': 'Vệ sinh', 'tools': []}],
    'sources': [{'document_id': 'sop-1', 'version': '2', 'title': 'SOP rò nước', 'summary': 'Quy trình'}],
    'fixtures': [{'fixture_profile_id': 'resident-a', 'description': 'Cư dân căn A-1203'}],
}
SCOPE = SuiteScope.from_context(CONTEXT)
RUBRIC = {f'score{i}_description': f'mức {i}' for i in range(1, 6)}


def stored(name, kind, required=(), forbidden=(), **expectations):
    return {'name': name, 'kind': kind, 'input': {'message': 'Nhà tôi bị rò nước', 'fixture_profile_id': 'resident-a'},
            'expectations': {'required_agents': list(required), 'forbidden_agents': list(forbidden),
                             'terminal_state': 'approval_pending', **expectations}, 'rubric': RUBRIC}


def suite():
    return [stored('Chính', 'in_scope', ['target'], required_tools=[{'server_id': 'technical-tools', 'name': 'technical.asset.read'}]),
            stored('Thiếu tin', 'in_scope', ['target'], required_sources=[{'document_id': 'sop-1', 'version': '2'}]),
            stored('Ngoài phạm vi', 'out_of_scope', forbidden=['target']),
            stored('Phối hợp', 'collaboration', ['target', 'cleaning'])]


def test_a_valid_suite_has_no_problems():
    cases, problems = validate_suite(suite(), SCOPE)
    assert problems == [] and len(cases) == 4


@pytest.mark.parametrize('size', [3, 5])
def test_only_exactly_four_cases_form_a_suite(size):
    cases = (suite() * 2)[:size]
    for i, c in enumerate(cases):
        c['name'] = f'Ca {i}'
    assert any('đúng 4 ca' in p for p in validate_suite(cases, SCOPE)[1])


@pytest.mark.parametrize('mutate,needle', [
    (lambda s: s[1].update(name='chính '), 'khác nhau'),
    (lambda s: s[0]['expectations'].update(required_agents=['target', 'ghost']), 'ghost'),
    (lambda s: s[0]['expectations']['required_tools'][0].update(name='technical.asset.write'), 'technical.asset.write'),
    (lambda s: s[1]['expectations']['required_sources'][0].update(version='9'), 'sop-1'),
    (lambda s: s[2]['input'].update(fixture_profile_id='real-person'), 'real-person'),
    (lambda s: s[2]['expectations'].update(forbidden_agents=[]), 'cấm chọn'),
    (lambda s: s[0]['expectations'].update(required_agents=[]), 'phải yêu cầu'),
    (lambda s: s[3]['expectations'].update(required_agents=['target']), 'phối hợp'),
    (lambda s: s[3]['expectations'].update(forbidden_agents=['target']), 'both required and forbidden'),
])
def test_wrong_ids_and_contradictions_are_refused(mutate, needle):
    cases = suite()
    mutate(cases)
    problems = validate_suite(cases, SCOPE)[1]
    assert any(needle in p for p in problems), problems


def model_answer(cases):
    flat = []
    for c in cases:
        e = c['expectations']
        flat.append({'name': c['name'], 'kind': c['kind'], 'message': c['input']['message'], 'follow_up_messages': [],
                     'fixture_profile_id': c['input']['fixture_profile_id'], 'required_agents': e['required_agents'],
                     'forbidden_agents': e['forbidden_agents'],
                     'required_tools': [{**t, 'arguments': [{'name': 'building_id', 'value': '$fixture.building_id'}]}
                                        for t in e.get('required_tools', [])],
                     'forbidden_tools': [], 'required_sources': [{'document_id': 'sop-1', 'version': None, 'agent_id': None,
                                                                  'citation_required': False}] if e.get('required_sources') else [],
                     'ticket': 'optional', 'terminal_state': e['terminal_state'], 'rubric': RUBRIC})
    return {'cases': flat}


async def test_generated_cases_are_stored_as_generated_and_validated_like_manual_ones():
    sent = []

    def reply(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(model_answer(suite()))}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        cases, problems, _ = await generate(client, ModelConfig('openai', 'gen', 'https://m.test/v1', 'k' * 40), CONTEXT)
    assert problems == [] and [c['source'] for c in cases] == ['generated'] * 4
    assert cases[0]['expectations']['required_tools'][0]['arguments'] == {'building_id': '$fixture.building_id'}
    assert 'instructions' not in sent[0]['messages'][1]['content']


async def test_an_invented_id_from_the_model_is_reported_not_replaced():
    answer = model_answer(suite())
    answer['cases'][2]['fixture_profile_id'] = 'Nguyễn Văn A'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(
            200, json={'choices': [{'message': {'content': json.dumps(answer)}}]}))) as client:
        cases, problems, _ = await generate(client, ModelConfig('openai', 'gen', 'https://m.test/v1', 'k' * 40), CONTEXT)
    assert cases[2]['input']['fixture_profile_id'] == 'Nguyễn Văn A' and any('Nguyễn Văn A' in p for p in problems)


async def test_the_agent_instructions_never_reach_the_generator():
    leaked = copy.deepcopy(CONTEXT)
    leaked['agent']['instructions'] = 'secret prompt'
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await generate(client, ModelConfig('openai', 'gen', 'https://m.test/v1', 'k' * 40), leaked)


def test_four_cases_must_include_the_task_and_something_outside_it():
    weak = [stored(f'Ranh giới {n}', 'boundary') for n in range(4)]
    assert any('trong năng lực và một ca ngoài năng lực' in p for p in validate_suite(weak, SCOPE)[1])
