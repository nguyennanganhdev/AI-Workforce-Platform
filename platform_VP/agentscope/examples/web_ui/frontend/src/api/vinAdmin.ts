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
export interface VinCatalogView extends VinCatalogEntry { catalog_id: string }
export interface VinGrant { catalog_id: string; subject_kind: 'user' | 'group' | 'role'; subject_id: string;
	permissions: ('view' | 'bind' | 'execute')[]; expires_at: string | null }
export interface VinPage<T> { contract_version: 'vin-platform-1'; items: T[]; total: number; offset: number; limit: number; next_offset: number | null }
export interface VinPolicyView { subject: string; revision: number; active: boolean; policy: VinQuotaPolicy }
export interface VinGrantView extends VinGrant { id: string; revision: number; active: boolean }
export interface VinMembership { id: string; user_id: string; group_id: string; active: boolean; revision: number; expires_at: string | null }
export interface VinAccount {
	user_id: string; email: string | null; username: string; role: string; status: 'active' | 'suspended' | 'deleted' | string;
	created_at: string | null; last_login_at: string | null; month_tokens: number; eligible: boolean; revision: number;
}
export interface VinDocument { document_id: string; catalog_id: string; filename: string; status: string;
	review_status: 'candidate' | 'approved' | 'retired'; revision: string; version: string; source_ref: string }
type Filters = Record<string, string | number | boolean | undefined>;
const query = (filters: Filters) => Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== undefined && value !== '').map(([key, value]) => [key, String(value)]));
const revisionQuery = (revision: number) => `?expected_revision=${revision}`;

export const vinAdminApi = {
	usage: async (userId: string) => parseUsage(await client.get(`/workforce/console/admin/vin/users/${encodeURIComponent(userId)}/usage`, undefined, { silent: true })),
	savePolicy: (subject: string, body: VinQuotaPolicy, revision: number) => client.put(`/admin/vin/quota-policies/${encodeURIComponent(subject)}${revisionQuery(revision)}`, body),
	policies: (filters: Filters) => client.get<VinPage<VinPolicyView>>('/admin/vin/quota-policies', query(filters)),
	removePolicy: (subject: string, revision: number) => client.delete(`/admin/vin/quota-policies/${encodeURIComponent(subject)}${revisionQuery(revision)}`),
	publish: (body: VinCatalogEntry) => client.post<{ id: string }>('/admin/vin/catalog', body),
	catalog: (filters: Filters) => client.get<VinPage<VinCatalogView>>('/admin/vin/catalog', query(filters)),
	grants: (filters: Filters) => client.get<VinPage<VinGrantView>>('/admin/vin/grants', query(filters)),
	memberships: (filters: Filters) => client.get<VinPage<VinMembership>>('/admin/vin/memberships', query(filters)),
	accounts: (filters: Filters) => client.get<VinPage<VinAccount>>('/admin/vin/accounts', query(filters)),
	documents: (id: string, filters: Filters) => client.get<VinPage<VinDocument>>(`/admin/vin/catalog/${encodeURIComponent(id)}/documents`, query(filters)),
	review: (id: string, documentId: string, status: 'approved' | 'retired', revision: string) => client.post<VinDocument>(`/admin/vin/catalog/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/review`, { status, expected_revision: revision }),
	grant: (body: VinGrant) => client.post<{ id: string }>('/admin/vin/grants', body),
	revokeGrant: (id: string, revision: number) => client.delete(`/admin/vin/grants/${encodeURIComponent(id)}${revisionQuery(revision)}`),
	membership: (userId: string, groupId: string, expiresAt: string | null) => client.post<{ id: string }>('/admin/vin/memberships',
		{ user_id: userId, group_id: groupId, expires_at: expiresAt }),
	revokeMembership: (id: string, revision: number) => client.delete(`/admin/vin/memberships/${encodeURIComponent(id)}${revisionQuery(revision)}`),
	suspend: (userId: string) => client.post(`/admin/vin/accounts/${encodeURIComponent(userId)}/suspend`),
	reactivate: (userId: string) => client.post(`/admin/vin/accounts/${encodeURIComponent(userId)}/reactivate`),
	deleteAccount: (userId: string) => client.delete(`/admin/vin/accounts/${encodeURIComponent(userId)}`),
	eligibility: (userId: string, eligible: boolean, revision: number) => client.put(`/admin/vin/accounts/${encodeURIComponent(userId)}/eligibility${revisionQuery(revision)}`, { eligible }),
};
