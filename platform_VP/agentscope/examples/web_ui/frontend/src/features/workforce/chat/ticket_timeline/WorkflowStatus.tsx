import type { TimelineState } from './state';

const labels: Record<TimelineState['workflowState'], string> = {
	accepted: 'Đã tiếp nhận',
	active: 'Đang xử lý',
	waiting_external_event: 'Đang chờ cập nhật từ nhà cung cấp',
	awaiting_user: 'Chờ khách hàng trả lời',
	awaiting_approval: 'Chờ xác nhận giao dịch',
	awaiting_confirmation: 'Chờ xác nhận hoàn tất',
	needs_attention: 'Cần kiểm tra',
	blocked_authorization: 'Quyền truy cập đã thay đổi',
	blocked_route_changed: 'Nơi quản lý đã thay đổi',
	closed: 'Đã đóng',
};

export function WorkflowStatus({ state }: { state: TimelineState }) {
	return (
		<div role="status" aria-live="polite" className="rounded-lg bg-muted p-3 text-sm">
			<p>{labels[state.workflowState]}</p>
			{state.connection === 'connecting' && <p>Đang kết nối…</p>}
			{state.connection === 'reconnecting' && (
				<p>Đang kết nối lại và tải các cập nhật còn thiếu…</p>
			)}
			{state.connection === 'blocked' && (
				<p>Không thể nhận cập nhật. Vui lòng kiểm tra lại quyền truy cập.</p>
			)}
		</div>
	);
}

