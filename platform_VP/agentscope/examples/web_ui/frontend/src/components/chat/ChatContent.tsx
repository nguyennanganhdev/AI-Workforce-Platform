import { ReplyFinishedReason } from '@agentscope-ai/agentscope/event';
import {
	type ContentBlock,
	getContentBlocks,
	type Msg,
	type TextBlock,
	type ToolCallBlock,
} from '@agentscope-ai/agentscope/message';
import { TriangleAlert, X } from 'lucide-react';
import React, { useContext, useEffect, useMemo, useState } from 'react';

import { visibleTeamMessages } from './team-presentation';
import { Button } from '../ui/button';
import { ASMessageBubble } from '@/components/chat/ASMessageBubble.tsx';
import { ChoiceCard } from '@/components/chat/ChoiceCard';
import { ConfirmCard } from '@/components/chat/ConfirmCard.tsx';
import { FlipCard } from '@/components/chat/FlipCard.tsx';
import { TicketViewContext } from '@/components/chat/team-roster';
import { type MentionOption, TextInput } from '@/components/chat/TextInput.tsx';
import { WorkingDirectoryDialog } from '@/components/dialog/WorkingDirectoryDialog';
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert.tsx';
import { Bubble, BubbleContent } from '@/components/ui/bubble';
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
import { useCurrentUser } from '@/context/CurrentUserContext';
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
	composerPlaceholder?: string;
	showWorkspace?: boolean;
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
	onSend: (content: ContentBlock[], targetAgentId?: string) => void;
	teamChat?: boolean;
	onUserConfirm: (
		toolCall: ToolCallBlock,
		confirm: boolean,
		replyId: string,
		rules?: ToolCallBlock['suggested_rules'],
	) => Promise<void>;
	autoComplete?: (input: string) => string | null;
	/** @see TextInputProps.mentions */
	mentions?: MentionOption[];
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
	/** @see TextInputProps.allowedInputTypes */
	allowedInputTypes: string[];
	/** @see TextInputProps.fileProcessor */
	fileProcessor: (file: File) => Promise<ContentBlock | null>;
	/** Agent owning the open session — drives the directory picker. */
	agentId: string | null;
	/** The open session, whose working directory the picker edits. */
	sessionId: string | null;
	/** Current working directory, relative to the workspace root. */
	cwd: string | null;
	/** Persists a new working directory. */
	onCwdChange: (cwd: string | null) => void | Promise<void>;
	/** Who is on the other end: names the composer and the empty state. */
	agentName?: string;
}

