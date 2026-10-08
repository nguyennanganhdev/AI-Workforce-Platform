/**
 * Canonical Action, Rule and Approval types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 8)
 */

export type RequestedByType =
  | 'HUMAN'
  | 'SYSTEM'
  | 'AUTOMATION'
  | 'AGENT'
  | 'EXTERNAL_SERVICE';

export type ActionType =
  | 'ASSIGN_WORK_ORDER'
  | 'DISPATCH_EMERGENCY_MEP'
  | 'APPROVE_BUDGET_DISBURSEMENT'
  | 'PURCHASE_MATERIAL'
  | 'SHUT_OFF_WATER_SUPPLY'
  | 'ESCALATE_TO_BOARD'
  | 'EXECUTE_CLEANING_PLAN';

export type RuleDecision = 'ALLOW' | 'REQUIRE_APPROVAL' | 'DENY';

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';

export interface VhActionRequest {
  id: string;
  incident_id: string;
  task_id: string | null;
  requested_by_type: RequestedByType;
  requested_by_id: string;
  requested_by_name?: string;
  requested_by_version: string | null;
  action_type: ActionType;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown>;
  payload_hash: string;
  status: 'PROPOSED' | 'EVALUATED' | 'APPROVED' | 'REJECTED' | 'EXECUTED';
  version: number;
  correlation_id: string;
  created_at: string;
}

export interface VhRuleEvaluation {
  id: string;
  action_request_id: string;
  decision: RuleDecision;
  reason_code: string;
  rule_version: string;
  evaluated_at: string;
  correlation_id: string;
}

export interface VhActionApproval {
  id: string;
  action_request_id: string;
  action_payload_hash: string;
  status: ApprovalStatus;
  requested_by_id: string;
  reviewer_id: string | null;
  reviewer_name?: string;
  expires_at: string;
  decided_at: string | null;
  reason: string | null;
  version: number;
  // Denormalized fields for quick UI presentation
  action_request?: VhActionRequest;
  rule_evaluation?: VhRuleEvaluation;
  estimated_cost_vnd?: number;
  urgency_level?: 'NORMAL' | 'HIGH' | 'CRITICAL';
}

export interface VhExecutionGrant {
  id: string;
  action_request_id: string;
  approval_id: string;
  granted_to: string;
  allowed_action_type: ActionType;
  payload_hash: string;
  status: 'ACTIVE' | 'CONSUMED' | 'REVOKED';
  consumed_by_work_order_id: string | null;
  granted_at: string;
  expires_at: string;
}

