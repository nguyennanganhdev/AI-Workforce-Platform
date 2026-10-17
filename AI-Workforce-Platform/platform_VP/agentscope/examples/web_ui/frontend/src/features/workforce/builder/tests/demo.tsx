import { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

import '@/index.css';

import { BuilderPanel } from '../BuilderPanel';
import { fakeClient, type Scenario } from './fakeClient';

export function Demo() {
	const [scenario, setScenario] = useState<Scenario>('ready');
	const client = useMemo(() => fakeClient(scenario), [scenario]);
	return <main className="min-h-screen bg-background text-foreground">
		<div className="mx-auto max-w-3xl p-6">
			<p className="font-semibold">DEMO / FAKE — Không tạo agent hay giao dịch thật</p>
			<label htmlFor="scenario">Kịch bản kiểm tra </label>
			<select id="scenario" value={scenario} onChange={event => setScenario(event.target.value as Scenario)}>
				<option value="ready">Đủ capability</option><option value="reused">Đã có agent</option>
				<option value="missing">Thiếu capability</option><option value="tracking">Theo dõi / revise</option>
				<option value="query_only">Query-only chưa chốt event semantics</option>
				<option value="refresh">D3 — Catalog refresh</option><option value="permission">D3 — Permission failure</option>
				<option value="optional_missing">D3 — Optional missing</option><option value="late_confirm">D3 — Late response after cancel</option>
			</select>
		</div>
		<BuilderPanel key={scenario} client={client} />
	</main>;
}

createRoot(document.getElementById('root')!).render(<Demo />);
