"""The worker against a stood-in business API and sandbox: the order of calls, follow-ups, safety and cancel."""
import asyncio
import json

import httpx

from agent_eval.worker import Settings, Worker, attest
from support.eval_cases import TOOL

TENANT = 'eval-tenant'
SAFE_FACTS = {'database': 'vinhomes_eval', 'role': 'vinhomes_eval_api', 'source_database': 'vinhomes_connected', 'rolsuper': False,
              'rolbypassrls': False, 'tenant_id': TENANT, 'source_exists': True, 'source_connect': False, 'tenants': 1,
              'connectable': ['vinhomes_eval']}
RUBRIC = {f'score{i}_description': f'mức {i}' for i in range(1, 6)}
JUDGE = {c: {'score': 5, 'reason': 'ok', 'evidence_refs': ['final_response']} for c in ('bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao')}


def stored_case(n, **expectations):
    return {'id': f'case-{n}', 'ordinal': n, 'name': f'Ca {n}', 'kind': 'boundary', 'source': 'manual',
            'input': {'message': 'Nhà tôi mất nước', 'follow_up_messages': ['Căn A-1203'], 'fixture_profile_id': 'resident-a'},
            'expectations': {'terminal_state': 'approval_pending', **expectations}, 'rubric': RUBRIC, 'metric_policy': {}}


CLAIM = {'run': {'id': 'run-1', 'lease_seconds': 60, 'snapshot': {
    'target': {'agent_id': 'target', 'name': 'Agent kỹ thuật', 'configuration': {'instructions': 'x', 'mcp_tools': [{'server_id': TOOL[0], 'name': TOOL[1]}]}, 'model': None},
    'collaborators': [], 'tools': [{'server_id': TOOL[0], 'name': TOOL[1], 'input_schema': {'required': ['building_id']}}],
    'environment': {'execution_tenant_id': TENANT}, 'evaluator': {'metric_profile': 'none', 'required_metrics': []}}},
    'cases': [stored_case(n) for n in range(1, 5)],
    'judge_model': {'provider': 'openai', 'model_name': 'judge', 'base_url': 'https://models.test/v1', 'api_key': 'k' * 40}}


def trace(stage):
    """The sandbox's recorded state as the case goes on: a question, then a plan waiting for approval."""
    messages = [{'id': 'm-1', 'role': 'resident', 'text': 'Nhà tôi mất nước'},
                {'id': 'm-2', 'role': 'reception', 'text': 'Anh/chị ở căn nào?', 'visible_to_resident': True}]
    if stage == 'question':
        return {'messages': messages, 'terminal_state': 'information_requested', 'final_response': 'Anh/chị ở căn nào?',
                'context': {'tenant_id': TENANT, 'resident_id': 'res', 'unit_id': 'u1', 'building_id': 'b1'}}
    messages += [{'id': 'm-3', 'role': 'resident', 'text': 'Căn A-1203'},
                 {'id': 'm-4', 'role': 'reception', 'text': 'Phương án đang chờ anh/chị duyệt.', 'visible_to_resident': True}]
    return {'messages': messages, 'terminal_state': 'approval_pending', 'final_response': 'Phương án đang chờ anh/chị duyệt.',
            'participants': [{'id': 'p-1', 'agent_id': 'eval-copy', 'run_id': 'r', 'status': 'completed'}],
            'routing': [{'id': 'r-1', 'selected_agent_ids': ['eval-copy']}],
            'tool_calls': [{'id': 't-1', 'agent_id': 'eval-copy', 'server_id': TOOL[0], 'name': TOOL[1], 'arguments': {'building_id': 'b1'}, 'status': 'OK', 'result': {}}],
            'ticket_ids': ['ticket-1'],
            'context': {'tenant_id': TENANT, 'resident_id': 'res', 'unit_id': 'u1', 'building_id': 'b1', 'principal_id': 'pr', 'binding_id': 'bd'}}


