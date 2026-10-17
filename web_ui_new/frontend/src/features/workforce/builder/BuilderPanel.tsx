import { useRef, useState } from 'react';


import { CapabilityPanel } from './async_capabilities/CapabilityPanel';
import { canConfirm, statusLabel } from './state';
import type { BuilderClient, BuildProposal } from './types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

const actionLabels = { create: 'Tạo mới', reuse: 'Đã có', revise: 'Nâng cấp agent hiện có', resume: 'Tiếp tục bản nháp', clarify: 'Cần làm rõ', repair: 'Cần sửa agent hiện có' };

export function BuilderPanel({ client }: { client: BuilderClient }) {
	const [message, setMessage] = useState('');
	const [proposal, setProposal] = useState<BuildProposal | null>(null);
	const [busy, setBusy] = useState(false);
	const [cancelling, setCancelling] = useState(false);
	const [error, setError] = useState('');
	const [history, setHistory] = useState<string[]>([]);
	const active = useRef<AbortController | null>(null);
	const generation = useRef(0);
	const pendingMessage = useRef<{ message: string; revision?: number; id: string } | null>(null);

	async function request(confirm = false) {
		if (active.current || (!confirm && !message.trim())) return;
		const controller = new AbortController();
		active.current = controller;
		const turn = ++generation.current;
		setBusy(true); setError('');
		try {
			let result: BuildProposal;
			if (confirm && proposal) {
				result = await client.confirm(proposal.proposal_id, proposal.revision, controller.signal);
			} else {
				if (!pendingMessage.current || pendingMessage.current.message !== message || pendingMessage.current.revision !== proposal?.revision) {
					pendingMessage.current = { message, revision: proposal?.revision, id: crypto.randomUUID() };
				}
				result = await client.prepare({ message, client_message_id: pendingMessage.current.id,
					proposal_id: proposal?.proposal_id, expected_revision: proposal?.revision }, controller.signal);
			}
			if (turn !== generation.current) return;
			setProposal(result);
			if (!confirm) { setHistory(previous => [...previous, message]); setMessage(''); pendingMessage.current = null; }
		} catch {
			if (turn === generation.current && !controller.signal.aborted) setError('Chưa xử lý được yêu cầu. Thử lại hoặc chỉnh nội dung.');
		} finally {
			if (turn === generation.current) { active.current = null; setBusy(false); }
		}
	}

	async function cancel() {
		if (cancelling) return;
		++generation.current;
		active.current?.abort(); active.current = null;
		setBusy(true); setCancelling(true); setError('');
		try {
			if (proposal) await client.cancel(proposal.proposal_id);
			setProposal(null); setHistory([]); pendingMessage.current = null;
		} catch { setError('Chưa hủy được đề xuất. Hãy thử lại.'); }
		finally { setBusy(false); setCancelling(false); }
	}

	const locked = proposal?.status === 'confirmed' || proposal?.status === 'completed_reused';
	return (
		<div className="mx-auto max-w-3xl space-y-5 p-6" aria-busy={busy}>
			<h2 className="text-xl font-semibold">Tạo một hoặc nhiều agent</h2>
			<p>Tạo nhiều agent là thao tác hàng loạt. Mỗi agent hoạt động độc lập trong thư viện.</p>
			{history.length > 0 && <ol aria-label="Hội thoại tạo agent" className="space-y-2">{history.map((text, index) => <li key={index} className="rounded bg-muted p-3">{text}</li>)}</ol>}
			{proposal && <>
				<p role="status">{statusLabel(proposal)} · {proposal.items.length} agent · {proposal.items.filter(item => item.reuse_decision.action === 'create').length} agent mới</p>
				{proposal.notices.map((notice, index) => <p key={index} role="alert">{notice}</p>)}
				{proposal.questions.map((question, index) => <p key={index}>{question}</p>)}
				{proposal.items.map(item => <article key={item.requirement.agent_key} className="space-y-2">
					<CapabilityPanel item={item} />
					<p>{actionLabels[item.reuse_decision.action]}: {item.reuse_decision.reason}</p>
					{item.reuse_decision.agent_id && <p className="text-sm">Agent {item.reuse_decision.agent_id} · Phiên bản {item.reuse_decision.version_id || 'Bản nháp'}</p>}
					{item.candidates.map(candidate => <div key={candidate.agent_id} className="text-sm">
						<p>Ứng viên {candidate.agent_id}: {candidate.reason}</p>
						<p>Còn thiếu: {candidate.missing_requirements.join(', ') || 'Không có thông tin thiếu'}</p>
						<p>Khác biệt: {candidate.differences.join(', ') || 'Không có thông tin khác biệt'}</p>
					</div>)}
					{item.duplicate_keys.length > 0 && <p>Đã gộp các yêu cầu cùng nghiệp vụ: {item.duplicate_keys.join(', ')}</p>}
				</article>)}
			</>}
			{!locked && <form onSubmit={event => { event.preventDefault(); void request(); }} className="space-y-3">
				<label htmlFor="builder-message">{proposal ? 'Bổ sung hoặc sửa toàn bộ yêu cầu tạo agent' : 'Bạn muốn tạo agent hỗ trợ việc gì?'}</label>
				<Textarea id="builder-message" value={message} onChange={event => setMessage(event.target.value)} maxLength={16000} disabled={busy} />
				<Button type="submit" disabled={busy || !message.trim()}>Xem đề xuất</Button>
			</form>}
			{error && <p role="alert" className="text-destructive">{error}</p>}
			<div className="flex gap-3">
				<Button onClick={() => void request(true)} disabled={busy || !canConfirm(proposal)}>Xác nhận lựa chọn</Button>
				<Button variant="outline" onClick={() => void cancel()} disabled={cancelling}>Hủy / bắt đầu lại</Button>
			</div>
		</div>
	);
}
