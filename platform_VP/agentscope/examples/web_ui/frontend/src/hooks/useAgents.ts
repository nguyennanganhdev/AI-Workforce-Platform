import { useState, useEffect, useCallback, useMemo } from 'react';

import { agentApi } from '../api';
import type { AgentView, CreateAgentRequest, UpdateAgentRequest } from '../api';

/**
 * Manages the full agent list with CRUD operations.
 * Fetches on mount and automatically re-fetches after each mutation.
 */
export function useAgents() {
	const [agents, setAgents] = useState<AgentView[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	const refetch = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await agentApi.list();
			setAgents(res.agents);
		} catch (e) {
			setError(e as Error);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refetch();
	}, [refetch]);

	/** Creates a new agent and refreshes the list. */
	const create = useCallback(
		async (body: CreateAgentRequest, options?: { silent?: boolean }) => {
			const res = await agentApi.create(body, options);
			await refetch();
			return res;
		},
		[refetch],
	);

	/** Partially updates an agent and refreshes the list. */
	const update = useCallback(
		async (agentId: string, body: UpdateAgentRequest, options?: { silent?: boolean }) => {
			const res = await agentApi.update(agentId, body, options);
			await refetch();
			return res;
		},
		[refetch],
	);

	/** Deletes an agent and refreshes the list. */
	const remove = useCallback(
		async (agentId: string) => {
			await agentApi.delete(agentId);
			await refetch();
		},
		[refetch],
	);

	// Stable between renders: effects may depend on it.
	const runnable = useMemo(() => agents.filter(isRunnableAgent), [agents]);

	return { agents, runnable, loading, error, refetch, create, update, remove };
}

/** Agents that may run unattended from a channel or schedule: the Leader or a published agent. */
export function isRunnableAgent(agent: AgentView): boolean {
	return agent.data.system_role === 'leader' || agent.data.lifecycle_state === 'published';
}
