import type { EventCursorStore } from './cursor';
import { conversationCursorKey } from './cursor';
import type { ConversationEvent } from '../contracts/workforce-v1';

interface ParsedSseEvent {
	id: string | null;
	event: string | null;
	data: string;
	retryMs: number | null;
}

export interface WorkforceEventStreamOptions {
	url: string;
	conversationId: string;
	getAccessToken: () => string | null | Promise<string | null>;
	refreshAccessToken?: () => Promise<void>;
	cursorStore: EventCursorStore;
	fetchImpl?: typeof fetch;
	signal?: AbortSignal;
	initialRetryMs?: number;
	maxRetryMs?: number;
}

export class EventCursorExpiredError extends Error {
	constructor() {
		super('The event cursor expired; fetch a snapshot before reconnecting.');
		this.name = 'EventCursorExpiredError';
	}
}

export class EventStreamHttpError extends Error {
	readonly status: number;

	constructor(
		status: number,
		message: string,
	) {
		super(message);
		this.name = 'EventStreamHttpError';
		this.status = status;
	}
}

const sleep = async (delayMs: number, signal?: AbortSignal): Promise<void> => {
	if (signal?.aborted) throw signal.reason;
	await new Promise<void>((resolve, reject) => {
		const finish = (): void => {
			signal?.removeEventListener('abort', abort);
			resolve();
		};
		const timer = window.setTimeout(finish, delayMs);
		const abort = (): void => {
			window.clearTimeout(timer);
			reject(signal?.reason);
		};
		signal?.addEventListener('abort', abort, { once: true });
	});
};

const parseBlock = (block: string): ParsedSseEvent | null => {
	let id: string | null = null;
	let event: string | null = null;
	let retryMs: number | null = null;
	const data: string[] = [];

	for (const rawLine of block.split('\n')) {
		const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
		if (line.startsWith(':')) continue;
		const separator = line.indexOf(':');
		const field = separator < 0 ? line : line.slice(0, separator);
		let value = separator < 0 ? '' : line.slice(separator + 1);
		if (value.startsWith(' ')) value = value.slice(1);

		if (field === 'id' && !value.includes('\0')) id = value;
		else if (field === 'event') event = value;
		else if (field === 'data') data.push(value);
		else if (field === 'retry' && /^\d+$/.test(value)) retryMs = Number(value);
	}

	if (data.length === 0) return null;
	return { id, event, data: data.join('\n'), retryMs };
};

async function* decodeSse(body: ReadableStream<Uint8Array>): AsyncGenerator<ParsedSseEvent> {
	const reader = body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	try {
		while (true) {
			const { done, value } = await reader.read();
			buffer += decoder.decode(value, { stream: !done }).replaceAll('\r\n', '\n');
			let boundary = buffer.indexOf('\n\n');
			while (boundary >= 0) {
				const parsed = parseBlock(buffer.slice(0, boundary));
				buffer = buffer.slice(boundary + 2);
				if (parsed !== null) yield parsed;
				boundary = buffer.indexOf('\n\n');
			}
			if (done) break;
		}
		if (buffer.length > 0) {
			const parsed = parseBlock(buffer);
			if (parsed !== null) yield parsed;
		}
	} finally {
		reader.releaseLock();
	}
}

const validateEvent = (value: unknown, conversationId: string): ConversationEvent => {
	if (typeof value !== 'object' || value === null) throw new Error('Invalid SSE event data');
	const candidate = value as Partial<ConversationEvent>;
	if (typeof candidate.event_id !== 'string' || candidate.event_id.length === 0) {
		throw new Error('SSE event is missing event_id');
	}
	if (candidate.conversation_id !== conversationId) {
		throw new Error('SSE event belongs to another conversation');
	}
	return candidate as ConversationEvent;
};

export async function* streamConversationEvents(
	options: WorkforceEventStreamOptions,
): AsyncGenerator<ConversationEvent> {
	const fetchImpl = options.fetchImpl ?? fetch;
	const cursorKey = conversationCursorKey(options.conversationId);
	let retryMs = options.initialRetryMs ?? 1_000;
	const maxRetryMs = options.maxRetryMs ?? 15_000;
	let refreshed = false;

	while (!options.signal?.aborted) {
		const cursor = options.cursorStore.get(cursorKey);
		const token = await options.getAccessToken();
		const headers = new Headers({ Accept: 'text/event-stream' });
		if (token !== null) headers.set('Authorization', `Bearer ${token}`);
		if (cursor !== null) headers.set('Last-Event-ID', cursor);

		const response = await fetchImpl(options.url, {
			method: 'GET',
			headers,
			signal: options.signal,
			cache: 'no-store',
		});
		if (response.status === 401 && options.refreshAccessToken !== undefined && !refreshed) {
			refreshed = true;
			await options.refreshAccessToken();
			continue;
		}
		if (response.status === 410) throw new EventCursorExpiredError();
		if (!response.ok || response.body === null) {
			throw new EventStreamHttpError(response.status, `SSE connection failed: ${response.status}`);
		}
		refreshed = false;

		for await (const frame of decodeSse(response.body)) {
			if (frame.retryMs !== null) retryMs = Math.min(frame.retryMs, maxRetryMs);
			const event = validateEvent(JSON.parse(frame.data) as unknown, options.conversationId);
			if (frame.id !== null && frame.id !== event.event_id) {
				throw new Error('SSE id does not match payload event_id');
			}
			if (frame.event !== null && frame.event !== event.event_type) {
				throw new Error('SSE event type does not match payload event_type');
			}
			if (options.cursorStore.get(cursorKey) === event.event_id) continue;
			yield event;
			// The generator resumes only after the caller requests the next item,
			// which is the transport-level acknowledgement that processing of
			// this event completed. A consumer that stops early will replay it.
			options.cursorStore.set(cursorKey, event.event_id);
		}

		await sleep(retryMs, options.signal);
		retryMs = Math.min(retryMs * 2, maxRetryMs);
	}
}
