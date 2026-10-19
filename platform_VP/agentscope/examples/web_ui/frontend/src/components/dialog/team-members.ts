import type { AgentView } from '@/api';

/** Agents the backend accepts as manual team members (see POST /sessions/{id}/team/members). */
export function isInvitableMember(agent: AgentView): boolean {
	return (
		agent.source === 'user' &&
		agent.data.system_role === 'business' &&
		agent.data.lifecycle_state === 'published' &&
		agent.data.invite_config.invitable === true &&
		Boolean(agent.data.invite_config.invite_description?.trim())
	);
}
