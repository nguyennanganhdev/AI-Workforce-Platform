import { useState, useCallback, useEffect } from 'react';
import type {
  VhIncident,
  VhTask,
  VhWorkOrder,
  VhEvidenceRef,
  VhQcResult,
  VhActionApproval,
  VhExecutionGrant,
  VhCase,
  VhIssueCandidate,
  OperationsPersona,
  IncidentStage,
  IncidentSeverity,
} from '../types';
import {
  MOCK_INCIDENTS,
  MOCK_TASKS,
  MOCK_WORK_ORDERS,
  MOCK_EVIDENCE,
  MOCK_QC_RESULTS,
  MOCK_APPROVALS,
  MOCK_CASES,
  MOCK_ISSUE_CANDIDATES,
} from '../mock';

const STORAGE_KEY_PREFIX = 'vhm_operations_data_v2';

export function useOperationsData() {
  // 1. Cases & Issue Candidates (Intake / Triage)
  const [cases, setCases] = useState<VhCase[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_cases`);
      return stored ? JSON.parse(stored) : MOCK_CASES;
    } catch {
      return MOCK_CASES;
    }
  });

  const [issueCandidates, setIssueCandidates] = useState<VhIssueCandidate[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_candidates`);
      return stored ? JSON.parse(stored) : MOCK_ISSUE_CANDIDATES;
    } catch {
      return MOCK_ISSUE_CANDIDATES;
    }
  });

  // 2. Incidents
  const [incidents, setIncidents] = useState<VhIncident[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_incidents`);
      return stored ? JSON.parse(stored) : MOCK_INCIDENTS;
    } catch {
      return MOCK_INCIDENTS;
    }
  });

  // 3. Tasks
  const [tasks, setTasks] = useState<VhTask[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_tasks`);
      return stored ? JSON.parse(stored) : MOCK_TASKS;
    } catch {
      return MOCK_TASKS;
    }
  });

  // 4. WorkOrders
  const [workOrders, setWorkOrders] = useState<VhWorkOrder[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_work_orders`);
      return stored ? JSON.parse(stored) : MOCK_WORK_ORDERS;
    } catch {
      return MOCK_WORK_ORDERS;
    }
  });

  // 5. Evidence
  const [evidence, setEvidence] = useState<VhEvidenceRef[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_evidence`);
      return stored ? JSON.parse(stored) : MOCK_EVIDENCE;
    } catch {
      return MOCK_EVIDENCE;
    }
  });

  // 6. QC Results
  const [qcResults, setQcResults] = useState<VhQcResult[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_qc_results`);
      return stored ? JSON.parse(stored) : MOCK_QC_RESULTS;
    } catch {
      return MOCK_QC_RESULTS;
    }
  });

  // 7. Approvals & Execution Grants
  const [approvals, setApprovals] = useState<VhActionApproval[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_approvals`);
      return stored ? JSON.parse(stored) : MOCK_APPROVALS;
    } catch {
      return MOCK_APPROVALS;
    }
  });

  const [executionGrants, setExecutionGrants] = useState<VhExecutionGrant[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_grants`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Current active persona: 'STAFF_TECHNICAL' | 'STAFF_SANITATION' | 'MANAGER'
  const [currentPersona, setCurrentPersona] = useState<OperationsPersona>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_persona`);
      return (stored as OperationsPersona) || 'STAFF_TECHNICAL';
    } catch {
      return 'STAFF_TECHNICAL';
    }
  });

  // Persist state
  useEffect(() => {
    try {
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_cases`, JSON.stringify(cases));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_candidates`, JSON.stringify(issueCandidates));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_incidents`, JSON.stringify(incidents));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_tasks`, JSON.stringify(tasks));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_work_orders`, JSON.stringify(workOrders));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_evidence`, JSON.stringify(evidence));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_qc_results`, JSON.stringify(qcResults));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_approvals`, JSON.stringify(approvals));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_grants`, JSON.stringify(executionGrants));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_persona`, currentPersona);
    } catch (e) {
      console.warn('Failed to sync operations state to localStorage', e);
    }
  }, [cases, issueCandidates, incidents, tasks, workOrders, evidence, qcResults, approvals, executionGrants, currentPersona]);

  // ==========================================
  // 1. INTAKE & TRIAGE ACTIONS
  // ==========================================
  const materializeCandidate = useCallback((candidateId: string) => {
    const candidate = issueCandidates.find((c) => c.id === candidateId);
    if (!candidate) return null;

    const incidentId = `INC-2026-${Math.floor(100 + Math.random() * 900)}`;
    const now = new Date().toISOString();

    const newIncident: VhIncident = {
      id: incidentId,
      tenant_id: 'tenant-vhm-sc',
      project_id: 'vh-smart-city',
      tower_id: candidate.location_json.towerCode ? `tower-${candidate.location_json.towerCode.toLowerCase()}` : null,
      category: candidate.category,
      title: candidate.normalized_summary,
      location_json: candidate.location_json,
      severity: candidate.severity,
      status: 'OPEN',
      stage: 'TRIAGE',
      owner_user_id: null,
      sla_due_at: candidate.severity === 'P1'
        ? new Date(Date.now() + 45 * 60 * 1000).toISOString()
        : new Date(Date.now() + 120 * 60 * 1000).toISOString(),
      resolved_at: null,
      closed_at: null,
      version: 1,
      created_at: now,
      updated_at: now,
    };

    setIncidents((prev) => [newIncident, ...prev]);

    setIssueCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId
          ? { ...c, status: 'MATERIALIZED', materialized_incident_id: incidentId, updated_at: now }
          : c,
      ),
    );

    return newIncident;
  }, [issueCandidates]);

  const splitIssueCandidate = useCallback(
    (candidateId: string, partA: Partial<VhIssueCandidate>, partB: Partial<VhIssueCandidate>) => {
      const parent = issueCandidates.find((c) => c.id === candidateId);
      if (!parent) return;

      const now = new Date().toISOString();
      const childA: VhIssueCandidate = {
        ...parent,
        ...partA,
        id: `${parent.id}-A`,
        created_at: now,
        updated_at: now,
      };

      const childB: VhIssueCandidate = {
        ...parent,
        ...partB,
        id: `${parent.id}-B`,
        created_at: now,
        updated_at: now,
      };

      setIssueCandidates((prev) => [
        childA,
        childB,
        ...prev.map((c) => (c.id === candidateId ? { ...c, status: 'DISCARDED' as const } : c)),
      ]);
    },
    [issueCandidates],
  );

  const mergeIssueCandidates = useCallback(
    (sourceId: string, targetId: string) => {
      const now = new Date().toISOString();
      setIssueCandidates((prev) =>
        prev.map((c) => {
          if (c.id === sourceId) {
            return { ...c, status: 'MERGED', merged_into_id: targetId, updated_at: now };
          }
          return c;
        }),
      );
    },
    [],
  );

  // ==========================================
  // 2. INCIDENT LIFECYCLE ACTIONS
  // ==========================================
  const assignIncidentOwner = useCallback((incidentId: string, ownerUserId: string) => {
    setIncidents((prev) =>
      prev.map((inc) =>
        inc.id === incidentId
          ? { ...inc, owner_user_id: ownerUserId, stage: inc.stage === 'INTAKE' ? 'TRIAGE' : inc.stage, updated_at: new Date().toISOString() }
          : inc,
      ),
    );
  }, []);

  const transitionIncidentStage = useCallback((incidentId: string, nextStage: IncidentStage) => {
    setIncidents((prev) =>
      prev.map((inc) =>
        inc.id === incidentId
          ? { ...inc, stage: nextStage, updated_at: new Date().toISOString() }
          : inc,
      ),
    );
  }, []);

  // Resolve Guard: Only allow resolve when all tasks are DONE and work orders are completed!
  const resolveIncident = useCallback(
    (incidentId: string) => {
      const incidentTasks = tasks.filter((t) => t.incident_id === incidentId);
      const incidentWos = workOrders.filter((w) => w.incident_id === incidentId);

      const hasUnfinishedTasks = incidentTasks.some((t) => t.status !== 'DONE' && t.status !== 'CANCELLED');
      const hasUnfinishedWos = incidentWos.some((w) => w.status !== 'COMPLETED' && w.status !== 'CANCELLED');

      if (hasUnfinishedTasks || hasUnfinishedWos) {
        throw new Error(
          'Không thể hoàn tất Sự cố: Vẫn còn nhiệm vụ chưa hoàn thành (DONE) hoặc phiếu công việc chưa nghiệm thu!',
        );
      }

      const now = new Date().toISOString();
      setIncidents((prev) =>
        prev.map((inc) =>
          inc.id === incidentId
            ? { ...inc, status: 'RESOLVED', stage: 'RESIDENT_CONFIRMATION', resolved_at: now, updated_at: now }
            : inc,
        ),
      );
    },
    [tasks, workOrders],
  );

  // Resident Confirmation: Accept closes incident; Reject reopens to PLANNING!
  const residentConfirmIncident = useCallback(
    (incidentId: string, confirmed: boolean, _feedback?: string) => {
      const now = new Date().toISOString();
      setIncidents((prev) =>
        prev.map((inc) => {
          if (inc.id !== incidentId) return inc;
          if (confirmed) {
            return { ...inc, status: 'CLOSED', closed_at: now, updated_at: now };
          }
          // If resident rejects: REOPEN to PLANNING
          return { ...inc, status: 'OPEN', stage: 'PLANNING', resolved_at: null, updated_at: now };
        }),
      );
    },
    [],
  );

  // ==========================================
  // 3. TASK LIFECYCLE & DEPENDENCY
  // ==========================================
  const updateTaskStatus = useCallback((taskId: string, nextStatus: VhTask['status']) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: nextStatus, updated_at: new Date().toISOString() } : t)),
    );
  }, []);

  const createDomainTask = useCallback((newTask: Omit<VhTask, 'id' | 'version' | 'created_at' | 'updated_at'>) => {
    const now = new Date().toISOString();
    const task: VhTask = {
      ...newTask,
      id: `TSK-2026-${Math.floor(200 + Math.random() * 800)}`,
      version: 1,
      created_at: now,
      updated_at: now,
    };
    setTasks((prev) => [task, ...prev]);
    return task;
  }, []);

  // ==========================================
  // 4. ACTION REQUEST, APPROVAL & EXECUTION GRANT
  // ==========================================
  const approveAction = useCallback(
    (approvalId: string, reviewerId: string, reviewerName: string, reason?: string) => {
      const now = new Date().toISOString();
      let grantedAction: VhActionApproval | null = null;

      setApprovals((prev) =>
        prev.map((app) => {
          if (app.id !== approvalId) return app;

          // Check expiry
          if (new Date(app.expires_at).getTime() < Date.now()) {
            return { ...app, status: 'EXPIRED' as const, updated_at: now };
          }

          grantedAction = app;
          return {
            ...app,
            status: 'APPROVED' as const,
            reviewer_id: reviewerId,
            reviewer_name: reviewerName,
            decided_at: now,
            reason: reason || 'Ban Quản Lý đã phê duyệt đề xuất.',
            version: app.version + 1,
          };
        }),
      );

      // Emit Execution Grant
      if (grantedAction) {
        const target = grantedAction as VhActionApproval;
        const grant: VhExecutionGrant = {
          id: `GRANT-${Date.now().toString().slice(-4)}`,
          action_request_id: target.action_request_id,
          approval_id: target.id,
          granted_to: target.requested_by_id,
          allowed_action_type: target.action_request?.action_type || 'PURCHASE_MATERIAL',
          payload_hash: target.action_payload_hash,
          status: 'ACTIVE',
          consumed_by_work_order_id: null,
          granted_at: now,
          expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        };
        setExecutionGrants((prev) => [grant, ...prev]);
      }
    },
    [],
  );

  const rejectAction = useCallback(
    (approvalId: string, reviewerId: string, reviewerName: string, reason: string) => {
      const now = new Date().toISOString();
      setApprovals((prev) =>
        prev.map((app) => {
          if (app.id !== approvalId) return app;
          return {
            ...app,
            status: 'REJECTED' as const,
            reviewer_id: reviewerId,
            reviewer_name: reviewerName,
            decided_at: now,
            reason: reason || 'Từ chối phê duyệt.',
            version: app.version + 1,
          };
        }),
      );
    },
    [],
  );

  // ==========================================
  // 5. WORK ORDER EXECUTION & REDO
  // ==========================================
  const updateWorkOrderStatus = useCallback(
    (workOrderId: string, nextStatus: VhWorkOrder['status'], note?: string) => {
      setWorkOrders((prev) =>
        prev.map((wo) => {
          if (wo.id !== workOrderId) return wo;
          const now = new Date().toISOString();
          return {
            ...wo,
            status: nextStatus,
            execution_started_at:
              nextStatus === 'IN_PROGRESS' && !wo.execution_started_at ? now : wo.execution_started_at,
            execution_completed_at: nextStatus === 'COMPLETED' ? now : wo.execution_completed_at,
            result: note ? { ...wo.result, note } : wo.result,
            updated_at: now,
          };
        }),
      );
    },
    [],
  );

  // Create WorkOrder from an actual Task and Incident
  const createWorkOrder = useCallback(
    (params: {
      incident_id: string;
      task_id: string;
      action_request_id?: string | null;
      execution_grant_id?: string | null;
      executor_type: VhWorkOrder['executor_type'];
      executor_id: string | null;
      executor_name?: string;
      executor_phone?: string;
      checklist_version_id?: string | null;
    }) => {
      const now = new Date().toISOString();
      const newWoId = `WO-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;

      // If tied to execution grant, consume the grant!
      if (params.execution_grant_id) {
        setExecutionGrants((prev) =>
          prev.map((g) =>
            g.id === params.execution_grant_id
              ? { ...g, status: 'CONSUMED' as const, consumed_by_work_order_id: newWoId }
              : g,
          ),
        );
      }

      const wo: VhWorkOrder = {
        id: newWoId,
        incident_id: params.incident_id,
        task_id: params.task_id,
        action_request_id: params.action_request_id || null,
        executor_type: params.executor_type,
        executor_id: params.executor_id,
        executor_name: params.executor_name,
        executor_phone: params.executor_phone,
        status: 'ASSIGNED',
        attempt_no: 1,
        redo_of_work_order_id: null,
        checklist_version_id: params.checklist_version_id || 'CKL-VER-MEP-01',
        execution_started_at: null,
        execution_completed_at: null,
        result: null,
        version: 1,
        created_at: now,
        updated_at: now,
      };

      setWorkOrders((prev) => [wo, ...prev]);

      // Automatically update task to IN_PROGRESS if open
      setTasks((prev) =>
        prev.map((t) => (t.id === params.task_id && t.status === 'OPEN' ? { ...t, status: 'IN_PROGRESS' as const } : t)),
      );

      return wo;
    },
    [],
  );

  // ==========================================
  // 6. STRICT QC WORKFLOW (WITH ALL GUARDS)
  // ==========================================
  const submitQcInspection = useCallback(
    (params: {
      workOrderId: string;
      outcome: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      criteria: Array<{ criterion_id: string; label: string; passed: boolean; note?: string }>;
      note: string;
      checkedBy: string;
      checkedByName?: string;
    }) => {
      const targetWo = workOrders.find((w) => w.id === params.workOrderId);
      if (!targetWo) {
        throw new Error('Không tìm thấy phiếu công việc để nghiệm thu!');
      }

      // Guard 1: Must be COMPLETED (Cannot QC open or in-progress works!)
      if (targetWo.status !== 'COMPLETED') {
        throw new Error(
          `Không thể nghiệm thu QC: Phiếu đang ở trạng thái "${targetWo.status}". Kỹ thuật viên phải hoàn thành (COMPLETED) trước khi QC!`,
        );
      }

      // Guard 2: Must have required BEFORE and AFTER evidence
      const woEvidence = evidence.filter((e) => e.work_order_id === targetWo.id);
      const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
      const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');

      if (!hasBefore || !hasAfter) {
        throw new Error(
          'Thiếu bằng chứng bắt buộc: Cần tối thiểu 1 ảnh BEFORE (Trước khi làm) và 1 ảnh AFTER (Sau khi làm) để tiến hành nghiệm thu QC!',
        );
      }

      // Guard 3: Segregation of duties - Executor cannot QC their own work!
      if (targetWo.executor_id && params.checkedBy === targetWo.executor_id) {
        throw new Error(
          'Vi phạm nguyên tắc độc lập kiểm định: Kỹ thuật viên thực hiện không được tự nghiệm thu QC công việc của chính mình!',
        );
      }

      const failedCriteria = params.criteria
        .filter((c) => !c.passed)
        .map((c) => `${c.label}${c.note ? ` (${c.note})` : ''}`);

      const redoRequired = params.outcome === 'FAIL';
      const now = new Date().toISOString();

      const newQc: VhQcResult = {
        id: `QC-${Date.now().toString().slice(-4)}`,
        work_order_id: params.workOrderId,
        outcome: params.outcome,
        criteria: params.criteria,
        failed_criteria: failedCriteria,
        redo_required: redoRequired,
        note: params.note,
        checked_by: params.checkedBy,
        checked_by_name: params.checkedByName || 'Kỹ sư QC Độc lập',
        checked_at: now,
      };

      setQcResults((prev) => [newQc, ...prev]);

      if (params.outcome === 'PASS') {
        // Mark Task as DONE if all other WOs of this task are completed
        setTasks((prev) =>
          prev.map((t) => (t.id === targetWo.task_id ? { ...t, status: 'DONE' as const, updated_at: now } : t)),
        );
      } else if (params.outcome === 'FAIL') {
        // Mark current attempt as FAILED
        updateWorkOrderStatus(params.workOrderId, 'FAILED', `QC FAIL: ${params.note}`);

        // Automatically spawn Redo WorkOrder per ERD Section 9
        const redoWoId = `WO-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
        const redoWo: VhWorkOrder = {
          id: redoWoId,
          incident_id: targetWo.incident_id,
          task_id: targetWo.task_id,
          action_request_id: targetWo.action_request_id,
          executor_type: targetWo.executor_type,
          executor_id: targetWo.executor_id,
          executor_name: targetWo.executor_name,
          executor_phone: targetWo.executor_phone,
          executor_avatar: targetWo.executor_avatar,
          status: 'ASSIGNED',
          attempt_no: (targetWo.attempt_no || 1) + 1,
          redo_of_work_order_id: targetWo.id,
          checklist_version_id: targetWo.checklist_version_id,
          execution_started_at: null,
          execution_completed_at: null,
          result: { redoReason: params.note, failedCriteria },
          version: 1,
          created_at: now,
          updated_at: now,
        };

        setWorkOrders((prev) => [redoWo, ...prev]);

        // Keep Task IN_PROGRESS
        setTasks((prev) =>
          prev.map((t) => (t.id === targetWo.task_id ? { ...t, status: 'IN_PROGRESS' as const, updated_at: now } : t)),
        );

        return { qc: newQc, redoWorkOrder: redoWo };
      } else if (params.outcome === 'INCONCLUSIVE') {
        // Inconclusive keeps WO open for additional evidence
        updateWorkOrderStatus(params.workOrderId, 'IN_PROGRESS', `QC INCONCLUSIVE: Cần bổ sung tài liệu kiểm định - ${params.note}`);
      }

      return { qc: newQc };
    },
    [workOrders, evidence, updateWorkOrderStatus],
  );

  // ==========================================
  // 7. EVIDENCE MANAGEMENT
  // ==========================================
  const addEvidence = useCallback(
    (newEvidence: Omit<VhEvidenceRef, 'id' | 'created_at'>) => {
      const evidenceRecord: VhEvidenceRef = {
        ...newEvidence,
        id: `EVD-${Date.now().toString().slice(-4)}`,
        created_at: new Date().toISOString(),
      };
      setEvidence((prev) => [evidenceRecord, ...prev]);
      return evidenceRecord;
    },
    [],
  );

  // Reset to default mock
  const resetToDefaultMock = useCallback(() => {
    setCases(MOCK_CASES);
    setIssueCandidates(MOCK_ISSUE_CANDIDATES);
    setIncidents(MOCK_INCIDENTS);
    setTasks(MOCK_TASKS);
    setWorkOrders(MOCK_WORK_ORDERS);
    setEvidence(MOCK_EVIDENCE);
    setQcResults(MOCK_QC_RESULTS);
    setApprovals(MOCK_APPROVALS);
    setExecutionGrants([]);
    localStorage.clear();
  }, []);

  return {
    cases,
    issueCandidates,
    incidents,
    tasks,
    workOrders,
    evidence,
    qcResults,
    approvals,
    executionGrants,
    currentPersona,
    setCurrentPersona,
    materializeCandidate,
    splitIssueCandidate,
    mergeIssueCandidates,
    assignIncidentOwner,
    transitionIncidentStage,
    resolveIncident,
    residentConfirmIncident,
    updateTaskStatus,
    createDomainTask,
    updateWorkOrderStatus,
    createWorkOrder,
    submitQcInspection,
    approveAction,
    rejectAction,
    addEvidence,
    resetToDefaultMock,
  };
}
