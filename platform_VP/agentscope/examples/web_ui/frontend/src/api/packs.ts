import { client } from './client';

export interface PackInput {
	name: string;
	description: string;
	catalog_ids: string[];
	template_agent_ids: string[];
	link_provider_id: string | null;
	active: boolean;
}
export interface PackView extends PackInput { id: string; revision: number; installed: boolean }
export interface PackChange { installed: boolean; agents: string[]; link_provider_id?: string | null }

export const packsApi = {
	list: () => client.get<PackView[]>('/me/packs'),
	install: (id: string) => client.post<PackChange>(`/me/packs/${encodeURIComponent(id)}/install`),
	remove: (id: string) => client.post<PackChange>(`/me/packs/${encodeURIComponent(id)}/remove`),
	adminList: () => client.get<PackView[]>('/admin/vin/packs'),
	adminSave: (id: string, body: PackInput, revision: number) =>
		client.put<{ revision: number }>(`/admin/vin/packs/${encodeURIComponent(id)}?expected_revision=${revision}`, body),
};
