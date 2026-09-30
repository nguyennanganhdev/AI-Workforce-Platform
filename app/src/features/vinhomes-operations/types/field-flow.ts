/**
 * Staff field flow types (Kỹ thuật viên hiện trường)
 * Spec: docs/vinhomes-operations-staff-field-flow.md
 */

export type FieldStage =
  | 'ASSIGNED'                       // AI vừa giao việc
  | 'ACCEPTED'                       // Nhân viên đã nhận việc, đang di chuyển
  | 'ON_SITE'                        // Đã đến nơi, đang kiểm tra & bàn với cư dân
  | 'QUOTE_DRAFT'                    // Đang lập danh mục vật tư
  | 'AWAITING_RESIDENT_AGREEMENT'    // Máy đang ở chế độ cư dân đọc danh mục
  | 'IN_PROGRESS'                    // Đang sửa
  | 'PAUSED'                         // Tạm dừng có lý do
  | 'AWAITING_RESIDENT_SIGNATURE'    // Đã đủ ảnh, chờ cư dân ký xác nhận
  | 'REPORT_READY'                   // Cư dân đã ký, chờ nhân viên gửi báo cáo
  | 'AWAITING_COMPLETION'            // Đã gửi báo cáo, chờ cư dân xác nhận / 72h
  | 'COMPLETED_BY_RESIDENT'
  | 'COMPLETED_AUTO'
  | 'REWORK_REQUIRED'
  | 'DISPUTED'
  | 'DECLINED'
  | 'CANCELLED_BY_RESIDENT'
  | 'DONE';                          // Vệ sinh: hoàn thành ngay khi gửi, AI báo cư dân

/**
 * REPAIR = kỹ thuật viên (danh mục + chữ ký), CLEANING = vệ sinh A5 (ảnh + biển cảnh báo),
 * SECURITY = an ninh xử lý phản ánh của cư dân (ảnh + kết quả nhắc nhở).
 */
export type FlowKind = 'REPAIR' | 'CLEANING' | 'SECURITY';

export type SecurityOutcome = 'COOPERATED' | 'NO_ANSWER' | 'UNCOOPERATIVE';

export const SECURITY_OUTCOME_LABELS: Record<SecurityOutcome, string> = {
  COOPERATED: 'Hợp tác, đã giảm ồn',
  NO_ANSWER: 'Không mở cửa',
  UNCOOPERATIVE: 'Không hợp tác',
};

export type DeclineReason = 'BUSY' | 'WRONG_SKILL' | 'OFF_SHIFT' | 'OTHER';

export type PauseReason = 'WAITING_PARTS' | 'RESIDENT_ABSENT' | 'NEED_SUPPORT' | 'OTHER';

export type CompletionType = 'RESIDENT_CONFIRMED' | 'AUTO_72H';

export const AUTO_COMPLETE_HOURS = 72;

export interface QuoteLine {
  id: string;
  material_code: string | null;
  name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
  is_additional: boolean;
  additional_reason: string | null;
}

export interface FieldQuote {
  lines: QuoteLine[];
  labor_cost: number;
  warranty_months: number;
}

export interface ResidentAgreement {
  quote_snapshot: QuoteLine[];
  labor_cost: number;
  total: number;
  agreed_at: string;
}

export interface ResidentSignature {
  quote_snapshot: QuoteLine[];
  labor_cost: number;
  final_total: number;
  signature_image_url: string;
  signed_at: string;
}

export interface FieldChecklistItem {
  id: string;
  label: string;
  done: boolean;
}

export interface FieldFlow {
  kind: FlowKind;
  stage: FieldStage;
  /** CLEANING: việc làm ướt sàn bắt buộc đặt biển cảnh báo trước khi lau */
  sign_required: boolean;
  sign_placed_at: string | null;
  cleaned_at: string | null;
  /** SECURITY: kết quả gặp hộ bị phản ánh */
  security_outcome: SecurityOutcome | null;
  accepted_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  auto_complete_at: string | null;
  completed_at: string | null;
  completion_type: CompletionType | null;
  no_charge: boolean;
  diagnosis_note: string;
  quote: FieldQuote;
  agreement: ResidentAgreement | null;
  signature: ResidentSignature | null;
  checklist: FieldChecklistItem[];
  pause_reason: PauseReason | CleaningPauseReason | null;
  pause_note: string | null;
  paused_from: FieldStage | null;
  decline_reason: DeclineReason | null;
  decline_note: string | null;
  dispute_note: string | null;
  rework_note: string | null;
  report_final_note: string;
  /**
   * Kênh đang chờ cư dân phản hồi ở bước đồng ý danh mục / ký xác nhận:
   * DEVICE = đưa máy nhân viên, APP = gửi sang app cư dân. Cả hai kênh đều được thao tác, kênh nào trước thắng.
   */
  resident_channel?: ResidentChannel | null;
}

export type ResidentChannel = 'DEVICE' | 'APP';

export const DECLINE_REASON_LABELS: Record<DeclineReason, string> = {
  BUSY: 'Đang bận việc khác',
  WRONG_SKILL: 'Không đúng chuyên môn',
  OFF_SHIFT: 'Đã hết ca',
  OTHER: 'Lý do khác',
};

export const PAUSE_REASON_LABELS: Record<PauseReason, string> = {
  WAITING_PARTS: 'Cần đặt vật tư',
  RESIDENT_ABSENT: 'Không gặp được cư dân',
  NEED_SUPPORT: 'Cần thêm người hỗ trợ',
  OTHER: 'Lý do khác',
};

export type CleaningPauseReason = 'MISSING_SUPPLIES' | 'AREA_OCCUPIED' | 'NEED_SUPPORT' | 'OTHER';

export const SECURITY_PAUSE_REASON_LABELS: Partial<Record<CleaningPauseReason, string>> = {
  NEED_SUPPORT: 'Cần thêm người hỗ trợ',
  OTHER: 'Lý do khác',
};

export const CLEANING_PAUSE_REASON_LABELS: Record<CleaningPauseReason, string> = {
  MISSING_SUPPLIES: 'Thiếu hóa chất / dụng cụ',
  AREA_OCCUPIED: 'Khu vực đang có người',
  NEED_SUPPORT: 'Cần thêm người hỗ trợ',
  OTHER: 'Lý do khác',
};

export function quoteTotal(lines: QuoteLine[], laborCost: number): number {
  return lines.reduce((sum, l) => sum + l.amount, 0) + laborCost;
}
