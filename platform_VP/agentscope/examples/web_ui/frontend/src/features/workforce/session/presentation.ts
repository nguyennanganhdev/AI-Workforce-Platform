import type { Msg } from '@agentscope-ai/agentscope/message';

import type { SessionOfficeSnapshot } from '../session-office/model';
import { cleanName, teamHintSource, teamMessageText } from '@/components/chat/teamDialogText';

/** Same read model for replay and API/SSE. No transport, timers, or rendering here. */
export interface SessionPresentation {
	id: string;
	source: 'mock' | 'live';
	messages: Msg[];
	participants: { id: string; name: string; role: string }[];
	activeAgentId: string | null;
	/** The session's owner, who leads its room. */
	hostId: string | null;
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

/** One line said in the room: who said it (a participant id, or `customer`) and what. */
type Line = { speaker: string; text: string };

function parseArgs(input: string | undefined): Record<string, unknown> {
	try {
		return JSON.parse(input || '{}') as Record<string, unknown>;
	} catch {
		return {};
	}
}

/**
 * The room's conversation, read from the host's session: what the host said or
 * assigned, and what each member reported back. A team hint names its sender
 * as `Name@<id prefix>`, so the speaker is matched by id, not by display name.
 */
function roomLines(session: SessionPresentation, messages: Msg[]): Line[] {
	const host = session.hostId;
	const byHandle = (handle: string) => {
		const prefix = handle.split('@')[1];
		const found = session.participants.find((p) =>
			prefix ? p.id.startsWith(prefix) : cleanName(p.name) === cleanName(handle),
		);
		return found?.id ?? null;
	};
	const lines: Line[] = [];
	for (const message of messages) {
		for (const block of message.content) {
			if (message.role === 'user') {
				if (block.type !== 'text') continue;
				const ticket = message.metadata?.ticket as { request?: string } | undefined;
				lines.push({ speaker: 'customer', text: ticket?.request || block.text });
			} else if (message.role !== 'assistant' || !host) {
				continue;
			} else if (block.type === 'text' && block.text.trim()) {
				lines.push({ speaker: host, text: block.text });
			} else if (block.type === 'hint' && typeof block.hint === 'string') {
				const team = teamHintSource(block.source);
				const speaker = team && byHandle(team.sender);
				if (speaker) lines.push({ speaker, text: teamMessageText(block.hint) });
			} else if (block.type === 'tool_call') {
				const args = parseArgs(block.input);
				if (block.name === 'AgentInvite') {
					lines.push({
						speaker: host,
						text: `Giao việc cho ${cleanName(String(args.target ?? ''))}: ${String(args.prompt ?? '')}`,
					});
				} else if (block.name === 'TeamSay') {
					const to = cleanName(String(args.to ?? '')) || 'Cả phòng';
					lines.push({ speaker: host, text: `${to}: ${String(args.content ?? '')}` });
				} else if (block.name === 'CaseSay' || block.name === 'CaseFinalize') {
					lines.push({ speaker: host, text: `Gửi cư dân: ${String(args.text ?? args.answer ?? '')}` });
				}
			}
		}
	}
	return lines;
}

export function officeFromSession(session: SessionPresentation): SessionOfficeSnapshot {
	const messages = uniqueMessages(session.messages);
	const lines = roomLines(session, messages);
	const last = lines.at(-1);
	const names = new Map(session.participants.map((p) => [p.id, cleanName(p.name)]));
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
			// Only the last speaker talks: a room full of bubbles reads as noise.
			message: last && last.speaker === participant.id ? last.text.slice(0, 160) : undefined,
		})),
		phase:
			session.phase === 'working'
				? 'work'
				: session.phase === 'waiting_approval'
					? 'approval'
					: session.phase === 'done'
						? 'done'
						: 'idle',
		// While the room works its agents meet; a lone agent has nobody to meet.
		meeting: session.phase === 'working' && session.participants.length > 1,
		hostId: session.hostId,
		activity: lines
			.map((line, index) => ({
				id: String(index),
				text: `${line.speaker === 'customer' ? 'Cư dân' : (names.get(line.speaker) ?? '')}: ${line.text}`.slice(0, 140),
			}))
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
