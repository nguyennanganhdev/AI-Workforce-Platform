import { useQuery } from '@tanstack/react-query';

import { client } from '@/api/client';
import { useCurrentUser } from '@/context/CurrentUserContext';

interface Run {
	id: string; status: string; outcome?: string; error?: string; created_at: string; session_id?: string;
	deliveries: { id: string; status: string; attempt: number; error?: string }[];
}
const labels: Record<string, string> = { pending: 'Đang chờ', leased: 'Đang xử lý', succeeded: 'Đã chạy',
	failed: 'Lỗi', awaiting_permission: 'Chờ bạn duyệt trên Platform', media_buffered: 'Chờ nội dung tin nhắn' };

export function PersonalRuns({ kind, sourceId }: { kind: 'schedule' | 'channels'; sourceId: string }) {
	const user = useCurrentUser();
	const query = useQuery({ queryKey: ['personal-runs', user?.tenant_id, user?.id, kind, sourceId],
		queryFn: () => client.get<{ items: Run[] }>(`/${kind}/${encodeURIComponent(sourceId)}/runs`, undefined, { silent: true }),
		enabled: user?.role === 'VIN_USER', retry: false, refetchInterval: 10000 });
	if (user?.role !== 'VIN_USER') return null;
	return <section className="space-y-2 py-3 text-sm" aria-label="Lịch sử chạy cá nhân">
		<h3 className="font-medium">Lịch sử chạy và gửi kết quả</h3>
		{query.isPending && <p>Đang tải lịch sử…</p>}
		{query.isError && <p role="alert">Chưa lấy được lịch sử chạy.</p>}
		{query.data?.items.length === 0 && <p className="text-muted-foreground">Chưa có lần chạy.</p>}
		{query.data?.items.slice().reverse().map((run) => <article key={run.id} className="space-y-1 border-b py-2">
			<p>{new Date(run.created_at).toLocaleString('vi-VN')} · {labels[run.outcome || run.status] || run.status}</p>
			{run.error && <p className="text-destructive">{run.error.includes('UNKNOWN') ? 'Chưa rõ kết quả; hệ thống không tự chạy lại tác vụ.' : `Lần chạy gặp lỗi: ${run.error}`}</p>}
			{run.deliveries.map((delivery) => <p key={delivery.id} className="text-xs text-muted-foreground">Gửi kết quả: {delivery.status === 'succeeded' ? 'Đã gửi' : labels[delivery.status] || delivery.status} · Lần {delivery.attempt}
				{delivery.error ? ` · ${delivery.error.includes('UNKNOWN') ? 'Chưa rõ kết quả gửi' : delivery.error}` : ''}</p>)}
		</article>)}
	</section>;
}
