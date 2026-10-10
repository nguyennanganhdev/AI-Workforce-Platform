import { useEffect, useState } from 'react';

import type { AgentsApi } from './api';
import type { AgentDefinition } from './types';
import { Button } from '@/components/ui/button';

export function WorkforceAgentsPage({ api, onSettings, onChat }: {
	api: AgentsApi; onSettings: (agent: AgentDefinition) => void; onChat: (agentId: string) => void;
}) {
	const [agents, setAgents] = useState<AgentDefinition[]>([]);
	const [cursor, setCursor] = useState<string>();
	const [error, setError] = useState('');
	const [busy, setBusy] = useState(false);
	useEffect(() => {
		let active = true;
		api.listAgents().then(page => {
			if (active) { setAgents(page.items); setCursor(page.next_cursor); }
		}).catch(e => { if (active) setError(String(e)); });
		return () => { active = false; };
	}, [api]);
	async function loadMore() {
		setBusy(true);
		try {
			const page = await api.listAgents(cursor);
			setAgents(old => [...old, ...page.items]); setCursor(page.next_cursor);
		} catch (e) { setError(String(e)); } finally { setBusy(false); }
	}
	return <section className="space-y-4 p-6">
		<h1 className="text-xl font-semibold">Thư viện agent</h1>
		{error && <p role="alert" className="text-destructive">{error}</p>}
		{agents.length === 0 && <p>Chưa có agent trong thư viện của bạn.</p>}
		{agents.map(agent => <article key={agent.agent_id} className="flex items-center justify-between rounded-lg border p-4">
			<div><h2 className="font-medium">{agent.name}</h2><p>{agent.status}{agent.draft_id ? ' · Có bản nháp' : ''}</p>
				<p className="text-muted-foreground text-sm">{agent.business_profile.capabilities.join(', ')}</p></div>
			<div className="flex gap-2"><Button variant="outline" onClick={() => onSettings(agent)}>Settings</Button>
				<Button disabled={agent.status !== 'published'} onClick={() => onChat(agent.agent_id)}>Chat</Button></div>
		</article>)}
		{cursor && <Button variant="outline" disabled={busy} onClick={loadMore}>Xem thêm</Button>}
	</section>;
}
