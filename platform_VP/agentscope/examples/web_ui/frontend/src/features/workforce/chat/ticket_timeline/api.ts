import { applyEvent, applySnapshot, StaleSnapshotError, timelineKey } from './state';
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

export interface TimelineApiOptions {
	baseUrl: string;
	getAccessToken: () => string | null | Promise<string | null>;
	refreshAccessToken?: () => Promise<void>;
	fetchImpl?: typeof fetch;
}

export function createTimelineApi(options: TimelineApiOptions) {
	const request = async <T>(
		path: string,
		method: string,
		body?: unknown,
		signal?: AbortSignal,
	): Promise<T> => {
		const serialized = body === undefined ? undefined : JSON.stringify(body);
		for (let attempt = 0; attempt < 2; attempt++) {
			signal?.throwIfAborted();
			const token = await options.getAccessToken();
			signal?.throwIfAborted();
			const response = await (options.fetchImpl ?? fetch)(
				`${options.baseUrl.replace(/\/$/, '')}${path}`,
				{
					method,
					headers: {
						'Content-Type': 'application/json',
						...(token ? { Authorization: `Bearer ${token}` } : {}),
					},
					body: serialized,
					signal,
					cache: 'no-store',
				},
			);
			if (response.status === 401 && attempt === 0 && options.refreshAccessToken) {
				await options.refreshAccessToken();
				continue;
			}
			if (!response.ok)
				throw new EventStreamHttpError(response.status, 'Không thể cập nhật hộp chat');
			return (await response.json()) as T;
		}
		throw new Error('Không thể làm mới quyền truy cập');
	};

	return {
		post: (body: PartnerRequestEnvelope, signal?: AbortSignal) =>
			request<InboundReceipt>('/requests', 'POST', body, signal),
		readResult: (requestId: string, externalUserId: string, signal?: AbortSignal) =>
			request<InboundReceipt>(
				`/requests/${encodeURIComponent(requestId)}?external_user_id=${encodeURIComponent(externalUserId)}`,
				'GET',
				undefined,
				signal,
			),
		snapshot: (binding: TimelineBinding, signal?: AbortSignal) =>
			request<TimelineSnapshot>(
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
				throw new Error('Giới hạn history không hợp lệ');
			const query = new URLSearchParams({
				external_user_id: binding.externalUserId,
				limit: String(limit),
			});
			if (cursor) query.set('after_cursor', cursor);
			return request<{
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
		close: (
			binding: TimelineBinding,
			body: CloseWorkflowCommand,
			signal?: AbortSignal,
		) => {
			if (
				body.external_user_id !== binding.externalUserId ||
				body.external_conversation_id !== binding.externalConversationId ||
				(body.external_ticket_id ?? null) !== binding.externalTicketId
			)
				throw new Error('Lệnh đóng không thuộc hộp chat');
			return request<InboundReceipt>(
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
	cursorStore: EventCursorStore = new MemoryEventCursorStore(),
	readCurrent?: () => TimelineState,
) {
	let state = initial;
	const ownerKey = timelineKey(initial.binding);
	const scopedStore: EventCursorStore = {
		get: (key) => cursorStore.get(`${ownerKey}:${key}`),
		set: (key, cursor) => cursorStore.set(`${ownerKey}:${key}`, cursor),
		clear: (key) => cursorStore.clear(`${ownerKey}:${key}`),
	};
	const cursorKey = conversationCursorKey(initial.binding.conversationId);
	if (initial.cursor) scopedStore.set(cursorKey, initial.cursor);
	const synchronize = () => {
		if (!readCurrent) return;
		const current = readCurrent();
		if (timelineKey(current.binding) !== ownerKey) throw new Error('Hộp chat đã thay đổi');
		if (current.revision >= state.revision) state = current;
	};
	const publish = (connection: TimelineState['connection']) => {
		synchronize();
		state = { ...state, connection };
		onChange(state);
	};
	const pause = (delay: number) =>
		new Promise<void>((resolve) => {
			if (signal.aborted) return resolve();
			const done = () => {
				clearTimeout(timer);
				signal.removeEventListener('abort', done);
				resolve();
			};
			const timer = setTimeout(done, delay);
			signal.addEventListener('abort', done, { once: true });
		});
	const recover = async () => {
		let delay = 50;
		while (!signal.aborted) {
			const snapshot = await api.snapshot(state.binding, signal);
			if (signal.aborted) return;
			synchronize();
			try {
				state = applySnapshot(state, snapshot);
			} catch (error) {
				if (!(error instanceof StaleSnapshotError)) throw error;
				publish('reconnecting');
				await pause(delay);
				delay = Math.min(1000, delay * 2);
				continue;
			}
			scopedStore.clear(cursorKey);
			if (state.cursor) scopedStore.set(cursorKey, state.cursor);
			onChange(state);
			return;
		}
	};
	if (scopedStore.get(cursorKey) && !state.cursor) await recover();
	while (!signal.aborted) {
		publish(state.sequence === 0 ? 'connecting' : 'reconnecting');
		try {
			for await (const event of streamConversationEvents({
				...api.options,
				url: `${api.options.baseUrl.replace(/\/$/, '')}/conversations/${encodeURIComponent(state.binding.conversationId)}/events?external_user_id=${encodeURIComponent(state.binding.externalUserId)}`,
				conversationId: state.binding.conversationId,
				cursorStore: scopedStore,
				signal,
			})) {
				if (signal.aborted) return;
				synchronize();
				state = applyEvent(state, event);
				onChange(state);
			}
		} catch (error) {
			if (signal.aborted) return;
			if (error instanceof EventCursorExpiredError) {
				await recover();
				continue;
			}
			if (error instanceof EventStreamHttpError && [401, 403].includes(error.status)) {
				scopedStore.clear(cursorKey);
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
			await pause(1000);
		}
	}
}

