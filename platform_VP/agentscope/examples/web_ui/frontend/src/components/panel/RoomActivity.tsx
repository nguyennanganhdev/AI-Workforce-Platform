import { useEffect, useState } from 'react';

import { workforceApi } from '@/api';
import type { RoomEntry, RoomView } from '@/api';
import { KIND_LABEL } from '@/components/chat/teamDialogText';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const REFRESH_MS = 5000;
const number = (value: number) => value.toLocaleString('vi-VN');

/** Kinds that are work traces rather than people talking. */
const QUIET = new Set(['tool', 'partner_event']);

function Entry({ entry }: { entry: RoomEntry }) {
	const [open, setOpen] = useState(false);
	const quiet = QUIET.has(entry.kind);
	const time = new Date(entry.at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
	return (
		<li
			className={cn(
				'rounded-lg border border-border/60 p-2',
				quiet && 'border-dashed bg-muted/40',
				entry.kind === 'error' && 'border-destructive/40 bg-destructive/5',
			)}
			onClick={() => setOpen((value) => !value)}
		>
			<div className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
				<span className="tabular-nums">{time}</span>
				<span className="font-medium text-foreground">{entry.sender || '—'}</span>
				{entry.to && <span>→ {entry.to}</span>}
				<Badge variant="outline" className="h-4 px-1 text-[10px]">
					{KIND_LABEL[entry.kind] ?? entry.kind}
				</Badge>
				{entry.after.length > 0 && <span>sau {entry.after.join(', ')}</span>}
			</div>
			<p className={cn('mt-1 whitespace-pre-wrap break-words text-xs', !open && 'line-clamp-3', quiet && 'text-muted-foreground')}>
				{entry.text}
			</p>
		</li>
	);
}

/**
 * A ticket's room for people: who assigned what to whom, what came back,
 * the message the user got, and what each agent spent on this ticket.
 */
export function RoomActivity({ sessionId }: { sessionId: string }) {
	const [room, setRoom] = useState<RoomView | null>(null);
	const [showWork, setShowWork] = useState(false);

	useEffect(() => {
		let active = true;
		const load = () =>
			workforceApi
				.room(sessionId)
				.then((value) => active && setRoom(value))
				.catch(() => active && setRoom(null));
		load();
		const timer = setInterval(load, REFRESH_MS);
		return () => {
			active = false;
			clearInterval(timer);
		};
	}, [sessionId]);

	if (!room || (room.timeline.length === 0 && room.participants.length === 0)) return null;
	const timeline = showWork ? room.timeline : room.timeline.filter((entry) => !QUIET.has(entry.kind));
	const total = room.participants.reduce(
		(sum, p) => ({
			input: sum.input + p.input_tokens,
			cached: sum.cached + p.cached_input_tokens,
			output: sum.output + p.output_tokens,
		}),
		{ input: 0, cached: 0, output: 0 },
	);

	return (
		<>
			<section className="flex flex-col gap-y-1 px-2">
				<div className="flex items-center justify-between">
					<span className="text-xs text-muted-foreground">Thảo luận trong phòng</span>
					<button
						type="button"
						className="text-[11px] text-muted-foreground hover:text-primary"
						onClick={() => setShowWork((value) => !value)}
					>
						{showWork ? 'Ẩn tra cứu' : 'Hiện cả tra cứu'}
					</button>
				</div>
				<ol className="flex flex-col gap-1.5">
					{timeline.map((entry, index) => (
						<Entry key={index} entry={entry} />
					))}
				</ol>
			</section>

			<section className="flex flex-col gap-y-1 px-2 pb-2">
				<span className="text-xs text-muted-foreground">Chi phí của phiếu</span>
				<table className="w-full text-[11px]">
					<thead className="text-muted-foreground">
						<tr>
							<th className="text-left font-normal">Agent</th>
							<th className="text-right font-normal">Gọi</th>
							<th className="text-right font-normal">Vào</th>
							<th className="text-right font-normal">Cache</th>
							<th className="text-right font-normal">Ra</th>
						</tr>
					</thead>
					<tbody>
						{room.participants.map((p) => (
							<tr key={p.agent_id}>
								<td className="max-w-24 truncate" title={`${p.name} · ${p.model}`}>
									{p.name}
									<span className="block text-[10px] text-muted-foreground">{p.model}</span>
								</td>
								<td className="text-right tabular-nums">{p.calls}</td>
								<td className="text-right tabular-nums">{number(p.input_tokens)}</td>
								<td className="text-right tabular-nums">
									{p.input_tokens ? `${Math.round((p.cached_input_tokens / p.input_tokens) * 100)}%` : '—'}
								</td>
								<td className="text-right tabular-nums">{number(p.output_tokens)}</td>
							</tr>
						))}
						<tr className="border-t font-medium">
							<td>Tổng</td>
							<td />
							<td className="text-right tabular-nums">{number(total.input)}</td>
							<td className="text-right tabular-nums">
								{total.input ? `${Math.round((total.cached / total.input) * 100)}%` : '—'}
							</td>
							<td className="text-right tabular-nums">{number(total.output)}</td>
						</tr>
					</tbody>
				</table>
				<span className="text-[10px] text-muted-foreground">
					Ngữ cảnh chung: {number(room.packet_tokens)} / {number(room.packet_budget)} token (cao nhất{' '}
					{number(room.peak_packet_tokens)})
				</span>
			</section>
		</>
	);
}
