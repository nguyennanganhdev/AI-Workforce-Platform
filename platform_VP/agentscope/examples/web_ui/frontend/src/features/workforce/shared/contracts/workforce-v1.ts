// Stable Workforce v1 boundary types. Internal routing fields are deliberately absent
// from public command bodies. Keep this file aligned with the generated JSON Schema.

export const WORKFORCE_CONTRACT_VERSION = "1" as const;

export type ManagerRole = "AREA_MANAGER";
export type PartnerCommandType = "start_workflow" | "workflow_reply";
export type RequestStatus =
  | "accepted"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "blocked";
export type WorkflowState =
  | "accepted"
  | "active"
  | "waiting_external_event"
  | "awaiting_user"
  | "awaiting_approval"
  | "awaiting_confirmation"
  | "needs_attention"
  | "blocked_authorization"
  | "blocked_route_changed"
  | "closed";
export type NextAction =
  | "none"
  | "submit_reply"
  | "submit_approval"
  | "watch_request"
  | "watch_events"
  | "confirm_close"
  | "resolve_attention";

export interface Scope {
  readonly tenant_id: string;
  readonly domain_id: string;
  readonly area_id: string;
  readonly manager_account_id: string;
}

export interface PartnerRequestEnvelope {
  readonly schema_version: "1";
  readonly command_type: PartnerCommandType;
  readonly external_request_id: string;
  readonly external_management_ref: string;
  readonly external_user_id: string;
  readonly external_ticket_id?: string | null;
  readonly external_conversation_id: string;
  readonly workflow_id?: string | null;
  readonly residence_id?: string | null;
  readonly timezone?: string | null;
  readonly message: { readonly type: "text"; readonly text: string };
}

export interface AssistantMessage {
  readonly message_id: string;
  readonly workflow_id: string;
  readonly sender: "assistant";
  readonly text: string;
  readonly created_at: string;
}

export interface InboundReceipt {
  readonly request_id: string;
  readonly request_status: RequestStatus;
  readonly external_ticket_id?: string | null;
  readonly conversation_id: string;
  readonly workflow_id: string;
  readonly ticket_id?: string | null;
  readonly workflow_state: WorkflowState;
  readonly next_action: NextAction;
  readonly workflow_revision: number;
  readonly result?: {
    readonly messages: readonly AssistantMessage[];
    readonly data: Readonly<Record<string, unknown>>;
  } | null;
  readonly accepted_at: string;
  readonly completed_at?: string | null;
  readonly status_url: string;
  readonly conversation_url: string;
  readonly event_stream_url: string;
}

export interface CloseWorkflowCommand {
  readonly schema_version: "1";
  readonly external_request_id: string;
  readonly external_user_id: string;
  readonly external_ticket_id?: string | null;
  readonly external_conversation_id: string;
  readonly expected_revision: number;
  readonly reason: string;
  readonly stop_tracking_only: boolean;
}

export interface ConversationEvent {
  readonly schema_version: "1";
  readonly event_id: string;
  readonly sequence: number;
  readonly event_type: string;
  readonly occurred_at: string;
  readonly recorded_at: string;
  readonly conversation_id: string;
  readonly external_ticket_id?: string | null;
  readonly external_conversation_id: string;
  readonly external_user_id: string;
  readonly workflow_id?: string | null;
  readonly ticket_id?: string | null;
  readonly causation_id?: string | null;
  readonly payload: Readonly<Record<string, unknown>>;
}

export interface ProviderEventEnvelope {
  readonly schema_version: "1";
  readonly external_event_id: string;
  readonly external_job_id?: string | null;
  readonly client_reference?: string | null;
  readonly event_type: string;
  readonly provider_version?: number | null;
  readonly occurred_at: string;
  readonly data: Readonly<Record<string, unknown>>;
}

export type WorkforceErrorCode =
  | "ROUTE_NOT_AUTHORIZED"
  | "EXTERNAL_TICKET_REQUIRED"
  | "TICKET_ALREADY_BOUND"
  | "CONVERSATION_ALREADY_BOUND"
  | "WORKFLOW_BINDING_MISMATCH"
  | "WORKFLOW_REFERENCE_REQUIRED"
  | "WORKFLOW_CLOSED"
  | "WORKFLOW_NOT_READY_TO_CLOSE"
  | "IDEMPOTENCY_CONFLICT"
  | "REVISION_CONFLICT"
  | "EVENT_ID_CONFLICT"
  | "EVENT_CURSOR_EXPIRED";
