import type { Msg } from '@agentscope-ai/agentscope/message';

import {
	cleanName,
	teamHintSource,
	teamMessageText,
} from '../../../components/chat/teamDialogText.ts';
import type { SessionOfficeSnapshot } from '../session-office/model';

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

/**
 * One line said in the room: who said it (a participant id, or `customer`) and
 * what. `invite` is the member a host's `AgentInvite` call named, by id.
 */
type Line = { speaker: string; text: string; invite?: string; kind?: string };

function parseArgs(input: string | undefined): Record<string, unknown> {
	try {
		const parsed: unknown = JSON.parse(input || '{}');
		return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)
			? (parsed as Record<string, unknown>)
			: {};
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
		const found = session.participants.filter((p) =>
			prefix ? p.id.startsWith(prefix) : cleanName(p.name) === cleanName(handle),
		);
		// A name two members share points at neither.
		return found.length === 1 ? found[0].id : null;
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
				if (speaker)
					lines.push({
						speaker,
						text: teamMessageText(block.hint),
						kind:
							team?.kind ?? /<team-message[^>]*kind="([^"]+)"/.exec(block.hint)?.[1],
					});
			} else if (block.type === 'tool_call') {
				const args = parseArgs(block.input);
				if (block.name === 'AgentInvite') {
					lines.push({
						speaker: host,
						text: `Giao việc cho ${cleanName(String(args.target ?? ''))}: ${String(args.prompt ?? '')}`,
						invite: byHandle(String(args.target ?? '')) ?? undefined,
					});
				} else if (block.name === 'TeamSay') {
					const to = cleanName(String(args.to ?? '')) || 'Cả phòng';
					const assigned =
						args.kind === 'handoff' ||
						args.kind === 'assign' ||
						(args.kind === 'review' && args.decision === 'challenge');
					lines.push({
						speaker: host,
						text: `${to}: ${String(args.content ?? '')}`,
						invite: assigned
							? (byHandle(String(args.to ?? '')) ?? undefined)
							: undefined,
					});
				} else if (block.name === 'CaseSay' || block.name === 'CaseFinalize') {
					lines.push({
						speaker: host,
						text: `Gửi cư dân: ${String(args.text ?? args.answer ?? '')}`,
					});
				}
			}
		}
	}
	return lines;
}

/**
 * Who the host called onto the current request and who has reported back, read
 * from structured events only: the host's `AgentInvite` calls and the members'
 * team messages to it, since the customer's last message.
 */
function currentTurn(lines: Line[], host: string | null) {
	const called = new Set<string>();
	const reported = new Set<string>();
	for (const line of lines) {
		if (line.invite && line.invite !== host) {
			called.add(line.invite);
			reported.delete(line.invite);
		}
		if (called.has(line.speaker) && (line.kind === 'result' || line.kind === 'error'))
			reported.add(line.speaker);
	}
	return { called: [...called], reported: [...reported] };
}

export function officeFromSession(session: SessionPresentation): SessionOfficeSnapshot {
	const messages = uniqueMessages(session.messages);
	const lines = roomLines(session, messages);
	const last = lines.at(-1);
	const names = new Map(session.participants.map((p) => [p.id, cleanName(p.name)]));
	const requestIndex = messages.findLastIndex((message) => message.role === 'user');
	const turn = messages[requestIndex]?.id ?? '';
	const { called, reported } = currentTurn(
		roomLines(session, messages.slice(requestIndex + 1)),
		session.hostId,
	);
	const working = session.phase === 'working';
	return {
		id: session.id,
		source: session.source,
		motion: 'events',
		participants: session.participants.map((participant) => ({
			...participant,
			// The active agent works, and so does every called member until it reports.
			status:
				working &&
				(session.activeAgentId === participant.id ||
					(called.includes(participant.id) && !reported.includes(participant.id)))
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
		turn,
		called,
		// A member's `TeamSay` to another member reaches only that member's session,
		// not the host's stream read here, so live sessions show no exchanges yet.
		exchanges: [],
		hostId: session.hostId,
		activity: lines
			.map((line, index) => ({
				id: String(index),
				text: `${line.speaker === 'customer' ? 'Cư dân' : (names.get(line.speaker) ?? '')}: ${line.text}`.slice(
					0,
					140,
				),
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
