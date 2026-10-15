/**
 * Pure helpers for the staff field flow (REPAIR = kỹ thuật viên, CLEANING = vệ sinh A5).
 * Spec: docs/vinhomes-operations-staff-field-flow.md
 */
import type { VhWorkOrder, WorkOrderStatus } from '../types/work-order';
import type { VhEvidenceRef } from '../types/evidence';
import type { VhTask } from '../types/task';
import type { CleaningPlan } from '../types/cleaning-plan';
import type { FieldChecklistItem, FieldFlow, FieldStage, FlowKind, QuoteLine } from '../types/field-flow';

export interface MaterialCatalogItem {
  code: string;
  name: string;
  unit: string;
  unit_price: number;
}

export const MATERIAL_CATALOG: MaterialCatalogItem[] = [
  { code: 'VT-VAN-DN15', name: 'Van khóa DN15', unit: 'cái', unit_price: 180000 },
  { code: 'VT-VAN-DN20', name: 'Van khóa DN20', unit: 'cái', unit_price: 240000 },
  { code: 'VT-ONG-PPR20', name: 'Ống nhựa PPR D20', unit: 'm', unit_price: 35000 },
  { code: 'VT-CO-PPR20', name: 'Co nối PPR D20', unit: 'cái', unit_price: 12000 },
  { code: 'VT-BANG-TAN', name: 'Băng tan chống rò', unit: 'cuộn', unit_price: 8000 },
  { code: 'VT-VOI-LAVABO', name: 'Vòi lavabo nóng lạnh', unit: 'bộ', unit_price: 650000 },
  { code: 'VT-DAY-CAP', name: 'Dây cấp nước inox 40cm', unit: 'sợi', unit_price: 55000 },
  { code: 'VT-PHAO-BC', name: 'Bộ phao xả bồn cầu', unit: 'bộ', unit_price: 320000 },
  { code: 'VT-CB-20A', name: 'Aptomat (CB) 20A', unit: 'cái', unit_price: 145000 },
  { code: 'VT-CB-32A', name: 'Aptomat (CB) 32A', unit: 'cái', unit_price: 185000 },
  { code: 'VT-DAY-25', name: 'Dây điện Cadivi 2.5mm²', unit: 'm', unit_price: 14000 },
  { code: 'VT-O-CAM', name: 'Ổ cắm đôi 3 chấu', unit: 'cái', unit_price: 95000 },
  { code: 'VT-CT-DEN', name: 'Công tắc đèn', unit: 'cái', unit_price: 60000 },
  { code: 'VT-BONG-LED', name: 'Bóng đèn LED 12W', unit: 'cái', unit_price: 75000 },
  { code: 'VT-GAS-R32', name: 'Gas điều hòa R32', unit: 'kg', unit_price: 280000 },
  { code: 'VT-SILICON', name: 'Keo silicon chống thấm', unit: 'tuýp', unit_price: 65000 },
];

const CHECKLIST_TEMPLATES: Record<string, string[]> = {
  ELECTRIC: [
    'Ngắt nguồn điện khu vực trước khi thao tác',
    'Kiểm tra cách điện bằng đồng hồ đo',
    'Siết chặt đầu cốt, không hở dây',
    'Đóng điện chạy thử, không nhảy aptomat',
  ],
  PLUMBING: [
    'Khóa van cấp nước trước khi thao tác',
    'Thay thế / xử lý điểm rò rỉ',
    'Mở nước chạy thử 5 phút, không rò rỉ',
    'Lau khô và vệ sinh khu vực làm việc',
  ],
  DEFAULT: [
    'Kiểm tra an toàn khu vực trước khi làm',
    'Xử lý đúng hạng mục đã thống nhất với cư dân',
    'Chạy thử / kiểm tra lại sau khi xử lý',
    'Vệ sinh khu vực làm việc',
  ],
};

export function defaultChecklist(category: string | undefined): FieldChecklistItem[] {
  const c = (category || '').toUpperCase();
  const key = c.includes('ELEC') || c.includes('DIEN') ? 'ELECTRIC' : c.includes('PLUMB') || c.includes('WATER') || c.includes('MEP') ? 'PLUMBING' : 'DEFAULT';
  return CHECKLIST_TEMPLATES[key].map((label, i) => ({ id: `ck-${i + 1}`, label, done: false }));
}

