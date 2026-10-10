/** Lifecycle feature response types until Foundation exports these shared DTOs. */
export interface AgentManifest {
	schema_version: string;
	business_profile: Record<string, unknown>;
	spec: {
		agent_key: string;
		name: string;
		system_prompt: string;
		model_config_ref: Record<string, unknown>;
		[key: string]: unknown;
	};
	async_policy_ref?: string;
	protocol_snapshot_hashes: string[];
}
export interface AgentDefinition {
	agent_id: string;
	name: string;
	status: string;
	revision: number;
	active_version_id?: string;
	draft_id?: string;
	business_profile: { capabilities: string[] };
}
export interface AgentDraft {
	draft_id: string;
	agent_id: string;
	revision: number;
	manifest: AgentManifest;
	manifest_hash: string;
	reuse_decision: Record<string, unknown>;
	source_version_id?: string;
}
export interface PublishedVersion {
	version_id: string;
	agent_id: string;
	manifest: AgentManifest;
	manifest_hash: string;
	published_at: string;
}
export interface EvaluationCase {
	case_id: string;
	status: string;
	metrics: Record<string, unknown>;
	hard_gate_failures: string[];
	error_code?: string;
}
export interface EvaluationRecord {
	snapshot: { draft_id: string; draft_revision: number; manifest_hash: string };
	report: {
		evaluation_id: string;
		status: string;
		suite_version: string;
		metrics: Record<string, unknown>;
		hard_gate_failures: string[];
		cases: EvaluationCase[];
	};
}
export interface Batch {
	batch_id: string;
	revision: number;
	status: string;
	items: {
		item_id: string;
		agent_key: string;
		status: string;
		draft_id?: string;
		evaluation_id?: string;
		reuse_agent_id?: string;
	}[];
}
export interface PublishSelection {
	draft_id: string;
	expected_revision: number;
	evaluation_id: string;
	manifest_hash: string;
}
export interface Page<T> { items: T[]; next_cursor?: string }
