import { client } from './client';

/** Agent Spec — mirrors `agentscope.app._agent_spec.AgentSpec`. */
export type SpecSource = 'manager' | 'builder' | 'agent' | 'template' | 'legacy';

export interface SpecRule {
	id: string;
	text: string;
	level: 'must' | 'should';
	source: SpecSource;
	locked: boolean;
	learned_from: string;
}

export interface SpecEscalation {
	id: string;
	when: string;
	to: string;
}

export interface SpecTool {
	tool_id: string;
	mcp_id: string;
	mcp_name: string;
	tool_name: string;
	use_when: string;
	requires_consent: boolean;
	read_only: boolean;
}

export interface SpecKnowledge {
	kb_id: string;
	name: string;
	use_for: string;
}

export interface SpecSkill {
	skill_id: string;
	name: string;
	use_when: string;
}

export interface SpecCollaborator {
	id: string;
	capability: string;
	ask_when: string;
}

export interface SpecExample {
	id: string;
	user: string;
	agent: string;
}

export interface SpecTest {
	id: string;
	scenario: string;
	expected: string;
	must_include: string[];
	must_not_include: string[];
	expect_tool: string;
}

export interface AgentSpec {
	name: string;
	description: string;
	audience: string;
	language: 'auto' | 'vi' | 'en';
	tone: string;
	goal: string;
	scope_in: string[];
	scope_out: string[];
	rules: SpecRule[];
	escalation: SpecEscalation[];
	tools: SpecTool[];
	knowledge: SpecKnowledge[];
	skills: SpecSkill[];
	collaborates: SpecCollaborator[];
	examples: SpecExample[];
	tests: SpecTest[];
	extra_instructions: string;
	prompt_override: string | null;
	model_tier: 'standard' | 'strong';
	memory_enabled: boolean;
	self_improve: boolean;
}

export interface SpecChange {
	field: string;
	action: 'changed' | 'added' | 'removed';
	before: unknown;
	after: unknown;
}

export interface TestResult {
	test_id: string;
	scenario: string;
	expected?: string;
	passed: boolean;
	checks: Array<{ name: string; passed: boolean }>;
	judge: { passed: boolean; reason: string } | null;
	answer: string;
	tool_calls: Array<{ name: string; arguments: Record<string, unknown>; executed: boolean }>;
}

export interface TestReport {
	spec_hash: string;
	ran_at: string;
	total: number;
	passed: number;
	pass_rate: number;
	/** Scenarios the model could not play (no credit, bad key…): not a verdict on the agent. */
	errors?: number;
	model_error?: string | null;
	publishable: boolean;
	results: TestResult[];
}

export interface AgentVersion {
	version: number;
	author: string;
	note: string;
	created_at: string;
	evaluation: { passed?: boolean; score?: number; total?: number } | null;
}

export interface AgentSummary {
	agent_id: string;
	name: string;
	description: string;
	lifecycle_state: 'draft' | 'published' | 'withdrawn';
	published_version: number;
	has_draft: boolean;
	tool_count: number;
	rule_count: number;
	learned_rule_count: number;
	test_count: number;
	last_test: {
		pass_rate: number;
		passed: number;
		total: number;
		ran_at: string;
		publishable: boolean;
		errors?: number;
	} | null;
}

export interface AgentDetail {
	agent_id: string;
	lifecycle_state: 'draft' | 'published' | 'withdrawn';
	published_version: number;
	published: AgentSpec | null;
	draft: AgentSpec;
	draft_meta: { author?: string; note?: string; updated_at?: string };
	changes: SpecChange[];
	rendered_prompt: string;
	versions: AgentVersion[];
	last_test: TestReport | null;
	can_publish: boolean;
	publish_blocker: string;
}

export interface CopilotResult {
	reply: { assistant_message: string; questions: string[] };
	changes: SpecChange[];
	agent: AgentDetail;
}

