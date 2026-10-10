import { useEffect, useState } from 'react';

import type { AgentsApi } from './api';
import type { Batch, PublishSelection } from './types';
import { Button } from '@/components/ui/button';

export function WorkforceBatchResults({ api, batchId }: { api: AgentsApi; batchId: string }) {
	return <BatchResults key={batchId} api={api} batchId={batchId} />;
}

function BatchResults({ api, batchId }: { api: AgentsApi; batchId: string }) {
	const [batch, setBatch] = useState<Batch>();
	const [selected, setSelected] = useState<string[]>([]);
	const [error, setError] = useState('');
	const [busy, setBusy] = useState(false);
	useEffect(() => {
		let active = true;
		api.getBatch(batchId).then(value => { if (active) setBatch(value); })
			.catch(e => { if (active) setError(String(e)); });
		return () => { active = false; };
	}, [api, batchId]);
	async function publish() {
		if (!batch) return;
		setBusy(true); setError('');
		try {
			const selections: PublishSelection[] = [];
			for (const item of batch.items.filter(value => selected.includes(value.item_id))) {
				if (!item.draft_id || !item.evaluation_id) throw new Error('Agent chưa đủ điều kiện');
				const evaluation = await api.getEvaluation(item.evaluation_id);
				selections.push({ draft_id: item.draft_id, expected_revision: evaluation.snapshot.draft_revision,
					evaluation_id: item.evaluation_id, manifest_hash: evaluation.snapshot.manifest_hash });
			}
			setBatch(await api.publishBatch(batch, selections)); setSelected([]);
		} catch (e) { setError(String(e)); } finally { setBusy(false); }
	}
	return <section className="space-y-3">
		<h2 className="font-semibold">Kết quả tạo nhiều agent</h2>
		{error && <p role="alert" className="text-destructive">{error}</p>}
		{batch?.items.map(item => <label key={item.item_id} className="flex gap-3 rounded-lg border p-3">
			<input type="checkbox" disabled={busy || item.status !== 'passed'} checked={selected.includes(item.item_id)}
				onChange={event => setSelected(old => event.target.checked ? [...old, item.item_id] : old.filter(id => id !== item.item_id))} />
			{item.agent_key} · {item.status === 'completed_reused' ? 'Đã có — không cần tạo lại' : item.status}
		</label>)}
		<Button disabled={busy || selected.length === 0} onClick={publish}>Phát hành {selected.length} agent đã chọn</Button>
	</section>;
}
