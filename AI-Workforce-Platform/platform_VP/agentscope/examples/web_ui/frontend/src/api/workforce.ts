import { ApiError, client } from './client';
import type { ChatModelConfig } from './types';

export interface BuilderTool {
	id: string;
	mcp_id: string;
	mcp_name: string;
	tool_name: string;
	description: string;
}

export interface BuilderKnowledgeBase {
	id: string;
	name: string;
	description: string;
}

export interface ProposedAgent {
	name: string;
	objective: string;
	execution_mode: 'context_only' | 'tool_backed';
	system_prompt: string;
	selected_tools: BuilderTool[];
	selected_knowledge_bases: BuilderKnowledgeBase[];
	skill_name: string;
	skill_markdown: string;
	evaluation: {
		passed?: boolean;
		score?: number;
		checks?: Record<string, boolean>;
		invalid_tool_ids?: string[];
		reuse_similarity?: number;
	};
	reuse_agent_id: string | null;
	reuse_agent_name: string | null;
}

export interface PlannedAgent {
	name: string;
	objective: string;
	required_capabilities: string[];
	request_modes: Array<'advice' | 'lookup' | 'action'>;
	effect: 'read' | 'write' | 'external_operation' | null;
	suggested_tools: BuilderTool[];
	suggested_knowledge_bases: BuilderKnowledgeBase[];
	reuse_agent_id: string | null;
	reuse_agent_name: string | null;
}

export interface BuilderProposal {
	conversation_id: string;
	proposal_id: string | null;
	revision: number;
	status: 'needs_input' | 'ready' | 'blocked' | 'published';
	assistant_message: string;
	clarification_question: string | null;
	planned_agents: PlannedAgent[];
	agents: ProposedAgent[];
	chat_model_config: ChatModelConfig;
	builder_chat_model_config: ChatModelConfig | null;
	fixed_config: {
		ownership: string;
		context_config: Record<string, unknown>;
		react_config: Record<string, unknown>;
		runtime_note: string;
	};
}

export interface BuilderMessage {
	role: 'user' | 'builder';
	text: string;
}

export interface BuilderConversationSummary {
	conversation_id: string;
	title: string;
	updated_at: string;
}

export interface BuilderConversation {
	conversation_id: string;
	title: string;
	messages: BuilderMessage[];
	proposal: BuilderProposal | null;
	progress: BuilderProgress | null;
}

export interface BuilderProgress {
	stage: 'generating' | 'validating' | 'repairing';
	completed: number;
	total: number;
}

export interface WorkforceAgent {
	agent_id: string;
	name: string;
	objective: string;
	execution_mode: 'context_only' | 'tool_backed' | null;
	lifecycle_state: 'draft' | 'published' | 'withdrawn';
	tool_count: number;
	knowledge_base_count: number;
	evaluation: Record<string, unknown>;
}

/** A normalized room event consumed by the optional team activity UI. */
export interface RoomEntry {
	at: string;
	kind: string;
	sender: string;
	to: string;
	text: string;
	after: string[];
}

/** Aggregate usage for one participant in a workforce room. */
export interface RoomParticipant {
	agent_id: string;
	name: string;
	model: string;
	calls: number;
	input_tokens: number;
	cached_input_tokens: number;
	output_tokens: number;
}

/** Optional room projection used by the new team conversation components. */
export interface RoomView {
	participants: RoomParticipant[];
	timeline: RoomEntry[];
	packet_tokens: number;
	peak_packet_tokens: number;
	packet_budget: number;
}

export interface AgentToolSettings {
	agent_id: string;
	selected_tool_ids: string[];
	selected_knowledge_base_ids: string[];
	knowledge_bases: BuilderKnowledgeBase[];
	mcps: Array<{
		mcp_id: string;
		mcp_name: string;
		tools: BuilderTool[];
	}>;
}

export interface LeaderSession {
	agent_id: string;
	session_id: string;
	name: string;
}

let roomUnavailable = false;

export const workforceApi = {
	prepare: (
		message: string,
		chatModelConfig: ChatModelConfig,
		builderChatModelConfig: ChatModelConfig | null,
		conversationId: string | null,
		confirmOutline = false,
	) =>
		client.post<BuilderProposal>('/workforce/console/builder/prepare', {
			message,
			chat_model_config: chatModelConfig,
			builder_chat_model_config: builderChatModelConfig,
			conversation_id: conversationId,
			confirm_outline: confirmOutline,
		}),
	publish: (
		conversationId: string,
		proposalId: string,
		expectedRevision: number,
		knowledgeBaseSelections: string[][],
	) =>
		client.post<{
			agents: Array<{
				agent_id: string;
				session_id: string | null;
				name: string;
				reused: boolean;
			}>;
		}>('/workforce/console/builder/publish', {
			conversation_id: conversationId,
			proposal_id: proposalId,
			expected_revision: expectedRevision,
			knowledge_base_selections: knowledgeBaseSelections,
		}),
	listBuilderConversations: () =>
		client.get<BuilderConversationSummary[]>('/workforce/console/builder/conversations'),
	getBuilderConversation: (conversationId: string, silent = false) =>
		client.get<BuilderConversation>(
			`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}`,
			undefined,
			{ silent },
		),
	deleteBuilderConversation: (conversationId: string) =>
		client.delete(
			`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}`,
		),
	listAgents: () => client.get<WorkforceAgent[]>('/workforce/console/agents'),
	getAgentTools: (agentId: string) =>
		client.get<AgentToolSettings>(
			`/workforce/console/agents/${encodeURIComponent(agentId)}/tools`,
		),
	updateAgentTools: (
		agentId: string,
		selectedToolIds: string[],
		selectedKnowledgeBaseIds: string[],
	) =>
		client.patch<AgentToolSettings>(
			`/workforce/console/agents/${encodeURIComponent(agentId)}/tools`,
			{
				selected_tool_ids: selectedToolIds,
				selected_knowledge_base_ids: selectedKnowledgeBaseIds,
			},
		),
	setLifecycle: (agentId: string, state: 'draft' | 'published') =>
		client.post<WorkforceAgent>(
			`/workforce/console/agents/${encodeURIComponent(agentId)}/lifecycle`,
			{ state },
		),
	bootstrapLeader: () => client.get<LeaderSession>('/workforce/console/leader/bootstrap'),
	createTicket: () => client.post<LeaderSession>('/workforce/console/leader/tickets'),
	// Optional extension: disabled for the stock FastAPI backend.
	room: async (sessionId: string): Promise<RoomView | null> => {
		if (import.meta.env.VITE_ENABLE_WORKFORCE_ROOM !== 'true' || roomUnavailable) return null;
		try {
			return await client.get<RoomView>(
				`/workforce/console/sessions/${encodeURIComponent(sessionId)}/room`,
				undefined,
				{ silent: true },
			);
		} catch (error) {
			if (error instanceof ApiError && error.status === 404) {
				roomUnavailable = true;
				return null;
			}
			throw error;
		}
	},
};
