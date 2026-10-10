import { useEffect, useRef, useState } from 'react';

import type { AgentsApi } from './api';
import { AsyncEvaluationReport } from './async_evaluation/AsyncEvaluationReport';
import type { EvaluationRecord } from './types';
import { Button } from '@/components/ui/button';

export function WorkforceEvaluationPage({ api, evaluationId }: { api: AgentsApi; evaluationId: string }) {
	return <EvaluationReportPage key={evaluationId} api={api} evaluationId={evaluationId} />;
}

function EvaluationReportPage({ api, evaluationId }: { api: AgentsApi; evaluationId: string }) {
	const [evaluation, setEvaluation] = useState<EvaluationRecord>();
	const [error, setError] = useState('');
	const [busy, setBusy] = useState(false);
	const [published, setPublished] = useState(false);
	const publishKey = useRef(crypto.randomUUID());
	useEffect(() => {
		let active = true;
		let timer: ReturnType<typeof setTimeout>;
		async function load() {
			try {
				const value = await api.getEvaluation(evaluationId);
				if (!active) return;
				setEvaluation(value);
				if (['queued', 'running'].includes(value.report.status)) timer = setTimeout(load, 2000);
			} catch (e) { if (active) setError(String(e)); }
		}
		void load();
		return () => { active = false; clearTimeout(timer); };
	}, [api, evaluationId]);
	const ready = evaluation?.report.status === 'passed' && evaluation.report.hard_gate_failures.length === 0;
	async function publish() {
		if (!evaluation) return;
		setBusy(true); setError('');
		try {
			await api.publish({ draft_id: evaluation.snapshot.draft_id,
				expected_revision: evaluation.snapshot.draft_revision,
				evaluation_id: evaluationId, manifest_hash: evaluation.snapshot.manifest_hash }, publishKey.current);
			setPublished(true);
		} catch (e) { setError(`${String(e)} · Nếu evaluation đã cũ, hãy đánh giá lại bản nháp.`); }
		finally { setBusy(false); }
	}
	return <section className="space-y-4 p-6">
		<h1 className="text-xl font-semibold">Báo cáo đánh giá</h1>
		{error && <p role="alert" className="text-destructive">{error}</p>}
		{evaluation && <AsyncEvaluationReport evaluation={evaluation} />}
		{published ? <p>Agent đã được phát hành vào thư viện.</p> : <Button disabled={!ready || busy} onClick={publish}>Phát hành agent</Button>}
		{evaluation && ['queued', 'running'].includes(evaluation.report.status) && <Button variant="outline" onClick={async () => {
			try { setEvaluation(await api.cancelEvaluation(evaluationId)); } catch (e) { setError(String(e)); }
		}}>Hủy đánh giá</Button>}
	</section>;
}
