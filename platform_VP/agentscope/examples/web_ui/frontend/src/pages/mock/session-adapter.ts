import type { ContentBlock, Msg } from '@agentscope-ai/agentscope/message';

import { MOCK_AGENTS, type MockAgentId, type MockEvent } from './chat-mock-data.ts';
import type { SessionPresentation } from '@/features/workforce/session/presentation';

/** Same SDK messages as useMessages; stable IDs/timestamps survive tab changes and replay. */
export function mockSessionPresentation(
	id: string,
	participants: MockAgentId[],
	events: MockEvent[],
	busy: boolean,
	typed: Record<string, string> = {},
	paused = false,
): SessionPresentation {
	const current = events.at(-1);
	const messages: Msg[] = events.flatMap((event, index) => {
		if (event.kind === 'gate' || event.kind === 'state') return [];
		const running = (busy || paused) && index === events.length - 1;
		const stamp = new Date(Date.UTC(2026, 0, 1) + index * 10000).toISOString();
		const end = new Date(
			Date.parse(stamp) + (event.kind === 'thinking' ? event.seconds * 1000 : 1000),
		).toISOString();
		const times = { created_at: stamp, finished_at: running ? null : end };
		let content: ContentBlock[];
		if (event.kind === 'thinking')
			content = [{ ...times, id: event.id, type: 'thinking', thinking: event.text }];
		else if (event.kind === 'tool')
			content = [
				{
					...times,
					id: event.id,
					type: 'tool_call',
					name: event.label,
					input: event.input,
					state: running ? 'pending' : 'finished',
				},
				...(!running
					? [
							{
								...times,
								id: event.id,
								type: 'tool_result' as const,
								name: event.label,
								output: `${event.summary}\n${event.result}`,
								state: 'success' as const,
							},
						]
					: []),
			];
		else
			content = [
				{
					...times,
					id: event.id,
					type: 'text',
					text: event.kind === 'user' ? (typed[event.id] ?? event.text) : event.text,
				},
			];
		const agentId = 'agent' in event ? event.agent : undefined;
		const metadata: Msg['metadata'] = {};
		if (agentId) metadata.office_agent_id = agentId;
		return [
			{
				...times,
				id: `${id}:${event.id}`,
				role: event.kind === 'user' ? 'user' : agentId ? 'assistant' : 'system',
				name:
					event.kind === 'user'
						? event.sender
						: agentId
							? MOCK_AGENTS[agentId].name
							: 'Hoạt động phiên',
				metadata,
				content,
			},
		];
	});
	const activeAgentId = busy && current && 'agent' in current ? (current.agent ?? null) : null;
	let phase: SessionPresentation['phase'] =
		current?.kind === 'gate'
			? current.action === 'approval'
				? 'waiting_approval'
				: current.action === 'reply'
					? 'waiting_reply'
					: 'waiting_external'
			: paused
				? 'idle'
				: busy
					? 'working'
					: 'done';
	if (current?.kind === 'state' && !paused) {
		switch (current.state) {
			case 'waiting_external_event':
				phase = 'waiting_external';
				break;
			case 'awaiting_user':
			case 'awaiting_confirmation':
				phase = 'waiting_reply';
				break;
			case 'awaiting_approval':
				phase = 'waiting_approval';
				break;
			case 'needs_attention':
			case 'blocked_authorization':
			case 'blocked_route_changed':
				phase = 'needs_attention';
				break;
			case 'closed':
				phase = 'done';
				break;
			default:
				phase = busy ? 'working' : 'idle';
		}
	}

	return {
		id: `mock:${id}`,
		source: 'mock',
		messages,
		participants: participants.map((id) => ({ id, ...MOCK_AGENTS[id] })),
		activeAgentId,
		phase,
	};
}
