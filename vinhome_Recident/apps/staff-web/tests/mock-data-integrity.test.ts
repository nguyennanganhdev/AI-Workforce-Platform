import { describe, expect, test } from "vitest";
import {
  MOCK_INCIDENTS,
  MOCK_TASKS,
  MOCK_TASK_DEPENDENCIES,
  MOCK_WORK_ORDERS,
  MOCK_EVIDENCE,
  MOCK_QC_RESULTS,
  MOCK_CHECKLISTS,
  MOCK_CHECKLIST_VERSIONS,
  MOCK_APPROVALS,
  MOCK_ACTION_REQUESTS,
} from '../src/features/vinhomes-operations/mock';
import { PERSONA_PROFILES } from '../src/features/vinhomes-operations/types/persona';

describe('Vinhomes Operations Data Integrity Audit Suite', () => {
  test('1. No Duplicate IDs across entities', () => {
    const checkUnique = (items: Array<{ id: string }>, entityName: string) => {
      const ids = items.map((i) => i.id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    };

    checkUnique(MOCK_INCIDENTS, 'Incidents');
    checkUnique(MOCK_TASKS, 'Tasks');
    checkUnique(MOCK_WORK_ORDERS, 'WorkOrders');
    checkUnique(MOCK_EVIDENCE, 'Evidence');
    checkUnique(MOCK_QC_RESULTS, 'QC Results');
    checkUnique(MOCK_CHECKLISTS, 'Checklists');
    checkUnique(MOCK_CHECKLIST_VERSIONS, 'Checklist Versions');
    checkUnique(MOCK_APPROVALS, 'Approvals');
    checkUnique(MOCK_ACTION_REQUESTS, 'Action Requests');
  });

  test('2. Invariant: workOrder.incident_id === task.incident_id', () => {
    const incidentMap = new Map(MOCK_INCIDENTS.map((i) => [i.id, i]));
    const taskMap = new Map(MOCK_TASKS.map((t) => [t.id, t]));

    for (const wo of MOCK_WORK_ORDERS) {
      expect(incidentMap.has(wo.incident_id)).toBe(true);
      expect(taskMap.has(wo.task_id)).toBe(true);

      const parentTask = taskMap.get(wo.task_id)!;
      expect(wo.incident_id).toBe(parentTask.incident_id);
    }
  });

  test('3. Invariant: Redo chain consistency', () => {
    const woMap = new Map(MOCK_WORK_ORDERS.map((w) => [w.id, w]));

    for (const wo of MOCK_WORK_ORDERS) {
      if (wo.redo_of_work_order_id) {
        expect(woMap.has(wo.redo_of_work_order_id)).toBe(true);
        const original = woMap.get(wo.redo_of_work_order_id)!;

        // Must be same task, same incident, and attempt_no incremented
        expect(wo.task_id).toBe(original.task_id);
        expect(wo.incident_id).toBe(original.incident_id);
        expect(wo.attempt_no).toBe(original.attempt_no + 1);
        expect(original.status).toBe('COMPLETED');
      }
    }
  });

  test('4. Invariant: Evidence linkage matches WorkOrder, Task, and Incident', () => {
    const woMap = new Map(MOCK_WORK_ORDERS.map((w) => [w.id, w]));

    for (const ev of MOCK_EVIDENCE) {
      expect(ev.work_order_id).toBeTruthy();
      if (ev.work_order_id) {
        expect(woMap.has(ev.work_order_id)).toBe(true);
        const parentWo = woMap.get(ev.work_order_id)!;

        expect(ev.incident_id).toBe(parentWo.incident_id);
        expect(ev.task_id).toBe(parentWo.task_id);
      }
    }
  });

  test('5. Invariant: QC Results validity & Segregation of Duties', () => {
    const woMap = new Map(MOCK_WORK_ORDERS.map((w) => [w.id, w]));
    const versionSet = new Set(MOCK_CHECKLIST_VERSIONS.map((v) => v.id));
    const validQcInspectors = new Set(
      Object.values(PERSONA_PROFILES)
        .filter((p) => p.canQC)
        .map((p) => p.id),
    );

    for (const qc of MOCK_QC_RESULTS) {
      // 5A. Target work order must exist and be COMPLETED
      expect(woMap.has(qc.work_order_id)).toBe(true);
      const targetWo = woMap.get(qc.work_order_id)!;
      expect(targetWo.status).toBe('COMPLETED');

      // 5B. Checklist version must exist
      expect(qc.checklist_version_id).toBeTruthy();
      if (qc.checklist_version_id) {
        expect(versionSet.has(qc.checklist_version_id)).toBe(true);
      }

      // 5C. QC must be signed by an authorized QC Inspector
      expect(validQcInspectors.has(qc.checked_by)).toBe(true);

      // 5D. Segregation of duties: Inspector cannot be the executor
      expect(qc.checked_by).not.toBe(targetWo.executor_id);

      // 5E. Before and After evidence must exist for QC'd work order
      const woEvidence = MOCK_EVIDENCE.filter((e) => e.work_order_id === targetWo.id);
      const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
      const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');
      expect(hasBefore).toBe(true);
      expect(hasAfter).toBe(true);
    }
  });

  test('6. Invariant: Checklists exist and match domain types', () => {
    const versionMap = new Map(MOCK_CHECKLIST_VERSIONS.map((v) => [v.id, v]));

    for (const wo of MOCK_WORK_ORDERS) {
      if (wo.checklist_version_id) {
        expect(versionMap.has(wo.checklist_version_id)).toBe(true);
      }
    }
  });

  test('7. Invariant: Approvals link to valid Action Requests with matching hash', () => {
    const actionRequestMap = new Map(MOCK_ACTION_REQUESTS.map((a) => [a.id, a]));

    for (const app of MOCK_APPROVALS) {
      expect(actionRequestMap.has(app.action_request_id)).toBe(true);
      const act = actionRequestMap.get(app.action_request_id)!;

      // Hash must match exactly
      expect(app.action_payload_hash).toBe(act.payload_hash);
    }
  });

  test('8. Invariant: Task assignees use canonical persona profiles', () => {
    const validProfileIds = new Set(Object.values(PERSONA_PROFILES).map((p) => p.id));

    for (const task of MOCK_TASKS) {
      if (task.assignee_id) {
        expect(validProfileIds.has(task.assignee_id)).toBe(true);
      }
    }
  });

  test('9. Invariant: Incident lifecycle consistency', () => {
    const incidentMap = new Map(MOCK_INCIDENTS.map((i) => [i.id, i]));

    for (const inc of MOCK_INCIDENTS) {
      if (inc.status === 'RESOLVED' || inc.status === 'CLOSED') {
        // No uncompleted tasks
        const incTasks = MOCK_TASKS.filter((t) => t.incident_id === inc.id);
        const uncompletedTasks = incTasks.filter((t) => t.status !== 'DONE');
        expect(uncompletedTasks.length).toBe(0);

        // No pending or in-progress work orders
        const incWos = MOCK_WORK_ORDERS.filter((w) => w.incident_id === inc.id);
        const activeWos = incWos.filter((w) => w.status !== 'COMPLETED');
        expect(activeWos.length).toBe(0);

        // All completed work orders must have passed QC (or their redo passed QC)
        for (const wo of incWos) {
          const qc = MOCK_QC_RESULTS.find((q) => q.work_order_id === wo.id);
          if (qc?.outcome === 'FAIL') {
            const redoWo = incWos.find((r) => r.redo_of_work_order_id === wo.id);
            expect(redoWo).toBeDefined();
            expect(redoWo!.status).toBe('COMPLETED');
            const redoQc = MOCK_QC_RESULTS.find((q) => q.work_order_id === redoWo!.id);
            expect(redoQc?.outcome).toBe('PASS');
          }
        }
      }
    }
  });

  test('10. Invariant: Security Domain Consistency', () => {
    const secTask = MOCK_TASKS.find((t) => t.domain_type === 'SECURITY');
    expect(secTask).toBeDefined();
    expect(secTask?.assignee_id).toBe('usr-sec-01');

    const secWo = MOCK_WORK_ORDERS.find((w) => w.task_id === secTask?.id);
    expect(secWo).toBeDefined();
    expect(secWo?.checklist_version_id).toBe('CKL-VER-SEC-01');
    expect(secWo?.executor_id).toBe('usr-sec-01');
  });

  test('11. Invariant: Task status synchronization with Redo chains', () => {
    // TSK-101 has an active redo attempt 2 (WO-085) which is ASSIGNED, so task must be IN_PROGRESS
    const tsk101 = MOCK_TASKS.find((t) => t.id === 'TSK-2026-101')!;
    const wo085 = MOCK_WORK_ORDERS.find((w) => w.id === 'WO-2026-085')!;
    expect(wo085.status).toBe('ASSIGNED');
    expect(tsk101.status).toBe('IN_PROGRESS');

    // TSK-107 has completed redo attempt 2 (WO-089) with QC PASS, so task must be DONE
    const tsk107 = MOCK_TASKS.find((t) => t.id === 'TSK-2026-107')!;
    const wo089 = MOCK_WORK_ORDERS.find((w) => w.id === 'WO-2026-089')!;
    expect(wo089.status).toBe('COMPLETED');
    expect(tsk107.status).toBe('DONE');
  });

  test('12. Invariant: Evidence capture phase strictly respects WorkOrder status', () => {
    const woMap = new Map(MOCK_WORK_ORDERS.map((w) => [w.id, w]));

    for (const ev of MOCK_EVIDENCE) {
      if (ev.work_order_id) {
        const wo = woMap.get(ev.work_order_id)!;

        // No AFTER photo if work order is still ASSIGNED
        if (wo.status === 'ASSIGNED') {
          expect(ev.capture_phase).not.toBe('AFTER');
        }

        // No QC photo unless work order is COMPLETED
        if (ev.capture_phase === 'QC') {
          expect(wo.status).toBe('COMPLETED');
        }
      }
    }
  });

  test('13. Invariant: Contractor interactive demo readiness', () => {
    const contractorWo = MOCK_WORK_ORDERS.find(
      (w) => w.executor_type === 'CONTRACTOR' && w.contractor_status === 'PENDING_ACCEPTANCE',
    );
    expect(contractorWo).toBeDefined();
    expect(contractorWo?.status).toBe('ASSIGNED');
    expect(contractorWo?.contractor_organization_id).toBe('org-otis');
    expect(contractorWo?.checklist_version_id).toBe('CKL-VER-ELEV-01');
  });

  test('14. Invariant: legacy QC pending inspection demo readiness', () => {
    // New field-flow orders await resident confirmation and do not enter legacy QC.
    const qcWoIds = new Set(MOCK_QC_RESULTS.map((q) => q.work_order_id));
    const pendingQcWos = MOCK_WORK_ORDERS.filter(
      (w) => w.status === 'COMPLETED' && !w.field_flow && !qcWoIds.has(w.id),
    );
    expect(pendingQcWos.length).toBeGreaterThanOrEqual(1);

    for (const wo of pendingQcWos) {
      const woEvidence = MOCK_EVIDENCE.filter((e) => e.work_order_id === wo.id);
      expect(woEvidence.some((e) => e.capture_phase === 'BEFORE')).toBe(true);
      expect(woEvidence.some((e) => e.capture_phase === 'AFTER')).toBe(true);
    }
  });

  test('15. Invariant: Incident resolution consistency (INC-2026-003)', () => {
    const inc003 = MOCK_INCIDENTS.find((i) => i.id === 'INC-2026-003')!;
    expect(inc003.status).toBe('RESOLVED');
    expect(inc003.stage).toBe('RESIDENT_CONFIRMATION');

    const inc003Tasks = MOCK_TASKS.filter((t) => t.incident_id === 'INC-2026-003');
    for (const t of inc003Tasks) {
      expect(t.status).toBe('DONE');
    }
  });
});
