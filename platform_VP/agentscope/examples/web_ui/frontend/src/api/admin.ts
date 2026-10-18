import { client } from './client';

export interface AdminAccount {
	id: string;
	email: string;
	username: string;
	status: 'pending' | 'active' | 'rejected' | string;
	role: string;
	domain_id: string | null;
	area_id: string | null;
	created_at: string;
	last_login_at: string | null;
}

export interface DirectoryArea {
	id: string;
	domain_id: string;
	name: string;
	status: string;
	managers: { id: string; username: string; status: string }[];
}

export interface DirectoryDomain {
	id: string;
	name: string;
	status: string;
	areas: DirectoryArea[];
}

export const adminApi = {
	accounts: (status?: string) =>
		client.get<AdminAccount[]>('/admin/accounts', status ? { status_filter: status } : undefined),
	approve: (id: string) => client.post<AdminAccount>(`/admin/accounts/${encodeURIComponent(id)}/approve`),
	reject: (id: string) => client.post<AdminAccount>(`/admin/accounts/${encodeURIComponent(id)}/reject`),
	directory: () => client.get<DirectoryDomain[]>('/admin/directory'),
	saveDomain: (id: string, name: string) =>
		client.put(`/admin/domains/${encodeURIComponent(id)}`, { name, active: true }),
	saveArea: (domainId: string, areaId: string, name: string) =>
		client.put(`/admin/domains/${encodeURIComponent(domainId)}/areas/${encodeURIComponent(areaId)}`, {
			name,
			active: true,
		}),
	createDomainAdmin: (body: { email: string; username: string; password: string; domain_id: string }) =>
		client.post<AdminAccount>('/admin/domain-admins', body),
};
