import { ClipboardList, Inbox, UserRound } from 'lucide-react';
import { type ReactNode, useLayoutEffect, useRef, useState } from 'react';

import { useAgentId } from './team-roster';
import { KIND_LABEL, cleanName, teamMessageText } from './teamDialogText';
import type { ToolCallWithResult } from './tool-renderers/types';
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
 * a conversation instead of raw tool calls and runtime headers.
 */

function parseArgs(input: string | undefined): Record<string, unknown> {
	try {
		return JSON.parse(input || '{}') as Record<string, unknown>;
	} catch {
		return {};
	}
}

/** Three lines of a message, the rest one click away. */
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
			<div ref={ref} className={cn('text-sm [&_p]:my-0', !open && 'line-clamp-3')}>
				{children}
			</div>
			{(overflows || open) && (
				<button
					type="button"
					className="mt-1 text-xs text-muted-foreground hover:text-foreground"
					onClick={() => setOpen((value) => !value)}
				>
					{open ? 'Thu gọn' : 'Xem thêm'}
				</button>
			)}
		</>
	);
}

/** An agent's portrait, or a person's circle for the end user. */
function Face({ name, person = false }: { name: string; person?: boolean }) {
	const id = useAgentId(name);
	if (person) {
		return (
			<span className="flex size-[22px] shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
				<UserRound className="size-3.5" />
			</span>
		);
	}
	return <ClayAvatar id={id} label={name} size={22} />;
}

export function DialogCard({
	who,
	person = false,
	label,
	note,
	tone,
	children,
}: {
	/** The other side of this message: who sent it, or who it is for. */
	who: string;
	person?: boolean;
	/** What the message is, in a few words ("giao việc", "báo kết quả"). */
	label?: string;
	note?: ReactNode;
	tone?: 'error';
	children: ReactNode;
}) {
	return (
		<div
			className={cn(
				'w-full rounded-xl border border-border/60 bg-background px-3 py-2.5',
				tone === 'error' && 'border-destructive/40 bg-destructive/5',
			)}
		>
			<div className="mb-1 flex min-w-0 items-center gap-2 text-[13px]/[18px]">
				<Face name={who} person={person} />
				<span className="truncate font-medium text-foreground">{who}</span>
				{label && <span className="shrink-0 text-muted-foreground">{label}</span>}
				{note}
			</div>
			<Clamped>{children}</Clamped>
		</div>
	);
}

const kindLabel = (kind: string | undefined) => (kind ? (KIND_LABEL[kind] ?? kind).toLocaleLowerCase('vi') : undefined);

/** A message another agent sent into this session (a team hint). */
export function TeamMessageCard({ sender, kind, text }: { sender: string; kind?: string; text: string }) {
	return (
		<DialogCard who={cleanName(sender)} label={kindLabel(kind)} tone={kind === 'error' ? 'error' : undefined}>
			<Markdown>{teamMessageText(text)}</Markdown>
		</DialogCard>
	);
}

function resultNote(pair: ToolCallWithResult): ReactNode {
	if (!pair.result) return <span className="text-muted-foreground">đang gửi…</span>;
	if (pair.result.state === 'error') return <span className="text-destructive">bị từ chối</span>;
	return null;
}

function resultText(pair: ToolCallWithResult): string {
	const output = pair.result?.output;
	if (!output) return '';
	if (typeof output === 'string') return output;
	return output.map((block) => ('text' in block ? block.text : '')).join('\n');
}

/** A message this agent sent: an assignment, a room message or the user reply. */
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
							who={cleanName(String(item.target ?? ''))}
							label={after.length > 0 ? `nhận việc, sau khi ${after.join(', ')} báo` : 'nhận việc'}
							note={<ClipboardList className="ml-auto size-3.5 shrink-0 text-muted-foreground" />}
						>
							<Markdown>{String(item.prompt ?? '')}</Markdown>
						</DialogCard>
					);
				})}
			</div>
		);
	}
	if (name === 'TeamSay') {
		return (
			<DialogCard
				who={cleanName(String(args.to ?? '')) || 'Cả phòng'}
				label={kindLabel(String(args.kind ?? '')) ?? 'nhận tin'}
				note={resultNote(pair)}
			>
				<Markdown>{String(args.content ?? '')}</Markdown>
			</DialogCard>
		);
	}
	// CaseSay / CaseFinalize: what the end user receives (unless refused).
	const refused = pair.result?.state === 'error';
	return (
		<DialogCard who="Cư dân" person label="nhận tin" note={resultNote(pair)} tone={refused ? 'error' : undefined}>
			<Markdown>{String(args.text ?? args.answer ?? '')}</Markdown>
			{refused && <p className="mt-2 text-xs text-destructive">{resultText(pair)}</p>}
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
			{hidden.length > 0 && (
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
