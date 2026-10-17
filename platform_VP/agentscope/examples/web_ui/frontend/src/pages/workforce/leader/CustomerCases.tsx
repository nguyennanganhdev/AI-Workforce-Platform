import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { customerCasesApi } from '@/api/customerCases';
import type { CustomerAction, CustomerCase } from '@/api/customerCases';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';

const statuses: Record<string, string> = {
	received: 'Đã tiếp nhận', in_progress: 'Đang xử lý', waiting_for_customer: 'Chờ bạn xác nhận',
	closed: 'Hoàn tất', cancelled: 'Đã hủy', needs_human: 'Cần nhân viên hỗ trợ',
};
const nextActions: Record<string, string> = {
	review_current_decision: 'Xem và quyết định trên thông tin bên dưới.', follow_progress: 'Theo dõi tiến độ từ bộ phận xử lý.',
	select_service_category: 'Cho Leader biết nhóm dịch vụ để chuyển yêu cầu.',
	contact_domain_emergency_support: 'Liên hệ ngay bộ phận hỗ trợ khẩn cấp của khu vực.',
	reconnect_domain: 'Liên kết lại tài khoản dịch vụ trong trang Kết nối.', retry_sync: 'Thử đồng bộ lại khi dịch vụ sẵn sàng.',
	retry_original_request: 'Nhờ Leader thử lại yêu cầu gốc để tra cứu kết quả; không tạo yêu cầu mới.',
};

function DecisionDetail({ value }: { value: unknown }) {
	if (typeof value === 'string' || typeof value === 'number') return <span>{value}</span>;
	if (Array.isArray(value)) return <ul className="space-y-1">{value.map((item, index) => <li key={index}><DecisionDetail value={item} /></li>)}</ul>;
	if (!value || typeof value !== 'object') return null;
	const labels: Record<string, string> = { title: 'Nội dung', description: 'Chi tiết', summary: 'Tóm tắt', amount: 'Số tiền',
		estimated_amount: 'Dự toán', currency: 'Đơn vị', items: 'Hạng mục', steps: 'Các bước', scheduled_at: 'Lịch dự kiến',
		note: 'Ghi chú', reason: 'Lý do', labor_cost: 'Tiền công', materials: 'Vật tư', total: 'Tổng cộng' };
	const entries = Object.entries(value).filter(([key]) => labels[key]);
	return entries.length ? <dl className="space-y-1">{entries.map(([key, item]) => <div key={key}><dt className="text-muted-foreground">{labels[key]}</dt><dd><DecisionDetail value={item} /></dd></div>)}</dl>
		: <p>Vui lòng liên hệ bộ phận xử lý để xem đầy đủ nội dung quyết định.</p>;
}

function EvidencePhoto({ photo }: { photo: { name: string; url: string } }) {
	const [url, setUrl] = useState('');
	useEffect(() => {
		let active = true;
		let objectUrl = '';
		void customerCasesApi.photo(photo.url).then((blob) => {
			if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
		}).catch(() => { /* Keep an explicit unavailable caption. */ });
		return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
	}, [photo.url]);
	return url ? <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={photo.name || 'Ảnh kết quả từ bộ phận xử lý'} className="max-h-48 rounded border object-contain" /></a>
		: <p className="text-xs text-muted-foreground">Ảnh {photo.name}: chưa tải được.</p>;
}