export function flowKindOf(task?: VhTask): FlowKind {
  if (task?.domain_type === 'SANITATION' || task?.domain_type === 'LANDSCAPE') return 'CLEANING';
  if (task?.domain_type === 'SECURITY') return 'SECURITY';
  return 'REPAIR';
}

/** Wet-floor work (spill, mopping, washing) must put up a warning sign before cleaning. */
export function signRequiredFor(task?: VhTask): boolean {
  if (flowKindOf(task) !== 'CLEANING') return false;
  const plan = task?.domain_data as Partial<CleaningPlan> | null | undefined;
  if (plan?.issueType === 'SPILL' || plan?.issueType === 'STAIN_REMOVAL') return true;
  return !!plan?.actions?.some((a) => a.type === 'MOP_FLOOR' || a.type === 'PRESSURE_WASH' || a.type === 'DEEP_CLEAN');
}

export function emptyFieldFlow(stage: FieldStage, category?: string, task?: VhTask): FieldFlow {
  return {
    kind: flowKindOf(task),
    stage,
    sign_required: signRequiredFor(task),
    sign_placed_at: null,
    cleaned_at: null,
    security_outcome: null,
    accepted_at: null,
    arrived_at: null,
    started_at: null,
    submitted_at: null,
    auto_complete_at: null,
    completed_at: null,
    completion_type: null,
    no_charge: false,
    diagnosis_note: '',
    quote: { lines: [], labor_cost: 0, warranty_months: 3 },
    agreement: null,
    signature: null,
    checklist: defaultChecklist(category),
    pause_reason: null,
    pause_note: null,
    paused_from: null,
    decline_reason: null,
    decline_note: null,
    dispute_note: null,
    rework_note: null,
    report_final_note: '',
  };
}

/** Legacy work orders (no field_flow yet) are mapped from their WO status. */
export function getFieldFlow(wo: VhWorkOrder, category?: string, task?: VhTask): FieldFlow {
  if (wo.field_flow) return wo.field_flow;
  const kind = flowKindOf(task);
  const legacy: Record<WorkOrderStatus, FieldStage> = {
    OPEN: 'ASSIGNED',
    ASSIGNED: 'ASSIGNED',
    IN_PROGRESS: 'IN_PROGRESS',
    BLOCKED: 'PAUSED',
    COMPLETED: kind === 'REPAIR' ? 'COMPLETED_BY_RESIDENT' : 'DONE',
    FAILED: 'CANCELLED_BY_RESIDENT',
    CANCELLED: 'DECLINED',
  };
  const flow = emptyFieldFlow(legacy[wo.status], category, task);
  if (flow.stage === 'IN_PROGRESS') {
    flow.no_charge = true;
    flow.accepted_at = flow.arrived_at = flow.started_at = wo.execution_started_at;
  }
  if (flow.stage === 'PAUSED') {
    flow.paused_from = 'IN_PROGRESS';
    flow.pause_reason = 'OTHER';
    flow.pause_note = wo.blocked_reason || null;
    flow.no_charge = true;
  }
  if (flow.stage === 'DONE') flow.completed_at = wo.execution_completed_at;
  if (flow.stage === 'COMPLETED_BY_RESIDENT') {
    flow.completed_at = wo.execution_completed_at;
    flow.completion_type = 'RESIDENT_CONFIRMED';
  }
  return flow;
}

/** Keep the canonical WO status in sync so QC / Supervisor / Manager views keep working. */
export function stageToWorkOrderStatus(stage: FieldStage): WorkOrderStatus {
  switch (stage) {
    case 'ASSIGNED':
    case 'ACCEPTED':
    case 'ON_SITE':
    case 'QUOTE_DRAFT':
    case 'AWAITING_RESIDENT_AGREEMENT':
      return 'ASSIGNED';
    case 'IN_PROGRESS':
    case 'AWAITING_RESIDENT_SIGNATURE':
    case 'REPORT_READY':
      return 'IN_PROGRESS';
    case 'PAUSED':
    case 'DISPUTED':
      return 'BLOCKED';
    case 'AWAITING_COMPLETION':
    case 'DONE':
    case 'COMPLETED_BY_RESIDENT':
    case 'COMPLETED_AUTO':
    case 'REWORK_REQUIRED':
      return 'COMPLETED';
    case 'DECLINED':
    case 'CANCELLED_BY_RESIDENT':
      return 'CANCELLED';
  }
}

