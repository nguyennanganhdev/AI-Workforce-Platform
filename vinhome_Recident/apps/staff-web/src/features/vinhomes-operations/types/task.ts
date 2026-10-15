/**
 * Canonical Task types from docx/02_VINHOMES_DOMAIN_ERD.md (Section 7: vh_task & vh_task_dependency)
 */
import type { CleaningPlan } from './cleaning-plan';

export type TaskStatus =
  | 'OPEN'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'BLOCKED'
  | 'DONE'
  | 'CANCELLED';

export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';

export type DomainType =
  | 'TECHNICAL'
  | 'SANITATION'
  | 'LANDSCAPE'
  | 'SECURITY'
  | 'MEP'
  | 'ELEVATOR'
  | 'GENERAL';

export type AssigneeType = 'STAFF' | 'CONTRACTOR' | 'AGENT' | 'AUTOMATION';

export interface VhTask<TDomainData = CleaningPlan | Record<string, unknown>> {
  id: string;
  incident_id: string;
  title: string;
  domain_type: DomainType;
  domain_data: TDomainData | null;
  domain_schema_version: number;
  assignee_type: AssigneeType;
  assignee_id: string | null;
  assignee_name?: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface VhTaskDependency {
  task_id: string;
  depends_on_task_id: string;
  dependency_type: 'FINISH_TO_START' | 'START_TO_START';
  required: boolean;
  created_at: string;
}
