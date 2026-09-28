import { useState, useCallback, useEffect, useMemo, createContext, useContext, createElement, type ReactNode } from 'react';
import {
  type VhIncident,
  type VhTask,
  type VhTaskDependency,
  type VhWorkOrder,
  type VhEvidenceRef,
  type VhQcResult,
  type VhActionApproval,
  type VhActionRequest,
  type VhExecutionGrant,
  type VhCase,
  type VhIssueCandidate,
  type OperationsPersona,
  type IncidentStage,
  type IncidentSeverity,
  type SecurityCheckpoint,
  type SecurityIncidentReport,
  type SecurityShiftHandover,
  type CleaningPlan,
  type MenuId,
  type CapturePhase,
  ALLOWED_WORK_ORDER_TRANSITIONS,
} from '../types';
import { PERSONA_PROFILES } from '../types/persona';
import {
  MOCK_INCIDENTS,
  MOCK_TASKS,
  MOCK_TASK_DEPENDENCIES,
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
import { MOCK_ACTION_REQUESTS } from '../mock/action-requests';

const STORAGE_KEY_PREFIX = 'vhm_operations_data_v5';

export const DOMAIN_CHECKLIST_MAP: Record<string, string> = {
  MEP: 'CKL-VER-MEP-01',
  TECHNICAL: 'CKL-VER-MEP-01',
  SANITATION: 'CKL-VER-SAN-01',
  LANDSCAPE: 'CKL-VER-SAN-01',
  ELEVATOR: 'CKL-VER-ELEV-01',
  SECURITY: 'CKL-VER-SEC-01',
  GENERAL: 'CKL-VER-MEP-01',
};

export function useOperationsDataInternal() {
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

  // 3. Tasks & Dependencies
  const [tasks, setTasks] = useState<VhTask[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_tasks`);
      return stored ? JSON.parse(stored) : MOCK_TASKS;
    } catch {
      return MOCK_TASKS;
    }
  });

  const [taskDependencies, setTaskDependencies] = useState<VhTaskDependency[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_task_deps`);
      return stored ? JSON.parse(stored) : MOCK_TASK_DEPENDENCIES;
    } catch {
      return MOCK_TASK_DEPENDENCIES;
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

  // 7. Action Requests, Approvals & Grants
  const [actionRequests, setActionRequests] = useState<VhActionRequest[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}_action_requests`);
      return stored ? JSON.parse(stored) : MOCK_ACTION_REQUESTS;
    } catch {
      return MOCK_ACTION_REQUESTS;
    }
  });

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

  // Filter "My Work Orders" strictly according to authenticated assignment
  const myWorkOrders = useMemo(() => {
    // 1. Manager & Supervisor see all team work orders
    if (currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER') {
      return workOrders;
    }

    // 2. QC Inspector sees completed tasks awaiting QC inspection + any direct tasks
    if (currentPersona === 'QC_INSPECTOR') {
      return workOrders.filter(
        (wo) => wo.status === 'COMPLETED' || wo.executor_id === currentProfile.id
      );
    }

    // 3. Field workers and contractors
    return workOrders.filter((wo) => {
      // Strict personal assignment by executor_id
      if (wo.executor_id === currentProfile.id) return true;

      // Contractor assignment by organization
      if (
        currentPersona === 'CONTRACTOR' &&
        wo.executor_type === 'CONTRACTOR' &&
        currentProfile.contractor_organization_id &&
        wo.contractor_organization_id === currentProfile.contractor_organization_id
      ) {
        return true;
      }

      return false;
    });
  }, [workOrders, currentProfile, currentPersona]);

  // Team / Area work orders for Supervisor & Manager oversight
  const teamWorkOrders = useMemo(() => {
    if (currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER') {
      return workOrders;
    }
    return myWorkOrders;
  }, [workOrders, currentPersona, myWorkOrders]);

  // Persist state safely to localStorage without storage quota overflow
  useEffect(() => {
    try {
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_cases`, JSON.stringify(cases));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_candidates`, JSON.stringify(issueCandidates));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_incidents`, JSON.stringify(incidents));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_tasks`, JSON.stringify(tasks));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_task_deps`, JSON.stringify(taskDependencies));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_work_orders`, JSON.stringify(workOrders));

      // Sanitize evidence URLs to avoid exceeding 5MB browser quota
      const sanitizedEvidence = evidence.map((e) => {
        if (e.file_url && e.file_url.startsWith('data:image/') && e.file_url.length > 50000) {
          return {
            ...e,
            file_url: `https://storage.vinhomes.vn/evidence/${e.file_id || e.id}.jpg`,
            metadata: {
              ...e.metadata,
              storage_key: `s3://vinhomes-evidence/${e.file_id || e.id}.jpg`,
              checksum_sha256: 'sha256-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
            },
          };
        }
        return e;
      });
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_evidence`, JSON.stringify(sanitizedEvidence));

      localStorage.setItem(`${STORAGE_KEY_PREFIX}_qc_results`, JSON.stringify(qcResults));
      localStorage.setItem(`${STORAGE_KEY_PREFIX}_action_requests`, JSON.stringify(actionRequests));
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
    actionRequests,
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
        throw new Error(`Không thể giải quyết sự cố: Còn ${pendingTasks.length} nhiệm vụ chưa hoàn thành (DONE).`);
      }

      const incidentWos = workOrders.filter((w) => w.incident_id === incidentId);
      const pendingWos = incidentWos.filter((w) => w.status !== 'COMPLETED');
      if (pendingWos.length > 0) {
        throw new Error(`Không thể giải quyết sự cố: Còn ${pendingWos.length} phiếu thi công chưa hoàn tất.`);
      }

      // Check QC results: Every task's latest attempt work order must have a passing QC result
      for (const t of incidentTasks) {
        const taskWos = incidentWos.filter((w) => w.task_id === t.id);
        if (taskWos.length > 0) {
          const latestWo = [...taskWos].sort((a, b) => (b.attempt_no || 1) - (a.attempt_no || 1))[0];
          if (latestWo.status !== 'COMPLETED') {
            throw new Error(`Không thể giải quyết sự cố: Phiếu thi công mới nhất (${latestWo.id}) của nhiệm vụ "${t.title}" chưa hoàn tất!`);
          }

          const latestQc = qcResults.find((q) => q.work_order_id === latestWo.id);
          if (!latestQc) {
            throw new Error(`Không thể giải quyết sự cố: Phiếu thi công ${latestWo.id} chưa có kết quả kiểm định chất lượng (QC)!`);
          }
          if (latestQc.outcome !== 'PASS') {
            throw new Error(`Không thể giải quyết sự cố: Kết quả kiểm định của phiếu ${latestWo.id} chưa đạt (kết quả: ${latestQc.outcome})!`);
          }
        }
      }

      // Check Pending Approvals
      const pendingApprovals = approvals.filter(
        (a) => a.action_request?.incident_id === incidentId && a.status === 'PENDING',
      );
      if (pendingApprovals.length > 0) {
        throw new Error(`Không thể giải quyết sự cố: Còn ${pendingApprovals.length} đề xuất phê duyệt đang chờ duyệt (PENDING)!`);
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
    [tasks, workOrders, qcResults, approvals],
  );

  const residentConfirmIncident = useCallback((incidentId: string, confirmed: boolean, rejectionReason?: string) => {
    const targetIncident = incidents.find((i) => i.id === incidentId);
    if (!targetIncident) throw new Error('Không tìm thấy sự cố!');

    if (targetIncident.status === 'CLOSED') {
      throw new Error(`Sự cố ${incidentId} đã được đóng (CLOSED), không thể thực hiện xác nhận lại!`);
    }

    if (targetIncident.status !== 'RESOLVED') {
      throw new Error(`Sự cố ${incidentId} chưa ở trạng thái ĐÃ XỬ LÝ (RESOLVED), hiện tại: ${targetIncident.status}!`);
    }

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
            location_json: {
              ...i.location_json,
              rejectionNote: rejectionReason || 'Cư dân/Khách hàng từ chối nghiệm thu, yêu cầu xử lý lại hiện trường.',
            },
            updated_at: now,
          };
        }
      }),
    );
  }, [incidents]);

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
        isQcInconclusive?: boolean;
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

      // Guard 1: Enforce State Machine Transition Map (with conditional bypass for QC INCONCLUSIVE)
      const currentStatus = targetWo.status;
      const validTargets = ALLOWED_WORK_ORDER_TRANSITIONS[currentStatus] || [];
      const isQcInconclusiveBypass =
        currentStatus === 'COMPLETED' &&
        targetStatus === 'IN_PROGRESS' &&
        Boolean(options?.isQcInconclusive);

      if (!validTargets.includes(targetStatus) && !isQcInconclusiveBypass) {
        throw new Error(
          `Vi phạm quy tắc State Machine: Không được phép chuyển từ "${currentStatus}" sang "${targetStatus}"! Các trạng thái hợp lệ tiếp theo: [${validTargets.join(', ')}]`,
        );
      }

      // Guard 1B: Enforce Task Dependency before starting IN_PROGRESS
      if (targetStatus === 'IN_PROGRESS') {
        const parentTask = tasks.find((t) => t.id === targetWo.task_id);
        if (parentTask) {
          const unresolvedDeps = taskDependencies
            .filter((dep) => dep.task_id === parentTask.id && dep.required)
            .filter((dep) => {
              const prereqTask = tasks.find((t) => t.id === dep.depends_on_task_id);
              if (dep.dependency_type === 'FINISH_TO_START') {
                return prereqTask?.status !== 'DONE';
              }
              if (dep.dependency_type === 'START_TO_START') {
                return prereqTask?.status !== 'IN_PROGRESS' && prereqTask?.status !== 'DONE';
              }
              return false;
            });

          if (unresolvedDeps.length > 0) {
            const depNames = unresolvedDeps
              .map((d) => {
                const t = tasks.find((task) => task.id === d.depends_on_task_id);
                return `${d.depends_on_task_id} (${t?.title || 'Chưa xong'})`;
              })
              .join(', ');
            throw new Error(`Vi phạm phụ thuộc quy trình (Task Dependency): Nhiệm vụ tiền nhiệm chưa hoàn tất [${depNames}]. Vui lòng hoàn thành nhiệm vụ trước khi bắt đầu thi công!`);
          }
        }
      }

      // Guard 2: Checks before transitioning to COMPLETED
      if (targetStatus === 'COMPLETED') {
        // 2A. Mandatory Evidence (1 BEFORE + 1 AFTER)
        const woEvidence = evidence.filter((e) => e.work_order_id === targetWo.id);
        const hasBefore = woEvidence.some((e) => e.capture_phase === 'BEFORE');
        const hasAfter = woEvidence.some((e) => e.capture_phase === 'AFTER');

        if (!hasBefore || !hasAfter) {
          throw new Error(
            'Chưa đủ điều kiện hoàn thành: Bắt buộc phải có tối thiểu 1 ảnh Trước (BEFORE) và 1 ảnh Sau (AFTER) khi thi công trước khi báo hoàn thành!',
          );
        }

        // 2B. A5 Sanitation / Landscape Checklist Guards
        const parentTask = tasks.find((t) => t.id === targetWo.task_id);
        if (parentTask?.domain_type === 'SANITATION' || parentTask?.domain_type === 'LANDSCAPE') {
          const plan = ((parentTask.domain_data as any)?.cleaning_plan as any) || (parentTask.domain_data as any) || {};
          if (!plan.arrived_at_site) {
            throw new Error('Chưa đủ điều kiện hoàn thành: Nhân viên vệ sinh chưa bấm xác nhận có mặt tại hiện trường!');
          }
          if (!plan.warning_signs_placed) {
            throw new Error('Chưa đủ điều kiện hoàn thành: Quy chuẩn vệ sinh A5 bắt buộc phải đặt biển cảnh báo an toàn!');
          }
          const pendingSteps = plan.actions?.filter((a: any) => !a.completed) || [];
          if (pendingSteps.length > 0) {
            throw new Error(`Chưa đủ điều kiện hoàn thành: Còn ${pendingSteps.length} bước công việc trong kế hoạch A5 chưa được tick hoàn thành!`);
          }
        }

        // 2C. Contractor Acceptance Guard
        if (targetWo.executor_type === 'CONTRACTOR') {
          if (targetWo.contractor_status !== 'ACCEPTED') {
            throw new Error('Chưa đủ điều kiện hoàn thành: Nhà thầu chưa thực hiện bước tiếp nhận công việc (ACCEPTED)!');
          }
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
            prev.map((t) =>
              t.id === targetWo.task_id && t.status !== 'IN_PROGRESS'
                ? { ...t, status: 'IN_PROGRESS' as const, updated_at: now }
                : t,
            ),
          );
        }
      }
    },
    [workOrders, evidence, tasks, currentProfile, currentPersona],
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
      contractor_organization_id?: string | null;
    }) => {
      // Guard 1: Only SUPERVISOR or MANAGER can assign work
      if (!currentProfile.canAssignWork) {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có quyền giao phiếu thi công (canAssignWork: false)! Chỉ Trưởng nhóm/Giám sát (SUPERVISOR) hoặc Ban Quản Lý (MANAGER) mới có thẩm quyền này.`,
        );
      }

      // Guard 2: Invariant Check - Task must belong to specified incident!
      const targetTask = tasks.find((t) => t.id === params.task_id);
      if (!targetTask) {
        throw new Error(`Nhiệm vụ ${params.task_id} không tồn tại trên hệ thống!`);
      }
      if (targetTask.incident_id !== params.incident_id) {
        throw new Error(
          `Lỗi toàn vẹn dữ liệu: Nhiệm vụ ${targetTask.id} thuộc sự cố ${targetTask.incident_id}, không khớp với sự cố ${params.incident_id} được chỉ định!`,
        );
      }

      // Guard 3: Duplicate active WorkOrder prevention for same task
      const existingActiveWo = workOrders.find(
        (w) => w.task_id === params.task_id && w.status !== 'CANCELLED' && w.status !== 'FAILED',
      );
      if (existingActiveWo) {
        throw new Error(
          `Nhiệm vụ ${params.task_id} đã có phiếu thi công đang hoạt động (${existingActiveWo.id}, trạng thái: ${existingActiveWo.status})! Không thể tạo thêm phiếu mới cho cùng nhiệm vụ.`,
        );
      }

      // Guard 4: Domain-appropriate Executor Check
      if (targetTask.domain_type === 'SANITATION' || targetTask.domain_type === 'LANDSCAPE') {
        if (params.executor_id === 'usr-tech-01' || params.executor_id === 'usr-sec-01') {
          throw new Error(`Nhiệm vụ ${targetTask.domain_type} phải giao cho nhân sự vệ sinh/cảnh quan (STAFF_SANITATION_A5), không thể giao cho kỹ thuật viên hoặc an ninh!`);
        }
      }
      if (targetTask.domain_type === 'SECURITY') {
        if (params.executor_id === 'usr-cleaner-01' || params.executor_id === 'usr-tech-01') {
          throw new Error(`Nhiệm vụ AN NINH phải giao cho nhân viên an ninh (STAFF_SECURITY), không thể giao cho nhân viên vệ sinh hoặc kỹ thuật viên!`);
        }
      }
      if (targetTask.domain_type === 'MEP' || targetTask.domain_type === 'TECHNICAL') {
        if (params.executor_id === 'usr-cleaner-01' || params.executor_id === 'usr-sec-01') {
          throw new Error(`Nhiệm vụ KỸ THUẬT/MEP phải giao cho kỹ thuật viên chuyên trách (STAFF_TECHNICAL), không thể giao cho nhân viên vệ sinh hoặc an ninh!`);
        }
      }
      if (targetTask.domain_type === 'ELEVATOR') {
        if (params.executor_type !== 'CONTRACTOR') {
          throw new Error('Nhiệm vụ Thang máy chuyên sâu bắt buộc phải giao cho Đối tác Nhà thầu (CONTRACTOR)!');
        }
        if (params.contractor_organization_id && params.contractor_organization_id !== 'org-otis') {
          throw new Error(`Tổ chức nhà thầu "${params.contractor_organization_id}" không có thẩm quyền đối với hệ thống thang máy Otis tại dự án!`);
        }
      }

      // Guard 5: Strict Checklist Derivation & Validation
      const expectedChecklist = (targetTask.domain_type && DOMAIN_CHECKLIST_MAP[targetTask.domain_type]) || 'CKL-VER-MEP-01';
      if (params.checklist_version_id && params.checklist_version_id !== expectedChecklist) {
        throw new Error(
          `Checklist ${params.checklist_version_id} không phù hợp với lĩnh vực ${targetTask.domain_type} của nhiệm vụ! (Checklist yêu cầu: ${expectedChecklist})`,
        );
      }
      const deducedChecklist = expectedChecklist;

      const now = new Date().toISOString();
      const newWoId = `WO-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;

      // Guard 6: Execution Grant Validation upon consumption
      if (params.execution_grant_id) {
        const targetGrant = executionGrants.find((g) => g.id === params.execution_grant_id);
        if (!targetGrant) {
          throw new Error(`Execution Grant "${params.execution_grant_id}" không tồn tại trên hệ thống!`);
        }
        if (targetGrant.status !== 'ACTIVE') {
          throw new Error(`Execution Grant "${params.execution_grant_id}" không ở trạng thái ACTIVE (hiện tại: ${targetGrant.status})!`);
        }
        if (new Date(targetGrant.expires_at).getTime() < Date.now()) {
          throw new Error(`Execution Grant "${params.execution_grant_id}" đã hết hạn vào lúc ${targetGrant.expires_at}! Không thể sử dụng.`);
        }

        const linkedReq = actionRequests.find((r) => r.id === targetGrant.action_request_id);
        if (linkedReq) {
          if (linkedReq.incident_id !== params.incident_id) {
            throw new Error(`Execution Grant thuộc sự cố ${linkedReq.incident_id}, không thể sử dụng cho sự cố ${params.incident_id}!`);
          }
          if (linkedReq.task_id && linkedReq.task_id !== params.task_id) {
            throw new Error(`Execution Grant thuộc nhiệm vụ ${linkedReq.task_id}, không thể sử dụng cho nhiệm vụ ${params.task_id}!`);
          }
        }

        if (targetGrant.granted_to && params.executor_id && targetGrant.granted_to !== params.executor_id) {
          const isGrantRecipient = targetGrant.granted_to === params.executor_id || targetGrant.granted_to === linkedReq?.requested_by_id;
          if (!isGrantRecipient) {
            throw new Error(`Execution Grant được cấp riêng cho tài khoản ${targetGrant.granted_to}, không thể chuyển giao cho ${params.executor_id}!`);
          }
        }

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
        contractor_organization_id:
          params.contractor_organization_id ||
          (params.executor_type === 'CONTRACTOR' ? 'org-otis' : null),
        status: 'ASSIGNED',
        attempt_no: 1,
        redo_of_work_order_id: null,
        checklist_version_id: deducedChecklist,
        execution_started_at: null,
        execution_completed_at: null,
        result: null,
        version: 1,
        created_at: now,
        updated_at: now,
      };

      setWorkOrders((prev) => [wo, ...prev]);

      // Move task from OPEN to ASSIGNED (not straight to IN_PROGRESS)
      setTasks((prev) =>
        prev.map((t) => (t.id === params.task_id && t.status === 'OPEN' ? { ...t, status: 'ASSIGNED' as const, updated_at: now } : t)),
      );

      return wo;
    },
    [currentProfile, tasks, workOrders, executionGrants, actionRequests],
  );

  // ==========================================
  // CONTRACTOR ACTIONS (WITH RBAC & ORG CHECK)
  // ==========================================
  const respondToContractorJob = useCallback(
    (workOrderId: string, action: 'ACCEPT' | 'REJECT', reason?: string, assignedStaff?: string) => {
      if (currentPersona !== 'CONTRACTOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân sự nhà thầu hoặc Quản lý BQL mới có quyền tiếp nhận/từ chối phiếu thầu!');
      }

      const targetWo = workOrders.find((w) => w.id === workOrderId);
      if (!targetWo) throw new Error('Không tìm thấy phiếu thi công của nhà thầu!');

      if (currentPersona === 'CONTRACTOR') {
        if (
          currentProfile.contractor_organization_id &&
          targetWo.contractor_organization_id &&
          targetWo.contractor_organization_id !== currentProfile.contractor_organization_id
        ) {
          throw new Error('Bạn không thuộc tổ chức nhà thầu phụ trách phiếu thi công này!');
        }
      }

      const now = new Date().toISOString();
      setWorkOrders((prev) =>
        prev.map((w) => {
          if (w.id !== workOrderId) return w;
          if (action === 'ACCEPT') {
            return {
              ...w,
              contractor_status: 'ACCEPTED',
              contractor_assigned_worker: assignedStaff || w.contractor_assigned_worker,
              status: 'ASSIGNED', // Remains ASSIGNED until technician clicks "Bắt đầu thi công"
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
    [currentPersona, currentProfile, workOrders],
  );

  const recordContractorMaterials = useCallback(
    (workOrderId: string, materials: Array<{ part_name: string; quantity: number; unit: string }>) => {
      if (currentPersona !== 'CONTRACTOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân sự nhà thầu hoặc Quản lý BQL mới có quyền cập nhật vật tư thay thế!');
      }

      const targetWo = workOrders.find((w) => w.id === workOrderId);
      if (!targetWo) throw new Error('Không tìm thấy phiếu thi công!');

      if (currentPersona === 'CONTRACTOR') {
        if (
          currentProfile.contractor_organization_id &&
          targetWo.contractor_organization_id &&
          targetWo.contractor_organization_id !== currentProfile.contractor_organization_id
        ) {
          throw new Error('Bạn không thuộc tổ chức nhà thầu được giao phiếu thi công này!');
        }
      }

      setWorkOrders((prev) =>
        prev.map((w) => (w.id === workOrderId ? { ...w, materials_used: materials, updated_at: new Date().toISOString() } : w)),
      );
    },
    [currentPersona, currentProfile, workOrders],
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
          `Vi phạm nguyên tắc độc lập kiểm định (Segregation of Duties): Bạn (${targetWo.executor_name || actualCheckerId}) là người trực tiếp thi công phiếu ${targetWo.id}, không được phép tự chấm nghiệm thu QC cho chính mình! Vui lòng nhờ QC Inspector độc lập nghiệm thu.`,
        );
      }

      // Guard 4: Must have explicit QC capability (canQC: true) - No manager bypass
      if (!currentProfile.canQC) {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có thẩm quyền ký ban hành biên bản nghiệm thu QC! Theo quy chuẩn kiểm định độc lập, chỉ chuyên viên QC Inspector độc lập (QC_INSPECTOR) mới có thẩm quyền này.`,
        );
      }

      // Guard 5: Immutability - Finalized QC record (PASS or FAIL) cannot be duplicated or overwritten
      const existingFinalQc = qcResults.find(
        (q) => q.work_order_id === targetWo.id && q.outcome !== 'INCONCLUSIVE',
      );
      if (existingFinalQc) {
        throw new Error(
          `Biên bản nghiệm thu QC (${existingFinalQc.id}: ${existingFinalQc.outcome}) cho phiếu ${targetWo.id} đã được ban hành và là bản ghi bất biến (Immutable Record). Không được phép tạo thêm biên bản QC thứ hai!`,
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
        // PASS -> Task is complete ONLY IF all other work orders for this task are completed and no active redos
        const taskWos = workOrders.filter((w) => w.task_id === targetWo.task_id);
        const hasUnfinishedWos = taskWos.some((w) => w.id !== targetWo.id && w.status !== 'COMPLETED');
        if (!hasUnfinishedWos) {
          setTasks((prev) =>
            prev.map((t) => (t.id === targetWo.task_id ? { ...t, status: 'DONE' as const, updated_at: now } : t)),
          );
        }
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
          isQcInconclusive: true,
        });
      }

      return { qc: newQc };
    },
    [workOrders, evidence, qcResults, currentProfile, transitionWorkOrderStatus],
  );

  // ==========================================
  // EVIDENCE MANAGEMENT (WITH ACTOR IDENTITY & GUARDS)
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
      // Guard 1: QC Phase requires explicit QC Inspector permission
      if (newEvidence.capture_phase === 'QC' && !currentProfile.canQC) {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có quyền tải ảnh nghiệm thu QC (capture_phase = QC)! Chỉ chuyên viên QC Inspector mới có thẩm quyền này.`,
        );
      }

      // Guard 2: Work Order Phase & Ownership Check
      if (newEvidence.work_order_id) {
        const targetWo = workOrders.find((w) => w.id === newEvidence.work_order_id);
        if (targetWo) {
          // Closed work order cannot receive new BEFORE/AFTER photos
          if (targetWo.status === 'COMPLETED' || targetWo.status === 'CANCELLED') {
            if (newEvidence.capture_phase === 'BEFORE' || newEvidence.capture_phase === 'AFTER') {
              throw new Error(
                `Phiếu thi công ${targetWo.id} đã ở trạng thái ${targetWo.status === 'COMPLETED' ? 'HOÀN THÀNH' : 'ĐÃ HỦY'}. Không thể tải thêm ảnh Trước/Sau thi công!`,
              );
            }
          }

          // AFTER photo requires IN_PROGRESS status
          if (newEvidence.capture_phase === 'AFTER' && targetWo.status !== 'IN_PROGRESS') {
            throw new Error(
              `Phiếu thi công ${targetWo.id} đang ở trạng thái "${targetWo.status}". Ảnh Sau thi công (AFTER) chỉ được tải lên khi công việc đang được tiến hành (IN_PROGRESS)!`,
            );
          }

          // QC photo requires COMPLETED status
          if (newEvidence.capture_phase === 'QC' && targetWo.status !== 'COMPLETED') {
            throw new Error(
              `Phiếu thi công ${targetWo.id} chưa hoàn thành (hiện tại: ${targetWo.status}). Ảnh nghiệm thu (QC) chỉ được chụp khi công việc đã hoàn tất (COMPLETED)!`,
            );
          }

          // Evidence Ownership Guard
          if (newEvidence.capture_phase === 'BEFORE' || newEvidence.capture_phase === 'AFTER') {
            const isExecutor = targetWo.executor_id === currentProfile.id;
            const isSameContractorOrg =
              currentPersona === 'CONTRACTOR' &&
              currentProfile.contractor_organization_id &&
              targetWo.contractor_organization_id === currentProfile.contractor_organization_id;
            const isSupervisorOrManager = currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER';

            if (!isExecutor && !isSameContractorOrg && !isSupervisorOrManager) {
              throw new Error(
                `Bạn không có quyền tải ảnh Trước/Sau cho phiếu ${targetWo.id}! Chỉ người thi công được giao (${targetWo.executor_name || targetWo.executor_id}) hoặc Giám sát/BQL mới được tải ảnh.`,
              );
            }
          }
        }
      }

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
          gpsCoordinates: newEvidence.fileMetadata?.gpsCoordinates || null,
          fileSizeKb: newEvidence.fileMetadata?.sizeBytes ? Math.round(newEvidence.fileMetadata.sizeBytes / 1024) : 480,
          fileName: newEvidence.fileMetadata?.fileName || 'evidence_capture.jpg',
          timestamp: new Date().toISOString(),
        },
      };

      setEvidence((prev) => [evidenceRecord, ...prev]);
      return evidenceRecord;
    },
    [workOrders, currentProfile, currentPersona],
  );

  // ==========================================
  // SECURITY OPERATIONS ACTIONS
  // ==========================================
  const toggleSecurityCheckpoint = useCallback(
    (checkpointId: string, notes?: string, photoUrl?: string) => {
      if (currentPersona !== 'STAFF_SECURITY' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân viên an ninh hiện trường mới có quyền check-in trạm tuần tra!');
      }

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
    [currentPersona, currentProfile],
  );

  const reportSecurityIncident = useCallback(
    (reportData: Omit<SecurityIncidentReport, 'id' | 'reported_at'>) => {
      if (currentPersona !== 'STAFF_SECURITY' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân viên an ninh hiện trường mới có quyền lập biên bản sự việc an ninh!');
      }

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
    [currentPersona, currentProfile],
  );

  const submitSecurityHandover = useCallback(
    (handoverData: Omit<SecurityShiftHandover, 'id' | 'handover_at'>) => {
      if (currentPersona !== 'STAFF_SECURITY' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân viên an ninh ca trực mới có quyền bàn giao ca trực!');
      }

      const now = new Date().toISOString();
      const newHandover: SecurityShiftHandover = {
        ...handoverData,
        id: `SH-${Date.now().toString().slice(-4)}`,
        handover_at: now,
      };

      setSecurityHandovers((prev) => [newHandover, ...prev]);
      return newHandover;
    },
    [currentPersona],
  );

  const escalateSecurityIncident = useCallback(
    (reportId: string): VhIncident => {
      const report = securityIncidents.find((s) => s.id === reportId);
      if (!report) throw new Error('Không tìm thấy biên bản an ninh!');

      const newIncId = `INC-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
      const now = new Date().toISOString();

      const personNames = report.persons_involved.map((p) => p.name).join(', ');
      const vehiclePlates = report.vehicles_involved.map((v) => v.license_plate).join(', ');

      const newInc: VhIncident = {
        id: newIncId,
        tenant_id: 'tenant-vhm-sc',
        project_id: 'proj-smart-city',
        tower_id: report.location.split(' ')[0] || 'S2.01',
        category: 'SECURITY',
        title: `[An Ninh Khẩn Cấp] ${report.title}`,
        location_json: {
          towerCode: report.location.split(' ')[0] || 'S2.01',
          areaCode: report.location,
          description: `Biên bản sự việc: ${report.action_taken}. Đối tượng: ${personNames || 'N/A'}. Phương tiện: ${vehiclePlates || 'N/A'}`,
        },
        severity: report.severity,
        status: 'OPEN',
        stage: 'TRIAGE',
        owner_user_id: currentProfile.id,
        sla_due_at: new Date(Date.now() + 2 * 3600 * 1000).toISOString(),
        resolved_at: null,
        closed_at: null,
        version: 1,
        created_at: now,
        updated_at: now,
      };

      const newTaskId = `TSK-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
      const newTask: VhTask = {
        id: newTaskId,
        incident_id: newIncId,
        title: `[Xử lý an ninh khẩn cấp] ${report.title}`,
        domain_type: 'SECURITY',
        domain_data: {
          reportId: report.id,
          location: report.location,
          actionTaken: report.action_taken,
        },
        domain_schema_version: 1,
        assignee_type: 'STAFF',
        assignee_id: currentProfile.id,
        assignee_name: currentProfile.name,
        status: 'OPEN',
        priority: report.severity === 'P1' ? 'URGENT' : 'HIGH',
        due_at: new Date(Date.now() + 2 * 3600 * 1000).toISOString(),
        version: 1,
        created_at: now,
        updated_at: now,
      };

      setIncidents((prev) => [newInc, ...prev]);
      setTasks((prev) => [newTask, ...prev]);
      return newInc;
    },
    [securityIncidents, currentProfile],
  );

  // ==========================================
  // A5 SANITATION ACTIONS
  // ==========================================
  const toggleCleaningAction = useCallback(
    (taskId: string, actionIndex: number, completed: boolean, note?: string) => {
      if (currentPersona !== 'STAFF_SANITATION_A5' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
        throw new Error('Chỉ nhân viên vệ sinh A5 trực tiếp mới có quyền tick hoàn thành các bước vệ sinh!');
      }

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
    [currentPersona],
  );

  const confirmSiteArrival = useCallback((taskId: string) => {
    if (currentPersona !== 'STAFF_SANITATION_A5' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
      throw new Error('Chỉ nhân viên vệ sinh A5 mới có quyền xác nhận có mặt hiện trường!');
    }

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
  }, [currentPersona]);

  const toggleWarningSigns = useCallback((taskId: string, placed: boolean) => {
    if (currentPersona !== 'STAFF_SANITATION_A5' && currentPersona !== 'SUPERVISOR' && currentPersona !== 'MANAGER') {
      throw new Error('Chỉ nhân viên vệ sinh A5 mới có quyền đặt biển cảnh báo!');
    }

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
  }, [currentPersona]);

  const saveCleaningRootCause = useCallback((taskId: string, rootCause: string, wasteKg?: number) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id !== taskId) return t;
        const currentPlan = ((t.domain_data as any)?.cleaning_plan as any) || (t.domain_data as any) || {};
        return {
          ...t,
          domain_data: {
            ...t.domain_data,
            ...currentPlan,
            root_cause_analysis: rootCause,
            waste_kg: wasteKg !== undefined ? wasteKg : currentPlan.waste_kg,
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
      if (!currentProfile.canApproveBudget) {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có thẩm quyền phê duyệt chi phí / lệnh thi công! Chỉ Ban Quản Lý (MANAGER) mới có quyền này.`,
        );
      }

      const targetApproval = approvals.find((a) => a.id === approvalId);
      if (!targetApproval) throw new Error('Không tìm thấy yêu cầu phê duyệt!');

      // Guard: Only PENDING approvals can be approved
      if (targetApproval.status !== 'PENDING') {
        throw new Error(`Yêu cầu phê duyệt ${targetApproval.id} không ở trạng thái PENDING (hiện tại: ${targetApproval.status})!`);
      }

      // Guard: Cannot approve expired approval
      if (targetApproval.expires_at && new Date(targetApproval.expires_at).getTime() < Date.now()) {
        throw new Error(`Yêu cầu phê duyệt ${targetApproval.id} đã hết hạn vào lúc ${targetApproval.expires_at}! Không thể phê duyệt.`);
      }

      // Guard: Avoid duplicate grants for the same approval
      const existingGrant = executionGrants.find((g) => g.approval_id === approvalId);
      if (existingGrant) {
        throw new Error(`Đã tồn tại Execution Grant (${existingGrant.id}) cho phê duyệt này! Không được tạo trùng lặp.`);
      }

      const now = new Date().toISOString();
      const grantId = `GRNT-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;

      // Issue grant to requester or executor (NOT the reviewer/Manager)
      const targetActor = targetApproval.requested_by_id || targetApproval.action_request?.requested_by_id || 'usr-tech-01';

      const newGrant: VhExecutionGrant = {
        id: grantId,
        action_request_id: targetApproval.action_request_id,
        approval_id: targetApproval.id,
        granted_to: targetActor,
        allowed_action_type: (targetApproval.action_request?.action_type || 'PURCHASE_MATERIAL') as any,
        granted_at: now,
        expires_at: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
        payload_hash: targetApproval.action_payload_hash || 'hash-mock',
        status: 'ACTIVE',
        consumed_by_work_order_id: null,
      };

      setExecutionGrants((prev) => [newGrant, ...prev]);

      // Synchronize Action Request status to APPROVED
      if (targetApproval.action_request_id) {
        setActionRequests((prev) =>
          prev.map((r) =>
            r.id === targetApproval.action_request_id ? { ...r, status: 'APPROVED' as const } : r,
          ),
        );
      }

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
    [approvals, currentProfile, executionGrants],
  );

  const rejectAction = useCallback(
    (approvalId: string, reason: string) => {
      if (!currentProfile.canApproveBudget) {
        throw new Error(
          `Tài khoản vai trò "${currentProfile.roleTitle}" không có thẩm quyền từ chối phê duyệt! Chỉ Ban Quản Lý (MANAGER) mới có quyền này.`,
        );
      }

      const targetApproval = approvals.find((a) => a.id === approvalId);
      if (!targetApproval) throw new Error('Không tìm thấy yêu cầu phê duyệt!');

      // Guard: Only PENDING approvals can be rejected
      if (targetApproval.status !== 'PENDING') {
        throw new Error(`Yêu cầu phê duyệt ${targetApproval.id} không ở trạng thái PENDING (hiện tại: ${targetApproval.status})!`);
      }

      // Guard: Cannot reject expired approval
      if (targetApproval.expires_at && new Date(targetApproval.expires_at).getTime() < Date.now()) {
        throw new Error(`Yêu cầu phê duyệt ${targetApproval.id} đã hết hạn vào lúc ${targetApproval.expires_at}! Không thể từ chối.`);
      }

      // Guard: Cannot reject if an active execution grant already exists
      const existingGrant = executionGrants.find((g) => g.approval_id === approvalId && g.status === 'ACTIVE');
      if (existingGrant) {
        throw new Error(`Phê duyệt này đã được ban hành Execution Grant (${existingGrant.id})! Không thể từ chối.`);
      }

      const now = new Date().toISOString();

      // Synchronize Action Request status to REJECTED
      if (targetApproval.action_request_id) {
        setActionRequests((prev) =>
          prev.map((r) =>
            r.id === targetApproval.action_request_id ? { ...r, status: 'REJECTED' as const } : r,
          ),
        );
      }

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
    [approvals, currentProfile, executionGrants],
  );

  // Reset to default mock
  const resetToDefaultMock = useCallback(() => {
    setCases(MOCK_CASES);
    setIssueCandidates(MOCK_ISSUE_CANDIDATES);
    setIncidents(MOCK_INCIDENTS);
    setTasks(MOCK_TASKS);
    setTaskDependencies(MOCK_TASK_DEPENDENCIES);
    setWorkOrders(MOCK_WORK_ORDERS);
    setEvidence(MOCK_EVIDENCE);
    setQcResults(MOCK_QC_RESULTS);
    setActionRequests(MOCK_ACTION_REQUESTS);
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
    taskDependencies,
    workOrders,
    myWorkOrders,
    teamWorkOrders,
    evidence,
    qcResults,
    actionRequests,
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
    escalateSecurityIncident,
    toggleCleaningAction,
    confirmSiteArrival,
    toggleWarningSigns,
    saveCleaningRootCause,
    resetToDefaultMock,
  };
}

export type OperationsDataContextType = ReturnType<typeof useOperationsDataInternal>;

const OperationsContext = createContext<OperationsDataContextType | null>(null);

export function OperationsProvider({ children }: { children: ReactNode }) {
  const data = useOperationsDataInternal();
  return createElement(OperationsContext.Provider, { value: data }, children);
}

export function useOperationsData(): OperationsDataContextType {
  const context = useContext(OperationsContext);
  if (!context) {
    throw new Error('useOperationsData must be used within an OperationsProvider');
  }
  return context;
}
