import type { EvaluationRecord } from '../types';

export function AsyncEvaluationReport({ evaluation }: { evaluation: EvaluationRecord }) {
	return <div className="space-y-4">
		<p>Suite: {evaluation.report.suite_version} · {evaluation.report.status}</p>
		<p>Chi phí: {String(evaluation.report.metrics.cost ?? '—')} · Độ trễ: {String(evaluation.report.metrics.latency_ms ?? '—')} ms</p>
		{evaluation.report.hard_gate_failures.length > 0 && <p role="alert" className="text-destructive">
			Chặn phát hành: {evaluation.report.hard_gate_failures.join(', ')}
		</p>}
		{evaluation.report.cases.map(test => <details key={test.case_id} className="rounded-lg border p-3">
			<summary>{test.case_id} · {test.status}</summary>
			<p className="text-destructive">{[...test.hard_gate_failures, test.error_code].filter(Boolean).join(', ')}</p>
			<pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(test.metrics, null, 2)}</pre>
		</details>)}
	</div>;
}