export type TechnicianTab = 'NEW' | 'ACTIVE' | 'WAITING' | 'HISTORY';
export type StageTone = 'red' | 'amber' | 'blue' | 'green' | 'slate' | 'violet';

export interface TechnicianStep {
  stage: FieldStage;
  /** 0 Nhận · 1 Đến nơi · 2 Thực hiện · 3 Báo cáo · 4 Xong */
  stepIndex: number;
  label: string;
  tone: StageTone;
  tab: TechnicianTab;
  /** Conditions still missing before the primary action can run. */
  blockers: string[];
}

export const STEP_LABELS: Record<FlowKind, string[]> = {
  REPAIR: ['Nhận việc', 'Đến nơi', 'Thực hiện', 'Báo cáo'],
  CLEANING: ['Nhận việc', 'Đến nơi', 'Làm sạch'],
  SECURITY: ['Nhận việc', 'Đến nơi', 'Xử lý'],
};

const STAGE_META: Record<FieldStage, { label: string; tone: StageTone; tab: TechnicianTab; stepIndex: number }> = {
  ASSIGNED: { label: 'Việc mới', tone: 'blue', tab: 'NEW', stepIndex: 0 },
  ACCEPTED: { label: 'Đang di chuyển', tone: 'blue', tab: 'ACTIVE', stepIndex: 1 },
  ON_SITE: { label: 'Đang kiểm tra', tone: 'blue', tab: 'ACTIVE', stepIndex: 2 },
  QUOTE_DRAFT: { label: 'Lập danh mục vật tư', tone: 'blue', tab: 'ACTIVE', stepIndex: 2 },
  AWAITING_RESIDENT_AGREEMENT: { label: 'Chờ cư dân đồng ý', tone: 'amber', tab: 'ACTIVE', stepIndex: 2 },
  IN_PROGRESS: { label: 'Đang sửa', tone: 'blue', tab: 'ACTIVE', stepIndex: 2 },
  PAUSED: { label: 'Tạm dừng', tone: 'amber', tab: 'ACTIVE', stepIndex: 2 },
  AWAITING_RESIDENT_SIGNATURE: { label: 'Chờ cư dân ký', tone: 'amber', tab: 'ACTIVE', stepIndex: 3 },
  REPORT_READY: { label: 'Sẵn sàng gửi báo cáo', tone: 'blue', tab: 'ACTIVE', stepIndex: 3 },
  AWAITING_COMPLETION: { label: 'Chờ cư dân xác nhận', tone: 'violet', tab: 'WAITING', stepIndex: 4 },
  COMPLETED_BY_RESIDENT: { label: 'Hoàn thành · Cư dân xác nhận', tone: 'green', tab: 'HISTORY', stepIndex: 4 },
  COMPLETED_AUTO: { label: 'Hoàn thành · Tự động sau 72h', tone: 'green', tab: 'HISTORY', stepIndex: 4 },
  REWORK_REQUIRED: { label: 'Đã tạo lượt làm lại', tone: 'slate', tab: 'HISTORY', stepIndex: 4 },
  DISPUTED: { label: 'Tranh chấp · Chờ BQL', tone: 'red', tab: 'WAITING', stepIndex: 3 },
  DECLINED: { label: 'Đã từ chối', tone: 'slate', tab: 'HISTORY', stepIndex: 0 },
  CANCELLED_BY_RESIDENT: { label: 'Cư dân không sửa', tone: 'slate', tab: 'HISTORY', stepIndex: 2 },
  DONE: { label: 'Hoàn thành', tone: 'green', tab: 'HISTORY', stepIndex: 4 },
};

