"""The verdict: no layer makes up for another, and nothing missing or broken counts as a pass."""
import pytest

from agent_eval.checks import run_checks
from agent_eval.contracts import RequiredMetric, case_verdict, run_passed
from support.eval_cases import CTX, case, trace

CRITERIA = ('bam_nguon', 'dung_quy_trinh', 'dung_pham_vi', 'phan_hoi_nguoi_bao')
RELEVANCY = (RequiredMetric('answer_relevancy', 0.7), RequiredMetric('faithfulness', 0.8))


def checks(**failing):
    found = {k: r.model_dump() for k, r in run_checks(case(), trace(), CTX).items()}
    for key in failing:
        found[key] = {'passed': False, 'reason': 'rớt', 'evidence_refs': []}
    return found


def judge(score=5, **low):
    return {'status': 'scored', 'backend': 'structured-chat', 'model_profile': 'openai/j', 'threshold': 4,
            'criteria': {c: {'score': low.get(c, score), 'reason': 'ok', 'evidence_refs': ['final_response']} for c in CRITERIA}}


def metric(name, value=0.9, status='scored'):
    return {'name': name, 'backend': 'ragas', 'version': '0.4.3', 'status': status, 'value': value if status == 'scored' else None,
            'threshold': 0.7, 'required': True}


SAFE = {'safe': True, 'reason': 'Chỉ chạm tenant eval.'}


def verdict(c=None, **parts):
    base = {'checks': checks(), 'judge': judge(), 'metrics': [], 'environment': SAFE, 'error': None}
    return case_verdict(c or case(), **{**base, **parts})


def test_every_layer_passing_is_a_pass():
    assert verdict() == ('passed', [])


@pytest.mark.parametrize('parts,layer', [
    ({'checks': checks(required_tools=True), 'judge': judge(5)}, 'code'),
    ({'judge': judge(5, dung_pham_vi=3)}, 'judge'),
    ({'environment': {'safe': False, 'reason': 'Role đọc được tenant nguồn.'}}, 'environment'),
])
def test_a_high_score_elsewhere_never_makes_up_for_a_failed_layer(parts, layer):
    status, layers = verdict(**parts)
    assert status == 'failed' and any(l['layer'] == layer and l['kind'] == 'failed' for l in layers)


@pytest.mark.parametrize('parts,layer', [
    ({'checks': None}, 'code'),
    ({'checks': {k: v for k, v in list(checks().items())[:8]}}, 'code'),
    ({'judge': None}, 'judge'),
    ({'judge': {'status': 'error', 'backend': 'b', 'model_profile': 'm', 'error': {'code': 'model_timeout'}}}, 'judge'),
    ({'judge': {**judge(), 'criteria': {c: v for c, v in list(judge()['criteria'].items())[:3]}}}, 'judge'),
    ({'environment': None}, 'environment'),
    ({'error': {'code': 'case_timeout'}}, 'execution'),
])
def test_missing_or_broken_evidence_is_an_error_not_a_pass(parts, layer):
    status, layers = verdict(**parts)
    assert status == 'error' and any(l['layer'] == layer for l in layers)


def test_required_metrics_must_score_above_threshold_and_cannot_be_dropped():
    resolved = case(terminal_state='approval_pending')
    assert verdict(resolved, metrics=[metric('faithfulness', 0.85), metric('answer_relevancy', status='not_applicable')],
                   required_metrics=RELEVANCY)[0] == 'passed'
    assert verdict(resolved, metrics=[metric('faithfulness', 0.5)], required_metrics=RELEVANCY[1:])[0] == 'failed'
    assert verdict(resolved, metrics=[metric('faithfulness', status='error')], required_metrics=RELEVANCY[1:])[0] == 'error'
    assert verdict(resolved, metrics=[], required_metrics=RELEVANCY[1:])[0] == 'error'
    answering = case(terminal_state='resolved')
    # Relevancy applies to a content answer: marking it not applicable there is dropping it.
    assert verdict(answering, metrics=[metric('faithfulness'), metric('answer_relevancy', status='not_applicable')],
                   required_metrics=RELEVANCY)[0] == 'error'


def test_a_nan_metric_is_refused_as_broken():
    status, layers = verdict(metrics=[metric('faithfulness', float('nan'))], required_metrics=RELEVANCY[1:])
    assert status == 'error' and layers[0]['layer'] == 'metric'


def test_a_run_needs_four_passing_results():
    assert run_passed(['passed'] * 4)
    assert not run_passed(['passed'] * 3)
    assert not run_passed(['passed', 'passed', 'passed', 'error'])
    assert not run_passed(['passed'] * 5)
