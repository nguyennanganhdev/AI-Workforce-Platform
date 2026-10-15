import { ArrowRight, ClipboardList, MessageSquareReply, Send, UserRound } from 'lucide-react';
import type { ReactNode } from 'react';

import { KIND_LABEL, cleanName, teamMessageText } from './teamDialogText';
import type { ToolCallWithResult } from './tool-renderers/types';
import { Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from '@/components/ui/collapsible.tsx';

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

export function DialogCard({
	icon,
	sender,
	to,
	kind,
	note,
	children,
}: {
	icon: ReactNode;
	sender?: string;
	to?: string;
	kind?: string;
	note?: ReactNode;
	children: ReactNode;
}) {
	return (
		<div className="w-full rounded-xl border border-border/70 bg-background p-3 text-sm">
			<div className="mb-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
				{icon}
				{sender && <span className="font-medium text-foreground">{sender}</span>}
				{to && (
					<>
						<ArrowRight className="size-3" />
						<span className="font-medium text-foreground">{to}</span>
					</>
				)}
				{kind && <Badge variant="outline">{KIND_LABEL[kind] ?? kind}</Badge>}
				{note}
			</div>
			<div className="text-sm">{children}</div>
		</div>
	);
}

/** A message another agent sent into this session (a team hint). */
export function TeamMessageCard({ sender, kind, text }: { sender: string; kind?: string; text: string }) {
	return (
		<DialogCard icon={<MessageSquareReply className="size-3.5" />} sender={cleanName(sender)} kind={kind}>
			<Markdown>{teamMessageText(text)}</Markdown>
		</DialogCard>
	);
}

function resultNote(pair: ToolCallWithResult): ReactNode {
	const state = pair.result?.state;
	if (!pair.result) return <span className="text-muted-foreground">đang gửi…</span>;
	if (state === 'error') return <Badge variant="destructive">bị từ chối</Badge>;
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
							icon={<ClipboardList className="size-3.5" />}
							to={cleanName(String(item.target ?? ''))}
							kind="assign"
							note={after.length > 0 && <span>sau khi {after.join(', ')} báo</span>}
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
				icon={<MessageSquareReply className="size-3.5" />}
				to={cleanName(String(args.to ?? '')) || 'Phòng'}
				kind={String(args.kind ?? '')}
				note={resultNote(pair)}
			>
				<Markdown>{String(args.content ?? '')}</Markdown>
			</DialogCard>
		);
	}
	// CaseSay / CaseFinalize: what the end user receives (unless refused).
	const refused = pair.result?.state === 'error';
	return (
		<DialogCard
			icon={refused ? <Send className="size-3.5" /> : <UserRound className="size-3.5" />}
			to="Người dùng"
			kind="reply"
			note={resultNote(pair)}
		>
			<Markdown>{String(args.text ?? args.answer ?? '')}</Markdown>
			{refused && <p className="mt-2 text-xs text-destructive">{resultText(pair)}</p>}
		</DialogCard>
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
