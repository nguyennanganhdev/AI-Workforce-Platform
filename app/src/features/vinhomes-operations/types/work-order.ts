/**
 * Canonical WorkOrder types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 9: vh_work_order)
 */

export type WorkOrderStatus =
  | 'OPEN'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type ExecutorType = 'STAFF' | 'CONTRACTOR' | 'ROBOT' | 'AUTOMATION';

export interface VhWorkOrder {
  id: string;
  incident_id: string;
  task_id: string;
  action_request_id: string | null;
  executor_type: ExecutorType;
  executor_id: string | null;
  executor_name?: string;
  executor_phone?: string;
  executor_avatar?: string;
  status: WorkOrderStatus;
  attempt_no: number;
  redo_of_work_order_id: string | null;
  checklist_version_id: string | null;
  execution_started_at: string | null;
  execution_completed_at: string | null;
  result: Record<string, unknown> | null;
  version: number;
  created_at: string;
  updated_at: string;
}
