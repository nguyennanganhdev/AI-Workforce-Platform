// Canonical vocabularies from docx/02, sections 6, 7 and 9.
// These types do not authorize transitions; guards belong in domain use cases.
export type IncidentStatus = 'NEW' | 'OPEN' | 'RESOLVED' | 'CLOSED';
export type TaskStatus = 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'BLOCKED' | 'DONE' | 'CANCELLED';
export type WorkOrderStatus = 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
