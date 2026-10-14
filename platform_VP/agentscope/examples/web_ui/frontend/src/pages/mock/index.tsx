import type { ContentBlock } from '@agentscope-ai/agentscope/message';
import { Pin, RadioTower, RotateCcw, Search } from 'lucide-react';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';

import {
	MOCK_AGENTS,
	MOCK_CONVERSATIONS,
	type GateEvent,
	type MockAgentId,
	type MockConversation,
	type MockEvent,
} from './chat-mock-data';
import { Enter, FlyIn } from './motion';
import { Participants } from './participants';
import { durationOf } from './playback';
import { AgentSticker, StateBadge, TranscriptEvent } from './transcript';
import { ChoiceCard } from '@/components/chat/ChoiceCard';
import { TextInput } from '@/components/chat/TextInput';
import { Brand } from '@/components/layout/Brand';
import { SELECTED_ROW } from '@/components/layout/selected-row';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkforceApprovalCard } from '@/features/workforce/approvals';
import { useCueTheme } from '@/hooks/useCueTheme';
import { cn } from '@/lib/utils';
import 'streamdown/styles.css';

/**
 * How far a conversation's script has played: `count` events are on screen,
 * and while `busy` the last of them is still under way.
 */
interface Playback {
	count: number;
	busy: boolean;
	/** Replaces the conversation's own script once a branch is taken (a refused approval). */
	events?: MockEvent[];
}

const START: Playback = { count: 1, busy: true };

/** The roster's one-line preview: the last thing anybody said, without markdown. */
export function previewOf(events: MockEvent[]): string {
	for (let index = events.length - 1; index >= 0; index -= 1) {
		const event = events[index];
		if (event.kind === 'user' || event.kind === 'agent') {
			return event.text.split('\n')[0].replaceAll('**', '');
		}
	}
	return '';
}

/**
 * Every agent that has acted or been brought in so far, in order of
 * appearance. A step's joins count once the step is done — that is when their
 * chips appear, and the participants list waits for the chips to fly from.
 */
function participantsOf(events: MockEvent[], busy: boolean): MockAgentId[] {
	const seen = new Set<MockAgentId>();
	events.forEach((event, index) => {
		if ('agent' in event && event.agent) seen.add(event.agent);
		const done = !busy || index < events.length - 1;
		if (event.kind === 'step' && done) event.joins?.forEach((agent) => seen.add(agent));
	});
	return [...seen];
}

/** One conversation in the roster: sticker, name, time, and the last line said. */
function ConversationRow({
	conversation,
	preview,
	active,
	onSelect,
}: {
	conversation: MockConversation;
	preview: string;
	active: boolean;
	onSelect: () => void;
}) {
	return (
		<li>
			<button
				type="button"
				aria-current={active ? 'true' : undefined}
				onClick={onSelect}
				// 60px rows, so the roster is a column the eye can run down.
				// `border-transparent` is reserved at rest so the selected slab's
				// border costs no layout.
				className={cn(
					'flex h-[60px] w-full items-center gap-3 rounded-xl border border-transparent px-3 text-left hover:bg-[var(--row-hover)]',
					active && SELECTED_ROW,
				)}
			>
				<ClayAvatar id={conversation.id} label={conversation.name} size={36} />
				<span className="min-w-0 flex-1">
					<span className="flex items-baseline gap-1.5">
						<span className="min-w-0 flex-1 truncate text-[15px]/5 font-medium text-foreground">
							{conversation.name}
						</span>
						<span className="shrink-0 text-xs/4 text-muted-foreground">
							{conversation.lastMessageAt}
						</span>
						{conversation.pinned && (
							<Pin className="size-3 shrink-0 fill-current text-[var(--ink-3)]" />
						)}
					</span>
					<span className="block truncate text-[13px]/[18px] text-muted-foreground">
						{preview}
					</span>
				</span>
			</button>
		</li>
	);
}

/**
 * Where the script has stopped and what moves it on. A real session waits here
 * for a person or a provider; the mock offers the scripted move as a button so
 * the reader decides when the next turn starts.
 */
