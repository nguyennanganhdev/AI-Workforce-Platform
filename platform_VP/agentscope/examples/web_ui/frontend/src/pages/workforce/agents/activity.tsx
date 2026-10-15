import { Activity } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { studioApi } from '@/api';
import type { AgentActivity, TicketQuality } from '@/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const number = (value: number) => value.toLocaleString('vi-VN');

const percent = (value: number) => `${Math.round(value * 100)}%`;
const usd = (value: number | null) => (value === null ? '—' : `$${value.toFixed(value < 1 ? 3 : 2)}`);

function QualitySummary({ quality }: { quality: TicketQuality }) {
	const items: [string, string][] = [
		['Phiếu', number(quality.tickets)],
		['Cư dân xác nhận', number(quality.closed_confirmed)],
		['Xác nhận ngay lần đầu', number(quality.first_time_confirmed)],
		['Cần xử lý', number(quality.needs_attention)],
		['Tin bị chặn (sai bằng chứng)', percent(quality.refusal_rate)],
		['Cache', percent(quality.cache_rate)],
		['Chi phí ước tính', usd(quality.est_cost_usd)],
		['Chi phí / phiếu xác nhận', usd(quality.cost_per_confirmed_usd)],
	];
	return (
		<section className="space-y-2">
			<p className="text-xs text-muted-foreground">Phiếu đối tác {quality.days} ngày qua</p>
			<div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
				{items.map(([label, value]) => (
					<div key={label} className="rounded-lg border border-border/70 p-2">
						<p className="text-[11px] text-muted-foreground">{label}</p>
						<p className="text-sm font-medium tabular-nums">{value}</p>
					</div>
				))}
			</div>
		</section>
	);
}

/** What each agent (the Leader included) spent: tickets, replies, tokens, cache. */
export function ActivityDialog() {
	const [open, setOpen] = useState(false);
	const [rows, setRows] = useState<AgentActivity[] | null>(null);
	const [quality, setQuality] = useState<TicketQuality | null>(null);

	useEffect(() => {
		if (!open) return;
		setRows(null);
		// Absent when the partner API is off: the section is then hidden.
		studioApi
			.quality()
			.then(setQuality)
			.catch(() => setQuality(null));
		studioApi
			.activity()
			.then(setRows)
			.catch((error) => {
				toast.error(error instanceof Error ? error.message : String(error));
				setRows([]);
			});
	}, [open]);

	return (
		<>
			<Button variant="outline" onClick={() => setOpen(true)}>
				<Activity /> Hoạt động
			</Button>
			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent className="sm:max-w-4xl">
					<DialogHeader>
						<DialogTitle>Hoạt động của agent</DialogTitle>
						<DialogDescription>
							Token theo số liệu nhà cung cấp model trả về cho từng lượt trả lời. Phần cache được tính giá thấp hơn.
						</DialogDescription>
					</DialogHeader>
					{quality && <QualitySummary quality={quality} />}
					{rows === null ? (
						<div className="flex justify-center p-6">
							<Spinner />
						</div>
					) : (
						<Table>
							<TableHeader>
								<TableRow>
									<TableHead>Agent</TableHead>
									<TableHead>Model</TableHead>
									<TableHead className="text-right">Ticket</TableHead>
									<TableHead className="text-right">Lượt trả lời</TableHead>
									<TableHead className="text-right">Token vào</TableHead>
									<TableHead className="text-right">Từ cache</TableHead>
									<TableHead className="text-right">Token ra</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{rows.map((row) => (
									<TableRow key={row.agent_id}>
										<TableCell>
											<p className="font-medium">{row.name}</p>
											{row.role === 'leader' && <Badge variant="outline">Leader</Badge>}
										</TableCell>
										<TableCell>{row.model_tier === 'strong' ? 'mạnh' : 'tiêu chuẩn'}</TableCell>
										<TableCell className="text-right">{number(row.tickets)}</TableCell>
										<TableCell className="text-right">{number(row.replies)}</TableCell>
										<TableCell className="text-right">{number(row.input_tokens)}</TableCell>
										<TableCell className="text-right">
											{row.input_tokens
												? `${Math.round((row.cached_input_tokens / row.input_tokens) * 100)}%`
												: '—'}
										</TableCell>
										<TableCell className="text-right">{number(row.output_tokens)}</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					)}
				</DialogContent>
			</Dialog>
		</>
	);
}
