import { EventType } from '@agentscope-ai/agentscope/event';
import type {
	AgentEvent,
	CustomEvent,
	DataBlockStartEvent,
	DataBlockDeltaEvent,
	DataBlockEndEvent,
	ReplyStartEvent,
	UserConfirmResultEvent,
} from '@agentscope-ai/agentscope/event';
import { UserMsg } from '@agentscope-ai/agentscope/message';
import type { Msg, ContentBlock } from '@agentscope-ai/agentscope/message';
import type { ToolCallBlock } from '@agentscope-ai/agentscope/message';
import { useState, useCallback, useRef, useEffect } from 'react';

import { mergeChatEvent } from '../utils/appendChatEvent';
import { sessionApi, takeFreshlyCreated } from '@/api';
import { chatApi } from '@/api';
import { useAudioManager } from '@/context/AudioContext';

/**
 * One pending subagent HITL request, projected from a team *member*
 * session onto its *leader* session so the leader UI can render and
 * resolve it. Mirrors the Python payload written by
 * ``SubagentHitlProjector`` and pushed/replayed as a ``CustomEvent``
 * (``name="subagent_require_user_confirm"``).
 */
export type SubagentHitlEntry = {
	worker_session_id: string;
	worker_agent_id: string;
	worker_agent_name: string;
	reply_id: string;
	event_type: 'require_user_confirm' | 'require_external_execution';
	/** The original ``RequireUserConfirmEvent`` payload (serialized). */
	event: { tool_calls?: ToolCallBlock[] } & Record<string, unknown>;
	created_at: string;
};

/**
 * Return true if ``msg`` is an assistant reply currently parked on a
 * pending tool_call (awaiting user confirmation or an external
 * execution result). Used both to detect the "in-flight reply on page
 * load" case and as the SDK-gap workaround that hides the confirm
 * card once the paired tool_result lands.
 */
const hasPendingToolCall = (msg: Msg | undefined): boolean => {
	if (!msg || msg.role !== 'assistant') return false;
	for (const block of msg.content) {
		if (block.type !== 'tool_call') continue;
		const state = (block as ToolCallBlock).state;
		if (state === 'asking' || state === 'submitted') return true;
	}
	return false;
};

const hitlKey = (e: { worker_session_id: string; reply_id: string }) =>
	`${e.worker_session_id}:${e.reply_id}`;

/**
 * Lifecycle phase of the reply currently owned by this session.
 *
 * - ``idle`` — no in-flight reply; the send button is enabled.
 * - ``streaming`` — a reply is in progress (either actively producing
 *   events or parked awaiting HITL). The send button is replaced by a
 *   Stop button. The parked-vs-generating distinction is not tracked
 *   here; HITL cards render themselves from message content when a
 *   ``RequireUserConfirmEvent`` block is present.
 * - ``interrupting`` — the user has requested a stop and we are
 *   waiting for the backend's terminating ``ReplyEndEvent``. Stop
 *   button is shown but disabled so users cannot spam it. Falls back
 *   to ``idle`` after a 10s safety timeout in case the terminating
 *   event never arrives (dropped SSE frame, backend bug, etc.).
 */
export type ReplyPhase = 'idle' | 'streaming' | 'interrupting';

/** Safety fallback: force phase back to idle if REPLY_END is not seen. */
const INTERRUPT_TIMEOUT_MS = 10_000;

/**
 * Manages messages for a single ``(agentId, sessionId)`` pair.
 *
 * Event delivery has two independent channels:
 *
 * - **History** — ``GET /sessions/{sid}/messages`` fetches persisted
 *   ``Msg`` objects (each a complete reply).
 * - **Live stream** — ``GET /sessions/{sid}/stream`` is a long-lived
 *   SSE connection that pushes ``AgentEvent`` deltas as they are
 *   produced by any chat run on this session (user-triggered,
 *   background retrigger, team member message, …).
 *
 * Interactive views open an SSE connection after fetching history.
 * Read-only observer views poll history instead, so inspecting a team
 * member does not consume another long-lived browser connection.
 *
 * ``phase`` is driven by event content, not HTTP lifecycle: it moves
 * to ``streaming`` on ``ReplyStartEvent`` and back to ``idle`` on
 * ``ReplyEndEvent``. Calling ``interrupt()`` moves it to
 * ``interrupting`` until the terminating ``ReplyEndEvent`` arrives (or
 * a 10s safety timeout fires).
 *
 * @param agentId - The agent whose session to subscribe. ``null`` to
 *   skip.
 * @param sessionId - The session to subscribe. ``null`` to skip.
 * @returns Object with ``msgs``, ``loading``, ``phase``, ``error``,
 *   ``send``, ``onUserConfirm``, and ``abort``. ``loading`` stays true
 *   until the history for the *current* ``(agentId, sessionId)`` has
 *   landed, so ``msgs`` must not be rendered while it is set.
 */

