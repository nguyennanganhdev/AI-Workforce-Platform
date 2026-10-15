import type { Edge, Node } from '@xyflow/react';

import type { AgentActivity, AgentView } from '@/api';

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

/** What one agent did, from the workforce activity report (no sample numbers). */
export type AgentMetrics = {
	/** Tickets the agent worked on. */
	tickets: number;
	/** Replies it produced (one reply may take several model calls). */
	replies: number;
	/** Its last reply, if any. */
	lastAt: string | null;
	/** It replied within the last {@link RECENT_MS}. */
	live: boolean;
};

/** How recent a reply must be for the agent to show as working now. */
export const RECENT_MS = 15 * 60 * 1000;

/** `delay`: when, in ms after the canvas opens, the node fades in — left to right. */
type Staged = { delay: number };
export type EntryData = Staged & {
	kind: 'entry';
	icon: 'resident' | 'manager';
	title: string;
	note: string;
};
export type AgentData = Staged & { kind: 'agent'; agent: GraphAgent; metrics: AgentMetrics };
export type SupervisorData = Staged & {
	kind: 'supervisor';
	title: string;
	note: string;
	tickets: number;
	live: boolean;
};
export type HumanData = Staged & { kind: 'human'; title: string; note: string; count: number };

export type FlowNode =
	| Node<EntryData, 'entry'>
	| Node<AgentData, 'agent'>
	| Node<SupervisorData, 'supervisor'>
	| Node<HumanData, 'human'>;

/**
 * `live`: sessions flowing now. `human`: waiting on a person. `idle`:
 * configured, quiet. `delay` staggers the draw-in like the nodes'.
 */
export type FlowEdgeData = {
	state: 'live' | 'human' | 'idle';
	label?: string;
	delay?: number;
};
export type FlowEdge = Edge<FlowEdgeData, 'flow'>;

type Translate = (key: string, options?: Record<string, unknown>) => string;

export function toGraphAgents(agents: AgentView[]): { agents: GraphAgent[]; sample: boolean } {
	return {
		sample: false,
		agents: agents.map((agent) => ({
			id: agent.id,
			name: agent.data.name,
			role: agent.data.invite_config?.invite_description?.trim() ?? '',
			invitable: !!agent.data.invite_config?.invitable,
			real: agent,
		})),
	};
}

export function metricsOf(activity: AgentActivity | undefined, now: number): AgentMetrics {
	const lastAt = activity?.last_at ?? null;
	return {
		tickets: activity?.tickets ?? 0,
		replies: activity?.replies ?? 0,
		lastAt,
		live: lastAt !== null && now - new Date(lastAt).getTime() < RECENT_MS,
	};
}

const AGENT_X = 560;
const AGENT_GAP = 64;
const SUPERVISOR_ID = 'leader';

/**
 * Lay the topology out left to right: who sends requests, the Leader, the
 * agents. Computed, not stored — it only changes when the agent set does.
 */
export function buildGraph(
	agents: GraphAgent[],
	t: Translate,
	activity: Map<string, AgentActivity>,
	now: number,
): { nodes: FlowNode[]; edges: FlowEdge[]; totalTickets: number; leaderLive: boolean } {
	const metrics = new Map(agents.map((agent) => [agent.id, metricsOf(activity.get(agent.id), now)]));
	const leader = [...activity.values()].find((row) => row.role === 'leader');
	const leaderMetrics = metricsOf(leader, now);
	const totalTickets = leaderMetrics.tickets;
	const leaderLive = leaderMetrics.live || [...metrics.values()].some((m) => m.live);

	const centre = ((agents.length - 1) * AGENT_GAP) / 2;

	const nodes: FlowNode[] = [
		{
			id: 'resident',
			type: 'entry',
			position: { x: 0, y: centre - 30 },
			data: {
				kind: 'entry',
				delay: 0,
				icon: 'resident',
				title: t('agents.graph.resident'),
				note: t('agents.graph.residentNote'),
			},
		},
		{
			id: 'manager',
			type: 'entry',
			position: { x: 0, y: centre + 34 },
			data: {
				kind: 'entry',
				delay: 60,
				icon: 'manager',
				title: t('agents.graph.you'),
				note: t('agents.graph.youNote'),
			},
		},
		{
			id: SUPERVISOR_ID,
			type: 'supervisor',
			position: { x: 230, y: centre - 4 },
			data: {
				kind: 'supervisor',
				delay: 160,
				title: t('agents.graph.leader'),
				note: t('agents.graph.leaderNote'),
				tickets: totalTickets,
				live: leaderLive,
			},
		},
		...agents.map((agent, index): FlowNode => ({
			id: agent.id,
			type: 'agent',
			position: { x: AGENT_X, y: index * AGENT_GAP },
			data: {
				kind: 'agent',
				delay: 320 + index * 70,
				agent,
				metrics: metrics.get(agent.id)!,
			},
		})),
	];

	const edges: FlowEdge[] = [
		{
			id: 'resident-leader',
			type: 'flow',
			source: 'resident',
			target: SUPERVISOR_ID,
			data: { state: leaderLive ? 'live' : 'idle', delay: 120 },
		},
		{
			id: 'manager-leader',
			type: 'flow',
			source: 'manager',
			target: SUPERVISOR_ID,
			data: { state: 'idle', delay: 160 },
		},
		// Only an agent that allows itself to be invited is one the Leader can
		// reach, so only those get an edge.
		...agents
			.filter((agent) => agent.invitable)
			.map((agent, index): FlowEdge => {
				const { tickets, live } = metrics.get(agent.id)!;
				const delay = 280 + index * 70;
				return {
					id: `leader-${agent.id}`,
					type: 'flow',
					source: SUPERVISOR_ID,
					target: agent.id,
					data:
						tickets > 0
							? {
									state: live ? 'live' : 'idle',
									label: t('agents.graph.sessionCount', { count: tickets }),
									delay,
								}
							: { state: 'idle', delay },
				};
			}),
	];

	return { nodes, edges, totalTickets, leaderLive };
}