const ChatContentComponent: React.FC<ChatContentProps> = ({
	msgs,
	composerPlaceholder,
	showWorkspace = true,
	loading = false,
	phase,
	disabled,
	onSend,
	teamChat = false,
	onUserConfirm,
	autoComplete,
	mentions,
	className,
	onInterrupt,
	footerSlot,
	allowedInputTypes,
	fileProcessor,
	agentId,
	sessionId,
	cwd,
	onCwdChange,
	agentName,
}) => {
	const { t, i18n } = useTranslation();
	const visibleMessages = useMemo(
		() => visibleTeamMessages(msgs, agentId, teamChat),
		[msgs, agentId, teamChat],
	);
	const lastVisibleAssistant = [...visibleMessages]
		.reverse()
		.find(
			({ message, teamMode }) => message.role === 'assistant' && teamMode !== 'activity',
		)?.message;
	const [replyTarget, setReplyTarget] = useState<{ agentId: string; name: string } | null>(null);
	useEffect(() => setReplyTarget(null), [sessionId]);
	const handleSend = (content: ContentBlock[]) => {
		onSend(content, replyTarget?.agentId);
		setReplyTarget(null);
	};
	const ticketView = useContext(TicketViewContext);
	// Only a session that finished loading with nothing in it is empty.
	// Treating "no messages yet" as empty would flash the greeting over
	// every session that does have history.
	const isEmpty = !loading && msgs.length === 0;
	const user = useCurrentUser();
	const onboardingOptions = t('chat.onboarding.options', { returnObjects: true }) as string[];
	const sendText = (text: string) => {
		const now = new Date().toISOString();
		onSend([
			{
				id: crypto.randomUUID(),
				type: 'text',
				text,
				created_at: now,
				finished_at: now,
			} as TextBlock,
		]);
	};

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

		return msgs
			.filter((message) => message.role === 'assistant')
			.flatMap((message) => {
				const resolved = new Set(
					getContentBlocks(message, 'tool_result').map((result) => result.id),
				);
				return getContentBlocks(message, 'tool_call')
					.filter((tc) => tc.state === 'asking' && !resolved.has(tc.id))
					.map((tc) => ({ replyId: message.id, toolCall: tc }));
			});
	}, [msgs]);
	const cardVisible = toConfirmedToolCalls.length > 0 || footerSlot != null;

	// Left-aligned with a 16px gutter, Cue-style: no centred reading column.
	// The composer always sits at the foot, empty session or not.
	return (
		<div className={cn('flex h-full w-full flex-col gap-3', className)}>
			{loading ? (
				<div className="flex flex-1 w-full items-center justify-center">
					{showSpinner ? <Spinner className="size-5 text-muted-foreground" /> : null}
				</div>
			) : isEmpty && ticketView ? (
				<div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted-foreground">
					Session này chưa nhận ticket nào.
				</div>
			) : isEmpty ? (
				// Cue's onboarding: the agent speaks first — a personal greeting,
				// then a few things it can do as a choice card. Picking one sends
				// it as the person's first message; typing works just as well.
				<div className="flex min-h-0 flex-1 flex-col items-start gap-6 overflow-y-auto px-4 pt-2 pb-4">
					<Bubble variant="agent">
						<BubbleContent>
							{user?.username
								? t('chat.onboarding.greeting', { name: user.username })
								: t('chat.onboarding.greetingNoName')}
						</BubbleContent>
					</Bubble>
					<ChoiceCard
						question={t('chat.onboarding.question')}
						options={onboardingOptions}
						hint={t('chat.onboarding.hint')}
						continueLabel={t('chat.onboarding.continue')}
						disabled={disabled}
						onSubmit={(index) => sendText(onboardingOptions[index])}
					/>
				</div>
			) : (
				<MessageScrollerProvider autoScroll={true} defaultScrollPosition={'end'}>
					<MessageScroller>
						<MessageScrollerViewport>
							<MessageScrollerContent className="px-4 pt-2 pb-4">
								{visibleMessages.map(({ message, teamMode }, index) => {
									const previous = visibleMessages[index - 1]?.message;
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
												teamChatMode={teamMode}
												onReplyTo={
													teamMode === 'customer-reply'
														? (targetAgentId, name) =>
																setReplyTarget({
																	agentId: targetAgentId,
																	name,
																})
														: undefined
												}
												onUserConfirm={onUserConfirm}
											/>
										</MessageScrollerItem>
									);
								})}
								{lastVisibleAssistant &&
									lastVisibleAssistant.finished_reason ===
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
				<div className="relative w-full px-4 pb-4">
					{/* In flow, not overlaid: the transcript shrinks to make room, so the
					    card never hides the message it answers. */}
					{replyTarget && (
						<div className="mb-2 flex items-center justify-between rounded-xl bg-muted px-3 py-2 text-sm">
							<span>Trả lời {replyTarget.name}</span>
							<Button
								variant="ghost"
								size="icon-xs"
								aria-label="Hủy trả lời agent"
								onClick={() => setReplyTarget(null)}
							>
								<X />
							</Button>
						</div>
					)}
					<FlipCard
						visible={cardVisible}
						className={cn(cardVisible && 'mb-2 max-h-[50vh] overflow-y-auto')}
					>
						{toConfirmedToolCalls.length > 0 ? (
							<ConfirmCard
								key={`${toConfirmedToolCalls[0].replyId}:${toConfirmedToolCalls[0].toolCall.id}`}
								toolCall={toConfirmedToolCalls[0].toolCall}
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
						className="w-full"
						placeholder={
							composerPlaceholder ??
							(agentName
								? t('chat.messagePlaceholder', { name: agentName })
								: undefined)
						}
						onSend={handleSend}
						disabled={disabled}
						autoComplete={autoComplete}
						mentions={mentions}
						allowedInputTypes={allowedInputTypes}
						fileProcessor={fileProcessor}
						phase={phase}
						onInterrupt={onInterrupt}
						headerSlot={
							<div className="flex w-full items-center justify-between pb-1.5 text-[13px] text-muted-foreground">
								{showWorkspace && (
									<WorkingDirectoryDialog
										agentId={agentId}
										sessionId={sessionId}
										value={cwd}
										onChange={onCwdChange}
									/>
								)}
							</div>
						}
					/>
				</div>
			)}
		</div>
	);
};

export const ChatContent = React.memo(ChatContentComponent);
