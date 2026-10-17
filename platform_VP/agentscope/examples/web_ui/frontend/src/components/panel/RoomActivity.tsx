import { ChevronRight, UserRound } from 'lucide-react';
import { useContext, useState } from 'react';

import type { RoomEntry } from '@/api';
import { RoomContext, useAgentId } from '@/components/chat/team-roster';
import { KIND_LABEL, cleanName, teamMessageText, toolLabel } from '@/components/chat/teamDialogText';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

/** Kinds that are work traces rather than people talking. */
const QUIET = new Set(['tool', 'partner_event']);
/** Who in the room is a person rather than an agent. */
const PEOPLE = new Set(['người dùng', 'cư dân', 'customer', 'user']);
const number = (value: number) => value.toLocaleString('vi-VN');

function Speaker({ name }: { name: string }) {
	const id = useAgentId(name);
	if (PEOPLE.has(name.toLocaleLowerCase())) {
		return (
			<span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
				<UserRound className="size-3.5" />
			</span>
		);
	}
	return <ClayAvatar id={id} label={name} size={28} />;
}

function Entry({ entry }: { entry: RoomEntry }) {
	const [open, setOpen] = useState(false);
	const quiet = QUIET.has(entry.kind);
	const sender = cleanName(entry.sender) || 'Hệ thống';
	const to = cleanName(entry.to);
	const kind = (KIND_LABEL[entry.kind] ?? '').toLocaleLowerCase('vi');
	return (
		<li className="flex gap-2 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
			<Speaker name={sender} />
			<button
				type="button"
				onClick={() => setOpen((value) => !value)}
				className={cn(
					'min-w-0 flex-1 rounded-xl rounded-tl-sm bg-muted/60 px-2.5 py-1.5 text-left',
					entry.kind === 'error' && 'bg-destructive/10',
				)}
			>
				<span className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
					<span className="truncate font-medium text-foreground">{sender}</span>
					{to && <span className="truncate">→ {to}</span>}
					{kind && <span className="shrink-0">· {kind}</span>}
				</span>
				<span
					className={cn(
						'mt-0.5 block whitespace-pre-wrap break-words text-xs/5',
						!open && 'line-clamp-2',
						quiet && 'text-muted-foreground',
						entry.kind === 'error' && 'text-destructive',
					)}
				>
					{entry.kind === 'tool' ? toolLabel(entry.text.split(' ')[0]) : teamMessageText(entry.text)}
				</span>
			</button>
		</li>
	);
}

/**
 * A ticket's room for people: who asked whom to do what, what came back and
 * what the user was told; what it cost sits folded underneath.
 */
export function RoomActivity() {
	const room = useContext(RoomContext);
	const [showWork, setShowWork] = useState(false);

	if (!room || (room.timeline.length === 0 && room.participants.length === 0)) return null;
	const timeline = showWork ? room.timeline : room.timeline.filter((entry) => !QUIET.has(entry.kind));

	return (
		<>
			<section className="flex flex-col gap-y-2 px-2">
				<div className="flex items-center justify-between px-1">
					<span className="text-xs font-medium text-muted-foreground">Trao đổi trong phòng</span>
					<button
						type="button"
						className="text-xs text-muted-foreground hover:text-foreground"
						onClick={() => setShowWork((value) => !value)}
					>
						{showWork ? 'Ẩn tra cứu' : 'Hiện tra cứu'}
					</button>
				</div>
				{timeline.length === 0 ? (
					<p className="px-1 text-xs text-muted-foreground">Chưa có trao đổi.</p>
				) : (
					<ol className="flex flex-col gap-2">
						{timeline.map((entry, index) => (
							<Entry key={index} entry={entry} />
						))}
					</ol>
				)}
			</section>
			{room.participants.length > 0 && (
				<Collapsible className="px-3 pb-3">
					<CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
						Mức sử dụng từng agent
						<ChevronRight className="size-3 transition-transform group-data-[state=open]:rotate-90" />
					</CollapsibleTrigger>
					<CollapsibleContent>
						<ul className="mt-2 flex flex-col gap-1 text-xs">
							{room.participants.map((p) => (
								<li key={p.agent_id} className="flex items-center justify-between gap-2">
									<span className="truncate">{cleanName(p.name)}</span>
									<span className="shrink-0 tabular-nums text-muted-foreground">
										{number(p.calls)} lượt · ↑{number(p.input_tokens)} ↓{number(p.output_tokens)}
										{p.input_tokens > 0 && ` · ${Math.round((p.cached_input_tokens / p.input_tokens) * 100)}% cache`}
									</span>
								</li>
							))}
						</ul>
					</CollapsibleContent>
				</Collapsible>
			)}
		</>
	);
}
