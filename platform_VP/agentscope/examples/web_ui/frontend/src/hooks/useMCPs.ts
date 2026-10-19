import { useCallback, useEffect, useState } from 'react';

import { usePrivateMCPManagement as useCatalogManagement } from './useCatalogManagement';
import { mcpApi } from '@/api';
import type { MCPView, UpdateMCPRequest } from '@/api';

/**
 * The user's library of installed MCPs.
 *
 * User-level, so unlike `useWorkspace` it needs no agent/session — an empty
 * list means the user has installed nothing yet, not that a session is
 * missing.
 */
export function useMCPs() {
	const canManage = useCatalogManagement();
	const [mcps, setMcps] = useState<MCPView[]>([]);
	// Starts true: the first paint happens before the effect fires, and
	// a false start would flash the empty state before the spinner.
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<Error | null>(null);

	const refetch = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			setMcps(await mcpApi.list());
		} catch (e) {
			setError(e as Error);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refetch();
	}, [refetch]);

	const update = useCallback(
		async (mcpId: string, body: UpdateMCPRequest) => {
			if (!canManage) throw new Error('CATALOG_READ_ONLY');
			await mcpApi.update(mcpId, body);
			await refetch();
		},
		[refetch, canManage],
	);

	const remove = useCallback(
		async (mcpId: string) => {
			if (!canManage) throw new Error('CATALOG_READ_ONLY');
			await mcpApi.remove(mcpId);
			await refetch();
		},
		[refetch, canManage],
	);

	return { mcps, loading, error, refetch, update, remove };
}