export function getStageMeta(stage: FieldStage) {
  return STAGE_META[stage];
}

export function getWorkBlockers(flow: FieldFlow, woEvidence: VhEvidenceRef[]): string[] {
  const blockers: string[] = [];
  if (!woEvidence.some((e) => e.capture_phase === 'BEFORE')) blockers.push('Chụp ít nhất 1 ảnh TRƯỚC khi sửa');
  if (!woEvidence.some((e) => e.capture_phase === 'AFTER')) blockers.push('Chụp ít nhất 1 ảnh SAU khi sửa');
  const pending = flow.checklist.filter((c) => !c.done).length;
  if (pending > 0) blockers.push(`Hoàn thành ${pending} mục checklist còn lại`);
  if (flow.quote.lines.some((l) => l.is_additional && !l.additional_reason?.trim())) {
    blockers.push('Ghi lý do cho vật tư phát sinh');
  }
  return blockers;
}

/** Cleaning steps run strictly in order: ảnh TRƯỚC → đặt biển → lau → ảnh SAU. */
export function getCleaningBlockers(flow: FieldFlow, woEvidence: VhEvidenceRef[]): string[] {
  const blockers: string[] = [];
  if (!woEvidence.some((e) => e.capture_phase === 'BEFORE')) blockers.push('Chụp ảnh hiện trường TRƯỚC khi làm');
  if (flow.sign_required && !flow.sign_placed_at) blockers.push('Đặt biển cảnh báo sàn ướt');
  if (!flow.cleaned_at) blockers.push('Xác nhận đã làm sạch');
  if (!woEvidence.some((e) => e.capture_phase === 'AFTER')) blockers.push('Chụp ảnh SAU khi làm');
  return blockers;
}

/** Security: ảnh hiện trường (bắt buộc) → kết quả nhắc nhở → ghi chú nếu không hợp tác. */
export function getSecurityBlockers(flow: FieldFlow, woEvidence: VhEvidenceRef[], note: string): string[] {
  const blockers: string[] = [];
  if (!woEvidence.some((e) => e.capture_phase === 'OTHER')) blockers.push('Chụp ít nhất 1 ảnh hiện trường');
  if (!flow.security_outcome) blockers.push('Chọn kết quả nhắc nhở');
  if (flow.security_outcome === 'UNCOOPERATIVE' && !note.trim()) blockers.push('Ghi chú diễn biến khi hộ không hợp tác');
  return blockers;
}

export function getTechnicianStep(wo: VhWorkOrder, woEvidence: VhEvidenceRef[], category?: string, task?: VhTask): TechnicianStep {
  const flow = getFieldFlow(wo, category, task);
  const meta = STAGE_META[flow.stage];
  let blockers: string[] = [];
  if (flow.stage === 'QUOTE_DRAFT' && flow.quote.lines.length === 0 && flow.quote.labor_cost <= 0) {
    blockers = ['Thêm ít nhất 1 vật tư hoặc tiền công'];
  }
  if (flow.stage === 'IN_PROGRESS') {
    blockers =
      flow.kind === 'CLEANING'
        ? getCleaningBlockers(flow, woEvidence)
        : flow.kind === 'SECURITY'
          ? getSecurityBlockers(flow, woEvidence, flow.report_final_note)
          : getWorkBlockers(flow, woEvidence);
  }
  return { stage: flow.stage, stepIndex: meta.stepIndex, label: meta.label, tone: meta.tone, tab: meta.tab, blockers };
}

export function isAdditionalAllowed(flow: FieldFlow): boolean {
  return flow.agreement !== null;
}

export function splitQuote(lines: QuoteLine[]) {
  return {
    agreed: lines.filter((l) => !l.is_additional),
    additional: lines.filter((l) => l.is_additional),
  };
}

export function formatVnd(n: number): string {
  return `${n.toLocaleString('vi-VN')}đ`;
}

export function formatDuration(ms: number): string {
  if (ms <= 0) return '0 phút';
  const totalMin = Math.floor(ms / 60000);
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  if (d > 0) return `${d} ngày ${h} giờ`;
  if (h > 0) return `${h} giờ ${m} phút`;
  return `${m} phút`;
}
