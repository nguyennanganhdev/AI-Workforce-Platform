// Builder-owned preview views. Shared policy/HTTP integration is pending Foundation.
export interface HandlingPolicy {
	schema_version: '1';
	capabilities: string[];
	event_types: string[];
	required_facts: string[];
	completion_condition: string;
	human_confirmation: boolean;
	timeout_behavior: 'status_query' | 'needs_attention';
}

export interface Blocker {
	code: string;
	message: string;
	capability?: string | null;
}

export interface AgentProposal {
	requirement: {
		agent_key: string;
		business_profile: { objective: string };
		capabilities: { capability: string; required: boolean; reason: string }[];
		effect: 'read' | 'write' | 'external_operation';
		tracking_intent: 'create_only' | 'track_to_completion' | 'unspecified';
		policy_proposal?: HandlingPolicy | null;
		clarification_questions: string[];
	};
	selection: {
		bindings: { tool_id: string; tool_version_id: string; schema_hash: string; required_capability: string; selection_reason: string }[];
		covered: string[];
		missing_optional: string[];
		blockers: Blocker[];
		support: string[];
		tracking_channel: 'none' | 'provider_events' | 'status_query';
		completion_policy?: string | null;
	};
	reuse_decision: {
		action: 'create' | 'reuse' | 'revise' | 'resume' | 'clarify' | 'repair';
		agent_id?: string | null;
		version_id?: string | null;
		draft_id?: string | null;
		reason: string;
	};
	candidates: { agent_id: string; covered_requirements: string[]; missing_requirements: string[]; differences: string[]; blockers: string[]; reason: string }[];
	blockers: Blocker[];
	duplicate_keys: string[];
}

export interface BuildProposal {
	proposal_id: string;
	revision: number;
	status: 'needs_input' | 'ready' | 'confirmed' | 'completed_reused';
	items: AgentProposal[];
	questions: string[];
	notices: string[];
}

export interface BuilderClient {
	prepare(input: { message: string; client_message_id: string; proposal_id?: string; expected_revision?: number }, signal: AbortSignal): Promise<BuildProposal>;
	confirm(proposalId: string, revision: number, signal: AbortSignal): Promise<BuildProposal>;
	cancel(proposalId: string): Promise<void>;
}
