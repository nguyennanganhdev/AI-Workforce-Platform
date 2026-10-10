import type { TimelineState } from './state';

const labels: Record<TimelineState['state'], string> = {
	accepted: 'Đã tiếp nhận',
	active: 'Đang xử lý',
	waiting_external_event: 'Đang chờ cập nhật từ nhà cung cấp',
	awaiting_user: 'Chờ bạn trả lời',
	awaiting_approval: 'Chờ xác nhận giao dịch',
	awaiting_confirmation: 'Chờ xác nhận hoàn tất',
	needs_attention: 'Cần kiểm tra',
	blocked_authorization: 'Cần kiểm tra quyền truy cập',
	blocked_route_changed: 'Cần xác nhận lại nơi xử lý',
	closed: 'Đã đóng',
};

export function WorkflowStatus({ state }: { state: TimelineState }) {
	return (
		<div role="status" aria-live="polite" className="rounded-lg bg-muted p-3 text-sm">
			<p>{labels[state.state]}</p>
			{state.connection === 'reconnecting' && (
				<p>Đang kết nối lại và tải các cập nhật còn thiếu…</p>
			)}
			{state.connection === 'connecting' && <p>Đang kết nối…</p>}
			{state.connection === 'blocked' && (
				<p>Chưa thể nhận cập nhật. Vui lòng kiểm tra quyền truy cập.</p>
			)}
		</div>
	);
}
