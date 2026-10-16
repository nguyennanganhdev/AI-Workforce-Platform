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
	error?: string;
	status?: 'passed' | 'failed' | 'error';
	error_kind?: 'environment' | 'model' | 'judge';
	test_id: string;
	scenario: string;
	expected?: string;
	latency_ms?: number;
	passed: boolean;
	checks: Array<{ name: string; passed: boolean }>;
	judge: { passed: boolean; reason: string; criteria?: Array<{ name: string; passed: boolean; reason: string }> } | null;
	answer: string;
	tool_calls: Array<{ name: string; arguments: Record<string, unknown>; executed: boolean; mode?: 'read_only' | 'simulated' | 'error'; output?: string; output_truncated?: boolean; error_code?: string; latency_ms?: number }>;
}

export interface EvalProgress {
	run_id: string;
	stage: string;
	status: 'running' | 'completed' | 'error' | 'interrupted';
	started_at: string;
	updated_at: string;
	error?: string;
	agents: Array<{ name: string; tests: Array<{ id: string; scenario: string; expected: string; safety_critical?: boolean; must_include?: string[]; must_not_include?: string[]; expect_tool?: string; status: string; step?: number; result?: TestResult }>; report?: TestReport }>;
}

export interface TestReport {
	spec_hash: string;
	ran_at: string;
	latency_ms?: number;
	total: number;
	passed: number;
	pass_rate: number;
	/** Scenarios the model could not play (no credit, bad key…): not a verdict on the agent. */
	errors?: number;
	model_error?: string | null;
	publishable: boolean;
	results: TestResult[];
	publish_blocker?: string;
	thresholds?: { minimum_tests: number; pass_rate: number; safety_pass_rate: number };
	metrics?: { evaluated: number; failed: number; environment_errors: number; model_errors: number; judge_errors: number; checks_passed: number; checks_total: number; judge_passed: number; judge_total: number; safety_passed: number; safety_total: number; tool_calls: number; tool_errors: number; real_reads: number; simulated_calls: number; p50_ms: number | null; p95_ms: number | null };
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
	status: 'active' | 'superseded' | 'rejected' | 'expired';
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

/** Outcomes, message quality and cost of the manager's partner tickets. */
export interface TicketQuality {
	days: number;
	tickets: number;
	open: number;
	needs_attention: number;
	closed_confirmed: number;
	closed_other: number;
	first_time_confirmed: number;
	messages_sent: number;
	messages_refused: number;
	refusal_rate: number;
	input_tokens: number;
	cached_input_tokens: number;
	output_tokens: number;
	cache_rate: number;
	est_cost_usd: number | null;
	cost_per_confirmed_usd: number | null;
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
	observability: (days = 30) => client.get<ModelObservability>(`${base}/observability`, { days: String(days) }),
	modelCalls: (since: string, until: string, offset = 0) =>
		client.get<{ calls: Record<string, unknown>[]; next_offset: number | null }>(`${base}/model-calls`, {
			since, until, offset: String(offset), limit: '1000',
		}),
	listAgents: () => client.get<AgentSummary[]>(`${base}/agents`),
	activity: () => client.get<AgentActivity[]>(`${base}/activity`),
	quality: (days = 30) => client.get<TicketQuality>(`${base}/quality`, { days: String(days) }),
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
	testProgress: (id: string) => client.get<EvalProgress | null>(`${agentPath(id)}/tests/progress`),
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

export interface CallMetrics {
	calls: number;
	completed_calls: number;
	failed_calls: number;
	cancelled_calls: number;
	pending_calls: number;
	input_tokens: number;
	cached_input_tokens: number;
	output_tokens: number;
	p50_ms: number | null;
	p95_ms: number | null;
	failure_rate: number | null;
	cache_hit_ratio: number | null;
	usage_complete: boolean;
	cost_complete: boolean;
	calls_missing_usage: number;
	calls_unpriced: number;
	calls_costed: number;
	calls_unknown_purpose: number;
	known_cost_usd: number;
	est_cost_usd: number | null;
}

export interface ModelObservability extends CallMetrics {
	days: number;
	window_since: string;
	by_model: (CallMetrics & { provider: string; endpoint_id: string; model: string; service_tier: string })[];
	by_purpose: (CallMetrics & { purpose: string })[];
	successful_tickets?: number;
	successful_ticket_cost_usd?: number | null;
	cost_per_successful_ticket_usd?: number | null;
	backlog: { model_calls_started: number; tickets_open?: number; tickets_need_attention?: number };
	coverage: { truncated: boolean; before_ledger_unknown: boolean; recording_failures_current_process: number; scope: string };
}
