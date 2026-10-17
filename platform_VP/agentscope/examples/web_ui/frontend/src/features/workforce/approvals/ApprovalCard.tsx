import { useEffect, useRef, useState } from 'react';

import { formatMoney } from './format';
import type { ApprovalView, DecisionInput } from './types';
import { Button } from '@/components/ui/button';

export interface WorkforceApprovalCardProps {
	approval: ApprovalView;
	canDecide: boolean;
	onDecide: (approvalId: string, decision: DecisionInput) => Promise<void>;
}

export function WorkforceApprovalCard({
	approval,
	canDecide,
	onDecide,
}: WorkforceApprovalCardProps) {
	return (
		<ApprovalCardContent
			key={approval.approval_id}
			approval={approval}
			canDecide={canDecide}
			onDecide={onDecide}
		/>
	);
}

function ApprovalCardContent({ approval, canDecide, onDecide }: WorkforceApprovalCardProps) {
	const [now, setNow] = useState(() => Date.now());
	const [busy, setBusy] = useState(false);
	const [submitted, setSubmitted] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const inFlight = useRef(false);
	useEffect(() => {
		const timer = window.setInterval(() => setNow(Date.now()), 1000);
		return () => window.clearInterval(timer);
	}, []);
	useEffect(() => {
		setSubmitted(false);
		setError(null);
	}, [approval.approval_id]);
	const expires = Date.parse(approval.expires_at);
	const expired = !Number.isFinite(expires) || now >= expires;
	const disabled = busy || submitted || expired || !canDecide || approval.status !== 'pending';

	async function decide(decision: DecisionInput['decision']) {
		if (disabled || inFlight.current) return;
		inFlight.current = true;
		setBusy(true);
		setError(null);
		try {
			await onDecide(approval.approval_id, {
				decision,
				arguments_hash: approval.arguments_hash,
				quote_hash: approval.quote_hash,
			});
			setSubmitted(true);
		} catch {
			setError('Chưa gửi được quyết định. Vui lòng tải lại trạng thái và thử lại.');
		} finally {
			inFlight.current = false;
			setBusy(false);
		}
	}

	return (
		<section
			aria-label="Xác nhận giao dịch"
			aria-busy={busy}
			className="space-y-3 rounded-lg border p-4"
		>
			<h3 className="font-semibold">Xác nhận {approval.quote.option}</h3>
			<dl className="grid grid-cols-2 gap-2 text-sm">
				<dt>Nhà cung cấp</dt>
				<dd>{approval.quote.provider}</dd>
				<dt>Ngày thực hiện</dt>
				<dd>{approval.quote.dates.join(', ')}</dd>
				<dt>Giá</dt>
				<dd>{formatMoney(approval.quote.amount)}</dd>
				<dt>Phí</dt>
				<dd>{formatMoney(approval.quote.fees)}</dd>
				<dt>Điều kiện hủy</dt>
				<dd>{approval.quote.cancellation_terms}</dd>
				<dt>Hiệu lực xác nhận</dt>
				<dd>{new Date(approval.expires_at).toLocaleString('vi-VN')}</dd>
			</dl>
			<p role="status" className="text-sm">
				{expired && approval.status === 'pending'
					? 'Xác nhận đã hết hạn. Cần lấy báo giá mới.'
					: submitted
						? 'Đã ghi nhận quyết định. Đang chờ cập nhật giao dịch.'
						: `Trạng thái: ${{ pending: 'Chờ xác nhận', approved: 'Đã đồng ý', rejected: 'Đã từ chối', consumed: 'Đã dùng xác nhận', expired: 'Hết hạn' }[approval.status]}`}
			</p>
			{error && (
				<p role="alert" className="text-sm text-destructive">
					{error}
				</p>
			)}
			<div className="flex gap-2">
				<Button disabled={disabled} onClick={() => void decide('approve')}>
					{busy ? 'Đang gửi…' : 'Đồng ý giao dịch'}
				</Button>
				<Button variant="outline" disabled={disabled} onClick={() => void decide('reject')}>
					Từ chối
				</Button>
			</div>
			{approval.decision_history.length > 0 && (
				<ul aria-label="Lịch sử quyết định" className="text-sm">
					{approval.decision_history.map((entry, index) => (
						<li key={`${entry.at}-${index}`}>
							{entry.decision === 'approve' ? 'Đồng ý' : 'Từ chối'} ·{' '}
							{new Date(entry.at).toLocaleString('vi-VN')}
						</li>
					))}
				</ul>
			)}
		</section>
	);
}
