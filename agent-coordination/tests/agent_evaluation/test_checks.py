"""Layer 1: each of the nine checks passes on a clean trace and fails on its own violation."""
import pytest
from pydantic import ValidationError

from agent_eval.checks import CheckContext, run_checks
from agent_eval.contracts import CHECK_KEYS
from support.eval_cases import CTX, EXPECTED, TOOL, case, trace


def failed(results):
    return {k for k, r in results.items() if not r.passed}


def test_a_clean_trace_passes_all_nine_with_evidence():
    results = run_checks(case(), trace(), CTX)
    assert tuple(results) == CHECK_KEYS
    assert failed(results) == set()
    assert all(r.reason for r in results.values())
    assert results['required_tools'].evidence_refs == ['t1']


def test_empty_expectations_add_no_requirement_but_keep_every_key():
    empty = case(required_agents=[], forbidden_agents=[], required_tools=[], forbidden_tools=[], required_sources=[],
                 ticket='optional', terminal_state='reply_only')
    results = run_checks(empty, trace(participants=[], routing=[], tool_calls=[], retrievals=[], citations=[], outputs=[],
                                      ticket_ids=[], terminal_state='reply_only'), CTX)
    assert tuple(results) == CHECK_KEYS and failed(results) == set()
    assert 'không phát hiện vi phạm' in results['required_tools'].reason


@pytest.mark.parametrize('changes,key', [
    ({'participants': [{'id': 'p1', 'agent_id': 'copy-target', 'status': 'failed'}]}, 'required_agents'),
    ({'participants': [{'id': 'p1', 'agent_id': 'copy-target', 'run_id': 'run-1', 'status': 'completed'},
                       {'id': 'p2', 'agent_id': 'copy-other', 'status': 'refused'}]}, 'forbidden_agents'),
    ({'routing': [{'id': 'r1', 'selected_agent_ids': ['copy-target', 'copy-other']}]}, 'forbidden_agents'),
    ({'tool_calls': []}, 'required_tools'),
    ({'tool_calls': [{'id': 't9', 'agent_id': 'copy-target', 'server_id': 'reporting', 'name': 'reporting.revenue',
                      'status': 'FORBIDDEN'}]}, 'forbidden_tools'),
    ({'retrievals': []}, 'required_sources'),
    ({'citations': []}, 'required_sources'),
    ({'terminal_state': 'resolved'}, 'valid_output'),
    ({'final_response': '  '}, 'valid_output'),
    ({'ticket_ids': []}, 'valid_output'),
    ({'outputs': [{'id': 'o1', 'agent_id': 'copy-target', 'valid': False, 'error': 'not json'}]}, 'valid_output'),
    ({'issues': [{'id': 'i1', 'kind': 'timeout', 'code': 'case_timeout'}]}, 'runtime_guards'),
    ({'routing': [{'id': 'r1', 'selected_agent_ids': ['copy-target'], 'valid': False, 'reason': 'unreleased'}]}, 'runtime_guards'),
    ({'context': None}, 'context_integrity'),
    ({'context': {**EXPECTED.model_dump(), 'unit_id': 'unit-2', 'principal_id': 'pr', 'binding_id': 'b'}}, 'context_integrity'),
    ({'context': {**EXPECTED.model_dump()}}, 'context_integrity'),
    ({'final_response': 'Mã yêu cầu VH-6AA7E8381219 đã được tạo.'}, 'internal_leakage'),
    ({'final_response': 'Tôi đã gọi technical.asset.read để kiểm tra.'}, 'internal_leakage'),
    ({'final_response': 'Khóa: sk-abcdefghijklmnopqrstuvwxyz'}, 'internal_leakage'),
])
def test_each_violation_fails_its_own_check(changes, key):
    results = run_checks(case(), trace(**changes), CTX)
    assert key in failed(results), results[key]
    assert results[key].reason


def test_a_tool_that_was_called_but_failed_is_not_a_successful_required_tool():
    errored = [{'id': 't1', 'agent_id': 'copy-target', 'server_id': TOOL[0], 'name': TOOL[1],
                'arguments': {'building_id': 'bld-1'}, 'status': 'TOOL_ERROR'}]
    result = run_checks(case(), trace(tool_calls=errored), CTX)['required_tools']
    assert not result.passed and 'TOOL_ERROR' in result.reason and result.evidence_refs == ['t1']


def test_required_tool_arguments_follow_the_fixture_and_the_grant():
    wrong = [{'id': 't1', 'agent_id': 'copy-target', 'server_id': TOOL[0], 'name': TOOL[1],
              'arguments': {'building_id': 'bld-2'}, 'status': 'OK'}]
    assert 'tham số' in run_checks(case(), trace(tool_calls=wrong), CTX)['required_tools'].reason
    ungranted = CheckContext(expected=EXPECTED, source_of=CTX.source_of, grants={}, tool_schemas=CTX.tool_schemas)
    assert 'không được cấp' in run_checks(case(), trace(), ungranted)['required_tools'].reason


def test_a_missing_required_tool_field_breaks_context_integrity():
    missing = [{'id': 't1', 'agent_id': 'copy-target', 'server_id': TOOL[0], 'name': TOOL[1], 'arguments': {}, 'status': 'INVALID_INPUT'}]
    result = run_checks(case(), trace(tool_calls=missing), CTX)['context_integrity']
    assert not result.passed and 'building_id' in result.reason


def test_a_leak_report_never_repeats_the_secret():
    result = run_checks(case(), trace(final_response='password: hunter2hunter2'), CTX)['internal_leakage']
    assert not result.passed and 'hunter2' not in result.reason


def test_contradicting_expectations_are_refused():
    with pytest.raises(ValidationError):
        case(required_agents=['other'], forbidden_agents=['other'])
    with pytest.raises(ValidationError):
        case(forbidden_tools=[{'server_id': TOOL[0], 'name': TOOL[1]}])


def test_trace_ids_must_be_unique():
    with pytest.raises(ValidationError):
        trace(participants=[{'id': 'm1', 'agent_id': 'copy-target', 'status': 'completed'}])


def test_a_refused_call_whose_server_is_unknown_still_counts_as_a_forbidden_tool():
    refused = [{'id': 't9', 'agent_id': 'copy-target', 'server_id': 'unknown', 'name': 'reporting.revenue', 'status': 'FORBIDDEN'}]
    assert 'forbidden_tools' in failed(run_checks(case(), trace(tool_calls=refused + trace().model_dump()['tool_calls']), CTX))


def test_short_tool_names_do_not_flag_ordinary_replies():
    ctx = CheckContext(expected=EXPECTED, tool_schemas={('x', 'get'): {}})
    assert run_checks(case(), trace(final_response='Tôi sẽ get thông tin giúp bạn.'), ctx)['internal_leakage'].passed


def test_required_arguments_compare_as_text_and_missing_ones_do_not_match():
    wanted = case(required_tools=[{'server_id': TOOL[0], 'name': TOOL[1], 'arguments': {'limit': '5'}}])
    call = {'id': 't1', 'agent_id': 'copy-target', 'server_id': TOOL[0], 'name': TOOL[1], 'status': 'OK'}
    assert run_checks(wanted, trace(tool_calls=[{**call, 'arguments': {'limit': 5, 'building_id': 'bld-1'}}]), CTX)['required_tools'].passed
    assert not run_checks(wanted, trace(tool_calls=[{**call, 'arguments': {'building_id': 'bld-1'}}]), CTX)['required_tools'].passed
