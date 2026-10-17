import { client } from './client';
import type { ChatModelConfig } from './types';

export interface PersonalGroup {
	sessionId: string;
	agentId: string;
	name: string;
	memberIds: string[];
	createdAt: string;
	goal: string;
	members: { agent_id: string; session_id: string; name: string }[];
}

export interface PersonalContext {
	kind: 'direct' | 'group';
	context_mode: 'shared' | 'isolated';
	private_summary: string;
	goal: string;
	revision: number;
	events: { id: string; content: string; source_agent_id: string | null; created_at: string }[];
	summary: { text: string; source_event_ids: string[]; covered_through_revision: number } | null;
	metrics: Record<string, number | string>;
}

export const personalChatApi = {
	groups: () => client.get<PersonalGroup[]>('/sessions/personal/groups'),
	createGroup: (body: {
		name: string; goal: string; agent_ids: string[];
		chat_model_config?: ChatModelConfig;
		fallback_chat_model_config?: ChatModelConfig;
	}) => client.post<PersonalGroup>('/sessions/personal/groups', body),
	deleteGroup: (sessionId: string, agentId: string) => client.delete(
		`/sessions/personal/groups/${sessionId}`, { agent_id: agentId },
	),
	context: (sessionId: string, agentId: string) => client.get<PersonalContext>(
		`/sessions/personal/${sessionId}/context`, { agent_id: agentId },
	),
	updateContext: (sessionId: string, agentId: string, body: {
		context_mode?: 'shared' | 'isolated'; note?: string;
	}) => client.patch(`/sessions/personal/${sessionId}/context`, body, { agent_id: agentId }),
};
