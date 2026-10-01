/**
 * Kiểu Guard và Location — P2 sở hữu (spec v0.3 §2.2, §10).
 * Nguồn cấu trúc là schema/common.schema.json (#/$defs/Location, GuardStatus, GuardSummary, *Input).
 */

/** location_id là khóa location; property_id thuộc scope trong Core, không phải alias của location. */
export type Location = {
  location_id: string;
  building: string | null;
  floor: string | null;
  zone: string | null;
};

/** Chỉ AVAILABLE đủ điều kiện ban đầu để dispatch. UNKNOWN chỉ khi nguồn thật sự không biết. */
export type GuardStatus = "AVAILABLE" | "ASSIGNED" | "UNAVAILABLE" | "OFF_DUTY" | "UNKNOWN";

export const GUARD_STATUSES: readonly GuardStatus[] = ["AVAILABLE", "ASSIGNED", "UNAVAILABLE", "OFF_DUTY", "UNKNOWN"];

export type GuardSummary = {
  guard_id: string;
  status: GuardStatus;
  /** null: không biết vị trí. Không có nghĩa guard thuộc mọi property. */
  current_location: Location | null;
  updated_at: string;
};

export type GetAvailableGuardsInput = { location_id: string; limit?: number; cursor?: string };
export type GetGuardStatusInput = { guard_id: string };

export type GuardPage = { guards: GuardSummary[]; next_cursor: string | null };

/**
 * Lịch trực của một guard tại property, đọc từ roster. Dữ liệu nội bộ provider, không phải DTO public.
 * Dùng cho `deriveGuardStatus` (guards/service.ts); shape chốt cùng P4.
 */
export type RosterEntry = {
  guard_id: string;
  /** Tài khoản/hợp đồng còn hiệu lực tại property. */
  employment: "ACTIVE" | "SUSPENDED" | "TERMINATED";
  /** Ca trực đã publish, `[start, end)` dạng Timestamp. */
  shifts: readonly { start: string; end: string }[];
  /** Tình trạng trong ca do guard app/điều phối báo. null: chưa có báo cáo nào. */
  duty_state: "ON_DUTY" | "ON_BREAK" | "ON_LEAVE" | "SICK" | null;
  current_location: Location | null;
  /** Lần cuối roster/duty_state/vị trí thay đổi. */
  updated_at: string;
};
