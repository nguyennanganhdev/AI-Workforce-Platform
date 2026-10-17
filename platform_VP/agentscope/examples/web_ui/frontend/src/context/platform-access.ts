import { createContext, useContext } from 'react';

import type { CapabilitiesView, CapabilityWorkspace } from '@/features/workforce/shell/access';

export interface PlatformAccess {
	view: CapabilitiesView | undefined;
	workspace: CapabilityWorkspace | undefined;
	pending: boolean;
	unavailable: boolean;
	refresh: () => void;
}

export const PlatformAccessContext = createContext<PlatformAccess | null>(null);

export function usePlatformAccess() {
	return useContext(PlatformAccessContext);
}
