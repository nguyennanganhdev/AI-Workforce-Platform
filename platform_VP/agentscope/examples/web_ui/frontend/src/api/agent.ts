import { client } from './client';
import type {
	AgentListResponse,
	AgentView,
	AgentSchemaV2Response,
	CreateAgentRequest,
	CreateAgentResponse,
	UpdateAgentRequest,
} from './types';

export type ToolPolicy = 'auto' | 'ask' | 'deny';

export const agentApi = {
	list: () => client.get<AgentListResponse>('/agent/'),

	getSchema: () => client.get<AgentSchemaV2Response>('/agent/schema/v2'),

	create: (body: CreateAgentRequest, options?: { silent?: boolean }) =>
		client.post<CreateAgentResponse>('/agent/', body, undefined, options),

	update: (agentId: string, body: UpdateAgentRequest, options?: { silent?: boolean }) =>
		client.patch<AgentView>(`/agent/${agentId}`, body, undefined, options),

	delete: (agentId: string) => client.delete(`/agent/${agentId}`),

	/**
	 * How one MCP tool of the agent runs: `auto` without asking, `ask`
	 * always first, `deny` never; `null` returns it to the platform's default
	 * (sensitive actions ask). Only an editor of the agent may change it.
	 */
	setToolPolicy: (agentId: string, toolName: string, policy: ToolPolicy | null) =>
		client.post<{ tool_policies: Record<string, ToolPolicy> }>(
			`/agent/${encodeURIComponent(agentId)}/tool-policies`,
			{ tool_name: toolName, policy },
		),
};
