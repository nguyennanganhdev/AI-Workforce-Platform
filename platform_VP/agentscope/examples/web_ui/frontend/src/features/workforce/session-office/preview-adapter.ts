import type { SessionOfficeSnapshot } from './model';
import type { AgentView } from '@/api';

/** Membership only. No invented live work until the backend event adapter is connected. */
export function previewOfficeSnapshot(id: string, agents: AgentView[]): SessionOfficeSnapshot {
	return {
		id: `session:${id}`,
		source: 'preview',
		motion: 'demo',
		phase: 'idle',
		activity: [],
		participants: [...new Map(agents.map((agent) => [agent.id, agent])).values()].map(
			(agent) => ({
				id: agent.id,
				name: agent.data.name,
				role: agent.data.invite_config?.invite_description ?? '',
				status: 'idle',
			}),
		),
	};
}
