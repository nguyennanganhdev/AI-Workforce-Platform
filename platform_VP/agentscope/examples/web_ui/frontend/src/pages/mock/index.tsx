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
import { Participants } from './participants';
import { AgentSticker, StateBadge, TranscriptEvent } from './transcript';
import { TextInput } from '@/components/chat/TextInput';
import { Brand } from '@/components/layout/Brand';
import { SELECTED_ROW } from '@/components/layout/selected-row';
import { Button } from '@/components/ui/button';
import { ClayAvatar } from '@/components/ui/clay-avatar';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkforceApprovalCard } from '@/features/workforce/approvals';
import { useClayTheme } from '@/hooks/useClayTheme';
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

/** How long an event stays "under way" before the next one appears. */
function durationOf(event: MockEvent): number {
	switch (event.kind) {
		case 'user':
			return 600;
		case 'step':
			return 900;
		case 'thinking':
			return Math.min(2600, event.seconds * 650);
		case 'tool':
			return 1100;
		case 'agent':
			return 1000;
		case 'state':
			return 350;
		case 'gate':
			return 0;
	}
}

/** The roster's one-line preview: the last thing anybody said, without markdown. */
function previewOf(events: MockEvent[]): string {
	for (let index = events.length - 1; index >= 0; index -= 1) {
		const event = events[index];
		if (event.kind === 'user' || event.kind === 'agent') {
			return event.text.split('\n')[0].replaceAll('**', '');
		}
	}
	return '';
}

/** Every agent that has acted or been brought in so far, in order of appearance. */
function participantsOf(events: MockEvent[]): MockAgentId[] {
	const seen = new Set<MockAgentId>();
	for (const event of events) {
		if ('agent' in event && event.agent) seen.add(event.agent);
		if (event.kind === 'step') event.joins?.forEach((agent) => seen.add(agent));
	}
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
					'flex min-h-[60px] w-full items-center gap-2.5 rounded-[var(--r-tile)] border border-transparent px-2 text-left hover:bg-[var(--canvas)]',
					active && SELECTED_ROW,
				)}
			>
				<ClayAvatar id={conversation.id} label={conversation.name} size={36} />
				<span className="min-w-0 flex-1">
					<span className="flex items-center gap-1.5">
						<span className="min-w-0 flex-1 truncate text-[12px]/[16px] text-muted-foreground">
							{conversation.name}
						</span>
						<span className="shrink-0 text-[12px]/[16px] text-[var(--ink-3)]">
							{conversation.lastMessageAt}
						</span>
						{conversation.pinned && (
							<Pin className="size-3 shrink-0 fill-current text-[var(--ink-3)]" />
						)}
					</span>
					<span className="mt-px block truncate text-[14px]/[20px] font-medium">
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
			<div className="rounded-[var(--r-card)] border border-white bg-[var(--raised)] shadow-[var(--clay-bubble)]">
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

	const fromProvider = gate.action === 'provider';
	return (
		<div className="flex flex-col items-start gap-2 rounded-[var(--r-tile)] border border-dashed border-[var(--ink-3)] px-3 py-2.5">
			<span className="text-[12px]/[16px] text-muted-foreground">
				{fromProvider
					? 'Phiên đang nghỉ chờ nhà cung cấp. Mô phỏng sự kiện tiếp theo:'
					: 'Phiên đang chờ người dùng. Bấm câu trả lời theo kịch bản, hoặc tự gõ ở ô bên dưới:'}
			</span>
			<Button variant="outline" size="sm" className="h-auto min-h-7 py-1" onClick={onAdvance}>
				{fromProvider && <RadioTower />}
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
}: {
	/** Rendered under the roster, e.g. to say this is sample data. */
	notice?: ReactNode;
	/** The foot of the sidebar: the chat page passes the account menu. */
	footer?: ReactNode;
}) {
	const [activeId, setActiveId] = useState(MOCK_CONVERSATIONS[0].id);
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

	const participants = participantsOf(shown);
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
	const advance = () => update(active.id, (prev) => ({ ...prev, count: prev.count + 1, busy: true }));

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
		<div className="flex size-full gap-2 p-2">
			<aside className="clay-panel flex w-[316px] shrink-0 flex-col gap-2 rounded-[var(--r-panel)] bg-sidebar p-2 text-sidebar-foreground max-md:hidden">
				<Brand className="px-2 pt-1 pb-1" />

				{/* Sunken, like the composer: raised things are pressed, sunken
				    things receive. */}
				<div className="relative">
					<Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
					<input
						type="search"
						aria-label="Tìm cuộc trò chuyện"
						placeholder="Tìm kiếm…"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						className="h-9 w-full rounded-[var(--r-tile)] border border-transparent bg-[var(--sunken)] pl-8 pr-3 text-sm shadow-[var(--clay-sunken)] placeholder:text-muted-foreground"
					/>
				</div>

				{visible.length > 0 ? (
					<ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
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
				<header className="flex min-h-[52px] shrink-0 flex-wrap items-center gap-x-3 gap-y-1 px-1 py-1">
					<ClayAvatar id={active.id} label={active.name} size={36} />
					<div className="min-w-0 flex-1">
						<h1 className="truncate text-[16px]/[24px] font-semibold">{active.name}</h1>
						<p className="truncate text-[12px]/[16px] text-muted-foreground">
							{active.subtitle}
						</p>
					</div>
					{state && <StateBadge state={state} />}
					{/* Who is in the session so far. A narrow window has no room for
					    the rail on the right, so the stickers stand in for it here. */}
					{participants.length > 0 && (
						<ul
							aria-label="Agent đang tham gia phiên"
							className="flex items-center gap-1 lg:hidden"
						>
							{participants.map((agent) => (
								<li key={agent}>
									<Tooltip>
										<TooltipTrigger asChild>
											<span tabIndex={0} className="block rounded-[10px]">
												<AgentSticker agent={agent} />
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
					<div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-2 py-6">
						{shown.map((event, index) =>
							event.kind === 'gate' ? null : (
								<TranscriptEvent
									key={event.id}
									event={event}
									running={play.busy && index === shown.length - 1}
									typedText={typed[event.id]}
								/>
							),
						)}
						{gate && (
							<Gate key={gate.id} gate={gate} onAdvance={advance} onReject={reject} />
						)}
						<div ref={transcriptEnd} />
					</div>
				</div>

				{/* Open only while the session is waiting for a reply — the one
				    state in which a real session accepts a message. Attaching is
				    off: the mock has nowhere to upload to. */}
				<TextInput
					key={`${active.id}:${gate?.id ?? 'closed'}`}
					className="mx-auto w-full max-w-2xl shrink-0 px-2 pb-2"
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
	useClayTheme();
	return (
		<div className="h-screen bg-canvas">
			<MockChat />
		</div>
	);
}
