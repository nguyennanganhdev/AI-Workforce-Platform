import { client } from './client';
import { parseUsage } from './personal';

export interface VinQuotaPolicy {
	daily_tokens: number; monthly_tokens: number; max_output_tokens: number; max_concurrency: number;
	storage_bytes: number; max_file_bytes: number; embedding_daily_tokens: number; models: string[]; enabled: boolean;
}
export interface VinCatalogEntry {
	kind: 'credential' | 'agent' | 'knowledge_base' | 'mcp' | 'skill';
	resource_id: string; owner_id: string; version: number; name: string; description: string;
	environment: 'production' | 'sandbox'; model_names: string[]; tool_names: string[]; active: boolean;
}
export interface VinCatalogView extends VinCatalogEntry { catalog_id: string; permissions: string[] }
export interface VinGrant { catalog_id: string; subject_kind: 'user' | 'group' | 'role'; subject_id: string;
	permissions: ('view' | 'bind' | 'execute')[]; expires_at: string | null }

export const vinAdminApi = {
	usage: async (userId: string) => parseUsage(await client.get(`/workforce/console/admin/vin/users/${encodeURIComponent(userId)}/usage`, undefined, { silent: true })),
	savePolicy: (subject: string, body: VinQuotaPolicy) => client.put(`/admin/vin/quota-policies/${encodeURIComponent(subject)}`, body),
	publish: (body: VinCatalogEntry) => client.post<{ id: string }>('/admin/vin/catalog', body),
	catalog: (kind: string, environment: string) => client.get<{ items: VinCatalogView[] }>(`/catalog/${kind}`, { environment }),
	grant: (body: VinGrant) => client.post<{ id: string }>('/admin/vin/grants', body),
	revokeGrant: (id: string) => client.delete(`/admin/vin/grants/${encodeURIComponent(id)}`),
	membership: (userId: string, groupId: string, expiresAt: string | null) => client.post<{ id: string }>('/admin/vin/memberships',
		{ user_id: userId, group_id: groupId, expires_at: expiresAt }),
	revokeMembership: (id: string) => client.delete(`/admin/vin/memberships/${encodeURIComponent(id)}`),
	eligibility: (userId: string, eligible: boolean) => client.put(`/admin/vin/accounts/${encodeURIComponent(userId)}/eligibility`, { eligible }),
};
