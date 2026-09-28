import { useState, useCallback, useEffect, useMemo } from 'react';
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
  SecurityCheckpoint,
  SecurityIncidentReport,
  SecurityShiftHandover,
  CleaningPlan,
  MenuId,
  CapturePhase,
} from '../types';
import { PERSONA_PROFILES } from '../types/persona';
import {
  MOCK_INCIDENTS,
  MOCK_TASKS,
  MOCK_WORK_ORDERS,
  MOCK_EVIDENCE,
  MOCK_QC_RESULTS,
  MOCK_APPROVALS,
  MOCK_CASES,
  MOCK_ISSUE_CANDIDATES,
  MOCK_SECURITY_CHECKPOINTS,
  MOCK_SECURITY_INCIDENTS,
  MOCK_SECURITY_HANDOVERS,
} from '../mock';

const STORAGE_KEY_PREFIX = 'vhm_operations_data_v3';

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

  // 7. Action Approvals & Grants
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

  // 8. Security Operations
  const [securityCheckpoints, setSecurityCheckpoints] = useState<SecurityCheckpoint[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_sec_cp`);
      return stored ? JSON.parse(stored) : MOCK_SECURITY_CHECKPOINTS;
    } catch {
      return MOCK_SECURITY_CHECKPOINTS;
    }
  });

  const [securityIncidents, setSecurityIncidents] = useState<SecurityIncidentReport[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_sec_inc`);
      return stored ? JSON.parse(stored) : MOCK_SECURITY_INCIDENTS;
    } catch {
      return MOCK_SECURITY_INCIDENTS;
    }
  });

  const [securityHandovers, setSecurityHandovers] = useState<SecurityShiftHandover[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_sec_handovers`);
      return stored ? JSON.parse(stored) : MOCK_SECURITY_HANDOVERS;
    } catch {
      return MOCK_SECURITY_HANDOVERS;
    }
  });

  // 9. Current active persona (7 roles)
  const [currentPersona, setCurrentPersona] = useState<OperationsPersona>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_persona`);
      return (stored as OperationsPersona) || 'STAFF_TECHNICAL';
    } catch {
      return 'STAFF_TECHNICAL';
    }
  });

  const currentProfile = useMemo(() => {
    return PERSONA_PROFILES[currentPersona] || PERSONA_PROFILES.STAFF_TECHNICAL;
  }, [currentPersona]);

  // Menu permission check
  const canAccessMenu = useCallback(
    (menuId: MenuId): boolean => {
      return currentProfile.allowedMenuIds.includes(menuId);
    },
    [currentProfile],
  );

  // Filter "My Work Orders" according to active persona
  const myWorkOrders = useMemo(() => {
    return workOrders.filter((wo) => {
      // 1. Matched by executor_id
      if (wo.executor_id === currentProfile.id) return true;

      // 2. Role-based fallback matching
      if (currentPersona === 'STAFF_TECHNICAL' && (wo.checklist_version_id?.includes('MEP') || wo.executor_id === 'usr-tech-01')) {
        return true;
      }
      if (currentPersona === 'STAFF_SANITATION_A5' && (wo.checklist_version_id?.includes('SAN') || wo.executor_id === 'usr-cleaner-01')) {
        return true;
      }
      if (currentPersona === 'CONTRACTOR' && (wo.executor_type === 'CONTRACTOR' || wo.executor_id === 'usr-contractor-01')) {
        return true;
      }
      if (currentPersona === 'STAFF_SECURITY' && (wo.checklist_version_id?.includes('SEC') || wo.executor_id === 'usr-sec-01')) {
        return true;
      }
      if (currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER') {
        return true; // Supervisors and managers oversee all
      }
      return false;
    });
  }, [workOrders, currentProfile, currentPersona]);

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
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_sec_cp`, JSON.stringify(securityCheckpoints));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_sec_inc`, JSON.stringify(securityIncidents));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_sec_handovers`, JSON.stringify(securityHandovers));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_persona`, currentPersona);
    } catch (e) {
      console.warn('Failed to sync operations state to localStorage', e);
    }
  }, [
    cases,
    issueCandidates,
    incidents,
    tasks,
    workOrders,
    evidence,
    qcResults,
    approvals,
    executionGrants,
    securityCheckpoints,
    securityIncidents,
    securityHandovers,
    currentPersona,
  ]);

  // ==========================================
  // INTAKE & TRIAGE
  // ==========================================
  const materializeCandidate = useCallback((candidateId: string) => {
    const candidate = issueCandidates.find((c) => c.id === candidateId);
    if (!candidate) return null;

    const newIncidentId = `INC-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
    const now = new Date().toISOString();

    const newIncident: VhIncident = {
      id: newIncidentId,
      tenant_id: 'tenant-vhm-sc',
      project_id: 'proj-smart-city',
      tower_id: candidate.location_json.towerCode || 'S2.01',
      category: candidate.category || 'TECHNICAL',
      title: candidate.normalized_summary || 'Sự cố hiện trường cần xử lý',
      location_json: candidate.location_json,
      severity: candidate.severity || 'P3',
      status: 'OPEN',
      stage: 'PLANNING',
      owner_user_id: currentProfile.id,
      sla_due_at: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
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
          ? { ...c, status: 'MATERIALIZED' as const, materialized_incident_id: newIncidentId, updated_at: now }
          : c,
      ),
    );

    return newIncident;
  }, [issueCandidates, currentProfile]);

  const splitIssueCandidate = useCallback(
    (candidateId: string, partA: { domain: string; summary: string }, partB: { domain: string; summary: string }) => {
      const original = issueCandidates.find((c) => c.id === candidateId);
      if (!original) return null;

      const now = new Date().toISOString();
      const idA = `CAN-SPLIT-${Date.now().toString().slice(-4)}-1`;
      const idB = `CAN-SPLIT-${Date.now().toString().slice(-4)}-2`;

      const candidateA: VhIssueCandidate = {
        ...original,
        id: idA,
        domain: partA.domain,
        normalized_summary: partA.summary,
        status: 'READY',
        confidence: 0.95,
        created_at: now,
        updated_at: now,
      };

      const candidateB: VhIssueCandidate = {
        ...original,
        id: idB,
        domain: partB.domain,
        normalized_summary: partB.summary,
        status: 'READY',
        confidence: 0.95,
        created_at: now,
        updated_at: now,
      };

      setIssueCandidates((prev) => [
        candidateA,
        candidateB,
        ...prev.map((c) => (c.id === candidateId ? { ...c, status: 'DISCARDED' as const, updated_at: now } : c)),
      ]);

      return { candidateA, candidateB };
    },
    [issueCandidates],
  );

  const mergeIssueCandidates = useCallback(
    (sourceCandidateId: string, targetCandidateId: string) => {
      const now = new Date().toISOString();
      setIssueCandidates((prev) =>
        prev.map((c) => {
          if (c.id === sourceCandidateId) {
            return {
              ...c,
              status: 'MERGED' as const,
              merged_into_id: targetCandidateId,
              updated_at: now,
            };
          }
          return c;
        }),
      );
    },
    [],
  );

  // ==========================================
  // INCIDENT MANAGEMENT
  // ==========================================
  const assignIncidentOwner = useCallback((incidentId: string, ownerUserId: string) => {
    setIncidents((prev) =>
      prev.map((i) =>
        i.id === incidentId
          ? {
              ...i,
              owner_user_id: ownerUserId,
              stage: i.stage === 'INTAKE' ? 'TRIAGE' : i.stage,
              updated_at: new Date().toISOString(),
            }
          : i,
      ),
    );
  }, []);

  const transitionIncidentStage = useCallback((incidentId: string, nextStage: IncidentStage) => {
    setIncidents((prev) =>
      prev.map((i) => (i.id === incidentId ? { ...i, stage: nextStage, updated_at: new Date().toISOString() } : i)),
    );
  }, []);

  const resolveIncident = useCallback(
    (incidentId: string) => {
      const incidentTasks = tasks.filter((t) => t.incident_id === incidentId);
      const pendingTasks = incidentTasks.filter((t) => t.status !== 'DONE');

      if (pendingTasks.length > 0) {
        throw new Error(`Không thể đóng sự cố: Còn ${pendingTasks.length} nhiệm vụ chưa hoàn thành (DONE).`);
      }

      const pendingWos = workOrders.filter((w) => w.incident_id === incidentId && w.status !== 'COMPLETED');
      if (pendingWos.length > 0) {
        throw new Error(`Không thể đóng sự cố: Còn ${pendingWos.length} phiếu thi công chưa hoàn tất.`);
      }

      setIncidents((prev) =>
        prev.map((i) =>
          i.id === incidentId
            ? {
                ...i,
                status: 'RESOLVED',
                stage: 'RESIDENT_CONFIRMATION',
                resolved_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }
            : i,
        ),
      );
    },
    [tasks, workOrders],
  );

  const residentConfirmIncident = useCallback((incidentId: string, confirmed: boolean) => {
    const now = new Date().toISOString();
    setIncidents((prev) =>
      prev.map((i) => {
        if (i.id !== incidentId) return i;
        if (confirmed) {
          return {
            ...i,
            status: 'CLOSED',
            stage: 'RESIDENT_CONFIRMATION',
            closed_at: now,
            updated_at: now,
          };
        } else {
          return {
            ...i,
            status: 'OPEN',
            stage: 'EXECUTION',
            updated_at: now,
          };
        }
      }),
    );
  }, []);

  // ==========================================
  // TASK MANAGEMENT
  // ==========================================
  const updateTaskStatus = useCallback((taskId: string, nextStatus: VhTask['status']) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: nextStatus, updated_at: new Date().toISOString() } : t)),
    );
  }, []);

  const createDomainTask = useCallback(
    (params: {
      incident_id: string;
      title: string;
      domain_type: VhTask['domain_type'];
      domain_data: CleaningPlan | Record<string, unknown> | null;
      assignee_id?: string;
      assignee_name?: string;
    }) => {
      const now = new Date().toISOString();
      const newTask: VhTask = {
        id: `TSK-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`,
        incident_id: params.incident_id,
        title: params.title,
        domain_type: params.domain_type,
        domain_data: params.domain_data,
        domain_schema_version: 1,
        assignee_type: 'STAFF',
        assignee_id: params.assignee_id || currentProfile.id,
        assignee_name: params.assignee_name || currentProfile.name,
        status: 'OPEN',
        priority: 'MEDIUM',
        due_at: new Date(Date.now() + 6 * 3600 * 1000).toISOString(),
        version: 1,
        created_at: now,
        updated_at: now,
      };

      setTasks((prev) => [newTask, ...prev]);
      return newTask;
    },
    [currentProfile],
  );

  // ==========================================
  // WORK ORDER STATE MACHINE & EXECUTION
  // ==========================================
  const transitionWorkOrderStatus = useCallback(
    (
      workOrderId: string,
      targetStatus: VhWorkOrder['status'],
      options?: {
        note?: string;
        reason?: string;
        blockedReason?: string;
        materialsUsed?: Array<{ part_name: string; quantity: number; unit: string }>;
        measurements?: Record<string, string | number>;
      },
    ) => {
      const targetWo = workOrders.find((w) => w.id === workOrderId);
      if (!targetWo) throw new Error('Không tìm thấy phiếu công việc!');

      // Check RBAC: Only assigned worker, contractor, supervisor, or manager
      const isAssignee = targetWo.executor_id === currentProfile.id;
      const isSupervisorOrManager = currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER';
      if (!isAssignee && !isSupervisorOrManager) {
        throw new Error(
          `Bạn không có quyền chuyển trạng thái phiếu ${workOrderId}! Chỉ người được giao việc (${targetWo.executor_name || targetWo.executor_id}) hoặc Giám sát/BQL mới có quyền thao tác.`,
        );
      }

      // Check State Machine Transition rules
      // Valid transitions:
      // OPEN -> ASSIGNED
      // ASSIGNED -> IN_PROGRESS
      // IN_PROGRESS -> BLOCKED
      // BLOCKED -> IN_PROGRESS
      // IN_PROGRESS -> COMPLETED
      if (targetStatus === 'COMPLETED') {
        const woEvidence = evidence.filter((e) => e.work_order_id === targetWo.id);
        const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
        const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');

        if (!hasBefore || !hasAfter) {
          throw new Error(
            'Chưa đủ điều kiện hoàn thành: Bắt buộc phải có tối thiểu 1 ảnh Trước (BEFORE) và 1 ảnh Sau (AFTER) khi thi công trước khi báo hoàn thành!',
          );
        }
      }

      if (targetStatus === 'BLOCKED' && !options?.blockedReason && !options?.reason) {
        throw new Error('Vui lòng nêu rõ lý do bị chặn / tạm dừng để Tổ trưởng và BQL nắm thông tin hỗ trợ!');
      }

      const now = new Date().toISOString();

      setWorkOrders((prev) =>
        prev.map((wo) => {
          if (wo.id !== workOrderId) return wo;
          return {
            ...wo,
            status: targetStatus,
            execution_started_at:
              targetStatus === 'IN_PROGRESS' && !wo.execution_started_at ? now : wo.execution_started_at,
            execution_completed_at: targetStatus === 'COMPLETED' ? now : wo.execution_completed_at,
            blocked_reason: targetStatus === 'BLOCKED' ? (options?.blockedReason || options?.reason || null) : null,
            materials_used: options?.materialsUsed || wo.materials_used,
            result: options?.note || options?.measurements
              ? { ...wo.result, note: options.note, measurements: options.measurements }
              : wo.result,
            updated_at: now,
          };
        }),
      );

      // Synchronize parent Task status
      if (targetWo.task_id) {
        if (targetStatus === 'IN_PROGRESS') {
          setTasks((prev) =>
            prev.map((t) => (t.id === targetWo.task_id && t.status === 'OPEN' ? { ...t, status: 'IN_PROGRESS' as const } : t)),
          );
        }
      }
    },
    [workOrders, evidence, currentProfile, currentPersona],
  );

  // Backward compatible updateWorkOrderStatus
  const updateWorkOrderStatus = useCallback(
    (workOrderId: string, nextStatus: VhWorkOrder['status'], note?: string) => {
      transitionWorkOrderStatus(workOrderId, nextStatus, { note });
    },
    [transitionWorkOrderStatus],
  );

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

      setTasks((prev) =>
        prev.map((t) => (t.id === params.task_id && t.status === 'OPEN' ? { ...t, status: 'IN_PROGRESS' as const } : t)),
      );

      return wo;
    },
    [],
  );

  // ==========================================
  // CONTRACTOR ACTIONS
  // ==========================================
  const respondToContractorJob = useCallback(
    (workOrderId: string, action: 'ACCEPT' | 'REJECT', reason?: string, assignedStaff?: string) => {
      const now = new Date().toISOString();
      setWorkOrders((prev) =>
        prev.map((w) => {
          if (w.id !== workOrderId) return w;
          if (action === 'ACCEPT') {
            return {
              ...w,
              contractor_status: 'ACCEPTED',
              contractor_assigned_worker: assignedStaff || w.contractor_assigned_worker,
              status: 'IN_PROGRESS',
              execution_started_at: w.execution_started_at || now,
              updated_at: now,
            };
          } else {
            return {
              ...w,
              contractor_status: 'REJECTED',
              contractor_reject_reason: reason || 'Nhà thầu từ chối tiếp nhận vì quá tải ca',
              status: 'BLOCKED',
              blocked_reason: reason || 'Nhà thầu từ chối tiếp nhận việc',
              updated_at: now,
            };
          }
        }),
      );
    },
    [],
  );

  const recordContractorMaterials = useCallback(
    (workOrderId: string, materials: Array<{ part_name: string; quantity: number; unit: string }>) => {
      setWorkOrders((prev) =>
        prev.map((w) => (w.id === workOrderId ? { ...w, materials_used: materials, updated_at: new Date().toISOString() } : w)),
      );
    },
    [],
  );

  // ==========================================
  // STRICT QC WORKFLOW (WITH ALL GUARDS)
  // ==========================================
  const submitQcInspection = useCallback(
    (params: {
      workOrderId: string;
      outcome: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      criteria: Array<{ criterion_id: string; label: string; passed: boolean; note?: string }>;
      note: string;
      checkedBy?: string;
      checkedByName?: string;
    }) => {
      const targetWo = workOrders.find((w) => w.id === params.workOrderId);
      if (!targetWo) {
        throw new Error('Không tìm thấy phiếu công việc để nghiệm thu!');
      }

      // Guard 1: Must be in COMPLETED status
      if (targetWo.status !== 'COMPLETED') {
        throw new Error(
          `Không thể nghiệm thu QC: Phiếu đang ở trạng thái "${targetWo.status}". Kỹ thuật viên phải hoàn thành thi công (COMPLETED) trước khi QC!`,
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
      const actualCheckerId = params.checkedBy || currentProfile.id;
      if (targetWo.executor_id && actualCheckerId === targetWo.executor_id) {
        throw new Error(
          `Vi phạm nguyên tắc độc lập kiểm định (Segregation of Duties): Bạn (${targetWo.executor_name || actualCheckerId}) là người trực tiếp thi công phiếu ${targetWo.id}, không được phép tự chấm nghiệm thu QC cho chính mình! Vui lòng nhờ QC Inspector hoặc Trưởng ca nghiệm thu.`,
        );
      }

      // Guard 4: Must have QC permission
      if (!currentProfile.canQC && currentPersona !== 'MANAGER') {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có quyền ký ban hành biên bản nghiệm thu QC! Vui lòng chuyển sang vai trò QC Inspector hoặc Quản lý BQL.`,
        );
      }

      const now = new Date().toISOString();
      const failedCriteria = params.criteria.filter((c) => !c.passed).map((c) => c.label);

      const newQc: VhQcResult = {
        id: `QC-${Date.now().toString().slice(-4)}`,
        work_order_id: targetWo.id,
        checklist_version_id: targetWo.checklist_version_id || 'CKL-VER-MEP-01',
        outcome: params.outcome,
        criteria: params.criteria,
        failed_criteria: failedCriteria,
        redo_required: params.outcome === 'FAIL',
        note: params.note,
        checked_by: actualCheckerId,
        checked_by_name: params.checkedByName || currentProfile.name,
        checked_at: now,
      };

      setQcResults((prev) => [newQc, ...prev]);

      if (params.outcome === 'PASS') {
        // PASS -> Task is complete!
        setTasks((prev) =>
          prev.map((t) => (t.id === targetWo.task_id ? { ...t, status: 'DONE' as const, updated_at: now } : t)),
        );
        return { qc: newQc };
      } else if (params.outcome === 'FAIL') {
        // FAIL -> Auto-generate REDO WorkOrder!
        const redoWoId = `WO-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;

        const redoWo: VhWorkOrder = {
          id: redoWoId,
          incident_id: targetWo.incident_id,
          task_id: targetWo.task_id,
          action_request_id: null,
          executor_type: targetWo.executor_type,
          executor_id: targetWo.executor_id,
          executor_name: targetWo.executor_name,
          executor_phone: targetWo.executor_phone,
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
        // Inconclusive keeps WO in-progress for additional evidence
        transitionWorkOrderStatus(params.workOrderId, 'IN_PROGRESS', {
          note: `QC INCONCLUSIVE: Cần bổ sung tài liệu kiểm định - ${params.note}`,
        });
      }

      return { qc: newQc };
    },
    [workOrders, evidence, currentProfile, currentPersona, transitionWorkOrderStatus],
  );

  // ==========================================
  // EVIDENCE MANAGEMENT (WITH ACTOR IDENTITY)
  // ==========================================
  const addEvidence = useCallback(
    (newEvidence: {
      incident_id: string;
      work_order_id?: string | null;
      task_id?: string | null;
      capture_phase: CapturePhase;
      file_url: string;
      caption?: string;
      file_id?: string;
      fileMetadata?: {
        sizeBytes?: number;
        fileName?: string;
        gpsCoordinates?: string;
      };
    }) => {
      const evidenceRecord: VhEvidenceRef = {
        id: `EVD-${Date.now().toString().slice(-4)}`,
        incident_id: newEvidence.incident_id,
        work_order_id: newEvidence.work_order_id || null,
        task_id: newEvidence.task_id || null,
        file_id: newEvidence.file_id || `FILE-${Date.now().toString().slice(-4)}`,
        kind: 'IMAGE',
        capture_phase: newEvidence.capture_phase,
        file_url: newEvidence.file_url,
        uploaded_by: currentProfile.id,
        created_at: new Date().toISOString(),
        metadata: {
          caption: newEvidence.caption || 'Hình ảnh hiện trường',
          uploadedByName: currentProfile.name,
          uploadedByRole: currentProfile.roleTitle,
          gpsCoordinates: newEvidence.fileMetadata?.gpsCoordinates || '21.0031° N, 105.7489° E (Vinhomes Smart City)',
          fileSizeKb: newEvidence.fileMetadata?.sizeBytes ? Math.round(newEvidence.fileMetadata.sizeBytes / 1024) : 480,
          fileName: newEvidence.fileMetadata?.fileName || 'evidence_capture.jpg',
          timestamp: new Date().toISOString(),
        },
      };

      setEvidence((prev) => [evidenceRecord, ...prev]);
      return evidenceRecord;
    },
    [currentProfile],
  );

  // ==========================================
  // SECURITY OPERATIONS ACTIONS
  // ==========================================
  const toggleSecurityCheckpoint = useCallback(
    (checkpointId: string, notes?: string, photoUrl?: string) => {
      const now = new Date().toISOString();
      setSecurityCheckpoints((prev) =>
        prev.map((cp) => {
          if (cp.id !== checkpointId) return cp;
          return {
            ...cp,
            status: 'CHECKED',
            checked_at: now,
            guard_id: currentProfile.id,
            guard_name: currentProfile.name,
            notes: notes || cp.notes,
            photo_url: photoUrl || cp.photo_url,
          };
        }),
      );
    },
    [currentProfile],
  );

  const reportSecurityIncident = useCallback(
    (reportData: Omit<SecurityIncidentReport, 'id' | 'reported_at'>) => {
      const now = new Date().toISOString();
      const newReport: SecurityIncidentReport = {
        ...reportData,
        id: `SEC-INC-${Date.now().toString().slice(-4)}`,
        reported_at: now,
        guard_id: currentProfile.id,
        guard_name: currentProfile.name,
      };

      setSecurityIncidents((prev) => [newReport, ...prev]);
      return newReport;
    },
    [currentProfile],
  );

  const submitSecurityHandover = useCallback(
    (handoverData: Omit<SecurityShiftHandover, 'id' | 'handover_at'>) => {
      const now = new Date().toISOString();
      const newHandover: SecurityShiftHandover = {
        ...handoverData,
        id: `SH-${Date.now().toString().slice(-4)}`,
        handover_at: now,
      };

      setSecurityHandovers((prev) => [newHandover, ...prev]);
      return newHandover;
    },
    [],
  );

  // ==========================================
  // A5 SANITATION ACTIONS
  // ==========================================
  const toggleCleaningAction = useCallback(
    (taskId: string, actionIndex: number, completed: boolean, note?: string) => {
      setTasks((prev) =>
        prev.map((t) => {
          if (t.id !== taskId || !t.domain_data) return t;
          const plan = t.domain_data as CleaningPlan;
          if (!plan.actions || !plan.actions[actionIndex]) return t;

          const updatedActions = [...plan.actions];
          updatedActions[actionIndex] = {
            ...updatedActions[actionIndex],
            completed,
            completed_at: completed ? new Date().toISOString() : undefined,
            issue_reported: note || updatedActions[actionIndex].issue_reported,
          };

          return {
            ...t,
            domain_data: {
              ...plan,
              actions: updatedActions,
            },
            updated_at: new Date().toISOString(),
          };
        }),
      );
    },
    [],
  );

  const confirmSiteArrival = useCallback((taskId: string) => {
    const now = new Date().toISOString();
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id !== taskId || !t.domain_data) return t;
        const plan = t.domain_data as CleaningPlan;
        return {
          ...t,
          domain_data: {
            ...plan,
            arrived_at_site: now,
          },
          updated_at: now,
        };
      }),
    );
  }, []);

  const toggleWarningSigns = useCallback((taskId: string, placed: boolean) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id !== taskId || !t.domain_data) return t;
        const plan = t.domain_data as CleaningPlan;
        return {
          ...t,
          domain_data: {
            ...plan,
            warning_signs_placed: placed,
          },
          updated_at: new Date().toISOString(),
        };
      }),
    );
  }, []);

  // ==========================================
  // APPROVAL WORKFLOW
  // ==========================================
  const approveAction = useCallback(
    (approvalId: string, notes?: string) => {
      const now = new Date().toISOString();
      const targetApproval = approvals.find((a) => a.id === approvalId);
      if (!targetApproval) return;

      const grantId = `GRNT-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;

      const newGrant: VhExecutionGrant = {
        id: grantId,
        action_request_id: targetApproval.action_request_id,
        approval_id: targetApproval.id,
        granted_to: currentProfile.id,
        allowed_action_type: (targetApproval.action_request?.action_type || 'PURCHASE_MATERIAL') as any,
        granted_at: now,
        expires_at: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
        payload_hash: targetApproval.action_payload_hash || 'hash-mock',
        status: 'ACTIVE',
        consumed_by_work_order_id: null,
      };

      setExecutionGrants((prev) => [newGrant, ...prev]);

      setApprovals((prev) =>
        prev.map((a) =>
          a.id === approvalId
            ? {
                ...a,
                status: 'APPROVED' as const,
                decided_by: currentProfile.id,
                decided_at: now,
                decision_notes: notes || 'Đồng ý phê duyệt phương án thi công.',
                execution_grant_id: grantId,
              }
            : a,
        ),
      );
    },
    [approvals, currentProfile],
  );

  const rejectAction = useCallback(
    (approvalId: string, reason: string) => {
      const now = new Date().toISOString();
      setApprovals((prev) =>
        prev.map((a) =>
          a.id === approvalId
            ? {
                ...a,
                status: 'REJECTED' as const,
                decided_by: currentProfile.id,
                decided_at: now,
                decision_notes: reason || 'Từ chối phê duyệt.',
              }
            : a,
        ),
      );
    },
    [currentProfile],
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
    setSecurityCheckpoints(MOCK_SECURITY_CHECKPOINTS);
    setSecurityIncidents(MOCK_SECURITY_INCIDENTS);
    setSecurityHandovers(MOCK_SECURITY_HANDOVERS);
    localStorage.clear();
  }, []);

  return {
    cases,
    issueCandidates,
    incidents,
    tasks,
    workOrders,
    myWorkOrders,
    evidence,
    qcResults,
    approvals,
    executionGrants,
    securityCheckpoints,
    securityIncidents,
    securityHandovers,
    currentPersona,
    currentProfile,
    setCurrentPersona,
    canAccessMenu,
    materializeCandidate,
    splitIssueCandidate,
    mergeIssueCandidates,
    assignIncidentOwner,
    transitionIncidentStage,
    resolveIncident,
    residentConfirmIncident,
    updateTaskStatus,
    createDomainTask,
    transitionWorkOrderStatus,
    updateWorkOrderStatus,
    createWorkOrder,
    submitQcInspection,
    approveAction,
    rejectAction,
    addEvidence,
    respondToContractorJob,
    recordContractorMaterials,
    toggleSecurityCheckpoint,
    reportSecurityIncident,
    submitSecurityHandover,
    toggleCleaningAction,
    confirmSiteArrival,
    toggleWarningSigns,
    resetToDefaultMock,
  };
}
