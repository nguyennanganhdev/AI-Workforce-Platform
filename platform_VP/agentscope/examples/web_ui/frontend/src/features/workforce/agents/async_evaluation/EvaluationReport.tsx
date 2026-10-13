/** Phase B report view. The composition owner supplies authorized API data. */
export interface EvaluationReportView {
	evaluation_id: string;
	status: string;
	suite_version: string;
	metrics: { completion_rate?: number; cost?: number; latency_ms?: number };
	hard_gate_failures: string[];
	cases: {
		case_id: string;
		status: string;
		error_code?: string | null;
		hard_gate_failures: string[];
		metrics: {
			pattern?: string;
			cost?: number;
			latency_ms?: number;
			argument_rate?: number;
			turns?: {
				cause: string;
				workflow_state: string;
				next_action: string;
				llm_calls: number;
				side_effect_calls: number;
				cost: number;
				latency_ms: number;
			}[];
		};
	}[];
}

export function EvaluationReport({
	report,
	loading = false,
	error,
}: {
	report?: EvaluationReportView;
	loading?: boolean;
	error?: string;
}) {
	if (loading) return <p role="status">Đang tải kết quả đánh giá…</p>;
	if (error) return <p role="alert">Không thể tải kết quả: {error}</p>;
	if (!report) return <p>Chưa có kết quả đánh giá.</p>;
	return (
		<section aria-label="Kết quả đánh giá agent">
			<h2>Đánh giá {report.evaluation_id}</h2>
			<p>Trạng thái: {report.status} · Bộ kiểm tra: {report.suite_version}</p>
			<p>
				Hoàn thành: {((report.metrics.completion_rate ?? 0) * 100).toFixed(0)}%
				{" · "}Chi phí: {report.metrics.cost ?? 0}
				{" · "}Thời gian: {report.metrics.latency_ms ?? 0} ms
			</p>
			{report.hard_gate_failures.length > 0 && (
				<div role="alert">
					<p>Đánh giá bị chặn:</p>
					<ul>{report.hard_gate_failures.map((failure) => <li key={failure}>{failure}</li>)}</ul>
				</div>
			)}
			{report.cases.map((item) => (
				<details key={item.case_id} open={item.status !== "passed"}>
					<summary>{item.case_id} · {item.metrics.pattern} · {item.status}</summary>
					<p>Chi phí: {item.metrics.cost ?? 0} · Thời gian: {item.metrics.latency_ms ?? 0} ms</p>
					{item.error_code && <p role="alert">{item.error_code}</p>}
					<ul>{item.hard_gate_failures.map((failure) => <li key={failure}>{failure}</li>)}</ul>
					<div className="overflow-x-auto">
						<table>
							<caption>Kết quả từng lượt</caption>
							<thead><tr><th>Lượt</th><th>Trạng thái</th><th>Hành động tiếp</th><th>LLM</th><th>Giao dịch</th><th>Chi phí</th><th>ms</th></tr></thead>
							<tbody>{item.metrics.turns?.map((turn, index) => (
								<tr key={`${index}-${turn.cause}`}>
									<td>{turn.cause}</td><td>{turn.workflow_state}</td><td>{turn.next_action}</td>
									<td>{turn.llm_calls}</td><td>{turn.side_effect_calls}</td><td>{turn.cost}</td><td>{turn.latency_ms}</td>
								</tr>
							))}</tbody>
						</table>
					</div>
				</details>
			))}
		</section>
	);
}
