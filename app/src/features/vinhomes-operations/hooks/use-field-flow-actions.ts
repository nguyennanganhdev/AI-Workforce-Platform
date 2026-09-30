/**
 * Technician field flow actions (rules R1–R10 of docs/vinhomes-operations-staff-field-flow.md).
 * Called inside useOperationsDataInternal so state stays in the single operations store.
 */
import { useCallback, useEffect, type Dispatch, type SetStateAction } from 'react';
import type { VhWorkOrder } from '../types/work-order';
import type { VhEvidenceRef } from '../types/evidence';
import type { VhIncident } from '../types/incident';
import type { VhTask } from '../types/task';
import type { OperationsPersona, UserProfile } from '../types/persona';
import {
  AUTO_COMPLETE_HOURS,
  quoteTotal,
  type DeclineReason,
  type FieldFlow,
  type FieldQuote,
  type FieldStage,
  type CleaningPauseReason,
  type PauseReason,
  type ResidentChannel,
  type SecurityOutcome,
} from '../types/field-flow';
import { emptyFieldFlow, getCleaningBlockers, getFieldFlow, getSecurityBlockers, getWorkBlockers, stageToWorkOrderStatus } from '../lib/field-flow';

interface Deps {
  workOrders: VhWorkOrder[];
  setWorkOrders: Dispatch<SetStateAction<VhWorkOrder[]>>;
  evidence: VhEvidenceRef[];
  incidents: VhIncident[];
  tasks: VhTask[];
  currentProfile: UserProfile;
  currentPersona: OperationsPersona;
}

const nowIso = () => new Date().toISOString();

type Patch = Partial<FieldFlow> | ((flow: FieldFlow) => Partial<FieldFlow>);

/**
 * Options for a step the resident takes. From the resident app the owner check does not apply, and
 * `expectedVersion` is the WO version the resident was looking at: if staff changed the job since
 * (or the other channel already answered), the action is refused instead of applied to newer content.
 */
export interface ResidentActOptions {
  fromResidentApp?: boolean;
  expectedVersion?: number;
}

interface LoadOptions {
  skipOwnerCheck?: boolean;
  expectedVersion?: number;
}

const residentLoad = (opts?: ResidentActOptions): LoadOptions => ({
  skipOwnerCheck: opts?.fromResidentApp,
  expectedVersion: opts?.expectedVersion,
});

