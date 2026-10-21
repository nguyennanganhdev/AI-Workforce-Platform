import { ReplyFinishedReason } from '@agentscope-ai/agentscope/event';
import {
	type ContentBlock,
	getContentBlocks,
	type Msg,
	type TextBlock,
	type ToolCallBlock,
} from '@agentscope-ai/agentscope/message';
import { GitBranch, TriangleAlert, X } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';

import { Button } from '../ui/button';
import { DiffStats } from './tool-renderers/_shared';
import type { GitStatus } from '@/api';
import { ASMessageBubble } from '@/components/chat/ASMessageBubble.tsx';
import { CaseFileSheet } from '@/components/chat/CaseFileSheet';
import { ConfirmCard } from '@/components/chat/ConfirmCard.tsx';
import { FlipCard } from '@/components/chat/FlipCard.tsx';
import { TextInput } from '@/components/chat/TextInput.tsx';
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert.tsx';
import { ClayPortrait } from '@/components/ui/clay-portrait';
import { Marker, MarkerContent } from '@/components/ui/marker';
import {
	MessageScroller,
	MessageScrollerButton,
	MessageScrollerContent,
	MessageScrollerItem,
	MessageScrollerProvider,
	MessageScrollerViewport,
} from '@/components/ui/message-scroller.tsx';
import { Spinner } from '@/components/ui/spinner';
import type { ReplyPhase } from '@/hooks/useMessages';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';

/** How long a load may run before it is worth showing a spinner. */
const SPINNER_DELAY_MS = 150;

/**
 * A gap this long between two messages gets a marker stamping when the
 * conversation resumed — long enough that it *was* resumed, rather than
 * merely paused to read the last reply.
 */
const TIME_MARKER_GAP_MS = 10 * 60 * 1000;

/**
 * Stamp for a resumed conversation. The time alone is enough while the
 * marker and the message above it share a day; once the gap crosses
 * midnight the date has to come with it. Both come from `Intl`, so
 * "Aug 13, 13:03" and "8月13日 13:03" fall out of the active language
 * rather than out of a hand-written pattern per locale.
 */
function markerStamp(at: Date, previous: Date, language: string): string {
	const sameDay = at.toDateString() === previous.toDateString();
	return new Intl.DateTimeFormat(language, {
		...(sameDay ? {} : { month: 'short', day: 'numeric' }),
		hour: '2-digit',
		minute: '2-digit',
		hour12: false,
	}).format(at);
}

interface ChatContentProps {
	msgs: Msg[];
	/**
	 * Whether the history for the currently selected session is still on
	 * the wire. Takes precedence over {@link msgs}, which still holds the
	 * *previous* session's messages until the fetch effect clears them.
	 */
	loading?: boolean;
	/**
	 * Reply lifecycle phase from ``useMessages`` — forwarded to
	 * ``TextInput`` so the single send / stop button can pick its
	 * icon, tooltip, disabled state and click handler from one source.
	 */
	phase: ReplyPhase;
	disabled: boolean;
	onSend: (content: ContentBlock[], targetAgentId?: string) => void | Promise<void>;
	teamChat?: boolean;
	onUserConfirm: (
		toolCall: ToolCallBlock,
		confirm: boolean,
		replyId: string,
		rules?: ToolCallBlock['suggested_rules'],
	) => Promise<void>;
	autoComplete?: (input: string) => string | null;
	className?: string;
	/** Called when the user clicks the stop button. */
	onInterrupt?: () => void;
	/**
	 * Optional content pinned at the bottom of the chat — between the
	 * message scroll area and the text input (e.g. pending subagent HITL
	 * cards on a team leader's view). Rendered below the conversation so
	 * a pending confirmation sits next to the input, where the user is
	 * looking, rather than scrolled off the top.
	 */
	footerSlot?: React.ReactNode;
	modelControls?: React.ReactNode;
	/** @see TextInputProps.allowedInputTypes */
	allowedInputTypes: string[];
	/** @see TextInputProps.fileProcessor */
	fileProcessor: (file: File) => Promise<ContentBlock | null>;
	/** The open session. */
	sessionId: string | null;
	/** Agent owning the open session; enables each answer's case file. */
	agentId?: string | null;
	/** Git state of the working directory; `null` hides the branch badge entirely. */
	git?: GitStatus | null;
	/** Re-reads the git state, since nothing polls for it. */
	onRefreshGit?: () => void | Promise<void>;
}