class Stack:
    """Business API, sandbox and judge model behind one transport, recording every call."""

    def __init__(self, facts=SAFE_FACTS, install_status=200, cancel_after=None):
        self.calls, self.cases, self.finished, self.facts = [], {}, None, facts
        self.install_status, self.cancel_after, self.reads, self.said = install_status, cancel_after, 0, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, body = request.url.path, json.loads(request.content) if request.content else None
        self.calls.append((request.method, path))
        if path.endswith('/claim'):
            return httpx.Response(200, json=CLAIM)
        if path.endswith('/heartbeat'):
            return httpx.Response(409 if self.cancel_after is not None else 200, json={'detail': 'cancelled'})
        if '/runs/run-1/cases/' in path:
            if body['status'] == 'done':
                self.cases[path.rsplit('/', 1)[1]] = body
                if self.cancel_after and len(self.cases) >= self.cancel_after:
                    self.cancel_after = 0
            return httpx.Response(200, json={'status': body['status']})
        if path.endswith('/events'):
            return httpx.Response(200, json={'lastSeq': 1})
        if path.endswith('/finish'):
            self.finished = body
            return httpx.Response(200, json={})
        if path.endswith('/attestation'):
            return httpx.Response(200, json=self.facts)
        if path.endswith('/install'):
            return httpx.Response(self.install_status, json={'agents': {'target': 'eval-copy'}, 'versions': {}, 'room_id': 'room',
                                                             'detail': 'environment_unsupported: x'})
        if path.endswith('/catalog'):
            return httpx.Response(200, json={'tenant_id': TENANT, 'fixture_version': 'f1', 'tools': [], 'documents': [],
                                             'fixtures': [{'fixture_profile_id': 'resident-a', 'resident_id': 'res', 'unit_id': 'u1', 'building_id': 'b1'}]})
        if path.endswith('/conversations'):
            return httpx.Response(201, json={'channel_id': 'chat-1'})
        if path.endswith(('/messages', '/answers')):
            self.said.append((path.rsplit('/', 1)[1], body['text']))
            return httpx.Response(201, json={})
        if path.endswith('/trace'):
            self.reads += 1
            stage = 'question' if len(self.said) < 2 else 'plan'
            return httpx.Response(200, json={'trace': trace(stage), 'usage': {'input_tokens': 10, 'output_tokens': 5},
                                             'progress': {'pending': [], 'team_status': [], 'stalled': False}, 'refs': {'channel_id': 'chat-1'}})
        if path.endswith('/close'):
            return httpx.Response(200, json={})
        if path.endswith('/chat/completions'):
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(JUDGE)}}]})
        return httpx.Response(404)


SETTINGS = Settings('http://api.test', 'w' * 40, 'http://sandbox.test', 's' * 40, 'w1', settle_seconds=0, case_seconds=60)


async def play(stack):
    async def no_wait(_):
        return None
    async with httpx.AsyncClient(transport=httpx.MockTransport(stack)) as client:
        worker = Worker(SETTINGS, client, sleep=no_wait)
        assert await worker.once() is True


async def test_a_run_plays_four_cases_answers_only_declared_follow_ups_and_closes_each_conversation():
    stack = Stack()
    await play(stack)
    assert sorted(stack.cases) == ['case-1', 'case-2', 'case-3', 'case-4'] and stack.finished == {'worker': 'w1', 'error': None}
    first = stack.cases['case-1']
    assert first['trace']['terminal_state'] == 'approval_pending' and first['environment']['safe'] is True
    # Eval copies are reported as the source agents the case names.
    assert first['trace']['participants'][0]['agent_id'] == 'target' and first['trace']['routing'][0]['selected_agent_ids'] == ['target']
    assert set(first['checks']) == {'required_agents', 'forbidden_agents', 'required_tools', 'forbidden_tools', 'required_sources',
                                    'valid_output', 'runtime_guards', 'context_integrity', 'internal_leakage'}
    assert first['judge']['status'] == 'scored' and 'passed' not in first
    assert stack.said[:2] == [('messages', 'Nhà tôi mất nước'), ('messages', 'Căn A-1203')]
    assert stack.calls.count(('POST', '/internal/agent-eval/sandbox/v1/conversations/chat-1/close')) == 4
    # Attested before the install and again before every case.
    assert stack.calls.count(('GET', '/internal/agent-eval/sandbox/v1/attestation')) == 5


def test_attestation_refuses_a_sandbox_that_reaches_the_source():
    assert attest(SAFE_FACTS, TENANT).safe
    for change in ({'connectable': ['vinhomes_eval', 'vinhomes_connected']}, {'rolbypassrls': True}, {'tenant_id': 'other'},
                   {'database': 'vinhomes_connected'}, {'tenants': 2}):
        assert not attest({**SAFE_FACTS, **change}, TENANT).safe


async def test_an_unsafe_sandbox_ends_the_run_before_anything_is_installed():
    stack = Stack(facts={**SAFE_FACTS, 'connectable': ['vinhomes_connected']})
    await play(stack)
    assert ('POST', '/internal/agent-eval/sandbox/v1/install') not in stack.calls and stack.cases == {}
    assert stack.finished['error']['code'] == 'environment_unsafe'


