import { useMemo } from 'react';
import { useOperationsData } from './use-operations-data';
import { MOCK_CHECKLIST_VERSIONS } from '../mock/checklists';
import type { VhChecklistVersion } from '../types/qc';

export function useQcWorkflow(workOrderId: string | undefined) {
  const { workOrders, evidence, qcResults, submitQcInspection } = useOperationsData();

  const workOrder = useMemo(() => {
    if (!workOrderId) return null;
    return workOrders.find((w) => w.id === workOrderId) || null;
  }, [workOrders, workOrderId]);

  const checklistVersion: VhChecklistVersion | null = useMemo(() => {
    if (!workOrder?.checklist_version_id) {
      return MOCK_CHECKLIST_VERSIONS[0]; // default MEP checklist
    }
    return (
      MOCK_CHECKLIST_VERSIONS.find((v: VhChecklistVersion) => v.id === workOrder.checklist_version_id) ||
      MOCK_CHECKLIST_VERSIONS[0]
    );
  }, [workOrder]);

  const relatedEvidence = useMemo(() => {
    if (!workOrderId) return [];
    return evidence.filter((e) => e.work_order_id === workOrderId);
  }, [evidence, workOrderId]);

  const beforeEvidence = useMemo(
    () => relatedEvidence.filter((e) => e.capture_phase === 'BEFORE'),
    [relatedEvidence],
  );

  const afterEvidence = useMemo(
    () => relatedEvidence.filter((e) => e.capture_phase === 'AFTER'),
    [relatedEvidence],
  );

  const qcEvidence = useMemo(
    () => relatedEvidence.filter((e) => e.capture_phase === 'QC'),
    [relatedEvidence],
  );

  const existingQcResult = useMemo(() => {
    if (!workOrderId) return null;
    return qcResults.find((q) => q.work_order_id === workOrderId) || null;
  }, [qcResults, workOrderId]);

  return {
    workOrder,
    checklistVersion,
    beforeEvidence,
    afterEvidence,
    qcEvidence,
    existingQcResult,
    submitQcInspection,
  };
}