/**
 * One entry per message id, at its first position with its latest copy. Older
 * team sessions stored a member reply twice (its start and its final copy).
 */
function latestCopies(msgs: Msg[]): Msg[] {
	const latest = new Map<string, Msg>();
	for (const message of msgs) latest.set(message.id, message);
	if (latest.size === msgs.length) return msgs;
	const seen = new Set<string>();
	return msgs.flatMap((message) => {
		if (seen.has(message.id)) return [];
		seen.add(message.id);
		return [latest.get(message.id)!];
	});
}

/** Whether a member's reply says something to the customer (text or a question). */
function addressesCustomer(content: ContentBlock[]): boolean {
	return content.some((block) => {
		if (block.type === 'text') return Boolean(block.text.trim());
		if (block.type !== 'tool_call' || block.name !== 'TeamSay') return false;
		try {
			const { to } = JSON.parse(block.input) as { to?: string | null };
			const target = typeof to === 'string' ? to.trim().toLowerCase() : '';
			return !target || target === 'null' || target === 'none';
		} catch {
			return false;
		}
	});
}

const ChatContentComponent: React.FC<ChatContentProps> = ({
	msgs,
	loading = false,
	phase,
	disabled,
	onSend,
	teamChat = false,
	onUserConfirm,
	autoComplete,
	className,
	onInterrupt,
	footerSlot,
	modelControls,
	allowedInputTypes,
	fileProcessor,
	sessionId,
	agentId = null,
	git,
	onRefreshGit,
}) => {
	const { t, i18n } = useTranslation();
	const [caseFileMessageId, setCaseFileMessageId] = useState<string | null>(null);
	useEffect(() => setCaseFileMessageId(null), [sessionId]);
	const { visibleMsgs, workingMembers } = useMemo(() => {
		const unique = latestCopies(msgs);
		if (!teamChat) return { visibleMsgs: unique, workingMembers: [] as string[] };
		const working = new Set<string>();
		const visible = unique.flatMap((message) => {
			if (message.role !== 'assistant') return [message];
			// Runtime hints stay out of team chats. Thinking is kept: the bubble
			// folds it into the collapsed trace. A finished reply with nothing
			// else to show is dropped.
			const content = message.content.filter((block) => block.type !== 'hint');
			const hasOutput = content.some((block) => block.type !== 'thinking');
			const failed = message.finished_reason === ReplyFinishedReason.ERROR;
			if (!hasOutput && message.finished_reason && !failed) return [];
			// A member's internal turn (lookups and messages to teammates) lives
			// in the team panel; the chat keeps what is addressed to the customer.
			const memberSession = message.metadata?.team_session_id;
			const isMember = typeof memberSession === 'string' && !!sessionId && memberSession !== sessionId;
			if (isMember && !failed && !addressesCustomer(content)) {
				if (!message.finished_reason && message.name) working.add(message.name);
				return [];
			}
			return [{ ...message, content }];
		});
		return { visibleMsgs: visible, workingMembers: [...working] };
	}, [msgs, teamChat, sessionId]);
	const [replyTarget, setReplyTarget] = useState<{ agentId: string; name: string } | null>(null);
	useEffect(() => setReplyTarget(null), [sessionId]);
	const handleSend = async (content: ContentBlock[]) => {
		await onSend(content, replyTarget?.agentId);
		setReplyTarget(null);
	};
	// Only a session that finished loading with nothing in it is empty.
	// Treating "no messages yet" as empty would flash the greeting over
	// every session that does have history.
	const isEmpty = !loading && msgs.length === 0;

	// A spinner that appears and vanishes inside a couple of frames reads
	// as a flicker, not as feedback — so hold it back until the load has
	// gone on long enough to be worth reporting. The gap renders blank,
	// which is invisible at this duration.
	const [showSpinner, setShowSpinner] = useState(false);
	useEffect(() => {
		if (!loading) {
			setShowSpinner(false);
			return;
		}
		const timer = setTimeout(() => setShowSpinner(true), SPINNER_DELAY_MS);
		return () => clearTimeout(timer);
	}, [loading]);

	const toConfirmedToolCalls = useMemo(() => {
		if (msgs.length === 0) return [];

		return msgs.filter((message) => message.role === 'assistant' &&
			// Mirrored member requests use the subagent card and its routing.
			(!message.metadata?.team_session_id || message.metadata.team_session_id === sessionId)).flatMap((message) => {
			const resolved = new Set(getContentBlocks(message, 'tool_result').map((result) => result.id));
			return getContentBlocks(message, 'tool_call')
				.filter((tc) => tc.state === 'asking' && !resolved.has(tc.id))
				.map((tc) => ({ replyId: message.id, toolCall: tc }));
		});
	}, [msgs, sessionId]);

	return (
		<div
			className={cn(
				'flex h-full w-full flex-col gap-3 px-3 pb-3',
				className,
			)}
		>
			{loading ? (
				<div className="flex flex-1 w-full items-center justify-center">
					{showSpinner ? <Spinner className="size-5 text-muted-foreground" /> : null}
				</div>
			) : isEmpty ? (
				<div className="flex flex-1 flex-col items-center justify-center gap-4 text-center text-2xl font-medium text-foreground">
					<ClayPortrait which="leader" size={96} />
					{t('chat.greeting')}
				</div>
			) : (
				<MessageScrollerProvider autoScroll={true} defaultScrollPosition={'end'}>
					<MessageScroller>
						<MessageScrollerViewport>
							<MessageScrollerContent>
								{visibleMsgs.map((message, index) => {
									const previous = visibleMsgs[index - 1];
									const at = new Date(message.created_at);
									const previousAt = previous
										? new Date(previous.finished_at ?? previous.created_at)
										: at;
									return (
										<MessageScrollerItem
											key={message.id}
											messageId={message.id}
										>
											{at.getTime() - previousAt.getTime() >
												TIME_MARKER_GAP_MS && (
												<Marker
													variant="separator"
													className="mb-6 font-mono text-xs"
												>
													<MarkerContent>
														{markerStamp(at, previousAt, i18n.language)}
													</MarkerContent>
												</Marker>
											)}
											<ASMessageBubble
												message={message}
												onUserConfirm={onUserConfirm}
												onReplyTo={teamChat ? (targetAgentId, name) => setReplyTarget({ agentId: targetAgentId, name }) : undefined}
												onOpenCaseFile={agentId && sessionId ? setCaseFileMessageId : undefined}
											/>
										</MessageScrollerItem>
									);
								})}
								{workingMembers.length > 0 && (
									<p className="flex items-center gap-2 px-4 text-sm text-muted-foreground shimmer" role="status">
										{t('messageBubble.trace.working', { names: workingMembers.join(', ') })}
									</p>
								)}
								{msgs.length > 0 &&
									msgs[msgs.length - 1].finished_reason ===
										ReplyFinishedReason.EXCEED_MAX_ITERS &&
									phase === 'idle' && (
										<Alert
											variant={'default'}
											className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-50"
										>
											<TriangleAlert />
											<AlertTitle>
												{t('chat.maxItersExceeded.title')}
											</AlertTitle>
											<AlertDescription>
												{t('chat.maxItersExceeded.description')}
											</AlertDescription>
											<AlertAction>
												<Button
													size={'xs'}
													onClick={() => {
														onSend([
															{
																id: crypto.randomUUID(),
																type: 'text',
																text: t(
																	'chat.maxItersExceeded.continue',
																),
																created_at:
																	new Date().toISOString(),
																finished_at:
																	new Date().toISOString(),
															} as TextBlock,
														]);
													}}
												>
													{t('chat.maxItersExceeded.continue')}
												</Button>
											</AlertAction>
										</Alert>
									)}
							</MessageScrollerContent>
						</MessageScrollerViewport>
						<MessageScrollerButton className="rounded-full" />
					</MessageScroller>
				</MessageScrollerProvider>
			)}

			{loading ? null : (
				<div className="relative min-w-full max-w-full w-full">
					{replyTarget && (
						<div className="mb-2 flex items-center justify-between rounded-xl bg-muted px-3 py-2 text-sm">
							<span>Trả lời {replyTarget.name}</span>
							<Button variant="ghost" size="icon-xs" aria-label="Hủy trả lời agent" onClick={() => setReplyTarget(null)}><X /></Button>
						</div>
					)}
					<FlipCard
						visible={toConfirmedToolCalls.length > 0 || footerSlot !== null}
						className="mb-2 max-h-[45vh] overflow-y-auto"
					>
						{toConfirmedToolCalls.length > 0 ? (
							<ConfirmCard
								key={`${toConfirmedToolCalls[0].replyId}:${toConfirmedToolCalls[0].toolCall.id}`}
								toolCall={toConfirmedToolCalls[0].toolCall}
								agentId={agentId}
								onUserConfirm={(confirm, rules) =>
									onUserConfirm(
										toConfirmedToolCalls[0].toolCall,
										confirm,
										toConfirmedToolCalls[0].replyId,
										rules,
									)
								}
							/>
						) : (
							footerSlot
						)}
					</FlipCard>
					<TextInput
						className="min-w-full max-w-full w-full rounded-[28px] border border-border bg-background p-1 shadow-[var(--cue-shadow-composer)]"
						toolbarSlot={modelControls}
						onSend={handleSend}
						disabled={disabled}
						autoComplete={autoComplete}
						allowedInputTypes={allowedInputTypes}
						fileProcessor={fileProcessor}
						phase={phase}
						onInterrupt={onInterrupt}
						headerSlot={git && (
							<div className="flex w-full items-center justify-between px-2 py-1 text-sm text-muted-foreground">
								{git && (
									<Button
										className="font-mono"
										variant="secondary"
										size="sm"
										onClick={() => void onRefreshGit?.()}
										title={t('workdir.gitTooltip', {
											staged: git.staged,
											unstaged: git.unstaged,
											untracked: git.untracked,
										})}
									>
										<GitBranch />
										{/* A detached HEAD has no branch to name, so
										    fall back to the commit it sits on. The
										    server sends no git at all when it has
										    neither. */}
										{git.branch ?? git.head?.slice(0, 7)}
										{git.ahead !== null && git.ahead > 0 && (
											<span className="text-xs">↑{git.ahead}</span>
										)}
										{git.behind !== null && git.behind > 0 && (
											<span className="text-xs">↓{git.behind}</span>
										)}
										{/* Renders nothing when both are zero, so a
										    clean tree shows just the branch. */}
										<DiffStats
											className="text-xs font-mono"
											insertions={git.insertions}
											deletions={git.deletions}
										/>
									</Button>
								)}
							</div>
						)}
					/>
				</div>
			)}
			<CaseFileSheet
				sessionId={sessionId}
				agentId={agentId}
				messageId={caseFileMessageId}
				onClose={() => setCaseFileMessageId(null)}
				leaderAgentId={teamChat ? agentId : null}
			/>
		</div>
	);
};

export const ChatContent = React.memo(ChatContentComponent);
