import type { Msg } from '@agentscope-ai/agentscope/message';

import type { SessionOfficeSnapshot } from '../session-office/model';

/** Same read model for replay and API/SSE. No transport, timers, or rendering here. */
export interface SessionPresentation {
	id: string;
	source: 'mock' | 'live';
	messages: Msg[];
	participants: { id: string; name: string; role: string }[];
	activeAgentId: string | null;
	phase:
		| 'idle'
		| 'working'
		| 'waiting_reply'
		| 'waiting_approval'
		| 'waiting_external'
		| 'done'
		| 'needs_attention';
}

/** History replay/reconnect replaces messages by ID, rather than replaying animations. */
export function uniqueMessages(messages: Msg[]): Msg[] {
	return [...new Map(messages.map((message) => [message.id, message])).values()];
}

export function officeFromSession(session: SessionPresentation): SessionOfficeSnapshot {
	const messages = uniqueMessages(session.messages);
	const latest = messages.at(-1);
	const text = (message: Msg) =>
		message.content
			.filter((block) => block.type === 'text')
			.map((block) => block.text)
			.join('\n');
	return {
		id: session.id,
		source: session.source,
		motion: 'events',
		participants: session.participants.map((participant) => ({
			...participant,
			status:
				session.phase === 'working' && session.activeAgentId === participant.id
					? 'working'
					: 'idle',
			// Speaker identity must be explicit; never match agents by a non-unique display name.
			message:
				latest?.role === 'assistant' && latest.metadata.office_agent_id === participant.id
					? text(latest).slice(0, 160) || undefined
					: undefined,
		})),
		phase:
			session.phase === 'working'
				? 'work'
				: session.phase === 'waiting_approval'
					? 'approval'
					: session.phase === 'done'
						? 'done'
						: 'idle',
		activity: messages
			.flatMap((message) => {
				const content = text(message);
				return content ? [{ id: message.id, text: content.slice(0, 140) }] : [];
			})
			.slice(-6),
		statusLabel: {
			idle: 'Sẵn sàng',
			working: 'Đang xử lý',
			waiting_reply: 'Chờ trả lời',
			waiting_approval: 'Chờ phê duyệt',
			waiting_external: 'Chờ kết quả bên ngoài',
			done: 'Hoàn thành lượt',
			needs_attention: 'Cần xử lý',
		}[session.phase],
	};
}