function Gate({
	gate,
	onAdvance,
	onReject,
}: {
	gate: GateEvent;
	onAdvance: () => void;
	onReject: () => void;
}) {
	// Consent in the real card expires; the mock's is always fifteen minutes out.
	const [expiresAt] = useState(() => new Date(Date.now() + 15 * 60 * 1000).toISOString());

	if (gate.action === 'approval') {
		return (
			<div className="max-w-[480px] rounded-[20px] border border-[var(--cue-border,var(--border))] bg-background">
				<WorkforceApprovalCard
					approval={{ ...gate.approval, expires_at: expiresAt }}
					canDecide
					onDecide={async (_id, { decision }) => {
						if (decision === 'approve') onAdvance();
						else onReject();
					}}
				/>
			</div>
		);
	}

	// The session waits on the reader: Cue's choice card, with the scripted
	// answer as the option and the composer as the way out.
	if (gate.action === 'reply') {
		return (
			<ChoiceCard
				question="Bạn muốn trả lời thế nào?"
				options={[gate.label]}
				hint="Không có lựa chọn phù hợp? Cứ gõ câu trả lời của bạn."
				continueLabel="Tiếp tục"
				onSubmit={onAdvance}
			/>
		);
	}

	return (
		<div className="flex w-[384px] max-w-full flex-col items-start gap-3 rounded-[20px] border border-[var(--cue-border,var(--border))] p-4">
			<span className="text-[13px]/[18px] text-muted-foreground">
				Phiên đang nghỉ chờ nhà cung cấp. Mô phỏng sự kiện tiếp theo:
			</span>
			<Button variant="outline" className="h-auto min-h-8 w-full py-1.5" onClick={onAdvance}>
				<RadioTower />
				<span className="whitespace-normal text-left">{gate.label}</span>
			</Button>
		</div>
	);
}

/**
 * The chat screen on scripted conversations: a roster on the left, the open
 * session on the right, replayed event by event — routing, the Leader's pick,
 * each agent's thinking and tool calls, the answer, and the state the turn
 * ends on. It talks to no backend; see `chat-mock-data.ts` for what each
 * script demonstrates.
 *
 * Fills its parent. The chat page shows it in place of the real chat while
 * the account has no agent to talk to; {@link MockChatPage} shows it with no
 * sign-in at all.
 */
