import { Check, ChevronRight, Loader2, Waypoints } from 'lucide-react';
import { Fragment, type ReactNode, useMemo } from 'react';

import {
	MOCK_AGENTS,
	type AgentEvent,
	type GateEvent,
	type MockAgentId,
	type MockEvent,
	type StateEvent,
	type StepEvent,
	type ThinkingEvent,
	type ToolEvent,
	type UserEvent,
} from './chat-mock-data';
import { streamPlan, thinkingMs, TYPING_MS } from './playback';
import { useElapsed, useLive } from './use-motion';
import { Markdown } from '@/components/markdown';
import { Bubble, BubbleContent } from '@/components/ui/bubble';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import type { NextAction, WorkflowState } from '@/features/workforce/shared/contracts/workforce-v1';
import { cn } from '@/lib/utils';

/** 28px is the smallest tile that draws the agent's sticker rather than initials. */
const STICKER = 28;

export function AgentSticker({
	agent,
	size = STICKER,
	working = false,
	flySource = false,
}: {
	agent: MockAgentId;
	size?: number;
	working?: boolean;
	/** Marks this tile as a place the agent can fly up from (see `FlyIn`). */
	flySource?: boolean;
}) {
	const tile = (
		<ClayAvatar id={agent} label={MOCK_AGENTS[agent].name} size={size} working={working} />
	);
	return flySource ? (
		<span data-fly-from={agent} className="inline-flex shrink-0">
			{tile}
		</span>
	) : (
		tile
	);
}

/** `**name**` → bold. The scripts mark names this way; nothing else is parsed. */
function withBold(text: string): ReactNode {
	return text.split('**').map((part, index) =>
		index % 2 === 1 ? (
			<strong key={index} className="font-semibold">
				{part}
			</strong>
		) : (
			<Fragment key={index}>{part}</Fragment>
		),
	);
}

/**
 * The identifiers and state names behind a plain-language line. Collapsed by
 * default: a manager reads the line, an engineer opens this.
 */
function TechDetail({ lines }: { lines?: string[] }) {
	if (!lines?.length) return null;
	return (
		<Collapsible>
			<CollapsibleTrigger asChild>
				<button
					type="button"
					className="group flex items-center gap-1 text-[12px]/[16px] text-[var(--ink-3)] hover:text-foreground"
				>
					Chi tiết kỹ thuật
					<ChevronRight className="size-3 transition-transform group-data-[state=open]:rotate-90" />
				</button>
			</CollapsibleTrigger>
			<CollapsibleContent>
				<ul className="mt-1 flex flex-col gap-0.5 rounded-[var(--r-chip)] bg-[var(--sunken)] px-2.5 py-2 font-mono text-[12px]/[16px] text-muted-foreground">
					{lines.map((line) => (
						<li key={line} className="break-words">
							{line}
						</li>
					))}
				</ul>
			</CollapsibleContent>
		</Collapsible>
	);
}

/**
 * Spinner while the step is under way, a check once it is done. A check that
 * replaces a spinner on screen draws itself in; one drawn done just sits.
 */
function Progress({ running, live }: { running: boolean; live: boolean }) {
	if (running) {
		return <Loader2 className="size-4 shrink-0 animate-spin" aria-label="Đang xử lý" />;
	}
	return live ? (
		<svg
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth={2}
			strokeLinecap="round"
			strokeLinejoin="round"
			className="cue-check size-4 shrink-0"
			aria-label="Xong"
		>
			<path d="M20 6 9 17l-5-5" />
		</svg>
	) : (
		<Check className="size-4 shrink-0" aria-label="Xong" />
	);
}

function UserMessage({ event, text }: { event: UserEvent; text: string }) {
	return (
		<div className="flex flex-col items-end gap-1">
			<span className="px-1 text-[12px]/[16px] text-muted-foreground">{event.sender}</span>
			<Bubble align="end" variant="question">
				<BubbleContent>
					<span className="whitespace-pre-wrap">{text}</span>
				</BubbleContent>
			</Bubble>
		</div>
	);
}

