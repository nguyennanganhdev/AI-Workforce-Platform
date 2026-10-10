import { applyEvent, applySnapshot, timelineKey } from './state';
import type { TimelineBinding, TimelineSnapshot, TimelineState } from './state';
import type {
	CloseWorkflowCommand,
	ConversationEvent,
	InboundReceipt,
	PartnerRequestEnvelope,
} from '../../shared/contracts/workforce-v1';
import {
	EventCursorExpiredError,
	EventStreamHttpError,
	MemoryEventCursorStore,
	conversationCursorKey,
	streamConversationEvents,
} from '../../shared/event_transport';
import type { EventCursorStore } from '../../shared/event_transport';

interface TimelineApiOptions {
	// Browser callers supply a manager JWT/BFF token, never a machine API key.
	baseUrl: string;
	getAccessToken: () => string | null | Promise<string | null>;
	refreshAccessToken?: () => Promise<void>;
	fetchImpl?: typeof fetch;
}

export function createTimelineApi(options: TimelineApiOptions) {
	const send = async <T>(
		path: string,
		method: string,
		body?: unknown,
		signal?: AbortSignal,
	): Promise<T> => {
		const token = await options.getAccessToken();
		const response = await (options.fetchImpl ?? fetch)(
			`${options.baseUrl.replace(/\/$/, '')}${path}`,
			{
				method,
				headers: {
					'Content-Type': 'application/json',
					...(token ? { Authorization: `Bearer ${token}` } : {}),
				},
				body: body === undefined ? undefined : JSON.stringify(body),
				signal,
				cache: 'no-store',
			},
		);
		if (!response.ok)
			throw new EventStreamHttpError(response.status, 'Không thể cập nhật hộp chat');
		return (await response.json()) as T;
	};
	return {
		post: (body: PartnerRequestEnvelope, signal?: AbortSignal) =>
			send<InboundReceipt>('/requests', 'POST', body, signal),
		readResult: (id: string, externalUserId: string, signal?: AbortSignal) =>
			send<InboundReceipt>(
				`/requests/${encodeURIComponent(id)}?external_user_id=${encodeURIComponent(externalUserId)}`,
				'GET',
				undefined,
				signal,
			),
		snapshot: (binding: TimelineBinding, signal?: AbortSignal) =>
			send<TimelineSnapshot>(
				`/conversations/${encodeURIComponent(binding.conversationId)}?external_user_id=${encodeURIComponent(binding.externalUserId)}`,
				'GET',
				undefined,
				signal,
			),
		history: (
			binding: TimelineBinding,
			cursor: string | null,
			limit = 100,
			signal?: AbortSignal,
		) => {
			if (!Number.isInteger(limit) || limit < 1 || limit > 500)
				throw new Error('Giới hạn lịch sử không hợp lệ');
			const query = new URLSearchParams({
				external_user_id: binding.externalUserId,
				limit: String(limit),
			});
			if (cursor) query.set('after_cursor', cursor);
			return send<{
				items: ConversationEvent[];
				next_cursor: string | null;
				has_more: boolean;
			}>(
				`/conversations/${encodeURIComponent(binding.conversationId)}/event-history?${query}`,
				'GET',
				undefined,
				signal,
			);
		},
		close: (binding: TimelineBinding, body: CloseWorkflowCommand, signal?: AbortSignal) => {
			if (
				body.external_user_id !== binding.externalUserId ||
				body.external_conversation_id !== binding.externalConversationId ||
				(body.external_ticket_id ?? null) !== binding.externalTicketId
			)
				throw new Error('Lệnh đóng sai hộp chat');
			return send<InboundReceipt>(
				`/workflows/${encodeURIComponent(binding.workflowId)}/close`,
				'POST',
				body,
				signal,
			);
		},
		options,
	};
}

export async function followTimeline(
	api: ReturnType<typeof createTimelineApi>,
	initial: TimelineState,
	onChange: (state: TimelineState) => void,
	signal: AbortSignal,
	store: EventCursorStore = new MemoryEventCursorStore(),
) {
	let state = initial;
	const key = timelineKey(initial.binding);
	const cursors: EventCursorStore = {
		get: (k) => store.get(`${key}:${k}`),
		set: (k, v) => store.set(`${key}:${k}`, v),
		clear: (k) => store.clear(`${key}:${k}`),
	};
	const cursorKey = conversationCursorKey(state.binding.conversationId);
	if (state.cursor) cursors.set(cursorKey, state.cursor);
	const publish = (connection: TimelineState['connection']) => {
		state = { ...state, connection };
		onChange(state);
	};
	async function recover() {
		const snapshot = await api.snapshot(state.binding, signal);
		if (signal.aborted) return;
		state = applySnapshot(state, snapshot);
		cursors.clear(cursorKey);
		if (state.cursor) cursors.set(cursorKey, state.cursor);
		onChange(state);
	}
	if (cursors.get(cursorKey) && !state.cursor) await recover();
	let connections = 0;
	while (!signal.aborted) {
		publish(state.sequence === 0 ? 'connecting' : 'reconnecting');
		try {
			for await (const event of streamConversationEvents({
				...api.options,
				url: `${api.options.baseUrl.replace(/\/$/, '')}/conversations/${encodeURIComponent(state.binding.conversationId)}/events?external_user_id=${encodeURIComponent(state.binding.externalUserId)}`,
				conversationId: state.binding.conversationId,
				cursorStore: cursors,
				signal,
				fetchImpl: async (input, init) => {
					if (connections++ > 0) publish('reconnecting');
					const response = await (api.options.fetchImpl ?? fetch)(input, init);
					if (response.ok && !signal.aborted) publish('live');
					return response;
				},
			})) {
				if (signal.aborted) return;
				state = applyEvent(state, event);
				onChange(state);
			}
		} catch (error) {
			if (signal.aborted) return;
			if (error instanceof EventCursorExpiredError) {
				try {
					await recover();
				} catch (recoveryError) {
					if (!signal.aborted) publish('blocked');
					throw recoveryError;
				}
				continue;
			}
			if (error instanceof EventStreamHttpError && [401, 403].includes(error.status)) {
				cursors.clear(cursorKey);
				publish('blocked');
				throw error;
			}
			if (
				!(error instanceof TypeError) &&
				!(error instanceof EventStreamHttpError && error.status >= 500)
			) {
				publish('blocked');
				throw error;
			}
			publish('reconnecting');
			await new Promise<void>((resolve) => {
				const done = () => {
					clearTimeout(timer);
					signal.removeEventListener('abort', done);
					resolve();
				};
				const timer = setTimeout(done, 1000);
				signal.addEventListener('abort', done, { once: true });
			});
		}
	}
}
