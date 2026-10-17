import type { AgentEvent } from '@agentscope-ai/agentscope/event';
import { appendEvent, AssistantMsg } from '@agentscope-ai/agentscope/message';
import type { Msg } from '@agentscope-ai/agentscope/message';

/** Reconcile replayed text with persisted history instead of appending it twice. */
export function appendChatEvent(message: Msg, event: AgentEvent): void {
	if ('reply_id' in event && event.reply_id !== message.id) return;
	if ('block_id' in event) {
		const block = message.content.find((item) => item.id === event.block_id);
		if (block?.type === 'text') {
			if (event.type === 'TEXT_BLOCK_START') {
				// An incomplete persisted block is rebuilt by the replay from its start.
				if (!block.finished_at) block.text = '';
				return;
			}
			if (event.type === 'TEXT_BLOCK_DELTA' && block.finished_at) return;
			if (event.type === 'TEXT_BLOCK_END' && 'text' in event && typeof event.text === 'string') {
				block.text = event.text;
			}
		}
	}
	appendEvent(message, event);
}

/** Team streams interleave replies; always update the event's own message. */
export function mergeChatEvent(messages: Msg[], event: AgentEvent): Msg[] {
	if (!('reply_id' in event)) return messages;
	const existing = messages.find((message) => message.id === event.reply_id);
	if (event.type === 'REPLY_START') {
		const metadata = { ...existing?.metadata, ...event.metadata } as Msg['metadata'];
		if (existing) {
			return messages.map((message) => message === existing ? { ...existing, metadata } : message);
		}
		return [...messages, AssistantMsg({
			id: event.reply_id,
			name: event.name,
			content: [],
			created_at: event.created_at,
			metadata,
		})];
	}
	if (!existing) return messages;
	const updated = { ...existing, content: [...existing.content] };
	appendChatEvent(updated, event);
	return messages.map((message) => message === existing ? updated : message);
}
