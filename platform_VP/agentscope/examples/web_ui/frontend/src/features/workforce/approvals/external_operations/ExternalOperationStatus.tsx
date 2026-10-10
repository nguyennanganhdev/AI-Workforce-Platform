export interface ExternalOperationView {
	creation_status: 'intent' | 'succeeded' | 'failed' | 'unknown';
	job_status: string | null;
	pending: boolean;
	external_job_id: string | null;
}

const creationLabels = {
	intent: 'Chuẩn bị gửi yêu cầu',
	succeeded: 'Nhà cung cấp đã nhận yêu cầu',
	failed: 'Gửi yêu cầu không thành công',
	unknown: 'Chưa xác định nhà cung cấp đã nhận yêu cầu',
};

export function WorkforceExternalOperationStatus({
	operation,
	progressLabel,
}: {
	operation: ExternalOperationView;
	progressLabel?: string;
}) {
	return (
		<section aria-label="Tiến độ công việc" className="space-y-1 rounded-lg border p-3 text-sm">
			<p role="status">{creationLabels[operation.creation_status]}</p>
			{operation.external_job_id && <p>Mã nhà cung cấp: {operation.external_job_id}</p>}
			<p>
				Tiến độ:{' '}
				{progressLabel ??
					(operation.pending ? 'Đang chờ cập nhật' : 'Đã kết thúc theo dõi công việc')}
			</p>
			{operation.creation_status === 'unknown' && (
				<p>Đang đối soát. Chưa gửi yêu cầu tạo mới.</p>
			)}
		</section>
	);
}
