import type { ExecutionState } from './types';

const labels: Record<ExecutionState, string> = {
	proposed: 'Đã đề xuất',
	awaiting_approval: 'Chờ xác nhận',
	executing: 'Đang thực hiện',
	succeeded: 'Gọi dịch vụ thành công',
	confirmed: 'Đã xác nhận giao dịch',
	unknown: 'Chưa xác định kết quả',
	failed: 'Không thực hiện được',
	partial: 'Một phần đã thành công',
};

export function WorkforceExecutionStatus({
	status,
	onRefresh,
}: {
	status: ExecutionState;
	onRefresh?: () => void;
}) {
	return (
		<div role="status" className="space-y-1 text-sm">
			<p>{labels[status]}</p>
			{status === 'unknown' && (
				<p>Đang đối soát với nhà cung cấp. Vui lòng chưa đặt lại giao dịch này.</p>
			)}
			{status === 'partial' && (
				<p>Xem kết quả từng giao dịch trước khi quyết định bước tiếp theo.</p>
			)}
			{onRefresh && (
				<button type="button" onClick={onRefresh} className="underline">
					Tải lại trạng thái
				</button>
			)}
		</div>
	);
}