/**
 * One line of the activity log. Violet when an agent did it, neutral when the
 * platform did — so who acted reads before the words do.
 */
function StepLine({ event, running }: { event: StepEvent; running: boolean }) {
	const live = useLive(running);
	return (
		<div className="flex flex-col gap-1.5">
			<div
				className={cn(
					'flex items-center gap-2.5 rounded-[var(--r-tile)] px-3 py-2 text-[13px]/[20px]',
					event.agent
						? 'bg-[var(--violet-soft)] text-[var(--violet-ink)]'
						: 'bg-[var(--sunken)] text-[var(--ink-2)]',
				)}
			>
				{event.agent ? (
					<AgentSticker agent={event.agent} working={running} flySource />
				) : (
					<Waypoints className="size-4 shrink-0" />
				)}
				<span className="min-w-0 flex-1">{withBold(event.text)}</span>
				<Progress running={running} live={live} />
			</div>
			{event.joins && !running && (
				<ul className="flex flex-wrap gap-1.5 pl-1">
					{event.joins.map((agent, index) => (
						// Pops out of the step that added it, one after another, before its
						// tile flies on up to the participants.
						<li
							key={agent}
							className={cn(
								'flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--raised)] py-0.5 pl-0.5 pr-2.5 text-[12px]/[16px] shadow-[var(--clay-bubble)]',
								live && 'cue-pop',
							)}
							style={live ? { animationDelay: `${index * 120}ms` } : undefined}
						>
							<AgentSticker agent={agent} flySource />
							<span className="font-semibold">{MOCK_AGENTS[agent].name}</span>
							<span className="text-muted-foreground">{MOCK_AGENTS[agent].role}</span>
						</li>
					))}
				</ul>
			)}
			<TechDetail lines={event.detail} />
		</div>
	);
}

/** An agent reasoning before it acts. Left open, since the reasoning is the point here. */
function Thinking({ event, running }: { event: ThinkingEvent; running: boolean }) {
	const name = MOCK_AGENTS[event.agent].name;
	const live = useLive(running);
	const elapsed = useElapsed(running);
	if (running) {
		// Scaled so the counter reaches the script's seconds just as the
		// playback moves on, however much the playback shortens the wait.
		const seconds = Math.min(
			event.seconds,
			(elapsed / thinkingMs(event.seconds)) * event.seconds,
		);
		return (
			<div className="flex items-center gap-2.5 text-sm text-muted-foreground">
				<AgentSticker agent={event.agent} working={running} flySource />
				<span className="shimmer">{name} đang suy nghĩ…</span>
				<span className="tabular-nums text-[var(--cue-text-tertiary,var(--muted-foreground))]">
					{seconds.toFixed(1).replace('.', ',')} giây
				</span>
			</div>
		);
	}
	return (
		<Collapsible defaultOpen>
			<CollapsibleTrigger asChild>
				<button
					type="button"
					className="group flex items-center gap-2.5 text-left text-sm text-muted-foreground hover:text-foreground"
				>
					<AgentSticker agent={event.agent} working={running} flySource />
					<span>
						{name} đã suy nghĩ {event.seconds} giây
					</span>
					<ChevronRight className="size-3 shrink-0 transition-transform group-data-[state=open]:rotate-90" />
				</button>
			</CollapsibleTrigger>
			<CollapsibleContent>
				<p
					className={cn(
						'ml-[38px] mt-1.5 rounded-[var(--r-tile)] bg-muted px-3 py-2 text-[13px]/[20px] text-muted-foreground',
						live && 'cue-unfold',
					)}
				>
					{event.text}
				</p>
			</CollapsibleContent>
		</Collapsible>
	);
}

