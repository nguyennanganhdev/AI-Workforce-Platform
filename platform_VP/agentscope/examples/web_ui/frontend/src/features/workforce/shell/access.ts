/** Mirrors the C01 producer in vin_platform._service.VinPlatformService. */
export const CAPABILITIES_SCHEMA = 'vin-platform-1';

export type WorkspaceKind = 'personal' | 'operations' | 'admin';
export interface CapabilityWorkspace {
	id: string;
	label: string;
	kind: WorkspaceKind;
	capabilities: string[];
}

export interface CapabilitiesView {
	contract_version: typeof CAPABILITIES_SCHEMA;
	initiator_user_id: string;
	tenant_id: string;
	workspace_id: string;
	authorization_revision: number;
	eligible: boolean;
	capabilities: Record<string, boolean>;
}

function record(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): value is string {
	return typeof value === 'string' && value.trim().length > 0;
}

/** Reject a mismatched principal and unknown versions before mounting a page. */
export function parseCapabilities(value: unknown, user: { id: string; tenant_id: string }): CapabilitiesView {
	if (!record(value) || value.contract_version !== CAPABILITIES_SCHEMA
		|| value.initiator_user_id !== user.id || value.tenant_id !== user.tenant_id
		|| !Number.isSafeInteger(value.authorization_revision) || Number(value.authorization_revision) < 1
		|| !text(value.workspace_id) || typeof value.eligible !== 'boolean'
		|| !record(value.capabilities) || !Object.values(value.capabilities).every((entry) => typeof entry === 'boolean')) {
		throw new Error('CAPABILITIES_UNAVAILABLE');
	}
	return {
		contract_version: CAPABILITIES_SCHEMA,
		initiator_user_id: user.id, tenant_id: user.tenant_id,
		authorization_revision: Number(value.authorization_revision),
		workspace_id: value.workspace_id, eligible: value.eligible,
		capabilities: Object.fromEntries(Object.entries(value.capabilities).map(([key, allowed]) => [key, allowed === true])),
	};
}

/** Presentation spaces only. No client choice changes the authenticated subject. */
export function workspacesFor(view: CapabilitiesView): CapabilityWorkspace[] {
	const capabilities = Object.keys(view.capabilities).filter((key) => view.capabilities[key]);
	const spaces: CapabilityWorkspace[] = [];
	if (capabilities.includes('personal.read')) spaces.push({ id: 'personal', label: 'Cá nhân', kind: 'personal', capabilities });
	if (capabilities.includes('management.read')) spaces.push({ id: 'operations', label: 'Vận hành', kind: 'operations', capabilities });
	if (capabilities.some((key) => ['accounts.manage', 'catalog.manage', 'quota.manage'].includes(key))) {
		spaces.push({ id: 'admin', label: 'Quản trị', kind: 'admin', capabilities });
	}
	return spaces;
}

export interface ShellDestination {
	path: string;
	label: string;
	capability: string;
	kinds: WorkspaceKind[];
}

/** Navigation and direct-URL guards share this table; roles never grant access. */
export const SHELL_DESTINATIONS: ShellDestination[] = [
	{ path: '/workforce/leader', label: 'Leader', capability: 'personal.read', kinds: ['personal'] },
	{ path: '/workforce/leader', label: 'Leader vận hành', capability: 'management.read', kinds: ['operations'] },
	{ path: '/chat', label: 'Chat riêng', capability: 'personal.read', kinds: ['personal'] },
	{ path: '/workforce/agents', label: 'Agent của tôi', capability: 'personal.read', kinds: ['personal'] },
	{ path: '/workforce/builder', label: 'Tạo agent', capability: 'personal.create', kinds: ['personal'] },
	{ path: '/knowledge', label: 'Knowledge', capability: 'knowledge.private.manage', kinds: ['personal'] },
	{ path: '/schedule', label: 'Lịch trình', capability: 'schedules.manage', kinds: ['personal'] },
	{ path: '/connections', label: 'Kết nối', capability: 'personal.read', kinds: ['personal'] },
	{ path: '/account', label: 'Tài khoản và hạn mức', capability: 'personal.read', kinds: ['personal', 'operations', 'admin'] },
	{ path: '/admin', label: 'Tài khoản', capability: 'accounts.manage', kinds: ['admin'] },
	{ path: '/credential', label: 'Provider', capability: 'providers.manage', kinds: ['admin'] },
	{ path: '/mcp', label: 'MCP', capability: 'catalog.manage', kinds: ['admin'] },
	{ path: '/skill', label: 'Skill', capability: 'catalog.manage', kinds: ['admin'] },
	{ path: '/channel', label: 'Quản trị kênh', capability: 'channels.manage', kinds: ['admin'] },
];

export function destinationsFor(workspace: CapabilityWorkspace): ShellDestination[] {
	return SHELL_DESTINATIONS.filter((destination) => destination.kinds.includes(workspace.kind)
		&& workspace.capabilities.includes(destination.capability));
}

export function mayVisit(workspace: CapabilityWorkspace, pathname: string): boolean {
	return destinationsFor(workspace).some(({ path }) => pathname === path || pathname.startsWith(`${path}/`));
}

export function homeFor(workspace: CapabilityWorkspace): string | null {
	return destinationsFor(workspace)[0]?.path ?? null;
}
