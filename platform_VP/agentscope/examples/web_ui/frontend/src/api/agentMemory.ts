import { client } from './client';

/** A memory an agent proposed or the user added; only approved, active ones reach the agent. */
export interface AgentMemory {
	id: string;
	content: string;
	reason: string;
	status: 'proposed' | 'approved' | 'rejected';
	pinned: boolean;
	confirmations: number;
	proposed_at: string;
	approved_at: string | null;
	last_confirmed_at: string | null;
	source_session_id: string | null;
	/** 1 when fresh or pinned, halving every 30 days without confirmation. */
	priority: number;
	/** Approved and still given to the agent. */
	active: boolean;
}

const base = (agentId: string) => `/agent/${agentId}/memories`;

export const agentMemoryApi = {
	list: (agentId: string) => client.get<AgentMemory[]>(base(agentId)),
	add: (agentId: string, content: string) => client.post<AgentMemory>(base(agentId), { content }),
	approve: (agentId: string, memoryId: string, content?: string) =>
		client.post<AgentMemory>(`${base(agentId)}/${memoryId}/approve`, content ? { content } : {}),
	reject: (agentId: string, memoryId: string) => client.post<AgentMemory>(`${base(agentId)}/${memoryId}/reject`),
	update: (agentId: string, memoryId: string, body: { pinned?: boolean; confirm?: boolean }) =>
		client.patch<AgentMemory>(`${base(agentId)}/${memoryId}`, body),
	remove: (agentId: string, memoryId: string) => client.delete(`${base(agentId)}/${memoryId}`),
};
