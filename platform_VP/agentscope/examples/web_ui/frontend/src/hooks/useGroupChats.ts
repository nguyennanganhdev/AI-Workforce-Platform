import { useQuery } from '@tanstack/react-query';

import { personalChatApi } from '@/api/personal-chat';
import { useCurrentUser } from '@/context/CurrentUserContext';

/** Authenticated, durable groups; no browser-local roster or kickoff. */
export function useGroupChats() {
	const user = useCurrentUser();
	return useQuery({
		queryKey: ['personal-groups', user?.id],
		queryFn: personalChatApi.groups,
		staleTime: 30_000,
		refetchInterval: 30_000,
	});
}
