/**
 * Canonical WorkOrder types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 9: vh_work_order)
 */

export type WorkOrderStatus =
  | 'OPEN'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'BLOCKED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export const ALLOWED_WORK_ORDER_TRANSITIONS: Record<WorkOrderStatus, WorkOrderStatus[]> = {
  OPEN: ['ASSIGNED', 'CANCELLED'],
  ASSIGNED: ['IN_PROGRESS', 'CANCELLED'],
  IN_PROGRESS: ['BLOCKED', 'COMPLETED', 'FAILED'],
  BLOCKED: ['IN_PROGRESS', 'CANCELLED'],
  COMPLETED: [], // Trạng thái cuối của thi công, chuyển sang chờ QC nghiệm thu
  FAILED: [],
  CANCELLED: [],
};

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
  contractor_organization_id?: string | null;
  status: WorkOrderStatus;
  attempt_no: number;
  redo_of_work_order_id: string | null;
  checklist_version_id: string | null;
  execution_started_at: string | null;
  execution_completed_at: string | null;
  blocked_reason?: string | null;
  contractor_status?: 'PENDING_ACCEPTANCE' | 'ACCEPTED' | 'REJECTED';
  contractor_reject_reason?: string;
  contractor_assigned_worker?: string;
  materials_used?: Array<{ part_name: string; quantity: number; unit: string }>;
  result: Record<string, unknown> | null;
  version: number;
  created_at: string;
  updated_at: string;
}