export interface ComposeResult extends CopilotResult {
	plan: { mode: 'single' | 'team'; reason: string; agents: { name: string; role: string }[] } | null;
	agents: AgentDetail[];
	test_reports: Record<string, TestReport>;
}

export interface CatalogTool {
	tool_id: string;
	mcp_id: string;
	mcp_name: string;
	tool_name: string;
	description: string;
	read_only: boolean;
}

export interface AgentTemplate {
	id: string;
	domain: string;
	title: string;
	spec: AgentSpec;
}

export interface AgentMemory {
	id: string;
	agent_id: string;
	kind: 'lesson' | 'fact' | 'preference';
	content: string;
	status: 'active' | 'superseded' | 'rejected';
	source_ticket: string;
	source_event_ids: string[];
	confidence: number;
	uses: number;
	supersedes: string | null;
	created_at: string;
	updated_at: string;
}

export interface AgentActivity {
	agent_id: string;
	name: string;
	role: 'leader' | 'business';
	model_tier: string;
	tickets: number;
	/** A reply may take several model calls; its tokens cover them all. */
	replies: number;
	input_tokens: number;
	cached_input_tokens: number;
	output_tokens: number;
	last_at: string | null;
}

export interface PartnerRoute {
	route_id: string;
	partner_client_id: string;
	external_management_ref: string;
	status: 'pending_confirmation' | 'active' | 'revoked';
	revision: number;
	created_at: string;
}

const base = '/workforce/console/studio';
const agentPath = (id: string) => `${base}/agents/${encodeURIComponent(id)}`;

export const studioApi = {
	listAgents: () => client.get<AgentSummary[]>(`${base}/agents`),
	activity: () => client.get<AgentActivity[]>(`${base}/activity`),
	getAgent: (id: string) => client.get<AgentDetail>(agentPath(id)),
	create: (body: { template_id?: string; clone_from?: string; spec?: AgentSpec }) =>
		client.post<AgentDetail>(`${base}/agents`, body),
	compose: (description: string, templateId?: string, options: { allowTeam?: boolean; runTests?: boolean } = {}) =>
		client.post<ComposeResult>(`${base}/agents/compose`, {
			description,
			template_id: templateId,
			allow_team: options.allowTeam ?? false,
			run_tests: options.runTests ?? false,
		}),
	saveDraft: (id: string, spec: AgentSpec, note = '') =>
		client.put<AgentDetail>(`${agentPath(id)}/draft`, { spec, note }),
	discardDraft: (id: string) => client.delete<AgentDetail>(`${agentPath(id)}/draft`),
	copilot: (id: string, message: string) =>
		client.post<CopilotResult>(`${agentPath(id)}/copilot`, { message }),
	runTests: (id: string) => client.post<TestReport>(`${agentPath(id)}/tests/run`),
	publish: (id: string, note: string) =>
		client.post<AgentDetail>(`${agentPath(id)}/publish`, { note }),
	rollback: (id: string, version: number) =>
		client.post<AgentDetail>(`${agentPath(id)}/rollback`, { version }),
	withdraw: (id: string) => client.post<AgentDetail>(`${agentPath(id)}/withdraw`),
	remove: (id: string) => client.delete(agentPath(id)),
	templates: () => client.get<AgentTemplate[]>(`${base}/templates`),
	tools: () => client.get<CatalogTool[]>(`${base}/tools`),
	memories: (id: string) => client.get<AgentMemory[]>(`${agentPath(id)}/memories`),
	partnerRoutes: () =>
		client.get<PartnerRoute[]>('/workforce/v1/manager/partner-routes', undefined, { silent: true }),
	grantPartnerRoute: (partnerClientId: string, externalManagementRef: string) =>
		client.post<PartnerRoute>('/workforce/v1/manager/partner-routes', {
			partner_client_id: partnerClientId,
			external_management_ref: externalManagementRef,
		}),
	retireMemory: (id: string, memoryId: string) =>
		client.post<AgentMemory>(`${agentPath(id)}/memories/${encodeURIComponent(memoryId)}/retire`),
};
