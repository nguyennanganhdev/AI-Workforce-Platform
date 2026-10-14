import type { Edge, Node } from '@xyflow/react';

import type { AgentView } from '@/api';

/** An agent as the graph draws it: a real one from the API, or a sample stand-in. */
export type GraphAgent = {
	id: string;
	name: string;
	/** One line on what it is for. Empty when the agent has none. */
	role: string;
	/** Whether other agents — the Leader — may bring it into a session. */
	invitable: boolean;
	/** The record behind it; `null` for a sample agent. */
	real: AgentView | null;
};

/**
 * Live figures for one agent. The backend does not report these yet, so they
 * are SAMPLE numbers, derived from the agent's id so they hold still between
 * renders. The canvas says so in its own chrome.
 */
export type AgentMetrics = {
	/** Sessions running right now. */
	running: number;
	/** Sessions started today. */
	today: number;
	responseSeconds: number;
};

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
	running: number;
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

/** The five agents of the plan's acceptance case, shown while the library is empty. */
const SAMPLE_AGENTS: GraphAgent[] = [
	['sample-planner', 'Agent Lập kế hoạch', 'Hỏi thông tin còn thiếu, trình phương án'],
	['sample-hotel', 'Agent Khách sạn', 'Tìm, tư vấn và đặt khách sạn'],
	['sample-car', 'Agent Xe', 'Tìm và đặt xe'],
	['sample-calculator', 'Agent Tính chi phí', 'Tính tổng chi phí bằng công cụ xác định'],
	['sample-technical', 'Agent Kỹ thuật', 'Tiếp nhận và theo dõi sửa chữa'],
].map(([id, name, role]) => ({ id, name, role, invitable: true, real: null }));

export function toGraphAgents(agents: AgentView[]): { agents: GraphAgent[]; sample: boolean } {
	if (agents.length === 0) return { agents: SAMPLE_AGENTS, sample: true };
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

function hash(id: string): number {
	let sum = 0;
	for (let index = 0; index < id.length; index += 1) {
		sum = (sum * 31 + id.charCodeAt(index)) % 9973;
	}
	return sum;
}

export function sampleMetrics(agent: GraphAgent): AgentMetrics {
	const h = hash(agent.id);
	// An agent the Leader cannot bring in has no sessions to show.
	const running = agent.invitable ? [0, 1, 3, 0, 5, 2][h % 6] : 0;
	return {
		running,
		today: running * 4 + (h % 7) + (agent.invitable ? 3 : 0),
		responseSeconds: 2.4 + (h % 50) / 10,
	};
}

const AGENT_X = 680;
const AGENT_GAP = 116;
const SUPERVISOR_ID = 'leader';
/** Sample count of plans waiting on the manager. */
const PENDING_APPROVALS = 2;

/**
 * Lay the topology out left to right: who sends requests, the Leader, the
 * agents. Computed, not stored — it only changes when the agent set does.
 */
export function buildGraph(
	agents: GraphAgent[],
	t: Translate,
): { nodes: FlowNode[]; edges: FlowEdge[]; totalRunning: number; averageResponse: number } {
	const metrics = new Map(agents.map((agent) => [agent.id, sampleMetrics(agent)]));
	const totalRunning = [...metrics.values()].reduce((sum, m) => sum + m.running, 0);
	const active = [...metrics.values()].filter((m) => m.running > 0);
	const averageResponse = active.length
		? active.reduce((sum, m) => sum + m.responseSeconds, 0) / active.length
		: 0;

	const centre = ((agents.length - 1) * AGENT_GAP) / 2;

	const nodes: FlowNode[] = [
		{
			id: 'resident',
			type: 'entry',
			position: { x: 0, y: centre - 44 },
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
			position: { x: 0, y: centre + 56 },
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
			position: { x: 290, y: centre },
			data: {
				kind: 'supervisor',
				delay: 160,
				title: t('agents.graph.leader'),
				note: t('agents.graph.leaderNote'),
				running: totalRunning,
			},
		},
		{
			id: 'approval',
			type: 'human',
			position: { x: 316, y: centre + 210 },
			data: {
				kind: 'human',
				delay: 320,
				count: PENDING_APPROVALS,
				title: t('agents.graph.approval'),
				note: t('agents.graph.approvalNote', { count: PENDING_APPROVALS }),
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
			data: { state: totalRunning > 0 ? 'live' : 'idle', delay: 120 },
		},
		{
			id: 'manager-leader',
			type: 'flow',
			source: 'manager',
			target: SUPERVISOR_ID,
			data: { state: 'idle', delay: 160 },
		},
		{
			id: 'leader-approval',
			type: 'flow',
			source: SUPERVISOR_ID,
			sourceHandle: 'bottom',
			target: 'approval',
			data: {
				state: 'human',
				label: t('agents.graph.pending', { count: PENDING_APPROVALS }),
				delay: 280,
			},
		},
		// Only an agent that allows itself to be invited is one the Leader can
		// reach, so only those get an edge.
		...agents
			.filter((agent) => agent.invitable)
			.map((agent, index): FlowEdge => {
				const running = metrics.get(agent.id)!.running;
				const delay = 280 + index * 70;
				return {
					id: `leader-${agent.id}`,
					type: 'flow',
					source: SUPERVISOR_ID,
					target: agent.id,
					data:
						running > 0
							? {
									state: 'live',
									label: t('agents.graph.sessionCount', { count: running }),
									delay,
								}
							: { state: 'idle', delay },
				};
			}),
	];

	return { nodes, edges, totalRunning, averageResponse };
}
