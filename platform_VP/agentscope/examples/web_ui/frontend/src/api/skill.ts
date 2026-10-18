import { client } from './client';
import type { SkillRecord, SkillView } from './types';

/**
 * The user's own library of installed skills, which is where a hub install
 * lands. Separate from `workspaceApi.skill`, which manages the skills one
 * session's workspace actually holds.
 */
export const skillApi = {
	create: (body: { name: string; description: string; markdown: string }) => client.post<SkillView>('/skill', body),
	review: (id: string, status: 'approved' | 'revoked') => client.post<SkillView>(`/skill/${encodeURIComponent(id)}/review`, { status }),
	list: () => client.get<SkillView[]>('/skill'),

	/** Unlike the list endpoint, this also carries the `SKILL.md` body. */
	get: (skillId: string) => client.get<SkillRecord>(`/skill/${encodeURIComponent(skillId)}`),

	/**
	 * Removes it from the library. Workspaces that already hold this skill
	 * keep their copy — the files were extracted into the workspace, and this
	 * record was only where they came from.
	 */
	remove: (skillId: string) => client.delete(`/skill/${encodeURIComponent(skillId)}`),
};
