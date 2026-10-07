"""Layer 3: library metrics, only those the run's profile names, never in place of the checks or the judge.

The profile is fixed in the run's snapshot before the run. Its default ('none') requires nothing: the Ragas
thresholds are not yet calibrated on Vietnamese answers. Profile 'ragas-rag-v1' requires Faithfulness >= 0.8,
AnswerRelevancy >= 0.7 and ContextPrecisionWithoutReference >= 0.7 (ragas==0.4.3, optional dependency:
pip install -e .[eval-metrics]). A required metric that cannot be computed is an error, never a pass.

Applicability follows the case: relevancy does not apply to a reply that rightly asks for more or waits
for approval; context precision reads only retrieved passages, never business tool results; a case that
requires a source but retrieved none is an error here (and a failed check in layer 1), not "not applicable".
"""
from __future__ import annotations

import math

from .contracts import EvalCase, MetricResult, Trace, metric_applies
from .llm import ModelConfig

BACKEND, VERSION = 'ragas', '0.4.3'
CONTEXT_METRICS = ('faithfulness', 'context_precision')


def question(case: EvalCase) -> str:
    return '\n'.join([case.input.message, *case.input.follow_up_messages])


def contexts(trace: Trace, *, with_tools: bool) -> list[str]:
    """Retrieved passages in retrieval order; for faithfulness also what successful tools returned."""
    found = [r.content for r in sorted(trace.retrievals, key=lambda r: (r.retrieval_run_id or '', r.rank)) if r.content.strip()]
    if with_tools:
        import json
        found += [json.dumps(c.result, ensure_ascii=False, default=str)[:4000] for c in trace.tool_calls if c.status == 'OK' and c.result is not None]
    return found


def result(name: str, status: str, threshold: float, *, value: float | None = None, reason: str = '', error: str | None = None) -> MetricResult:
    return MetricResult(name=name, backend=BACKEND, version=VERSION, status=status, value=value, threshold=threshold,
                        required=True, reason=reason[:2000], error=error)


async def ragas_scorers(model: ModelConfig, embedding_model: str):
    """The three Ragas metrics on the evaluator's model. Imported here: an optional dependency."""
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms.base import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, ContextPrecisionWithoutReference, Faithfulness
    client = AsyncOpenAI(api_key=model.api_key, base_url=model.base_url)
    llm = llm_factory(model.model_name, provider='openai', client=client)
    embeddings = embedding_factory(provider='openai', model=embedding_model, client=client, interface='modern')
    return {'faithfulness': Faithfulness(llm=llm), 'answer_relevancy': AnswerRelevancy(llm=llm, embeddings=embeddings),
            'context_precision': ContextPrecisionWithoutReference(llm=llm)}


async def score_metrics(case: EvalCase, trace: Trace, evaluator: dict, model: ModelConfig | None,
                        *, scorers=None, embedding_model: str = 'text-embedding-3-small') -> list[MetricResult]:
    required = evaluator.get('required_metrics') or []
    if not required:
        return []
    out, pending = [], []
    for spec in required:
        name, threshold = spec['name'], spec['threshold']
        if not metric_applies(case, name):
            out.append(result(name, 'not_applicable', threshold, reason='Hành vi kỳ vọng của ca không phải câu trả lời nội dung.'))
            continue
        if name in CONTEXT_METRICS and not contexts(trace, with_tools=name == 'faithfulness'):
            if case.expectations.required_sources:
                out.append(result(name, 'error', threshold, error='no_context', reason='Ca yêu cầu nguồn nhưng không có ngữ cảnh nào được truy xuất.'))
            else:
                out.append(result(name, 'not_applicable', threshold, reason='Không có đoạn tài liệu hay kết quả tool nào để đối chiếu.'))
            continue
        if not (trace.final_response or '').strip():
            out.append(result(name, 'error', threshold, error='no_response', reason='Không có phản hồi để chấm.'))
            continue
        pending.append((name, threshold))
    if not pending:
        return out
    if scorers is None:
        if model is None:
            return out + [result(n, 'error', t, error='metric_model_unconfigured') for n, t in pending]
        try:
            scorers = await ragas_scorers(model, embedding_model)
        except ImportError:
            return out + [result(n, 'error', t, error='ragas_not_installed', reason='Cài agent-coordination[eval-metrics].') for n, t in pending]
    for name, threshold in pending:
        try:
            if name == 'answer_relevancy':
                scored = await scorers[name].ascore(user_input=question(case), response=trace.final_response)
            else:
                scored = await scorers[name].ascore(user_input=question(case), response=trace.final_response,
                                                    retrieved_contexts=contexts(trace, with_tools=name == 'faithfulness'))
            value = float(scored.value)
            if not math.isfinite(value):
                raise ValueError('NaN')
        except Exception as failure:  # noqa: BLE001 - a library failure is recorded as this metric's error
            out.append(result(name, 'error', threshold, error=type(failure).__name__, reason='Thư viện không trả được điểm.'))
            continue
        out.append(result(name, 'scored', threshold, value=value,
                          reason=f'{value:.3f} {"đạt" if value >= threshold else "dưới"} ngưỡng {threshold}.'))
    return out