/** A tool call: who called what, whether it writes, and what came back. */
function ToolCall({ event, running }: { event: ToolEvent; running: boolean }) {
	const name = MOCK_AGENTS[event.agent].name;
	const live = useLive(running);
	return (
		<Collapsible>
			<CollapsibleTrigger asChild>
				<button
					type="button"
					className="group flex w-full items-center gap-2.5 text-left text-[13px]/[20px] text-muted-foreground hover:text-foreground"
				>
					<AgentSticker agent={event.agent} working={running} flySource />
					<span className={cn('min-w-0 flex-1', running && 'shimmer')}>
						{name} {running ? 'đang dùng' : 'đã dùng'} công cụ{' '}
						<strong className="font-semibold text-foreground">{event.label}</strong>
						{!running && (
							<span className={live ? 'cue-fade' : undefined}>
								, kết quả: {event.summary}
							</span>
						)}
					</span>
					<Progress running={running} live={live} />
					{/* A write is a side effect, so it is marked apart from a read. */}
					<span
						className={cn(
							'shrink-0 rounded-full px-2 py-0.5 text-[12px]/[16px] font-semibold',
							event.effect === 'write'
								? 'bg-[var(--amber-soft)] text-[var(--amber-ink)]'
								: 'bg-[var(--sunken)] text-[var(--ink-2)]',
							// A write that just landed rings once, so the side effect is noticed.
							live && !running && event.effect === 'write' && 'cue-flash',
						)}
					>
						{event.effect === 'write' ? 'Ghi' : 'Đọc'}
					</span>
					<ChevronRight className="size-3 shrink-0 transition-transform group-data-[state=open]:rotate-90" />
				</button>
			</CollapsibleTrigger>
			<CollapsibleContent>
				<div className="ml-[38px] mt-1.5 flex flex-col gap-2 rounded-[var(--r-tile)] bg-muted px-3 py-2 text-[13px]/[20px]">
					<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
						<dt className="text-muted-foreground">Gửi đi</dt>
						<dd className="whitespace-pre-wrap">{event.input}</dd>
						{!running && (
							<>
								<dt className="text-muted-foreground">Nhận về</dt>
								<dd className="whitespace-pre-wrap">{event.result}</dd>
							</>
						)}
					</dl>
					<TechDetail lines={event.detail} />
				</div>
			</CollapsibleContent>
		</Collapsible>
	);
}

/** Three bouncing dots, shown in an agent's bubble before its answer lands. */
function TypingDots() {
	return (
		<span className="flex items-center gap-1 py-1.5">
			<span className="sr-only">Đang trả lời…</span>
			{['-0.3s', '-0.15s', '0s'].map((delay) => (
				<span
					key={delay}
					className="size-1.5 animate-bounce rounded-full bg-[var(--ink-3)]"
					style={{ animationDelay: delay }}
				/>
			))}
		</span>
	);
}

/** An agent's answer, headed by which agent it is. */
function AgentAnswer({ event, running }: { event: AgentEvent; running: boolean }) {
	const elapsed = useElapsed(running);
	// Words and the whitespace between them, so a prefix keeps the line breaks.
	const tokens = useMemo(() => event.text.split(/(\s+)/), [event.text]);
	const words = running
		? Math.floor((elapsed - TYPING_MS) / streamPlan(event.text).wordMs)
		: Infinity;
	return (
		<div className="flex flex-col items-start gap-1.5">
			<div className="flex items-center gap-2">
				<AgentSticker agent={event.agent} working={running} flySource />
				<span className="text-[13px]/[20px] font-semibold">
					{MOCK_AGENTS[event.agent].name}
				</span>
			</div>
			<Bubble variant="agent">
				<BubbleContent>
					{/* Dots first, then the answer word by word, as a stream would. */}
					{words <= 0 ? (
						<TypingDots />
					) : (
						<Markdown isAnimating={running}>
							{running ? tokens.slice(0, words * 2).join('') : event.text}
						</Markdown>
					)}
				</BubbleContent>
			</Bubble>
		</div>
	);
}

