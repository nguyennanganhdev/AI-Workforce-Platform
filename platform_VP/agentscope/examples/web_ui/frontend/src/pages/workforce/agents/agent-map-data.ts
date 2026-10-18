import type { AgentActivity, AgentSummary, ModelObservability } from '@/api';
import type { MapAgent } from '@/pages/agents/AgentMap3D';

export const STATUS = {
	draft: { label: 'Bản nháp', variant: 'secondary' },
	published: { label: 'Đang phát hành', variant: 'default' },
	withdrawn: { label: 'Đã ngừng', variant: 'outline' },
} as const;

export const usd = (value: number | null | undefined) =>
	value == null ? '–' : value < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;

/** Each agent's cost from the ledger: what is known, never a guess. */
function costByAgent(cost: ModelObservability | null) {
	return new Map((cost?.by_agent ?? []).map((row) => [row.agent_id, row.calls_costed ? row.known_cost_usd : null]));
}

const LIVE_MS = 15 * 60 * 1000;

/** The Leader and the business agents for the map, from the shared cache. */
export function mapAgents(agents: AgentSummary[], activity: AgentActivity[], cost: ModelObservability | null): MapAgent[] {
	const byId = new Map(activity.map((row) => [row.agent_id, row]));
	const costs = costByAgent(cost);
	const live = (at: string | null | undefined) => !!at && Date.now() - new Date(at).getTime() < LIVE_MS;
	const leader = activity.find((row) => row.role === 'leader');
	return [
		...(leader
			? [{ id: leader.agent_id, name: 'Leader', role: 'leader' as const, state: 'published' as const,
				tickets: leader.tickets, live: live(leader.last_at), costUsd: costs.get(leader.agent_id) ?? null }]
			: []),
		...agents.map((agent) => ({
			id: agent.agent_id,
			name: agent.name,
			role: 'business' as const,
			state: agent.lifecycle_state,
			tickets: byId.get(agent.agent_id)?.tickets ?? 0,
			live: live(byId.get(agent.agent_id)?.last_at),
			costUsd: costs.get(agent.agent_id) ?? null,
		})),
	];
}
