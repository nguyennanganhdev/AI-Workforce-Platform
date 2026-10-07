"""Layer 3: only the profile's metrics, applied as the case says, and never a silent pass."""
from types import SimpleNamespace

from agent_eval.metrics import score_metrics
from support.eval_cases import case, trace

PROFILE = {'metric_profile': 'ragas-rag-v1', 'required_metrics': [
    {'name': 'faithfulness', 'threshold': 0.8}, {'name': 'answer_relevancy', 'threshold': 0.7},
    {'name': 'context_precision', 'threshold': 0.7}]}


class Scorer:
    def __init__(self, value, calls):
        self.value, self.calls = value, calls

    async def ascore(self, **arguments):
        self.calls.append(arguments)
        return SimpleNamespace(value=self.value)


def scorers(values, calls):
    return {name: Scorer(value, calls) for name, value in values.items()}


async def test_the_default_profile_requires_nothing():
    assert await score_metrics(case(), trace(), {'metric_profile': 'none', 'required_metrics': []}, None) == []


async def test_relevancy_does_not_apply_to_waiting_for_approval_and_contexts_are_passages():
    calls = []
    found = await score_metrics(case(), trace(), PROFILE, None, scorers=scorers({'faithfulness': 0.9, 'context_precision': 0.75}, calls))
    by_name = {m.name: m for m in found}
    assert by_name['answer_relevancy'].status == 'not_applicable'
    assert by_name['faithfulness'].status == 'scored' and by_name['context_precision'].value == 0.75
    precision = next(c for c in calls if 'retrieved_contexts' in c and c['retrieved_contexts'] == ['Khóa van tổng trước khi sửa.'])
    assert precision['user_input'] == 'Nhà tôi bị rò nước'
    # Faithfulness also reads what the tools returned; precision reads passages only.
    assert any(len(c.get('retrieved_contexts', [])) == 2 for c in calls)


async def test_a_content_answer_is_scored_for_relevancy():
    found = await score_metrics(case(terminal_state='resolved'), trace(terminal_state='resolved'), PROFILE, None,
                                scorers=scorers({'faithfulness': 0.9, 'answer_relevancy': 0.5, 'context_precision': 0.9}, []))
    assert {m.name: m.status for m in found} == {'faithfulness': 'scored', 'answer_relevancy': 'scored', 'context_precision': 'scored'}


async def test_missing_required_source_is_an_error_not_not_applicable():
    found = await score_metrics(case(), trace(retrievals=[], tool_calls=[]), PROFILE, None, scorers={})
    assert {m.name: m.status for m in found}['context_precision'] == 'error'
    no_rag = case(required_sources=[])
    found = await score_metrics(no_rag, trace(retrievals=[], tool_calls=[]), PROFILE, None, scorers={})
    assert {m.name: m.status for m in found}['context_precision'] == 'not_applicable'


async def test_library_failures_and_nan_are_errors():
    class Broken:
        async def ascore(self, **_):
            raise RuntimeError('rate limited')
    found = await score_metrics(case(), trace(), PROFILE, None,
                                scorers={'faithfulness': Broken(), 'context_precision': Scorer(float('nan'), [])})
    assert {m.name: m.status for m in found if m.name != 'answer_relevancy'} == {'faithfulness': 'error', 'context_precision': 'error'}


async def test_without_a_model_or_the_library_required_metrics_are_errors():
    found = await score_metrics(case(), trace(), PROFILE, None)
    assert {m.status for m in found if m.name != 'answer_relevancy'} == {'error'}
