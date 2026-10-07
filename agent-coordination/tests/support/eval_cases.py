"""Shared case and trace for the evaluator tests: one in-scope case and a clean trace that satisfies it."""
from agent_eval.checks import CheckContext
from agent_eval.contracts import EvalCase, ExecutionContext, Trace

TOOL = ('technical-tools', 'technical.asset.read')
EXPECTED = ExecutionContext(tenant_id='eval-tenant', resident_id='res-1', unit_id='unit-1', building_id='bld-1')
CTX = CheckContext(expected=EXPECTED, source_of={'copy-target': 'target', 'copy-other': 'other'},
                   grants={'target': frozenset({TOOL})},
                   tool_schemas={TOOL: {'type': 'object', 'required': ['building_id']}},
                   leak_literals=('copy-target', 'eval-tenant'))


def case(**expectations):
    return EvalCase.model_validate({
        'name': 'Rò nước', 'kind': 'in_scope',
        'input': {'message': 'Nhà tôi bị rò nước', 'fixture_profile_id': 'resident-a'},
        'expectations': {'required_agents': ['target'], 'forbidden_agents': ['other'],
                         'required_tools': [{'server_id': TOOL[0], 'name': TOOL[1], 'arguments': {'building_id': '$fixture.building_id'}}],
                         'forbidden_tools': [{'server_id': 'reporting', 'name': 'reporting.revenue'}],
                         'required_sources': [{'document_id': 'sop-1', 'version': '2', 'citation_required': True}],
                         'ticket': 'required', 'terminal_state': 'approval_pending', **expectations},
        'rubric': {f'score{i}_description': f'mức {i}' for i in range(1, 6)}})


def trace(**changes):
    base = {
        'messages': [{'id': 'm1', 'role': 'resident', 'text': 'Nhà tôi bị rò nước'},
                     {'id': 'm2', 'role': 'reception', 'text': 'Ban quản lý đang xử lý, kế hoạch chờ bạn duyệt.', 'visible_to_resident': True}],
        'participants': [{'id': 'p1', 'agent_id': 'copy-target', 'run_id': 'run-1', 'status': 'completed'}],
        'routing': [{'id': 'r1', 'selected_agent_ids': ['copy-target']}],
        'tool_calls': [{'id': 't1', 'agent_id': 'copy-target', 'server_id': TOOL[0], 'name': TOOL[1],
                        'arguments': {'building_id': 'bld-1'}, 'status': 'OK', 'result': {'assets': []}}],
        'retrievals': [{'id': 'k1', 'agent_id': 'copy-target', 'document_id': 'sop-1', 'version': '2', 'chunk_id': 'c1',
                        'rank': 0, 'content': 'Khóa van tổng trước khi sửa.'}],
        'citations': [{'id': 'cite1', 'agent_id': 'copy-target', 'document_id': 'sop-1', 'version': '2'}],
        'outputs': [{'id': 'o1', 'agent_id': 'copy-target', 'valid': True}],
        'context': {**EXPECTED.model_dump(), 'principal_id': 'pr-1', 'binding_id': 'b-1'},
        'ticket_ids': ['ticket-1'],
        'final_response': 'Ban quản lý đang xử lý, kế hoạch chờ bạn duyệt.',
        'terminal_state': 'approval_pending'}
    return Trace.model_validate({**base, **changes})
