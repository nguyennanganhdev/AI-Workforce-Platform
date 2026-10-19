import type { AgentView } from '@/api';

/** An agent as the graph draws it. */
export type GraphAgent = {
	id: string;
	name: string;
	/** One line on what it is for. Empty when the agent has none. */
	role: string;
	/** Whether other agents — the Leader — may bring it into a session. */
	invitable: boolean;
	/** The record behind it. */
	real: AgentView | null;
};

export function toGraphAgents(agents: AgentView[]): { agents: GraphAgent[] } {
	return {
		agents: agents.map((agent) => ({
			id: agent.id,
			name: agent.data.name,
			role: agent.data.invite_config?.invite_description?.trim() ?? '',
			invitable: !!agent.data.invite_config?.invitable,
			real: agent,
		})),
	};
}
