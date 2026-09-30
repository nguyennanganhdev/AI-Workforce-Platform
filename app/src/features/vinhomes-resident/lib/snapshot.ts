import type { VhEvidenceRef } from '@/features/vinhomes-operations/types/evidence';
import type { VhIncident } from '@/features/vinhomes-operations/types/incident';
import type { VhCase, VhIssueCandidate } from '@/features/vinhomes-operations/types/intake';
import type { VhWorkOrder } from '@/features/vinhomes-operations/types/work-order';

/** The part of the operations store a resident ticket is derived from ("backend" of the demo). */
export interface OperationsSnapshot {
  cases: VhCase[];
  issueCandidates: VhIssueCandidate[];
  incidents: VhIncident[];
  workOrders: VhWorkOrder[];
  evidence: VhEvidenceRef[];
}

export interface CaseLinks {
  kase: VhCase;
  candidate: VhIssueCandidate | null;
  incident: VhIncident | null;
  /** Oldest first; the last one is the current attempt. */
  workOrders: VhWorkOrder[];
}

/** Case → candidate (following merges) → incident → work orders. */
export function linkCase(caseId: string, snapshot: OperationsSnapshot): CaseLinks | null {
  const kase = snapshot.cases.find((c) => c.id === caseId);
  if (!kase) return null;
  let candidate = snapshot.issueCandidates.find((c) => c.case_id === caseId) ?? null;
  for (let hops = 0; candidate?.merged_into_id && hops < 5; hops++) {
    const target = snapshot.issueCandidates.find((c) => c.id === candidate?.merged_into_id);
    if (!target) break;
    candidate = target;
  }
  const incident = candidate?.materialized_incident_id
    ? snapshot.incidents.find((i) => i.id === candidate?.materialized_incident_id) ?? null
    : null;
  const workOrders = incident
    ? snapshot.workOrders
        .filter((w) => w.incident_id === incident.id)
        .sort((a, b) => a.attempt_no - b.attempt_no || a.created_at.localeCompare(b.created_at))
    : [];
  return { kase, candidate, incident, workOrders };
}

/** Mã ngắn cư dân dùng để tra cứu. */
export function ticketCode(caseId: string): string {
  return `YC-${caseId.split('-').pop()}`;
}
