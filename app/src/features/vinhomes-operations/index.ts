// Vinhomes Operations Platform - Barrel Exports

// Layout
export { OperationsLayout } from './layout/operations-layout';
export { OperationsHeader } from './layout/operations-header';
export { OperationsSidebar } from './layout/operations-sidebar';

// Workspace Components
export { OperationsDashboard } from './components/operations-dashboard';
export { TriageWorkspace } from './components/triage-workspace';
export { IncidentsWorkspace } from './components/incidents-workspace';
export { KanbanBoard } from './components/kanban-board';
export { WorkOrderTable } from './components/work-order-table';
export { EvidenceGallery } from './components/evidence-gallery';
export { QcWorkspace } from './components/qc-workspace';
export { ApprovalQueue } from './components/approval-queue';
export { SanitationWorkspace } from './components/sanitation-workspace';

// Modals & Dialogs
export { WorkOrderDialog } from './components/work-order-dialog';
export { EvidenceModal } from './components/evidence-modal';
export { QcInspectorModal } from './components/qc-inspector-modal';

// Hooks
export { useOperationsData } from './hooks/use-operations-data';
export { useApprovalQueue } from './hooks/use-approval-queue';
export { useIncidentDetail } from './hooks/use-incident-detail';
export { useQcWorkflow } from './hooks/use-qc-workflow';
export { useTaskBoard } from './hooks/use-task-board';

// Types & Mock
export * from './types';
export * from './mock';
