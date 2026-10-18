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
const usd = (value?: number | null) => value == null ? 'Chưa xác định' : value < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
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
		['Phiếu hoàn tất', number(data.successful_tickets ?? 0)],
		['Cần kiểm tra', number(data.backlog.tickets_need_attention ?? 0)],
		['Latency p50 / p95', `${duration(data.p50_ms)} / ${duration(data.p95_ms)}`],
		['Chi phí (USD)', data.est_cost_usd != null ? usd(data.est_cost_usd) : data.calls_costed ? `${usd(data.known_cost_usd)} · chưa đủ` : usd(null)],
	] : [];
	return <>
		<Button variant="outline" onClick={() => setOpen(true)}><Activity /> Hoạt động và chi phí</Button>
		<Dialog open={open} onOpenChange={setOpen}>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl">
				<DialogHeader>
					<DialogTitle>Hoạt động và chi phí · 30 ngày</DialogTitle>
					<DialogDescription>Kết quả xử lý và mức sử dụng trợ lý trong 30 ngày. Phiếu hoàn tất cần được cư dân xác nhận.</DialogDescription>
				</DialogHeader>
				<div className="flex gap-2"><Button variant="outline" size="sm" disabled={loading} onClick={load}><RefreshCw /> Cập nhật</Button>
					</div>
				{loading && <div className="flex justify-center p-4"><Spinner /></div>}
				{error && <p role="alert" className="text-sm text-destructive">Không tải được số liệu hoạt động. Vui lòng thử lại.</p>}
				{data && <>
					<div className="flex flex-wrap gap-2"><Badge variant={data.usage_complete ? 'secondary' : 'outline'}>{data.usage_complete ? 'Số liệu sử dụng đầy đủ' : 'Số liệu sử dụng chưa đầy đủ'}</Badge>
					</div>
					<div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium tabular-nums">{value}</p></div>)}</div>
					{data.calls_unpriced > 0 && <p className="text-xs text-muted-foreground">{data.calls_unpriced} lần gọi chưa có bảng giá (model khác gpt-6-luna hoặc chưa có số token), nên tổng chỉ gồm phần đã tính được.</p>}
					<Table><TableHeader><TableRow><TableHead>Model</TableHead><TableHead>Lần gọi</TableHead><TableHead>Token vào / ra</TableHead><TableHead>Latency p50 / p95</TableHead><TableHead>Chi phí</TableHead></TableRow></TableHeader>
						<TableBody>{data.by_model.map(row => <TableRow key={[row.provider, row.endpoint_id, row.model, row.service_tier].join(':')}><TableCell className="font-medium">{row.model}</TableCell><TableCell>{number(row.calls)}</TableCell><TableCell>{row.calls_missing_usage === row.calls ? 'Chưa xác định' : `${number(row.input_tokens)} / ${number(row.output_tokens)}${row.usage_complete ? '' : ' · chưa đầy đủ'}`}</TableCell><TableCell>{duration(row.p50_ms)} / {duration(row.p95_ms)}</TableCell><TableCell>{usd(row.est_cost_usd)}</TableCell></TableRow>)}</TableBody></Table>
					{data.calls === 0 && <p className="py-3 text-center text-sm text-muted-foreground">Chưa có lần gọi nào trong sổ mới.</p>}
					<details className="text-xs text-muted-foreground"><summary className="cursor-pointer py-2">Chi tiết đối soát</summary>
						{data.coverage.truncated && <p>Dashboard chỉ chứa 20.000 lần gọi đầu; cần xuất API để xem đủ.</p>}
						{data.calls_unknown_purpose > 0 && <p>{data.calls_unknown_purpose} lần chưa phân loại mục đích.</p>}
						{data.coverage.recording_failures_current_process > 0 && <p>Có lỗi ghi ledger trong tiến trình hiện tại.</p>}
						<p>Lỗi hoặc hủy: {percent(data.failure_rate)} · Dữ liệu vào từ cache: {percent(data.cache_hit_ratio)} · Phản hồi chậm (95%): {duration(data.p95_ms)}</p>
						<p>Thiếu số liệu: {number(data.calls_missing_usage)} · Chưa có giá: {number(data.calls_unpriced)} · Chi phí đã biết: {usd(data.calls_costed ? data.known_cost_usd : null)}</p>
						<Button className="mt-2" variant="outline" size="sm" disabled={exporting} onClick={download}><Download /> Xuất số liệu đối soát</Button>
					</details>
				</>}
			</DialogContent>
		</Dialog>
	</>;
}
