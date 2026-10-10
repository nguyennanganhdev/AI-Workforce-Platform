import { useRef, useState } from 'react';

import { timelineKey } from './state';
import type { TimelineBinding, TimelineState } from './state';
import { WorkflowStatus } from './WorkflowStatus';
import { WorkforceApprovalCard } from '../../approvals';
import type { ApprovalView, DecisionInput } from '../../approvals';

export interface TicketTimelineProps {
	state: TimelineState;
	onClose: (
		binding: TimelineBinding,
		revision: number,
		stopTrackingOnly: boolean,
	) => Promise<void>;
	approvals?: readonly ApprovalView[];
	onDecide?: (approvalId: string, decision: DecisionInput) => Promise<void>;
}

export function TicketTimeline(props: TicketTimelineProps) {
	return <TimelineContent key={timelineKey(props.state.binding)} {...props} />;
}

function TimelineContent({ state, onClose, approvals = [], onDecide }: TicketTimelineProps) {
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [stopTracking, setStopTracking] = useState(false);
	const closing = useRef(false);
	const canClose =
		state.state !== 'closed' &&
		state.state !== 'awaiting_approval' &&
		state.approvalIds.length === 0 &&
		state.revision > 0 &&
		state.connection !== 'blocked' &&
		(state.state === 'awaiting_confirmation' || stopTracking);
	async function close() {
		if (!canClose || closing.current) return;
		closing.current = true;
		setBusy(true);
		setError(null);
		try {
			await onClose(state.binding, state.revision, stopTracking);
		} catch {
			setError('Chưa đóng được yêu cầu. Hãy tải lại trạng thái rồi thử lại.');
		} finally {
			closing.current = false;
			setBusy(false);
		}
	}
	return (
		<section
			aria-label={`Yêu cầu ${state.binding.externalTicketId ?? state.binding.workflowId}`}
			className="space-y-4 rounded-xl border p-5"
		>
			<h2 className="text-lg font-semibold">
				Yêu cầu {state.binding.externalTicketId ?? state.binding.workflowId}
			</h2>
			<WorkflowStatus state={state} />
			<ol aria-label="Tin nhắn" className="space-y-3">
				{state.messages.map((message) => (
					<li key={message.message_id} className="rounded-lg bg-primary/5 p-3">
						<p className="text-xs font-semibold">Trợ lý</p>
						<p className="whitespace-pre-wrap">{message.text}</p>
					</li>
				))}
			</ol>
			<ol aria-label="Tiến độ yêu cầu" className="space-y-2 text-sm">
				{state.cards
					.filter((event) =>
						[
							'operation.status_changed',
							'ticket.status_changed',
							'workflow.needs_attention',
							'approval.required',
						].includes(event.event_type),
					)
					.map((event) => (
						<li key={event.event_id} className="border-l-2 pl-3">
							{event.event_type === 'operation.status_changed' ||
							event.event_type === 'ticket.status_changed'
								? `Cập nhật tiến độ: ${String(event.payload.status)}`
								: event.event_type === 'approval.required'
									? String(event.payload.summary)
									: 'Yêu cầu cần kiểm tra'}
						</li>
					))}
			</ol>
			{onDecide &&
				approvals
					.filter((a) => state.approvalIds.includes(a.approval_id))
					.map((approval) => (
						<WorkforceApprovalCard
							key={approval.approval_id}
							approval={approval}
							canDecide={
								state.state === 'awaiting_approval' &&
								state.connection !== 'blocked'
							}
							onDecide={onDecide}
						/>
					))}
			{state.state !== 'closed' && state.state !== 'awaiting_confirmation' && (
				<label className="flex gap-2 text-sm">
					<input
						type="checkbox"
						checked={stopTracking}
						onChange={(e) => setStopTracking(e.target.checked)}
					/>
					Dừng theo dõi yêu cầu này (giao dịch với nhà cung cấp vẫn tiếp tục)
				</label>
			)}
			{error && <p role="alert">{error}</p>}
			<button
				type="button"
				disabled={busy || !canClose}
				onClick={() => void close()}
				className="rounded-md border px-4 py-2 disabled:opacity-50"
			>
				{busy
					? 'Đang đóng…'
					: state.state === 'closed'
						? 'Đã đóng yêu cầu'
						: 'Đóng yêu cầu'}
			</button>
		</section>
	);
}