/** Whether the page is in a background tab (always false outside a browser). */
function pageHidden(): boolean {
	return typeof document !== 'undefined' && document.hidden;
}

/** Delay before reconnect attempt number ``failures`` (0 = right after a live stream). */
function reconnectDelay(failures: number): number {
	if (failures === 0) return 1_500;
	const capped = Math.min(30_000, 1_500 * 2 ** failures);
	return capped / 2 + Math.random() * (capped / 2);
}

/** Wait ``ms``, then also until the tab is visible; abort ends the wait. */
function waitToReconnect(ms: number, signal: AbortSignal): Promise<void> {
	return new Promise<void>((resolve) => {
		const finish = () => {
			clearTimeout(timer);
			signal.removeEventListener('abort', finish);
			if (typeof document !== 'undefined') {
				document.removeEventListener('visibilitychange', onVisible);
			}
			resolve();
		};
		const onVisible = () => {
			if (!pageHidden()) finish();
		};
		const timer = setTimeout(() => {
			if (!pageHidden()) finish();
			else document.addEventListener('visibilitychange', onVisible);
		}, ms);
		signal.addEventListener('abort', finish, { once: true });
	});
}

export function useMessages(
	agentId: string | null,
	sessionId: string | null,
	options?: {
		/** Shared team chat keeps its composer available during peer runs. */
		teamChat?: boolean;
		/** Open the live SSE stream. Disable for read-only observer views. */
		stream?: boolean;
		/**
		 * Called when a ``CUSTOM`` event with ``name="team_updated"``
		 * arrives — the team membership has changed (TeamCreate /
		 * AgentCreate / TeamDelete ran). The typical response is to
		 * refetch the session list so the team sidebar updates.
		 */
		onTeamUpdated?: () => void;
		/**
		 * Called when a ``CUSTOM`` event with ``name="state_updated"``
		 * arrives — agent state (tasks / permission) changed during a
		 * tool call. The ``value`` payload contains the latest
		 * ``tasks_context`` and ``permission_context``.
		 */
		onStateUpdated?: (value: Record<string, unknown>) => void;
		/**
		 * Called when a ``CUSTOM`` event with ``name="session_updated"``
		 * arrives — the session record changed server-side, currently
		 * only when auto-naming replaced its placeholder name. Refetch
		 * the session list to pick the new one up.
		 */
		onSessionUpdated?: () => void;
	},
) {
	const stream = options?.stream ?? true;
	const [msgs, setMsgs] = useState<Msg[]>([]);
	// The (agent, session) pair `msgs` actually belongs to. Loading is
	// derived from it rather than set inside the fetch effect: an effect
	// runs *after* the render that changed `sessionId`, so a flag it owns
	// is still `false` for one frame — long enough to paint the empty
	// state over a session that does have messages.
	const [loadedKey, setLoadedKey] = useState<string | null>(null);
	const [phase, setPhase] = useState<ReplyPhase>('idle');
	const [error, setError] = useState<Error | null>(null);
	// Pending subagent HITL cards projected onto this (leader) session.
	const [subagentHitl, setSubagentHitl] = useState<SubagentHitlEntry[]>([]);

	const msgsRef = useRef<Msg[]>([]);
	const currentReplyRef = useRef<Msg | null>(null);
	const runningRepliesRef = useRef(new Set<string>());
	const answeredConfirmationsRef = useRef(new Map<string, UserConfirmResultEvent>());
	const abortRef = useRef<AbortController | null>(null);
	const rafRef = useRef<number | null>(null);
	// Timer that reverts ``interrupting`` back to ``idle`` if the
	// terminating REPLY_END never arrives (dropped SSE frame, etc.).
	const interruptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const clearInterruptTimer = useCallback(() => {
		if (interruptTimerRef.current !== null) {
			clearTimeout(interruptTimerRef.current);
			interruptTimerRef.current = null;
		}
	}, []);

	const audioManager = useAudioManager();

	const optionsRef = useRef(options);
	useEffect(() => {
		optionsRef.current = options;
	}, [options]);
	const scheduleUpdate = useCallback(() => {
		if (rafRef.current !== null) return;
		rafRef.current = requestAnimationFrame(() => {
			rafRef.current = null;
			setMsgs([...msgsRef.current]);
		});
	}, []);

	/** Apply a single AgentEvent to the in-progress reply. */
	const processEvent = useCallback(
		(event: AgentEvent) => {
			// Custom events are service-layer notifications, not agent
			// reply content — route them to callbacks and skip appendEvent.
			if (event.type === EventType.CUSTOM) {
				const custom = event as CustomEvent;
				if (custom.name === 'team_updated') {
					optionsRef.current?.onTeamUpdated?.();
				} else if (custom.name === 'state_updated' && custom.value) {
					optionsRef.current?.onStateUpdated?.(custom.value as Record<string, unknown>);
				} else if (custom.name === 'session_updated') {
					optionsRef.current?.onSessionUpdated?.();
				} else if (custom.name === 'subagent_require_user_confirm') {
					// A team member is asking for confirmation; show (or
					// refresh) its card on this leader view. Dedup by
					// (worker_session_id, reply_id).
					const e = custom.value as unknown as SubagentHitlEntry;
					const tool_calls = (e.event.tool_calls ?? []).filter(
						(tc) => !answeredConfirmationsRef.current.has(`${e.reply_id}:${tc.id}`),
					);
					setSubagentHitl((prev) => [
						...prev.filter((x) => hitlKey(x) !== hitlKey(e)),
						...(tool_calls.length > 0 ? [{ ...e, event: { ...e.event, tool_calls } }] : []),
					]);
				} else if (custom.name === 'subagent_user_confirm_result') {
					// The member resolved (or its run ended); clear the card.
					const v = custom.value as { worker_session_id: string; reply_id: string };
					setSubagentHitl((prev) => prev.filter((x) => hitlKey(x) !== hitlKey(v)));
				}
				return;
			}
			if (event.type === EventType.USER_CONFIRM_RESULT) {
				for (const result of event.confirm_results) {
					answeredConfirmationsRef.current.set(`${event.reply_id}:${result.tool_call.id}`, event);
				}
				setSubagentHitl((prev) => prev.flatMap((entry) => {
					const tool_calls = (entry.event.tool_calls ?? []).filter(
						(tc) => !answeredConfirmationsRef.current.has(`${entry.reply_id}:${tc.id}`),
					);
					return tool_calls.length > 0 ? [{ ...entry, event: { ...entry.event, tool_calls } }] : [];
				}));
			}
			if (event.type === EventType.REQUIRE_USER_CONFIRM) {
				const replyId = event.reply_id;
				event = { ...event, tool_calls: event.tool_calls.filter(
					(tc) => !answeredConfirmationsRef.current.has(`${replyId}:${tc.id}`),
				) };
			}
			if (event.type === EventType.REPLY_START && !msgsRef.current.some((message) => message.id === event.reply_id)) {
				audioManager?.stopAllPlayback();
			}
			msgsRef.current = mergeChatEvent(msgsRef.current, event);
			if (event.type === EventType.REPLY_START) {
				const e = event as ReplyStartEvent;
				// A continuation (the run resuming after a confirmation or an
				// external execution result) re-emits REPLY_START with the
				// *same* reply_id. Re-point at the existing reply instead of
				// appending a second msg under that id: a duplicate would
				// collide on React keys, strand the original bubble in its
				// running state, and hide any still-pending confirmation card
				// — those are read off the tail msg, which would be the empty
				// duplicate.
				currentReplyRef.current = msgsRef.current.find((m) => m.id === e.reply_id) ?? null;
				runningRepliesRef.current.add(e.reply_id);
				clearInterruptTimer();
				setPhase('streaming');
			} else if (event.type === EventType.REPLY_END) {
				runningRepliesRef.current.delete(event.reply_id);
				clearInterruptTimer();
				setPhase(runningRepliesRef.current.size > 0 ? 'streaming' : 'idle');
				currentReplyRef.current = null;
			}

			// Route streaming audio DataBlocks to the audio manager. They still
			// flow through `appendEvent` above (which builds up `source.data`
			// in the Msg), but MessageBubble reads playback state from the
			// manager so it can show progress and autoplay on completion.
			if (audioManager) {
				if (event.type === EventType.DATA_BLOCK_START) {
					const e = event as DataBlockStartEvent;
					if (e.media_type.startsWith('audio/')) {
						audioManager.start(e.block_id, e.media_type);
					}
				} else if (event.type === EventType.DATA_BLOCK_DELTA) {
					const e = event as DataBlockDeltaEvent;
					if (e.media_type.startsWith('audio/')) {
						audioManager.append(e.block_id, e.data);
					}
				} else if (event.type === EventType.DATA_BLOCK_END) {
					const e = event as DataBlockEndEvent;
					// `end` is a no-op when the block isn't being tracked, so
					// we can call it unconditionally.
					audioManager.end(e.block_id);
				}
			}

			scheduleUpdate();
		},
		[scheduleUpdate, audioManager, clearInterruptTimer],
	);

	// ── Lifecycle: fetch history + open SSE stream ──────────────────
	useEffect(() => {
		setLoadedKey(null);
		msgsRef.current = [];
		currentReplyRef.current = null;
		runningRepliesRef.current.clear();
		answeredConfirmationsRef.current.clear();
		setMsgs([]);
		setError(null);
		clearInterruptTimer();
		setPhase('idle');
		setSubagentHitl([]);
		audioManager?.disposeAll();

		if (!agentId || !sessionId) return;

		const controller = new AbortController();
		abortRef.current = controller;
		let cancelled = false;
		let pollTimer: ReturnType<typeof setTimeout> | null = null;

		(async () => {
			const loadHistory = async (silent = false, reconcile = false) => {
				try {
					const { messages, is_running } = await sessionApi.messages(
						sessionId,
						agentId,
						undefined,
						{ signal: controller.signal, silent },
					);
					if (cancelled) return;
					if (reconcile) {
						const localById = new Map(msgsRef.current.map((message) => [message.id, message]));
						const persistedIds = new Set(messages.map((message) => message.id));
						const newestPersisted = Math.max(
							0,
							...messages.map((message) => new Date(message.created_at).getTime()),
						);
						msgsRef.current = [
							...messages.map((message) => {
								const local = localById.get(message.id);
								return !local || message.finished_at || message.finished_reason
									? message
									: local;
							}),
							...msgsRef.current.filter(
								(message) =>
									!persistedIds.has(message.id) &&
									(runningRepliesRef.current.has(message.id) ||
										new Date(message.created_at).getTime() >= newestPersisted),
							),
						];
						for (const message of messages) {
							if (message.finished_at || message.finished_reason) {
								runningRepliesRef.current.delete(message.id);
							}
						}
					} else {
						msgsRef.current = messages;
					}
					// Polling can return the parked snapshot before an accepted decision runs.
					for (const decision of answeredConfirmationsRef.current.values()) {
						msgsRef.current = mergeChatEvent(msgsRef.current, decision);
					}
					// If a reply is in flight (running on a worker) OR the
					// tail msg is parked on a pending tool_call (awaiting
					// user confirmation / external execution), initialise the
					// phase to ``streaming`` so the interrupt button is
					// available immediately — otherwise a fresh page load
					// while parked leaves the UI stuck on ``idle`` with no
					// way to abort.
					const tail = msgsRef.current[msgsRef.current.length - 1];
					const inProgress = is_running || hasPendingToolCall(tail);
					setPhase(inProgress ? 'streaming' : 'idle');
					if (inProgress) {
						if (hasPendingToolCall(tail)) {
							// Prime the ref so continuation events (which
							// arrive without a fresh REPLY_START) apply to
							// the right msg.
							currentReplyRef.current = tail ?? null;
						}
					}
					setError(null);
					// Published synchronously, not through `scheduleUpdate`:
					// its requestAnimationFrame batching exists for
					// high-frequency streaming deltas, and deferring here
					// would let `loadedKey` below clear `loading` a frame
					// before the messages land — painting the empty-session
					// greeting over a conversation that does have history.
					// Both setters now land in the same React batch.
					setMsgs([...msgsRef.current]);
				} catch (e) {
					if (!cancelled && (e as Error).name !== 'AbortError') setError(e as Error);
				} finally {
					// Marks the load done whether it succeeded or threw —
					// an error surfaces through `error`, and leaving
					// `loading` stuck on would hide it behind a spinner
					// forever.
					if (!cancelled) setLoadedKey(`${agentId}:${sessionId}`);
				}
			};

			// 1. Fetch persisted history — unless this tab just created the
			// session, in which case there is provably none.
			if (takeFreshlyCreated(sessionId)) {
				if (!cancelled) setLoadedKey(`${agentId}:${sessionId}`);
			} else {
				await loadHistory();
			}

			// Observer views poll instead of streaming. Team chat also reconciles
			// periodically so a dropped terminal SSE event cannot leave a stale
			// spinner after every member has already finished.
			if (!stream || optionsRef.current?.teamChat) {
				const poll = async () => {
					// A hidden tab does not need a live transcript.
					if (!pageHidden()) await loadHistory(true, stream);
					if (!cancelled) pollTimer = setTimeout(() => void poll(), 1_500);
				};
				if (!cancelled) pollTimer = setTimeout(() => void poll(), 1_500);
			}
			if (!stream) {
				return;
			}

			// 2. Keep the live stream connected. A reconnect after a live stream
			// first reconciles persisted history, which closes replies whose
			// REPLY_END was missed. While the server is down, retries back off
			// (1.5 s doubling to 30 s, with jitter) and pause in a hidden tab,
			// so every open tab does not hammer a restarting backend.
			let failures = 0;
			while (!cancelled) {
				let received = false;
				try {
					for await (const event of sessionApi.streamEvents(
						sessionId,
						agentId,
						controller.signal,
					)) {
						if (cancelled) break;
						received = true;
						processEvent(event);
					}
				} catch (e) {
					if ((e as Error).name !== 'AbortError' && !cancelled) {
						setError(e as Error);
						// Gone, or no longer ours: retrying cannot help.
						const status = (e as { status?: number }).status;
						if (status === 401 || status === 403 || status === 404) break;
					}
				}
				if (cancelled) break;
				if (received || failures === 0) await loadHistory(true, true);
				failures = received ? 0 : failures + 1;
				await waitToReconnect(reconnectDelay(failures), controller.signal);
			}
		})();

		return () => {
			cancelled = true;
			controller.abort();
			if (pollTimer) clearTimeout(pollTimer);
			abortRef.current = null;
			clearInterruptTimer();
		};
	}, [agentId, sessionId, stream, scheduleUpdate, processEvent, audioManager, clearInterruptTimer]);

	/**
	 * Send a user message. Appends the message to the local list
	 * optimistically, then fires a ``POST /chat/`` trigger. Events
	 * arrive via the already-open SSE connection.
	 *
	 * @param content - The message content blocks.
	 */
	const send = useCallback(
		async (content: ContentBlock[], targetAgentId?: string) => {
			if (!agentId || !sessionId) return;

			const userMsg = UserMsg({ name: 'user', content });
			msgsRef.current = [...msgsRef.current, userMsg];
			scheduleUpdate();

			try {
				const response = await chatApi.trigger({
					agent_id: agentId,
					session_id: sessionId,
					input: userMsg,
					...(targetAgentId && { target_agent_id: targetAgentId }),
				});
				if (response.message) {
					msgsRef.current = [...msgsRef.current, response.message];
					scheduleUpdate();
				}
			} catch (e) {
				setError(e as Error);
			}
		},
		[agentId, sessionId, scheduleUpdate],
	);

	/**
	 * Confirm or deny a tool call (human-in-the-loop). Fires a
	 * ``POST /chat/`` with a ``UserConfirmResultEvent``; events
	 * arrive via SSE.
	 *
	 * @param toolCall - The tool call block to confirm/deny.
	 * @param confirm - Whether the user confirmed.
	 * @param replyId - The reply id the tool call belongs to.
	 * @param rules - Optional permission rules to attach.
	 */
	const onUserConfirm = useCallback(
		async (
			toolCall: ToolCallBlock,
			confirm: boolean,
			replyId: string,
			rules?: ToolCallBlock['suggested_rules'],
		) => {
			if (!agentId || !sessionId) return;
			if (answeredConfirmationsRef.current.has(`${replyId}:${toolCall.id}`)) return;

			// Restore the ref so continuation events (no REPLY_START)
			// have a target.
			currentReplyRef.current = msgsRef.current.find((m) => m.id === replyId) ?? null;

			const event: UserConfirmResultEvent = {
				type: EventType.USER_CONFIRM_RESULT,
				id: crypto.randomUUID(),
				created_at: new Date().toISOString(),
				reply_id: replyId,
				confirm_results: [
					{ confirmed: confirm, tool_call: toolCall, rules: rules ?? null },
				],
			};

			try {
				await chatApi.trigger({
					agent_id: agentId,
					session_id: sessionId,
					input: event,
				});
				// Apply accepted decisions locally before the queued worker resumes.
				processEvent(event);
			} catch (e) {
				setError(e as Error);
				throw e;
			}
		},
		[agentId, sessionId, processEvent],
	);

	/** Abort the current SSE connection. */
	const abort = useCallback(() => {
		abortRef.current?.abort();
	}, []);

	/**
	 * Request interruption of the in-progress reply (running or parked
	 * on HITL). Optimistically moves ``phase`` to ``interrupting`` so
	 * the UI can disable the Stop button; the phase reverts to
	 * ``idle`` when the backend's terminating ``ReplyEndEvent``
	 * arrives via SSE (or after a 10s safety timeout, in case that
	 * event is lost).
	 *
	 * Backend contract:
	 * - 202: interrupt was accepted (cancel signal broadcast for a
	 *   running reply, or wakeup enqueued for a parked one). The
	 *   resulting ``ReplyEndEvent`` arrives through the SSE stream and
	 *   drives the phase transition.
	 * - Idle sessions are a silent no-op at the agent layer, so
	 *   spamming this callback is safe.
	 */
	const interrupt = useCallback(async () => {
		if (!agentId || !sessionId) return;
		// Only escalate to ``interrupting`` if a reply is actually in
		// flight; if we're already idle (SSE completed just before the
		// click) leave the phase alone.
		setPhase((prev) => (prev === 'streaming' ? 'interrupting' : prev));
		clearInterruptTimer();
		interruptTimerRef.current = setTimeout(() => {
			interruptTimerRef.current = null;
			setPhase((prev) => (prev === 'interrupting' ? 'idle' : prev));
		}, INTERRUPT_TIMEOUT_MS);
		try {
			await sessionApi.interrupt(sessionId, agentId);
		} catch (e) {
			clearInterruptTimer();
			setPhase((prev) => (prev === 'interrupting' ? 'idle' : prev));
			setError(e as Error);
		}
	}, [agentId, sessionId, clearInterruptTimer]);

	/**
	 * Confirm or deny a tool call that a *team member* is awaiting,
	 * from this leader view (design §3.6 — backend routing).
	 *
	 * The result is POSTed to the **leader** session (the
	 * ``(agentId, sessionId)`` this hook is bound to), NOT the worker.
	 * The backend resolves ``reply_id`` → worker session via the
	 * leader's pending hash and forwards the event to the worker's
	 * continuation. The client never addresses the worker directly —
	 * ``entry.worker_*`` ids are used only for local dedup / clearing.
	 *
	 * @param entry - The pending subagent HITL entry being resolved.
	 * @param toolCall - The tool call block to confirm/deny.
	 * @param confirm - Whether the user confirmed.
	 * @param rules - Optional permission rules to attach.
	 */
	const onSubagentConfirm = useCallback(
		async (
			entry: SubagentHitlEntry,
			toolCall: ToolCallBlock,
			confirm: boolean,
			rules?: ToolCallBlock['suggested_rules'],
		) => {
			await onUserConfirm(toolCall, confirm, entry.reply_id, rules);
		},
		[onUserConfirm],
	);

	const currentKey = agentId !== null && sessionId !== null ? `${agentId}:${sessionId}` : null;
	const awaitingConsent = msgs.some((message) => message.role === 'assistant' &&
		message.content.some((block) => block.type === 'tool_call' &&
			(block as ToolCallBlock).state === 'asking' &&
			!message.content.some((result) => result.type === 'tool_result' && result.id === block.id))) ||
		subagentHitl.some((entry) => entry.event_type === 'require_user_confirm');
	const ownsConversation = currentKey !== null && loadedKey === currentKey;
	const loading = currentKey !== null && !ownsConversation;

	return {
		msgs: ownsConversation ? msgs : [],
		loading,
		phase: ownsConversation && !awaitingConsent && !options?.teamChat ? phase : ('idle' as ReplyPhase),
		error: ownsConversation ? error : null,
		send,
		onUserConfirm,
		onSubagentConfirm,
		subagentHitl: ownsConversation ? subagentHitl : [],
		abort,
		interrupt,
	};
}
