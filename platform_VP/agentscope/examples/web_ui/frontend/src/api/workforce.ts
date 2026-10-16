import { client } from './client';
import type { EvalProgress, TestReport } from './studio';
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
	tests?: { scenario: string; expected: string }[];
	name: string;
	objective: string;
	execution_mode: 'context_only' | 'tool_backed';
	system_prompt: string;
	selected_tools: BuilderTool[];
	skill_name: string;
	skill_markdown: string;
	/** Knowledge bases of the manager attached by the Builder. */
	knowledge?: { kb_id: string; name: string; description?: string }[];
	/** Library skills reused instead of a written SKILL.md. */
	library_skills?: { skill_id: string; name: string; description?: string }[];
	evaluation: {
		passed?: boolean;
		score?: number;
		checks?: Record<string, boolean>;
		publish_blocker?: string;
		model_report?: TestReport;
		invalid_tool_ids?: string[];
		reuse_probability?: number;
	};
	reuse_agent_id: string | null;
	reuse_agent_name: string | null;
}

export interface PlannedAgent {
	name: string;
	objective: string;
	suggested_tools: BuilderTool[];
	suggested_knowledge_bases: BuilderKnowledgeBase[];
	missing_resources?: string[];
	reuse_agent_id?: string | null;
	reuse_agent_name?: string | null;
	reuse_probability?: number | null;
}

export interface BuilderProposal {
	conversation_id: string;
	proposal_id: string | null;
	revision: number;
	resources_locked?: boolean;
	resource_selection?: 'jev' | 'llm' | 'hybrid' | null;
	status: 'needs_input' | 'ready' | 'blocked' | 'published';
	assistant_message: string;
	clarification_question: string | null;
	planned_agents: PlannedAgent[];
	agents: ProposedAgent[];
	chat_model_config: ChatModelConfig;
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
	context_messages?: number;
	context_summarized?: boolean;
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

/** A ticket's room as people read it (GET /workforce/console/sessions/{id}/room). */
export interface RoomEntry {
	at: string;
	kind: string;
	sender: string;
	to: string;
	text: string;
	after: string[];
}

export interface RoomParticipant {
	agent_id: string;
	name: string;
	model: string;
	calls: number;
	input_tokens: number;
	cached_input_tokens: number;
	output_tokens: number;
}

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

export const workforceApi = {
	prepare: (
		message: string,
		chatModelConfig: ChatModelConfig,
		conversationId: string | null,
		confirmOutline = false,
		expectedRevision?: number,
	) =>
		client.post<BuilderProposal>('/workforce/console/builder/prepare', {
			message,
			chat_model_config: chatModelConfig,
			conversation_id: conversationId,
			confirm_outline: confirmOutline,
			...(expectedRevision !== undefined && { expected_revision: expectedRevision }),
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
	deleteBuilderConversation: (conversationId: string) =>
		client.delete(`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}`),
	getBuilderConversation: (conversationId: string) =>
		client.get<BuilderConversation>(
			`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}`,
		),
	builderProgress: (conversationId: string) => client.get<EvalProgress | null>(`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}/progress`),
	evaluate: (conversationId: string, proposalId: string, expectedRevision: number) => client.post<BuilderProposal>('/workforce/console/builder/evaluate', { conversation_id: conversationId, proposal_id: proposalId, expected_revision: expectedRevision }),
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
	room: (sessionId: string) =>
		client.get<RoomView>(`/workforce/console/sessions/${encodeURIComponent(sessionId)}/room`),
};
