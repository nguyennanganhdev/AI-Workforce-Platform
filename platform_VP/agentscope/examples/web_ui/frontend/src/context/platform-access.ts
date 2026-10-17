import { createContext, useContext } from 'react';

import type { CapabilitiesView, CapabilityWorkspace } from '@/features/workforce/shell/access';

export interface PlatformAccess {
	view: CapabilitiesView | undefined;
	workspace: CapabilityWorkspace | undefined;
	workspaces: CapabilityWorkspace[];
	pending: boolean;
	unavailable: boolean;
	refresh: () => void;
	switchWorkspace: (id: string) => Promise<void>;
}

export const PlatformAccessContext = createContext<PlatformAccess | null>(null);

export function usePlatformAccess() {
	return useContext(PlatformAccessContext);
}