/** Same wording as `features/workforce/chat/ticket_timeline/WorkflowStatus.tsx`. */
const WORKFLOW_STATE_LABEL: Record<WorkflowState, string> = {
	accepted: 'Đã tiếp nhận',
	active: 'Đang xử lý',
	waiting_external_event: 'Đang chờ cập nhật từ nhà cung cấp',
	awaiting_user: 'Chờ khách hàng trả lời',
	awaiting_approval: 'Chờ xác nhận giao dịch',
	awaiting_confirmation: 'Chờ xác nhận hoàn tất',
	needs_attention: 'Cần kiểm tra',
	blocked_authorization: 'Quyền truy cập đã thay đổi',
	blocked_route_changed: 'Nơi quản lý đã thay đổi',
	closed: 'Đã đóng',
};

const NEXT_ACTION_LABEL: Record<NextAction, string> = {
	none: 'không cần làm gì thêm',
	submit_reply: 'chờ câu trả lời',
	submit_approval: 'chờ đồng ý trước khi thực hiện',
	watch_request: 'theo dõi kết quả lượt này',
	watch_events: 'theo dõi cập nhật',
	confirm_close: 'chờ xác nhận để đóng',
	resolve_attention: 'cần người xử lý',
};

/** Waiting on a person is amber; waiting on a machine or working is violet; done is neutral. */
const STATE_TONE: Record<WorkflowState, string> = {
	accepted: 'bg-[var(--violet-soft)] text-[var(--violet-ink)]',
	active: 'bg-[var(--violet-soft)] text-[var(--violet-ink)]',
	waiting_external_event: 'bg-[var(--violet-soft)] text-[var(--violet-ink)]',
	awaiting_user: 'bg-[var(--amber-soft)] text-[var(--amber-ink)]',
	awaiting_approval: 'bg-[var(--amber-soft)] text-[var(--amber-ink)]',
	awaiting_confirmation: 'bg-[var(--amber-soft)] text-[var(--amber-ink)]',
	needs_attention: 'bg-[var(--coral-soft)] text-[var(--coral-ink)]',
	blocked_authorization: 'bg-[var(--coral-soft)] text-[var(--coral-ink)]',
	blocked_route_changed: 'bg-[var(--coral-soft)] text-[var(--coral-ink)]',
	closed: 'bg-[var(--sunken)] text-[var(--ink-2)]',
};

/** A dot and a label; the dot means colour is never the only signal of the tone. */
export function StateBadge({ state }: { state: WorkflowState }) {
	return (
		<span
			className={cn(
				'inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[12px]/[16px] font-semibold',
				STATE_TONE[state],
			)}
		>
			<span className="size-1.5 rounded-full bg-current" />
			{WORKFLOW_STATE_LABEL[state]}
		</span>
	);
}

/** Where the turn left the workflow, and what is expected next. */
function StateLine({ event }: { event: StateEvent }) {
	return (
		<div className="flex flex-col gap-1.5">
			<div className="flex flex-wrap items-center gap-2 text-[13px]/[20px] text-muted-foreground">
				<span>Trạng thái sau lượt này:</span>
				<StateBadge state={event.state} />
				<span>Bước tiếp theo: {NEXT_ACTION_LABEL[event.nextAction]}.</span>
			</div>
			<TechDetail
				lines={[
					`workflow_state=${event.state}, next_action=${event.nextAction}`,
					...(event.detail ?? []),
				]}
			/>
		</div>
	);
}

/**
 * One event of a scripted conversation. `running` is true for the event the
 * playback is currently on: a step still spinning, an agent still thinking, an
 * answer not yet landed.
 */
export function TranscriptEvent({
	event,
	running,
	typedText,
}: {
	event: Exclude<MockEvent, GateEvent>;
	running: boolean;
	/** What was actually typed into the composer for a `user` event, if anything. */
	typedText?: string;
}) {
	switch (event.kind) {
		case 'user':
			return <UserMessage event={event} text={typedText ?? event.text} />;
		case 'step':
			return <StepLine event={event} running={running} />;
		case 'thinking':
			return <Thinking event={event} running={running} />;
		case 'tool':
			return <ToolCall event={event} running={running} />;
		case 'agent':
			return <AgentAnswer event={event} running={running} />;
		case 'state':
			return <StateLine event={event} />;
	}
}
