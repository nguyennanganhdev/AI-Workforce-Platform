import { useQuery } from '@tanstack/react-query';

import { client } from '@/api/client';
import { useCurrentUser } from '@/context/CurrentUserContext';

interface DiscordIdentity { verified: boolean; discord_user_id?: string; verified_at?: number; revision?: number }

export function useDiscordIdentity(enabled = true) {
	const user = useCurrentUser();
	return useQuery({ queryKey: ['discord-identity', user?.tenant_id, user?.id],
		queryFn: () => client.get<DiscordIdentity>('/channels/discord/identity', undefined, { silent: true }),
		enabled: enabled && user?.role === 'VIN_USER', retry: false, staleTime: 30000 });
}
