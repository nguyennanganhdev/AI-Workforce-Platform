import { ArrowRight, ChevronRight, Inbox, UserRound, Wrench } from 'lucide-react';
import { type ReactNode, useContext, useLayoutEffect, useRef, useState } from 'react';

import { RoomContext, TicketViewContext, memberToolCalls, useAgentId } from './team-roster';
import { KIND_LABEL, cleanName, teamMessageText, toolLabel } from './teamDialogText';
import type { ToolCallWithResult } from './tool-renderers/types';
import type { RoomEntry } from '@/api';
import { Markdown } from '@/components/markdown';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from '@/components/ui/collapsible.tsx';
import { cn } from '@/lib/utils';

/**
 * How agents talk to each other (and to the end user) in a ticket, shown as
 * a conversation instead of raw tool calls and runtime headers: who wrote to
 * whom, what kind of message it is, its text, and the tools behind a report.
 */

function parseArgs(input: string | undefined): Record<string, unknown> {
	try {
		return JSON.parse(input || '{}') as Record<string, unknown>;
	} catch {
		return {};
	}
}

/** One tone per kind of message, used for its label and its edge. */
type Tone = 'task' | 'report' | 'talk' | 'review' | 'error' | 'reply';

const TONE: Record<Tone, { edge: string; pill: string }> = {
	task: { edge: 'before:bg-sky-400', pill: 'bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300' },
	report: { edge: 'before:bg-emerald-400', pill: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' },
	talk: { edge: 'before:bg-violet-400', pill: 'bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300' },
	review: { edge: 'before:bg-amber-400', pill: 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300' },
	error: { edge: 'before:bg-red-400', pill: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300' },
	reply: { edge: 'before:bg-foreground/70', pill: 'bg-foreground text-background' },
};

function toneOf(kind: string | undefined, decision?: string): Tone {
	if (kind === 'review') return decision === 'challenge' ? 'review' : 'report';
	if (kind === 'assign' || kind === 'handoff') return 'task';
	if (kind === 'error' || kind === 'conflict') return 'error';
	if (kind === 'question' || kind === 'answer' || kind === 'progress') return 'talk';
	if (kind === 'reply') return 'reply';
	return 'report';
}

function labelOf(kind: string | undefined, decision?: string): string {
	if (kind === 'review' && decision === 'challenge') return 'Yêu cầu làm lại';
	return (kind && KIND_LABEL[kind]) || 'Tin nhắn';
}

/** Four lines of a message, the rest one click away. */
function Clamped({ children }: { children: ReactNode }) {
	const ref = useRef<HTMLDivElement>(null);
	const [open, setOpen] = useState(false);
	const [overflows, setOverflows] = useState(false);
	useLayoutEffect(() => {
		const element = ref.current;
		if (element && !open) setOverflows(element.scrollHeight > element.clientHeight + 1);
	}, [children, open]);
	return (
		<>
			<div ref={ref} className={cn('text-sm/6 [&_p]:my-0', !open && 'line-clamp-4')}>
				{children}
			</div>
			{(overflows || open) && (
				<button
					type="button"
					className="mt-1 text-xs font-medium text-muted-foreground hover:text-foreground"
					onClick={() => setOpen((value) => !value)}
				>
					{open ? 'Thu gọn' : 'Xem thêm'}
				</button>
			)}
		</>
	);
}

/** An agent's portrait (the same on every screen). */
function Face({ name }: { name: string }) {
	return <ClayAvatar id={useAgentId(name)} label={name} size={28} />;
}

/** The tool calls behind a report: a count, then each call with its arguments. */
function ToolTrace({ calls }: { calls: RoomEntry[] }) {
	if (calls.length === 0) return null;
	const names = [...new Set(calls.map((call) => toolLabel(call.text.split(/\s/, 1)[0])))];
	return (
		<Collapsible className="mt-2.5 border-t border-dashed border-border/80 pt-2">
			<CollapsibleTrigger className="group flex w-full items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
				<Wrench className="size-3.5 shrink-0" />
				<span className="shrink-0">Đã gọi {calls.length} công cụ</span>
				<span className="min-w-0 flex-1 truncate text-left font-mono">{names.join(' · ')}</span>
				<ChevronRight className="size-3 shrink-0 transition-transform group-data-[state=open]:rotate-90" />
			</CollapsibleTrigger>
			<CollapsibleContent>
				<ol className="mt-2 flex flex-col gap-1">
					{calls.map((call, index) => {
						const tool = toolLabel(call.text.split(' ')[0]);
						return (
							<li key={index} className="rounded-lg bg-muted/60 px-2.5 py-1.5 font-mono text-xs">
								<span className="font-semibold">{tool}</span>
							</li>
						);
					})}
				</ol>
			</CollapsibleContent>
		</Collapsible>
	);
}

export function DialogCard({
	from,
	to,
	toPerson = false,
	kind,
	decision,
	note,
	footer,
	children,
}: {
	from: string;
	to?: string;
	toPerson?: boolean;
	kind?: string;
	decision?: string;
	note?: ReactNode;
	footer?: ReactNode;
	children: ReactNode;
}) {
	const tone = TONE[toneOf(kind, decision)];
	return (
		<div
			className={cn(
				'relative w-full overflow-hidden rounded-2xl border border-border/70 bg-background py-3 pr-3.5 pl-4',
				'before:absolute before:inset-y-0 before:left-0 before:w-[3px]',
				tone.edge,
				'motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-1',
			)}
		>
			<div className="mb-1.5 flex min-w-0 items-center gap-2 text-[13px]/[18px]">
				<Face name={from} />
				<span className="truncate font-semibold text-foreground">{from}</span>
				{to && (
					<>
						<ArrowRight className="size-3.5 shrink-0 text-muted-foreground" />
						<span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
							{toPerson && <UserRound className="size-3.5 shrink-0" />}
							<span className="truncate">{to}</span>
						</span>
					</>
				)}
				<span className={cn('ml-auto shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium', tone.pill)}>
					{labelOf(kind, decision)}
				</span>
			</div>
			<Clamped>{children}</Clamped>
			{note && <div className="mt-1.5 text-xs text-muted-foreground">{note}</div>}
			{footer}
		</div>
	);
}

/** A message another agent sent into this session (a team hint). */
export function TeamMessageCard({
	sender,
	kind,
	text,
	at,
}: {
	sender: string;
	kind?: string;
	text: string;
	at?: string;
}) {
	const room = useContext(RoomContext);
	const from = cleanName(sender);
	const calls = room ? memberToolCalls(room.timeline, from, at) : [];
	return (
		<DialogCard from={from} to="Leader" kind={kind} footer={<ToolTrace calls={calls} />}>
			<Markdown>{teamMessageText(text)}</Markdown>
		</DialogCard>
	);
}

function resultNote(pair: ToolCallWithResult): ReactNode {
	if (!pair.result) return <span>Đang gửi…</span>;
	if (pair.result.state === 'error') return <span className="text-destructive">Bị từ chối</span>;
	return null;
}

/** A message the Leader sent: an assignment, a room message or the user reply. */
export function DialogToolCard({ pair }: { pair: ToolCallWithResult }) {
	const args = parseArgs(pair.call.input);
	const name = pair.call.name;
	if (name === 'AgentInvite') {
		const assignments = [
			{ target: args.target, prompt: args.prompt, depends_on: args.depends_on },
			...((args.additional_assignments as Array<Record<string, unknown>> | undefined) ?? []),
		];
		return (
			<div className="flex w-full flex-col gap-2">
				{assignments.map((item, index) => {
					const after = ((item.depends_on as string[] | undefined) ?? []).map(cleanName);
					return (
						<DialogCard
							key={index}
							from="Leader"
							to={cleanName(String(item.target ?? ''))}
							kind="assign"
							note={after.length > 0 && <>Bắt đầu sau khi {after.join(', ')} báo kết quả</>}
						>
							<Markdown>{teamMessageText(String(item.prompt ?? ''))}</Markdown>
						</DialogCard>
					);
				})}
			</div>
		);
	}
	if (name === 'TeamSay') {
		return (
			<DialogCard
				from="Leader"
				to={cleanName(String(args.to ?? '')) || 'Cả phòng'}
				kind={String(args.kind ?? '')}
				decision={String(args.decision ?? '')}
				note={resultNote(pair)}
			>
				<Markdown>{teamMessageText(String(args.content ?? ''))}</Markdown>
			</DialogCard>
		);
	}
	// CaseSay / CaseFinalize: what the end user receives (unless refused).
	const refused = pair.result?.state === 'error';
	return (
		<DialogCard
			from="Leader"
			to="Khách hàng"
			toPerson
			kind={refused ? 'error' : 'reply'}
			note={refused ? 'Nội dung chưa được gửi cho khách hàng.' : resultNote(pair)}
		>
			<Markdown>{refused ? 'Cần xác minh lại trước khi gửi cập nhật.' : teamMessageText(String(args.text ?? args.answer ?? ''))}</Markdown>
		</DialogCard>
	);
}

/** The ticket as reception confirmed it: what is asked, and a few facts. */
export function TicketCard({ request, facts }: { request: string; facts: string[] }) {
	return (
		<div className="w-full max-w-xl rounded-2xl border border-border/70 bg-background px-3.5 py-3 text-left">
			<div className="flex items-center gap-1.5 text-[13px]/[18px] text-muted-foreground">
				<Inbox className="size-3.5" /> Yêu cầu từ lễ tân
			</div>
			<p className="mt-1 line-clamp-4 whitespace-pre-wrap text-[15px]/6 text-foreground">{request}</p>
			{facts.length > 0 && (
				<div className="mt-2 flex flex-wrap gap-1.5">
					{facts.map((fact) => (
						<span key={fact} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
							{fact}
						</span>
					))}
				</div>
			)}
		</div>
	);
}

export function HandoverCard({ shown, hidden }: { shown: [string, string][]; hidden: string[] }) {
	const ticketView = useContext(TicketViewContext);
	return (
		<div className="flex flex-col gap-2 text-sm">
			<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
				{shown.map(([key, value], index) => (
					<div key={index} className="contents">
						<dt className="text-muted-foreground">{key}</dt>
						<dd>{value}</dd>
					</div>
				))}
			</dl>
			{!ticketView && hidden.length > 0 && (
				<Collapsible>
					<CollapsibleTrigger className="text-xs text-muted-foreground hover:text-primary">
						Thông tin kỹ thuật ({hidden.length})
					</CollapsibleTrigger>
					<CollapsibleContent className="mt-1 whitespace-pre-wrap break-all text-xs text-muted-foreground">
						{hidden.join('\n')}
					</CollapsibleContent>
				</Collapsible>
			)}
		</div>
	);
}
