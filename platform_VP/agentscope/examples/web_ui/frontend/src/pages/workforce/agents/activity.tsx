import { Activity, Download, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { studioApi } from '@/api';
import type { ModelObservability } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const number = (value: number) => value.toLocaleString('vi-VN');
const percent = (value: number | null) => value === null ? 'Chưa biết' : `${(value * 100).toFixed(1)}%`;
const usd = (value?: number | null) => value == null ? 'Chưa xác định' : `$${value.toFixed(5)}`;
const duration = (value: number | null) => value === null ? 'Chưa biết' : `${(value / 1000).toFixed(2)} s`;

export function ActivityDialog() {
	const [open, setOpen] = useState(false);
	const [data, setData] = useState<ModelObservability | null>(null);
	const [loading, setLoading] = useState(false);
	const [exporting, setExporting] = useState(false);
	const [error, setError] = useState('');
	const load = () => {
		setLoading(true);
		setError('');
		studioApi.observability().then(setData).catch((e) => setError(String(e))).finally(() => setLoading(false));
	};
	useEffect(() => { if (open) load(); }, [open]);
	const download = async () => {
		if (!data) return;
		setExporting(true);
		try {
			const calls: Record<string, unknown>[] = [];
			const until = new Date().toISOString();
			let offset: number | null = 0;
			do {
				const page = await studioApi.modelCalls(data.window_since, until, offset);
				calls.push(...page.calls);
				offset = page.next_offset;
				if (offset !== null && offset >= 100000) throw new Error('Dữ liệu vượt giới hạn xuất trên trình duyệt. Hãy xuất từng khoảng thời gian qua API.');
			} while (offset !== null);
			const url = URL.createObjectURL(new Blob([JSON.stringify({ since: data.window_since, until, calls }, null, 2)], { type: 'application/json' }));
			const link = document.createElement('a'); link.href = url; link.download = 'model-call-ledger.json'; link.click();
			URL.revokeObjectURL(url);
		} catch (e) { toast.error(String(e)); } finally { setExporting(false); }
	};
	const metrics: [string, string][] = data ? [
		['Lần gọi provider', number(data.calls)], ['p50 / p95', `${duration(data.p50_ms)} / ${duration(data.p95_ms)}`],
		['Lỗi hoặc hủy', percent(data.failure_rate)], ['Token vào từ cache', percent(data.cache_hit_ratio)],
		['Chưa có kết thúc', number(data.pending_calls)], ['Thiếu usage', number(data.calls_missing_usage)],
		['Chưa có giá', number(data.calls_unpriced)], ['Chi phí đủ bằng chứng', usd(data.est_cost_usd)],
		['Phần chi phí đã biết', usd(data.calls_costed ? data.known_cost_usd : null)], ['Phiếu thành công', number(data.successful_tickets ?? 0)],
		['Chi phí / phiếu thành công', usd(data.cost_per_successful_ticket_usd)],
		['Phiếu cần xử lý', number(data.backlog.tickets_need_attention ?? 0)],
	] : [];
	return <>
		<Button variant="outline" onClick={() => setOpen(true)}><Activity /> Hoạt động và chi phí</Button>
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl">
				<DialogHeader>
					<DialogTitle>Hoạt động và chi phí · 30 ngày</DialogTitle>
					<DialogDescription>Mỗi lần gọi được ghi riêng theo provider, model, tier và mục đích. Chi phí là ước tính theo giá có phiên bản; dữ liệu trước khi bật ledger chưa được đối soát.</DialogDescription>
				</DialogHeader>
				<div className="flex gap-2"><Button variant="outline" size="sm" disabled={loading} onClick={load}><RefreshCw /> Cập nhật</Button>
					<Button variant="outline" size="sm" disabled={!data || exporting} onClick={download}><Download /> Xuất từng lần gọi</Button></div>
				{loading && <div className="flex justify-center p-4"><Spinner /></div>}
				{error && <p role="alert" className="text-sm text-destructive">Không tải được sổ usage: {error}</p>}
				{data && <>
					<div className="flex flex-wrap gap-2"><Badge variant={data.usage_complete ? 'secondary' : 'outline'}>{data.usage_complete ? 'Usage đầy đủ trong sổ' : 'Usage chưa đầy đủ'}</Badge>
						{data.coverage.truncated && <Badge variant="destructive">Dashboard chỉ chứa 20.000 lần gọi đầu; cần xuất API để xem đủ</Badge>}
						{data.calls_unknown_purpose > 0 && <Badge variant="outline">{data.calls_unknown_purpose} lần chưa phân loại mục đích</Badge>}
						{data.coverage.recording_failures_current_process > 0 && <Badge variant="destructive">Có lỗi ghi ledger trong tiến trình hiện tại</Badge>}</div>
					<div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium tabular-nums">{value}</p></div>)}</div>
					<p className="text-xs text-muted-foreground">Phần chi phí đã biết không bao gồm lần gọi thiếu usage hoặc chưa có bảng giá. Các lần thử lại được tính riêng. Phiếu thành công cần cư dân nghiệm thu; dừng theo dõi không được tính thành công.</p>
					<Table><TableHeader><TableRow><TableHead>Provider / model / tier</TableHead><TableHead>Lần gọi</TableHead><TableHead>Token vào / cache / ra</TableHead><TableHead>p95</TableHead><TableHead>Chi phí</TableHead></TableRow></TableHeader>
						<TableBody>{data.by_model.map(row => <TableRow key={[row.provider, row.endpoint_id, row.model, row.service_tier].join(':')}><TableCell><p className="font-medium">{row.model}</p><p className="text-xs text-muted-foreground">{row.provider} · {row.service_tier} · {row.endpoint_id.slice(0, 8)}</p></TableCell><TableCell>{number(row.calls)}</TableCell><TableCell>{row.calls_missing_usage === row.calls ? 'Chưa xác định' : `${number(row.input_tokens)} / ${number(row.cached_input_tokens)} / ${number(row.output_tokens)}${row.usage_complete ? '' : ' · chưa đủ usage'}`}</TableCell><TableCell>{duration(row.p95_ms)}</TableCell><TableCell>{usd(row.est_cost_usd)}</TableCell></TableRow>)}</TableBody></Table>
					{data.calls === 0 && <p className="py-3 text-center text-sm text-muted-foreground">Chưa có lần gọi nào trong sổ mới.</p>}
					<div className="flex flex-wrap gap-2">{data.by_purpose.map(row => <Badge key={row.purpose} variant="outline">{row.purpose}: {number(row.calls)}</Badge>)}</div>
				</>}
			</DialogContent>
		</Dialog>
	</>;
}
