import { type QueryClient, useQuery } from '@tanstack/react-query';

import { studioApi } from '@/api';

/**
 * The manager's business agents, their activity, collaboration and cost:
 * one cache for the list, the map and the agent page, so a change made in
 * one place (publish, withdraw, delete) shows everywhere.
 */
export const STUDIO_KEY = ['studio'] as const;
const LIVE_MS = 30_000;

export function useStudioAgents() {
	return useQuery({ queryKey: [...STUDIO_KEY, 'agents'], queryFn: () => studioApi.listAgents() });
}

export function useAgentMapData() {
	const activity = useQuery({ queryKey: [...STUDIO_KEY, 'activity'], queryFn: () => studioApi.activity(), refetchInterval: LIVE_MS });
	const links = useQuery({ queryKey: [...STUDIO_KEY, 'collaboration'], queryFn: () => studioApi.collaboration(), refetchInterval: LIVE_MS });
	const cost = useQuery({ queryKey: [...STUDIO_KEY, 'observability'], queryFn: () => studioApi.observability(), refetchInterval: 2 * LIVE_MS });
	return { activity: activity.data ?? [], links: links.data ?? [], cost: cost.data ?? null };
}

/** After any agent change: every studio view reads again. */
export function refreshStudio(client: QueryClient) {
	return client.invalidateQueries({ queryKey: STUDIO_KEY });
}
