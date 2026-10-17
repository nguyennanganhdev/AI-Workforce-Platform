import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import { meApi } from '@/api/me';
import { useCurrentUser } from '@/context/CurrentUserContext';
import { PlatformAccessContext } from '@/context/platform-access';
import { workspacesFor } from '@/features/workforce/shell/access';

export function PlatformAccessProvider({ children }: { children: ReactNode }) {
	const user = useCurrentUser()!;
	const queryClient = useQueryClient();
	const [acceptedScope, setAcceptedScope] = useState('');
	const key = ['capabilities', user.tenant_id, user.id];
	const query = useQuery({
		queryKey: key, queryFn: () => meApi.capabilities(user), retry: false,
		refetchInterval: 30000, refetchOnWindowFocus: 'always', staleTime: 0,
	});
	const scope = query.data ? `${query.data.workspace_id}:${query.data.authorization_revision}` : '';
	useEffect(() => {
		if (!scope || scope === acceptedScope) return;
		let active = true;
		void queryClient.cancelQueries({ predicate: (entry) => entry.queryKey[0] !== 'capabilities' }).then(() => {
			queryClient.removeQueries({ predicate: (entry) => entry.queryKey[0] !== 'capabilities' });
			if (active) setAcceptedScope(scope);
		});
		return () => { active = false; };
	}, [acceptedScope, queryClient, scope]);

	const workspaces = query.data && !query.isError ? workspacesFor(query.data) : [];
	return (
		<PlatformAccessContext.Provider value={{
			view: query.isError ? undefined : query.data,
			workspace: workspaces[0],
			pending: query.isPending || (!!scope && scope !== acceptedScope), unavailable: query.isError,
			refresh: () => { void query.refetch(); },
		}}>
			{children}
		</PlatformAccessContext.Provider>
	);
}