export function useFieldFlowActions({ workOrders, setWorkOrders, evidence, incidents, tasks, currentProfile, currentPersona }: Deps) {
  const categoryOf = useCallback(
    (wo: VhWorkOrder) => incidents.find((i) => i.id === wo.incident_id)?.category,
    [incidents],
  );
  const taskOf = useCallback((wo: VhWorkOrder) => tasks.find((t) => t.id === wo.task_id), [tasks]);

  const load = useCallback(
    (woId: string, allowed: FieldStage[] | null, opts?: LoadOptions) => {
      const wo = workOrders.find((w) => w.id === woId);
      if (!wo) throw new Error(`Không tìm thấy phiếu công việc ${woId}!`);
      if (opts?.expectedVersion !== undefined && opts.expectedVersion !== wo.version) {
        throw new Error('Nội dung công việc vừa được cập nhật. Vui lòng xem lại trước khi xác nhận.');
      }
      // R1: only the assignee (or supervisor/manager) may act on the job
      const isOwner = wo.executor_id === currentProfile.id;
      const isLead = currentPersona === 'SUPERVISOR' || currentPersona === 'MANAGER';
      if (!opts?.skipOwnerCheck && !isOwner && !isLead) {
        throw new Error('Phiếu công việc này không được giao cho bạn!');
      }
      const flow = getFieldFlow(wo, categoryOf(wo), taskOf(wo));
      if (allowed && !allowed.includes(flow.stage)) {
        throw new Error(`Thao tác không hợp lệ ở bước hiện tại (${flow.stage}).`);
      }
      return { wo, flow };
    },
    [workOrders, currentProfile, currentPersona, categoryOf, taskOf],
  );

  const commit = useCallback(
    (woId: string, patch: Patch, extra?: Partial<VhWorkOrder>) => {
      const now = new Date().toISOString();
      setWorkOrders((prev) =>
        prev.map((wo) => {
          if (wo.id !== woId) return wo;
          const flow = getFieldFlow(wo, categoryOf(wo), taskOf(wo));
          const next = { ...flow, ...(typeof patch === 'function' ? patch(flow) : patch) };
          return {
            ...wo,
            ...extra,
            field_flow: next,
            status: stageToWorkOrderStatus(next.stage),
            version: wo.version + 1,
            updated_at: now,
          };
        }),
      );
    },
    [setWorkOrders, categoryOf, taskOf],
  );



  // ---------- Bước 1–2: Nhận việc, đến nơi ----------
  const acceptJob = useCallback((woId: string) => {
    load(woId, ['ASSIGNED']);
    commit(woId, { stage: 'ACCEPTED', accepted_at: nowIso() });
  }, [load, commit]);

  const declineJob = useCallback((woId: string, reason: DeclineReason, note?: string) => {
    load(woId, ['ASSIGNED']);
    if (reason === 'OTHER' && !note?.trim()) throw new Error('Vui lòng ghi rõ lý do từ chối.');
    commit(woId, { stage: 'DECLINED', decline_reason: reason, decline_note: note?.trim() || null });
  }, [load, commit]);

  const checkIn = useCallback((woId: string) => {
    const { flow } = load(woId, ['ACCEPTED']);
    const now = nowIso();
    if (flow.kind !== 'REPAIR') {
      // Vệ sinh / an ninh không có bước báo giá: đến nơi là bắt đầu làm
      commit(woId, { stage: 'IN_PROGRESS', arrived_at: now, started_at: now, no_charge: true }, { execution_started_at: now });
      return;
    }
    commit(woId, { stage: 'ON_SITE', arrived_at: now });
  }, [load, commit]);

  // ---------- Vệ sinh A5: ảnh TRƯỚC → đặt biển → lau → ảnh SAU → hoàn thành ----------
  const jobEvidence = useCallback(
    (woId: string) => evidence.filter((e) => e.work_order_id === woId),
    [evidence],
  );

  const placeWarningSign = useCallback((woId: string) => {
    const { flow } = load(woId, ['IN_PROGRESS']);
    if (flow.kind !== 'CLEANING' || !flow.sign_required) throw new Error('Việc này không yêu cầu đặt biển cảnh báo.');
    if (!jobEvidence(woId).some((e) => e.capture_phase === 'BEFORE')) {
      throw new Error('Chụp ảnh hiện trường TRƯỚC khi đặt biển.');
    }
    commit(woId, { sign_placed_at: nowIso() });
  }, [load, commit, jobEvidence]);

  const markCleaned = useCallback((woId: string) => {
    const { flow } = load(woId, ['IN_PROGRESS']);
    if (flow.kind !== 'CLEANING') throw new Error('Thao tác chỉ dành cho việc vệ sinh.');
    if (!jobEvidence(woId).some((e) => e.capture_phase === 'BEFORE')) throw new Error('Chụp ảnh hiện trường TRƯỚC khi làm.');
    if (flow.sign_required && !flow.sign_placed_at) throw new Error('Đặt biển cảnh báo sàn ướt trước khi lau.');
    commit(woId, { cleaned_at: nowIso() });
  }, [load, commit, jobEvidence]);

  const completeCleaning = useCallback((woId: string, note: string) => {
    const { flow } = load(woId, ['IN_PROGRESS']);
    if (flow.kind !== 'CLEANING') throw new Error('Thao tác chỉ dành cho việc vệ sinh.');
    const blockers = getCleaningBlockers(flow, jobEvidence(woId));
    if (blockers.length > 0) throw new Error(`Chưa đủ điều kiện: ${blockers.join('; ')}.`);
    const now = nowIso();
    commit(
      woId,
      { stage: 'DONE', submitted_at: now, completed_at: now, report_final_note: note.trim() },
      { execution_completed_at: now },
    );
  }, [load, commit, jobEvidence]);

  // ---------- Bước 3–5: Chẩn đoán, danh mục, cư dân đồng ý ----------
  // ---------- An ninh: ảnh hiện trường → kết quả nhắc nhở → hoàn thành ----------
  const setSecurityOutcome = useCallback((woId: string, outcome: SecurityOutcome) => {
    const { flow } = load(woId, ['IN_PROGRESS']);
    if (flow.kind !== 'SECURITY') throw new Error('Thao tác chỉ dành cho việc an ninh.');
    commit(woId, { security_outcome: outcome });
  }, [load, commit]);

  const setReportNote = useCallback((woId: string, note: string) => {
    load(woId, ['IN_PROGRESS', 'REPORT_READY']);
    commit(woId, { report_final_note: note });
  }, [load, commit]);

  const completeSecurity = useCallback((woId: string) => {
    const { flow } = load(woId, ['IN_PROGRESS']);
    if (flow.kind !== 'SECURITY') throw new Error('Thao tác chỉ dành cho việc an ninh.');
    const blockers = getSecurityBlockers(flow, jobEvidence(woId), flow.report_final_note);
    if (blockers.length > 0) throw new Error(`Chưa đủ điều kiện: ${blockers.join('; ')}.`);
    const now = nowIso();
    commit(woId, { stage: 'DONE', submitted_at: now, completed_at: now }, { execution_completed_at: now });
  }, [load, commit, jobEvidence]);

  const setDiagnosisNote = useCallback((woId: string, note: string) => {
    load(woId, null);
    commit(woId, { diagnosis_note: note });
  }, [load, commit]);

  const startQuote = useCallback((woId: string) => {
    load(woId, ['ON_SITE']);
    commit(woId, { stage: 'QUOTE_DRAFT', no_charge: false });
  }, [load, commit]);

  const startNoCharge = useCallback((woId: string) => {
    load(woId, ['ON_SITE']);
    commit(woId, { stage: 'IN_PROGRESS', no_charge: true, started_at: nowIso() }, { execution_started_at: nowIso() });
  }, [load, commit]);

  const saveQuote = useCallback((woId: string, quote: FieldQuote) => {
    const { flow } = load(woId, ['QUOTE_DRAFT', 'IN_PROGRESS']);
    if (quote.lines.some((l) => l.quantity <= 0 || l.unit_price < 0)) {
      throw new Error('Số lượng phải lớn hơn 0 và đơn giá không được âm.');
    }
    let lines = quote.lines.map((l) => ({ ...l, amount: l.quantity * l.unit_price }));
    let laborCost = quote.labor_cost;
    if (flow.stage === 'IN_PROGRESS' && flow.agreement) {
      // Agreed lines are frozen; anything new is additional (R5 enforced at signature time)
      const agreedIds = new Set(flow.agreement.quote_snapshot.map((l) => l.id));
      const extra = lines.filter((l) => !agreedIds.has(l.id)).map((l) => ({ ...l, is_additional: true }));
      lines = [...flow.agreement.quote_snapshot, ...extra];
      laborCost = flow.agreement.labor_cost;
    }
    commit(woId, { quote: { lines, labor_cost: laborCost, warranty_months: quote.warranty_months } });
  }, [load, commit]);

  /** DEVICE = đưa máy cho cư dân xem; APP = gửi danh mục sang app cư dân. */
  const handToResidentForAgreement = useCallback((woId: string, channel: ResidentChannel = 'DEVICE') => {
    const { flow } = load(woId, ['QUOTE_DRAFT']);
    if (flow.quote.lines.length === 0 && flow.quote.labor_cost <= 0) {
      throw new Error('Danh mục đang trống: thêm vật tư hoặc tiền công trước khi đưa cư dân xem.');
    }
    commit(woId, { stage: 'AWAITING_RESIDENT_AGREEMENT', resident_channel: channel });
  }, [load, commit]);

  /** Đổi kênh khi đang chờ cư dân (VD: đã gửi app nhưng cư dân đứng cạnh, đưa máy luôn). */
  const setResidentChannel = useCallback((woId: string, channel: ResidentChannel) => {
    load(woId, ['AWAITING_RESIDENT_AGREEMENT', 'AWAITING_RESIDENT_SIGNATURE']);
    commit(woId, { resident_channel: channel });
  }, [load, commit]);

  const residentAgree = useCallback((woId: string, opts?: ResidentActOptions) => {
    const { flow } = load(woId, ['AWAITING_RESIDENT_AGREEMENT'], residentLoad(opts));
    const now = nowIso();
    commit(
      woId,
      {
        stage: 'IN_PROGRESS',
        resident_channel: null,
        started_at: now,
        agreement: {
          quote_snapshot: flow.quote.lines,
          labor_cost: flow.quote.labor_cost,
          total: quoteTotal(flow.quote.lines, flow.quote.labor_cost),
          agreed_at: now,
        },
      },
      { execution_started_at: now },
    );
  }, [load, commit]);

  const residentRequestChanges = useCallback((woId: string, opts?: ResidentActOptions) => {
    load(woId, ['AWAITING_RESIDENT_AGREEMENT'], residentLoad(opts));
    commit(woId, { stage: 'QUOTE_DRAFT', resident_channel: null });
  }, [load, commit]);

  const residentCancel = useCallback((woId: string, opts?: ResidentActOptions) => {
    load(woId, ['AWAITING_RESIDENT_AGREEMENT'], residentLoad(opts));
    commit(woId, { stage: 'CANCELLED_BY_RESIDENT', resident_channel: null, completed_at: nowIso() });
  }, [load, commit]);

  // ---------- Bước 6–7: Sửa, tạm dừng ----------
  const toggleChecklistItem = useCallback((woId: string, itemId: string) => {
    load(woId, ['IN_PROGRESS']);
    commit(woId, (f) => ({ checklist: f.checklist.map((c) => (c.id === itemId ? { ...c, done: !c.done } : c)) }));
  }, [load, commit]);

  const pauseJob = useCallback((woId: string, reason: PauseReason | CleaningPauseReason, note?: string) => {
    const { flow } = load(woId, ['ACCEPTED', 'ON_SITE', 'QUOTE_DRAFT', 'IN_PROGRESS']);
    // R10
    if (reason === 'OTHER' && !note?.trim()) throw new Error('Vui lòng ghi rõ lý do tạm dừng.');
    commit(
      woId,
      { stage: 'PAUSED', paused_from: flow.stage, pause_reason: reason, pause_note: note?.trim() || null },
      { blocked_reason: note?.trim() || reason },
    );
  }, [load, commit]);

  const resumeJob = useCallback((woId: string) => {
    const { flow } = load(woId, ['PAUSED']);
    commit(woId, { stage: flow.paused_from || 'IN_PROGRESS', paused_from: null, pause_reason: null, pause_note: null }, { blocked_reason: null });
  }, [load, commit]);

  // ---------- Bước 8: Cư dân ký ----------
  const requestSignature = useCallback((woId: string, channel: ResidentChannel = 'DEVICE') => {
    const { wo, flow } = load(woId, ['IN_PROGRESS']);
    // R4 + R5
    const blockers = getWorkBlockers(flow, evidence.filter((e) => e.work_order_id === wo.id));
    if (blockers.length > 0) throw new Error(`Chưa đủ điều kiện: ${blockers.join('; ')}.`);
    commit(woId, { stage: 'AWAITING_RESIDENT_SIGNATURE', resident_channel: channel });
  }, [load, commit, evidence]);

  const backToWork = useCallback((woId: string) => {
    load(woId, ['AWAITING_RESIDENT_SIGNATURE']);
    commit(woId, { stage: 'IN_PROGRESS', resident_channel: null });
  }, [load, commit]);

  const residentSign = useCallback((woId: string, signatureDataUrl: string, opts?: ResidentActOptions) => {
    const { flow } = load(woId, ['AWAITING_RESIDENT_SIGNATURE'], residentLoad(opts));
    // R6
    if (!signatureDataUrl.startsWith('data:image/')) throw new Error('Chữ ký không hợp lệ, vui lòng ký lại.');
    commit(woId, {
      stage: 'REPORT_READY',
      resident_channel: null,
      signature: {
        quote_snapshot: flow.quote.lines,
        labor_cost: flow.quote.labor_cost,
        final_total: quoteTotal(flow.quote.lines, flow.quote.labor_cost),
        signature_image_url: signatureDataUrl,
        signed_at: nowIso(),
      },
    });
  }, [load, commit]);

  const residentDispute = useCallback((woId: string, note: string, opts?: ResidentActOptions) => {
    load(woId, ['AWAITING_RESIDENT_SIGNATURE'], residentLoad(opts));
    if (!note.trim()) throw new Error('Vui lòng ghi lại ý kiến của cư dân để BQL xử lý.');
    commit(woId, { stage: 'DISPUTED', resident_channel: null, dispute_note: note.trim() }, { blocked_reason: note.trim() });
  }, [load, commit]);

  // ---------- Bước 9: Gửi báo cáo ----------
  const submitReport = useCallback((woId: string, finalNote: string) => {
    const { flow } = load(woId, ['REPORT_READY']);
    if (!flow.signature) throw new Error('Thiếu chữ ký xác nhận của cư dân.');
    const now = new Date();
    commit(
      woId,
      {
        stage: 'AWAITING_COMPLETION',
        report_final_note: finalNote.trim(),
        submitted_at: now.toISOString(),
        auto_complete_at: new Date(now.getTime() + AUTO_COMPLETE_HOURS * 3600 * 1000).toISOString(),
      },
      { execution_completed_at: now.toISOString(), materials_used: flow.quote.lines.map((l) => ({ part_name: l.name, quantity: l.quantity, unit: l.unit })) },
    );
  }, [load, commit]);

  // ---------- Bước 10: Hoàn thành (app cư dân, hoặc giả lập trên máy nhân viên) ----------
  const residentConfirmCompletion = useCallback((woId: string, opts?: ResidentActOptions) => {
    load(woId, ['AWAITING_COMPLETION'], { skipOwnerCheck: true, expectedVersion: opts?.expectedVersion });
    commit(woId, { stage: 'COMPLETED_BY_RESIDENT', completion_type: 'RESIDENT_CONFIRMED', completed_at: nowIso() });
  }, [load, commit]);

  const residentReportIssue = useCallback((woId: string, note: string, opts?: ResidentActOptions) => {
    const { wo, flow } = load(woId, ['AWAITING_COMPLETION'], { skipOwnerCheck: true, expectedVersion: opts?.expectedVersion });
    if (!note.trim()) throw new Error('Vui lòng mô tả điều chưa được xử lý.');
    // R8: issues are only accepted inside the 72h window
    if (flow.auto_complete_at && Date.now() >= new Date(flow.auto_complete_at).getTime()) {
      throw new Error('Đã quá 72 giờ: phản ánh này sẽ được tạo thành ticket bảo hành mới.');
    }
    const now = nowIso();
    commit(woId, { stage: 'REWORK_REQUIRED', rework_note: note, completed_at: now });
    const redo: VhWorkOrder = {
      ...wo,
      id: `WO-${new Date().getFullYear()}-R${Date.now().toString().slice(-5)}`,
      status: 'ASSIGNED',
      attempt_no: (wo.attempt_no || 1) + 1,
      redo_of_work_order_id: wo.id,
      execution_started_at: null,
      execution_completed_at: null,
      blocked_reason: null,
      materials_used: undefined,
      result: { redoReason: note },
      field_flow: { ...emptyFieldFlow('ACCEPTED', categoryOf(wo), taskOf(wo)), accepted_at: now, rework_note: note },
      version: 1,
      created_at: now,
      updated_at: now,
    };
    setWorkOrders((prev) => [redo, ...prev]);
    return redo;
  }, [load, commit, setWorkOrders, categoryOf, taskOf]);

  const simulateResidentConfirm = useCallback((woId: string) => residentConfirmCompletion(woId), [residentConfirmCompletion]);
  const simulateResidentIssue = useCallback((woId: string, note: string) => residentReportIssue(woId, note), [residentReportIssue]);

  // R9: idempotent auto-complete sweep (mock of the backend cron)
  const runAutoComplete = useCallback(() => {
    const now = Date.now();
    setWorkOrders((prev) => {
      let changed = false;
      const next = prev.map((wo) => {
        const f = wo.field_flow;
        if (f?.stage !== 'AWAITING_COMPLETION' || !f.auto_complete_at) return wo;
        if (new Date(f.auto_complete_at).getTime() > now) return wo;
        changed = true;
        return {
          ...wo,
          field_flow: { ...f, stage: 'COMPLETED_AUTO' as const, completion_type: 'AUTO_72H' as const, completed_at: new Date(now).toISOString() },
          updated_at: new Date(now).toISOString(),
        };
      });
      return changed ? next : prev;
    });
  }, [setWorkOrders]);

  useEffect(() => {
    runAutoComplete();
    const timer = window.setInterval(runAutoComplete, 30_000);
    return () => window.clearInterval(timer);
  }, [runAutoComplete]);

  const simulateFastForward72h = useCallback((woId: string) => {
    load(woId, ['AWAITING_COMPLETION'], { skipOwnerCheck: true });
    commit(woId, { auto_complete_at: new Date(Date.now() - 1000).toISOString() });
    runAutoComplete();
  }, [load, commit, runAutoComplete]);

  return {
    acceptJob,
    declineJob,
    checkIn,
    placeWarningSign,
    markCleaned,
    completeCleaning,
    setSecurityOutcome,
    setReportNote,
    completeSecurity,
    setDiagnosisNote,
    startQuote,
    startNoCharge,
    saveQuote,
    handToResidentForAgreement,
    setResidentChannel,
    residentAgree,
    residentRequestChanges,
    residentCancel,
    toggleChecklistItem,
    pauseJob,
    resumeJob,
    requestSignature,
    backToWork,
    residentSign,
    residentDispute,
    submitReport,
    residentConfirmCompletion,
    residentReportIssue,
    simulateResidentConfirm,
    simulateResidentIssue,
    simulateFastForward72h,
    runAutoComplete,
  };
}
