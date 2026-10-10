import { useEffect, useRef, useState } from 'react';

import type { AgentsApi } from './api';
import type { AgentDefinition, AgentDraft, AgentManifest, PublishedVersion } from './types';
import { Button } from '@/components/ui/button';

export function WorkforceAgentSettingsPage({ api, agent, onEvaluation }: {
	api: AgentsApi; agent: AgentDefinition; onEvaluation: (id: string) => void;
}) {
	return <AgentSettingsEditor key={agent.agent_id} api={api} agent={agent} onEvaluation={onEvaluation} />;
}

function AgentSettingsEditor({ api, agent, onEvaluation }: {
	api: AgentsApi; agent: AgentDefinition; onEvaluation: (id: string) => void;
}) {
	const [draft, setDraft] = useState<AgentDraft>();
	const [editor, setEditor] = useState('');
	const [versions, setVersions] = useState<PublishedVersion[]>([]);
	const [diff, setDiff] = useState<unknown[]>([]);
	const [error, setError] = useState('');
	const [busy, setBusy] = useState(false);
	const evaluationKeys = useRef(new Map<string, string>());
	useEffect(() => {
		let active = true;
		api.history(agent.agent_id).then(page => { if (active) setVersions(page.items); })
			.catch(e => { if (active) setError(String(e)); });
		if (agent.draft_id) api.getDraft(agent.draft_id).then(value => {
			if (active) { setDraft(value); setEditor(JSON.stringify(value.manifest, null, 2)); }
		}).catch(e => { if (active) setError(String(e)); });
		return () => { active = false; };
	}, [api, agent.agent_id, agent.draft_id]);
	async function act(operation: () => Promise<void>) {
		setBusy(true); setError('');
		try { await operation(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
	}
	function openDraft(value: AgentDraft) { setDraft(value); setEditor(JSON.stringify(value.manifest, null, 2)); }
	return <section className="space-y-4 p-6">
		<h1 className="text-xl font-semibold">Settings · {agent.name}</h1>
		{error && <p role="alert" className="text-destructive">{error} · Tải lại dữ liệu nếu bản nháp hoặc evaluation đã thay đổi.</p>}
		{!draft && agent.active_version_id && <Button disabled={busy} onClick={() => act(async () => {
			openDraft(await api.fork(agent.active_version_id!));
		})}>Tạo bản nháp chỉnh sửa</Button>}
		{draft && <>
			<p>Bản nháp revision {draft.revision}. Prompt, model, tool, knowledge, skill và policy được lưu trong cấu hình dưới đây.</p>
			<label className="block">Cấu hình agent<textarea aria-label="Cấu hình agent" className="mt-2 min-h-80 w-full rounded-lg border p-3 font-mono text-xs"
				value={editor} onChange={event => setEditor(event.target.value)} /></label>
			<p className="text-muted-foreground">Model dùng credential_ref. Thay đổi cấu hình cần đánh giá lại trước phát hành.</p>
			<div className="flex gap-2">
				<Button disabled={busy} onClick={() => act(async () => {
					openDraft(await api.updateDraft(draft, JSON.parse(editor) as AgentManifest));
					setDiff((await api.diff(draft.draft_id)).items);
				})}>Lưu bản nháp</Button>
				<Button variant="outline" disabled={busy} onClick={() => act(async () => {
					const report = await api.validateDraft(draft.draft_id);
					openDraft(await api.getDraft(draft.draft_id));
					if (!report.valid) throw new Error(report.blockers.join(', '));
				})}>Kiểm tra cấu hình</Button>
				<Button disabled={busy || editor !== JSON.stringify(draft.manifest, null, 2)} onClick={() => act(async () => {
					const request = `${draft.draft_id}:${draft.revision}`;
					if (!evaluationKeys.current.has(request)) evaluationKeys.current.set(request, crypto.randomUUID());
					const result = await api.evaluate(draft, 'lifecycle-patterns-v1', evaluationKeys.current.get(request)!);
					onEvaluation(result.report.evaluation_id);
				})}>Đánh giá</Button>
			</div>
			{diff.length > 0 && <details><summary>Thay đổi so với phiên bản gốc</summary><pre className="overflow-auto text-xs">{JSON.stringify(diff, null, 2)}</pre></details>}
		</>}
		<h2 className="font-semibold">Lịch sử phiên bản</h2>
		{versions.map(version => <div key={version.version_id} className="flex items-center justify-between rounded-lg border p-3">
			<span>{version.published_at} · {version.version_id === agent.active_version_id ? 'Đang hoạt động' : version.version_id}</span>
			<Button variant="outline" disabled={busy || version.version_id === agent.active_version_id} onClick={() => act(async () => {
				const deployments = await api.deployments();
				const current = deployments.items.find(item => item.agent_id === agent.agent_id);
				if (!current) throw new Error('Không tìm thấy deployment');
				await api.rollback(current.deployment_id, version.version_id, current.revision);
				setError('Đã rollback. Tải lại trang để xem phiên bản đang hoạt động.');
			})}>Rollback</Button>
		</div>)}
	</section>;
}
