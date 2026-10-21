import { client } from './client';

/** A test case saved from a conversation or typed by hand. */
export interface AgentEvalCase {
	id: string;
	created_at: string;
	scenario: string;
	expected: string;
	expect_tool: string;
	/** Real results of read tools from the saved turn, by tool name. */
	recorded: Record<string, string[]>;
	source_session_id: string | null;
	source_message_id: string | null;
}

export interface AgentEvalTest {
	case_id: string;
	scenario: string;
	expected: string;
	status: 'pending' | 'running' | 'checking' | 'judging' | 'passed' | 'failed' | 'error';
	result?: {
		passed: boolean;
		summary?: string;
		answer?: string;
		error?: string;
		criteria?: { name: string; passed: boolean; reason: string }[];
		tool_calls?: { name: string; mode: string }[];
	};
}

/** One replay of every saved case; `version` hashes the agent's configuration. */
export interface AgentEvalRun {
	id: string;
	created_at: string;
	version: string;
	model: string;
	status: 'running' | 'completed' | 'failed';
	started_at: string;
	finished_at: string | null;
	tests: AgentEvalTest[];
	report: { total: number; passed: number; errors: number; pass_rate: number } | null;
	error: string | null;
	comparison?: {
		run_id: string;
		version: string | null;
		cases: { case_id: string; scenario: string; before: string | null; after: string; change: 'same' | 'better' | 'worse' | 'new' }[];
	};
}

export interface CreateAgentEvalCase {
	expected: string;
	scenario?: string;
	session_id?: string;
	session_agent_id?: string;
	message_id?: string;
}

const base = (agentId: string) => `/agent/${agentId}/eval`;

export const agentEvalApi = {
	listCases: (agentId: string) => client.get<AgentEvalCase[]>(`${base(agentId)}/cases`),
	createCase: (agentId: string, body: CreateAgentEvalCase) =>
		client.post<AgentEvalCase>(`${base(agentId)}/cases`, body),
	deleteCase: (agentId: string, caseId: string) => client.delete(`${base(agentId)}/cases/${caseId}`),
	startRun: (agentId: string) => client.post<AgentEvalRun>(`${base(agentId)}/runs`),
	listRuns: (agentId: string) => client.get<AgentEvalRun[]>(`${base(agentId)}/runs`),
	getRun: (agentId: string, runId: string, compareTo?: string) =>
		client.get<AgentEvalRun>(
			`${base(agentId)}/runs/${runId}`,
			compareTo ? { compare_to: compareTo } : undefined,
			{ silent: true },
		),
};