export function MockChat({
	notice,
	footer,
	headerActions,
	conversationId,
	hideSidebar = false,
}: {
	/** Opens this conversation and keeps it open, e.g. one picked elsewhere. */
	conversationId?: string;
	/** Just the transcript, for a page that brings its own sidebar. */
	hideSidebar?: boolean;
	/** Beside the mark at the top of the sidebar, e.g. the "+" menu. */
	headerActions?: ReactNode;
	/** Rendered under the roster, e.g. to say this is sample data. */
	notice?: ReactNode;
	/** The foot of the sidebar: the chat page passes the account menu. */
	footer?: ReactNode;
}) {
	const [pickedId, setActiveId] = useState(MOCK_CONVERSATIONS[0].id);
	const activeId = conversationId ?? pickedId;
	const [search, setSearch] = useState('');
	const [playback, setPlayback] = useState<Record<string, Playback>>({});
	/** What was typed into the composer in place of a scripted reply, by event id. */
	const [typed, setTyped] = useState<Record<string, string>>({});
	const transcriptEnd = useRef<HTMLDivElement>(null);

	const active = MOCK_CONVERSATIONS.find((c) => c.id === activeId) ?? MOCK_CONVERSATIONS[0];
	const play = playback[active.id] ?? START;
	const events = play.events ?? active.events;
	const shown = useMemo(() => events.slice(0, play.count), [events, play.count]);
	const current = shown[shown.length - 1];
	const gate = current.kind === 'gate' && !play.busy ? current : null;
	const finished = !play.busy && !gate;

	const participants = participantsOf(shown, play.busy);
	const activeAgent = play.busy && 'agent' in current ? (current.agent ?? null) : null;
	const state = shown.findLast((event) => event.kind === 'state')?.state;

	const needle = search.trim().toLowerCase();
	const visible = needle
		? MOCK_CONVERSATIONS.filter((c) => c.name.toLowerCase().includes(needle))
		: MOCK_CONVERSATIONS;

	const update = (id: string, change: (prev: Playback) => Playback) =>
		setPlayback((prev) => ({ ...prev, [id]: change(prev[id] ?? START) }));

	// The player. While the latest event is under way, wait out its duration,
	// then bring in the next one — or stop at a gate, or at the end. Only the
	// open conversation plays; the others hold their place.
	useEffect(() => {
		if (!play.busy) return;
		const id = active.id;
		const timer = setTimeout(() => {
			setPlayback((all) => {
				const prev = all[id] ?? START;
				const next = (prev.events ?? active.events)[prev.count];
				return {
					...all,
					[id]: next
						? { ...prev, count: prev.count + 1, busy: next.kind !== 'gate' }
						: { ...prev, busy: false },
				};
			});
		}, durationOf(current));
		return () => clearTimeout(timer);
	}, [active, play.busy, play.count, current]);

	// Keep the newest event in view.
	useEffect(() => {
		transcriptEnd.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
	}, [activeId, play.count, play.busy]);

	/** Past the gate, onto whatever the script has after it. */
	const advance = () =>
		update(active.id, (prev) => ({ ...prev, count: prev.count + 1, busy: true }));

	/** A refused approval: drop the rest of the script and play the refusal branch. */
	const reject = () => {
		if (gate?.action !== 'approval') return;
		update(active.id, (prev) => ({
			count: prev.count + 1,
			busy: true,
			events: [...events.slice(0, prev.count), ...gate.rejected],
		}));
	};

	const handleSend = (blocks: ContentBlock[]) => {
		if (gate?.action !== 'reply') return;
		const text = blocks
			.filter((b) => b.type === 'text')
			.map((b) => b.text)
			.join('\n');
		const reply = events[play.count];
		if (text && reply?.kind === 'user') setTyped((prev) => ({ ...prev, [reply.id]: text }));
		advance();
	};

	const composerHint = finished
		? 'Kịch bản đã kết thúc. Bấm “Phát lại” để xem từ đầu.'
		: gate?.action === 'reply'
			? 'Nhập câu trả lời…'
			: gate?.action === 'provider'
				? 'Phiên đang chờ cập nhật từ nhà cung cấp…'
				: gate?.action === 'approval'
					? 'Phiên đang chờ đồng ý giao dịch…'
					: 'Agent đang xử lý…';

	return (
		<div className="flex size-full">
			<aside
				className={cn(
					'cue-column flex w-[320px] shrink-0 flex-col gap-2 border-r border-sidebar-border px-2 pb-2 text-sidebar-foreground max-md:hidden',
					hideSidebar && 'hidden',
				)}
			>
				<div className="flex h-12 shrink-0 items-center justify-between gap-2 pl-2">
					<Brand />
					{headerActions}
				</div>

				<div className="relative">
					<Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
					<input
						type="search"
						aria-label="Tìm cuộc trò chuyện"
						placeholder="Tìm kiếm…"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						className="h-9 w-full rounded-xl border border-[var(--cue-border,var(--border))] bg-background pl-9 pr-3 text-[15px] outline-none placeholder:text-[var(--cue-text-tertiary,var(--muted-foreground))] focus-visible:border-[var(--ring)]"
					/>
				</div>

				{visible.length > 0 ? (
					<ul className="flex min-h-0 flex-1 flex-col overflow-y-auto">
						{visible.map((conversation) => {
							const its = playback[conversation.id] ?? START;
							return (
								<ConversationRow
									key={conversation.id}
									conversation={conversation}
									preview={previewOf(
										(its.events ?? conversation.events).slice(0, its.count),
									)}
									active={conversation.id === active.id}
									onSelect={() => setActiveId(conversation.id)}
								/>
							);
						})}
					</ul>
				) : (
					<p className="flex-1 px-2 py-4 text-center text-sm text-muted-foreground">
						Không tìm thấy cuộc trò chuyện nào khớp với “{search.trim()}”.
					</p>
				)}

				{notice}

				{footer}
			</aside>

			<main className="flex min-w-0 flex-1 flex-col">
				<header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-2 gap-y-1 px-4 py-1">
					<ClayAvatar id={active.id} label={active.name} size={20} />
					<div className="flex min-w-0 flex-1 items-baseline gap-2">
						<h1 className="truncate text-[17px]/6 font-medium">{active.name}</h1>
						<p className="truncate text-[13px]/[18px] text-[var(--cue-text-tertiary,var(--muted-foreground))]">
							{active.subtitle}
						</p>
					</div>
					{state && (
						// Keyed by state, so a change swaps the badge in rather than recolouring it.
						<span key={state} className="cue-pop inline-flex">
							<StateBadge state={state} />
						</span>
					)}
					{/* Who is in the session so far. A narrow window has no room for
					    the rail on the right, so the stickers stand in for it here. */}
					{participants.length > 0 && (
						<ul
							aria-label="Agent đang tham gia phiên"
							className="flex items-center -space-x-1.5 lg:hidden"
						>
							{participants.map((agent) => (
								// Overlapping tiles; the one at work lifts above the rest.
								<li
									key={agent}
									className={cn(
										'relative transition-transform duration-300',
										agent === activeAgent && 'z-10 -translate-y-0.5',
									)}
								>
									<Tooltip>
										<TooltipTrigger asChild>
											<span
												tabIndex={0}
												className="block rounded-[10px] ring-2 ring-background"
											>
												<FlyIn agent={agent}>
													<AgentSticker
														agent={agent}
														working={agent === activeAgent}
													/>
												</FlyIn>
											</span>
										</TooltipTrigger>
										<TooltipContent>
											{MOCK_AGENTS[agent].name}: {MOCK_AGENTS[agent].role}
										</TooltipContent>
									</Tooltip>
								</li>
							))}
						</ul>
					)}
					<Button
						variant="ghost"
						size="sm"
						onClick={() => {
							update(active.id, () => START);
							setTyped({});
						}}
					>
						<RotateCcw />
						Phát lại
					</Button>
				</header>

				<div className="min-h-0 flex-1 overflow-y-auto">
					<div className="flex w-full max-w-3xl flex-col gap-6 px-4 py-4">
						{shown.map((event, index) =>
							event.kind === 'gate' ? null : (
								// Only the event that just arrived rises in; reopening a
								// conversation draws its history still.
								<Enter
									key={event.id}
									animate={play.busy && index === shown.length - 1}
								>
									<TranscriptEvent
										event={event}
										running={play.busy && index === shown.length - 1}
										typedText={typed[event.id]}
									/>
								</Enter>
							),
						)}
						{gate && (
							<Enter key={gate.id} animate>
								<Gate gate={gate} onAdvance={advance} onReject={reject} />
							</Enter>
						)}
						<div ref={transcriptEnd} />
					</div>
				</div>

				{/* Open only while the session is waiting for a reply — the one
				    state in which a real session accepts a message. Attaching is
				    off: the mock has nowhere to upload to. */}
				<TextInput
					key={`${active.id}:${gate?.id ?? 'closed'}`}
					className="w-full shrink-0 px-4 pb-4"
					placeholder={composerHint}
					disabled={gate?.action !== 'reply'}
					onSend={handleSend}
					allowedInputTypes={[]}
					fileProcessor={async () => null}
				/>
			</main>

			<Participants
				requester={active.requester}
				agents={participants}
				activeAgent={activeAgent}
			/>
		</div>
	);
}

/**
 * The mock on its own, with no app shell around it and no sign-in — `App`
 * serves it at `/mock/chat` ahead of the auth check.
 */
export function MockChatPage() {
	useCueTheme();
	return (
		<div className="h-screen bg-canvas">
			<MockChat />
		</div>
	);
}
