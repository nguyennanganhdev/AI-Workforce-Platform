import { useMemo } from 'react';
import { useOperationsData } from './use-operations-data';
import { MOCK_MESSAGES, MOCK_BUSINESS_EVENTS } from '../mock';
import type { VhMessage, VhBusinessEvent } from '../types/message';

export function useIncidentDetail(incidentId: string | undefined) {
  const { incidents, tasks, workOrders, evidence, approvals, qcResults } = useOperationsData();

  const incident = useMemo(() => {
    if (!incidentId) return null;
    return incidents.find((inc) => inc.id === incidentId) || null;
  }, [incidents, incidentId]);

  const relatedTasks = useMemo(() => {
    if (!incidentId) return [];
    return tasks.filter((t) => t.incident_id === incidentId);
  }, [tasks, incidentId]);

  const relatedWorkOrders = useMemo(() => {
    if (!incidentId) return [];
    return workOrders.filter((wo) => wo.incident_id === incidentId);
  }, [workOrders, incidentId]);

  const relatedEvidence = useMemo(() => {
    if (!incidentId) return [];
    return evidence.filter((e) => e.incident_id === incidentId);
  }, [evidence, incidentId]);

  const relatedApprovals = useMemo(() => {
    if (!incidentId) return [];
    return approvals.filter((a) => a.action_request?.incident_id === incidentId);
  }, [approvals, incidentId]);

  const messages = useMemo(() => {
    if (!incidentId) return [];
    return MOCK_MESSAGES.filter((m: VhMessage) => m.incident_id === incidentId);
  }, [incidentId]);

  const timelineEvents = useMemo(() => {
    if (!incidentId) return [];
    return MOCK_BUSINESS_EVENTS.filter((e: VhBusinessEvent) => e.incident_id === incidentId);
  }, [incidentId]);

  return {
    incident,
    tasks: relatedTasks,
    workOrders: relatedWorkOrders,
    evidence: relatedEvidence,
    approvals: relatedApprovals,
    qcResults,
    messages,
    timelineEvents,
  };
}
