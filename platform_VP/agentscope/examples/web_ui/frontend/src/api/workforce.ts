import { client } from './client';
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
	peer_dependencies?: string[];
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
	chat_model_config: ChatModelConfig | null;
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

export interface AgentToolSettings {
	agent_id: string;
	selected_tool_ids: string[];
	selected_knowledge_base_ids: string[];
	knowledge_bases: BuilderKnowledgeBase[];
	/** How each tool runs, keyed by runtime name; absent = platform default. */
	tool_policies?: Record<string, 'auto' | 'ask' | 'deny'>;
	mcps: Array<{
		mcp_id: string;
		mcp_name: string;
		tools: BuilderTool[];
	}>;
}

/** One case of a Builder behavioural evaluation. */
export interface BuilderEvalCase {
	id: string;
	scenario: string;
	expected: string;
	expect_tool: string;
	safety: boolean;
	status: 'pending' | 'running' | 'checking' | 'judging' | 'passed' | 'failed' | 'error';
	result?: {
		passed: boolean;
		checks?: Array<{ name: string; passed: boolean }>;
		criteria?: Array<{ name: string; passed: boolean; reason: string }>;
		summary?: string;
		answer?: string;
		tool_calls?: Array<{ name: string; mode: string }>;
		latency_ms?: number;
		error?: string;
	};
}

export interface BuilderEvalAgent {
	name: string;
	stage: 'pending' | 'generating' | 'running' | 'completed' | 'error';
	error?: string;
	tests: BuilderEvalCase[];
	report?: {
		total: number;
		passed: number;
		errors: number;
		pass_rate: number;
		advisory: boolean;
	};
	finished_at?: string;
}

/** A Builder evaluation run: live progress, or the result saved with the proposal. */
export interface BuilderEval {
	status: 'idle' | 'running' | 'completed' | 'error';
	run_id?: string;
	proposal_id?: string;
	revision?: number;
	started_at?: string;
	updated_at?: string;
	agents: BuilderEvalAgent[];
}

export interface LeaderSession {
	agent_id: string;
	session_id: string | null;
	name: string;
	chat_model_config?: ChatModelConfig | null;
}

export const workforceApi = {
	prepare: (
		message: string,
		chatModelConfig: ChatModelConfig,
		conversationId: string | null,
		confirmOutline = false,
		expectedRevision?: number,
	) =>
		client.post<BuilderProposal | BuilderConversation>('/workforce/console/builder/prepare', {
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
	evaluate: (conversationId: string, proposalId: string, expectedRevision: number) =>
		client.post<BuilderEval>('/workforce/console/builder/evaluate', {
			conversation_id: conversationId,
			proposal_id: proposalId,
			expected_revision: expectedRevision,
		}),
	getBuilderEval: (conversationId: string) =>
		client.get<BuilderEval>(
			`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}/eval`,
			undefined,
			{ silent: true },
		),
	listBuilderConversations: () =>
		client.get<BuilderConversationSummary[]>('/workforce/console/builder/conversations'),
	getBuilderConversation: (conversationId: string) =>
		client.get<BuilderConversation>(
			`/workforce/console/builder/conversations/${encodeURIComponent(conversationId)}`,
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
	createTicket: () => client.post<LeaderSession & { session_id: string }>('/workforce/console/leader/tickets'),
};