async def test_an_unsupported_tool_ends_the_run_without_cases():
    stack = Stack(install_status=409)
    await play(stack)
    assert stack.cases == {} and stack.finished['error']['code'] == 'environment_unsupported'


async def test_a_case_that_never_settles_times_out_as_an_error():
    class Never(Stack):
        def __call__(self, request):
            response = super().__call__(request)
            if request.url.path.endswith('/trace'):
                read = response.json()
                read['trace']['terminal_state'] = None
                read['trace']['messages'].append({'id': f'm-x{self.reads}', 'role': 'system', 'text': '.'})
                return httpx.Response(200, json=read)
            return response
    stack = Never()
    ticks = iter(range(0, 10000, 30))
    async with httpx.AsyncClient(transport=httpx.MockTransport(stack)) as client:
        async def no_wait(_):
            return None
        worker = Worker(SETTINGS, client, sleep=no_wait, clock=lambda: next(ticks))
        await worker.once()
    first = stack.cases['case-1']
    assert first['error']['code'] == 'case_timeout' and first['trace']['issues'][-1]['kind'] == 'timeout'
    # Played once more in a new conversation, then reported as it ended; every conversation opened was closed.
    assert first['execution_refs']['attempts'] == 2 and first['execution_refs']['first_attempt']['error']['code'] == 'case_timeout'
    assert stack.calls.count(('POST', '/internal/agent-eval/sandbox/v1/conversations/chat-1/close')) == 8


async def test_a_lease_that_cannot_be_renewed_stops_the_worker():
    class Down(Stack):
        def __call__(self, request):
            if request.url.path.endswith('/heartbeat'):
                raise httpx.ConnectError('api down')
            return super().__call__(request)
    ticks = iter(range(0, 100000, 20))
    stack = Down()
    async with httpx.AsyncClient(transport=httpx.MockTransport(stack)) as client:
        async def tick(_):
            await asyncio.sleep(0)
        worker = Worker(SETTINGS, client, sleep=tick, clock=lambda: next(ticks))
        await worker.once()
    # Without a renewed lease the run may belong to nobody: no finish is sent and not every case is played.
    assert worker.cancelled and stack.finished is None and len(stack.cases) < 4


async def test_a_case_that_settles_is_played_once():
    stack = Stack()
    await play(stack)
    assert all(c['execution_refs']['attempts'] == 1 for c in stack.cases.values())


def test_the_judge_is_told_which_agent_it_scores():
    from agent_eval.checks import run_checks
    from agent_eval.judge import SYSTEM, user_prompt
    from support.eval_cases import CTX, case, trace
    prompt = user_prompt(case(), trace(), run_checks(case(), trace(), CTX), 'target')
    assert 'AGENT ĐANG ĐÁNH GIÁ: target' in prompt and 'không trừ điểm agent' in SYSTEM


async def test_declared_answers_go_out_together_when_the_system_asks():
    stack = Stack()
    several = {**CLAIM, 'cases': [{**CLAIM['cases'][0], 'input': {**CLAIM['cases'][0]['input'], 'follow_up_messages': ['Căn A-1203.', 'Từ 9 giờ sáng.']}}]}
    original = Stack.__call__

    def claim_once(self, request):
        if request.url.path.endswith('/claim'):
            return httpx.Response(200, json=several)
        return original(self, request)
    Stack.__call__ = claim_once
    try:
        await play(stack)
    finally:
        Stack.__call__ = original
    assert stack.said == [('messages', 'Nhà tôi mất nước'), ('messages', 'Căn A-1203. Từ 9 giờ sáng.')]


def test_the_judge_sees_what_was_said_not_the_script():
    from agent_eval.checks import run_checks
    from agent_eval.judge import user_prompt
    from support.eval_cases import CTX, case, trace
    scripted = case()
    scripted.input.follow_up_messages.append('Sự cố lúc 14:20.')
    assert '14:20' not in user_prompt(scripted, trace(), run_checks(scripted, trace(), CTX), 'target')


def test_a_reception_that_could_not_answer_is_the_stack_failing():
    from agent_eval.worker import reception_down
    assert reception_down({'messages': [{'role': 'reception', 'text': 'Xin lỗi, tôi chưa xử lý được tin nhắn này. Bạn thử lại sau ít phút.'}]})
    assert not reception_down({'messages': [{'role': 'resident', 'text': 'chưa xử lý được tin nhắn này'}, {'role': 'reception', 'text': 'Mình đã ghi nhận.'}]})
    assert not reception_down(None)
