import { createContext, useContext } from 'react';

import type { AuthUser } from '@/api';

/**
 * The signed-in account, as `App` learned it at sign-in or session restore.
 * `null` outside a signed-in tree.
 */
const CurrentUserContext = createContext<AuthUser | null>(null);

export const CurrentUserProvider = CurrentUserContext.Provider;

export function useCurrentUser(): AuthUser | null {
	return useContext(CurrentUserContext);
}