function CaseCard({ item, refresh }: { item: CustomerCase; refresh: () => Promise<unknown> }) {
	const [choice, setChoice] = useState<{ action: CustomerAction; key: string; summary: string } | null>(null);
	const [note, setNote] = useState('');
	const [submittedNote, setSubmittedNote] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState('');
	const [receipt, setReceipt] = useState(false);
	const [extraEvents, setExtraEvents] = useState<CustomerCase['events']>([]);
	const [more, setMore] = useState<boolean | null>(null);
	const [loadingMore, setLoadingMore] = useState(false);
	const applied = item.sync_status === 'applied';
	const events = [...new Map([...item.events, ...extraEvents].map((event) => [event.id, event])).values()].sort((a, b) => a.sequence - b.sequence);
	const loadMore = async () => {
		setLoadingMore(true); setError('');
		try {
			const page = await customerCasesApi.events(item.id, events.at(-1)?.sequence ?? 0);
			setExtraEvents((previous) => [...previous, ...page.items.map((event) => ({ id: event.event_id, sequence: event.sequence,
				at: event.occurred_at, label: event.data.label || event.event_type, note: event.data.note }))]);
			setMore(page.has_more);
		} catch { setError('Chưa tải được các sự kiện tiếp theo. Vui lòng thử lại.'); }
		finally { setLoadingMore(false); }
	};
	const confirm = async () => {
		if (!choice || busy) return;
		setBusy(true); setError('');
		const exactNote = submittedNote ?? note.trim();
		setSubmittedNote(exactNote);
		try {
			await customerCasesApi.decide(item.id, choice.action, exactNote, choice.key);
			setReceipt(true); setChoice(null);
			await refresh();
		} catch {
			setError('Chưa xác nhận được kết quả. Bạn có thể thử lại cùng quyết định; nếu nội dung đã thay đổi, đóng thẻ và tải lại tiến độ.');
		} finally { setBusy(false); }
	};
	return <article className="space-y-3 border-b py-4" data-testid="customer-case">
		<div><h3 className="font-medium">{item.code || 'Yêu cầu dịch vụ'} · {item.title || item.description || item.id.slice(0, 8)}</h3>
			<p className="text-sm">{statuses[item.service_status ?? ''] || 'Đang cập nhật trạng thái'}</p></div>
		<p className="text-xs text-muted-foreground" role="status">{applied ? 'Đã đồng bộ' : 'Chưa đồng bộ đầy đủ'}{item.as_of ? ` · Dữ liệu đến ${new Date(item.as_of).toLocaleString('vi-VN')}` : ''}</p>
		{item.next_action && <p className="text-sm">{nextActions[item.next_action] || 'Xem tiến độ và hướng dẫn từ dịch vụ.'}</p>}
		{item.error && <p className="text-sm text-destructive">Không thể lấy tiến độ: {item.error}</p>}
		{item.pending_decisions?.map((decision) => <div key={decision.id} className="rounded border p-3 text-sm">
			<p className="font-medium">Nội dung cần bạn xem · {decision.kind}</p>
			<DecisionDetail value={decision.request_detail} />
		</div>)}
		{item.work_orders?.map((work) => <p key={work.id} className="text-sm">Công việc: {work.status}{work.scheduled_at ? ` · ${new Date(work.scheduled_at).toLocaleString('vi-VN')}` : ''}</p>)}
		{item.resolution && <div className="space-y-2"><h4 className="text-sm font-medium">Kết quả từ bộ phận xử lý</h4><p className="text-sm whitespace-pre-wrap">{item.resolution.summary}</p>
			{item.resolution.photos.map((photo) => <EvidencePhoto key={photo.id} photo={photo} />)}</div>}
		<ol className="space-y-2 border-l pl-3 text-sm" aria-label="Tiến độ yêu cầu">{events.map((event) => <li key={event.id}>
			<p>{event.label}</p><time className="text-xs text-muted-foreground">{new Date(event.at).toLocaleString('vi-VN')}</time>{event.note && <p>{event.note}</p>}
		</li>)}</ol>
		{(more ?? item.has_more) && <Button size="sm" variant="ghost" disabled={loadingMore} onClick={() => void loadMore()}>Tải sự kiện tiếp</Button>}
		{receipt && <p className="text-sm" role="status">Dịch vụ đã ghi nhận quyết định của bạn.</p>}
		<div className="flex flex-wrap gap-2">{applied && item.actions.map((action) => <Button key={`${action.action}:${JSON.stringify(action.payload)}`} variant="outline" size="sm" onClick={() => {
			setNote(''); setSubmittedNote(null); setError(''); setChoice({ action, key: crypto.randomUUID(), summary: item.resolution?.summary || item.description || item.title || '' });
		}}>{action.label}</Button>)}</div>
		<Dialog open={choice !== null} onOpenChange={(open) => { if (!open && !busy) setChoice(null); }}>
			<DialogContent><DialogHeader><DialogTitle>{choice?.action.label}</DialogTitle><DialogDescription>
				Kiểm tra nội dung yêu cầu {item.code || item.id.slice(0, 8)} và kết quả bên trên. Chỉ nút xác nhận bên dưới mới gửi quyết định của bạn.
			</DialogDescription></DialogHeader>
			<p className="text-sm whitespace-pre-wrap">{choice?.summary}</p>
			{choice?.action.requires_note && <label className="space-y-2 text-sm">Lý do / ghi chú<Textarea value={note} disabled={busy || submittedNote !== null} onChange={(event) => setNote(event.target.value)} maxLength={2000} /></label>}
			{error && <p role="alert" className="text-sm text-destructive">{error}</p>}
			<Button disabled={busy || (choice?.action.requires_note && note.trim().length < (choice.action.action === 'reopen' ? 8 : 1))} onClick={confirm}>{busy ? 'Đang gửi…' : 'Xác nhận gửi quyết định'}</Button>
			<Button variant="ghost" disabled={busy} onClick={() => setChoice(null)}>Quay lại</Button>
			</DialogContent>
		</Dialog>
		{error && !choice && <p role="alert" className="text-sm text-destructive">{error}</p>}
	</article>;
}

export function CustomerCases({ agentId, sessionId }: { agentId: string; sessionId: string }) {
	const queryClient = useQueryClient();
	const queryKey = ['customer-cases', agentId, sessionId];
	const query = useQuery({ queryKey, queryFn: () => customerCasesApi.list(agentId, sessionId), refetchInterval: 15000, retry: false });
	return <details className="shrink-0 border-b bg-background px-4" data-testid="customer-cases">
		<summary className="cursor-pointer py-2 text-sm font-medium">Yêu cầu dịch vụ của bạn{query.data ? ` (${query.data.items.length})` : ''}</summary>
		<div className="max-h-[55vh] overflow-y-auto pb-3">
			<p className="text-xs text-muted-foreground">Gửi yêu cầu cho Leader trong khung chat. Tiến độ và xác nhận từ dịch vụ xuất hiện ở đây.</p>
			{query.isPending && <p className="py-3 text-sm">Đang lấy tiến độ…</p>}
			{query.isError ? <p role="alert" className="py-3 text-sm">Chưa lấy được tiến độ. Thông tin trước đó có thể đã thay đổi.</p>
				: query.data?.items.map((item) => <CaseCard key={item.id} item={item} refresh={() => queryClient.invalidateQueries({ queryKey })} />)}
			<Button variant="ghost" size="sm" disabled={query.isFetching} onClick={() => void query.refetch()}>Tải lại tiến độ</Button>
		</div>
	</details>;
}
