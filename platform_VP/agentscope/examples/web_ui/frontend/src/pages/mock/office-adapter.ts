import { MOCK_AGENTS, type MockAgentId, type MockEvent } from './chat-mock-data';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';

/** The only mock-specific translation; the office never reads script events directly. */
export function mockOfficeSnapshot(
	id: string,
	participants: MockAgentId[],
	events: MockEvent[],
	busy: boolean,
): SessionOfficeSnapshot {
	const current = events.at(-1);
	const speaking = current && 'agent' in current ? current.agent : undefined;
	return {
		id: `mock:${id}`,
		source: 'mock',
		motion: 'demo',
		participants: participants.map((id) => ({
			id,
			...MOCK_AGENTS[id],
			status: busy && speaking === id ? 'working' : 'idle',
			message:
				speaking === id && current?.kind === 'agent'
					? current.text.slice(0, 160)
					: undefined,
		})),
		phase:
			current?.kind === 'gate'
				? current.action === 'approval'
					? 'approval'
					: 'idle'
				: busy
					? 'work'
					: 'done',
		activity: events
			.flatMap((event) => {
				if (event.kind === 'agent' || event.kind === 'user' || event.kind === 'step')
					return [{ id: event.id, text: event.text.slice(0, 140) }];
				return [];
			})
			.slice(-6),
	};
}
