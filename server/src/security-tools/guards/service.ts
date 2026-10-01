/**
 * Quy tắc nghiệp vụ Guard (spec v0.3 §6.1). Hàm thuần: mock provider dùng trực tiếp, real provider
 * dùng khi phải tự ghép roster + reservation. Core vẫn là nơi kiểm availability cuối cùng khi WRITE.
 */
import { fail } from "../common/errors";
import type { GuardStatus, GuardSummary, RosterEntry } from "./types";

/** So ID theo code unit, giống sort mặc định của Core/JSON; không dùng localeCompare. */
export const compareIds = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

export const sortGuards = (guards: readonly GuardSummary[]) => [...guards].sort((a, b) => compareIds(a.guard_id, b.guard_id));

/**
 * Danh sách cho get_available_guards: guard được phân công property, AVAILABLE và không có dispatch
 * mở. Không lọc theo current_location (có thể null hoặc ở chỗ khác). Bản đọc không đặt chỗ.
 */
export function availableGuards(guards: readonly GuardSummary[], guardsWithOpenDispatch: ReadonlySet<string>): GuardSummary[] {
  return sortGuards(guards.filter((g) => g.status === "AVAILABLE" && !guardsWithOpenDispatch.has(g.guard_id)));
}

/**
 * Ghép roster và reservation thành GuardStatus (§6.1: "kết hợp roster và reservation, không reset
 * mù về AVAILABLE"). Bảng ánh xạ, theo thứ tự ưu tiên:
 *
 * | Điều kiện                                         | GuardStatus  |
 * |---------------------------------------------------|--------------|
 * | Không có roster, đang giữ dispatch mở             | ASSIGNED     |
 * | Không có roster                                   | UNKNOWN      |
 * | employment SUSPENDED/TERMINATED                   | UNAVAILABLE  |
 * | Đang giữ dispatch mở (PENDING/EN_ROUTE/ON_SITE)   | ASSIGNED     |
 * | `now` ngoài mọi ca `[start, end)`                 | OFF_DUTY     |
 * | Trong ca, duty_state ON_DUTY                      | AVAILABLE    |
 * | Trong ca, ON_BREAK/ON_LEAVE/SICK                  | UNAVAILABLE  |
 * | Trong ca, chưa có duty_state (chưa check-in)      | UNKNOWN      |
 *
 * Giá trị roster ngoài các enum trên → PROVIDER_INVALID_RESPONSE, không đoán.
 * Bảng này chờ P4 xác nhận (đầu mục 13); đổi bảng thì sửa test guards đi kèm.
 */
export function deriveGuardStatus(roster: RosterEntry | null, hasOpenDispatch: boolean, now: string): GuardStatus {
  if (roster === null) return hasOpenDispatch ? "ASSIGNED" : "UNKNOWN";
  switch (roster.employment) {
    case "ACTIVE":
      break;
    case "SUSPENDED":
    case "TERMINATED":
      return "UNAVAILABLE";
    default:
      return unsupported();
  }
  if (hasOpenDispatch) return "ASSIGNED";
  if (!roster.shifts.some((shift) => shift.start <= now && now < shift.end)) return "OFF_DUTY";
  switch (roster.duty_state) {
    case "ON_DUTY":
      return "AVAILABLE";
    case "ON_BREAK":
    case "ON_LEAVE":
    case "SICK":
      return "UNAVAILABLE";
    case null:
      return "UNKNOWN";
    default:
      return unsupported();
  }
}

/**
 * GuardSummary từ roster. `reservationUpdatedAt`: lúc reservation đổi gần nhất (nếu có), để
 * updated_at phản ánh thay đổi mới nhất trong hai nguồn.
 */
export function toGuardSummary(
  roster: RosterEntry,
  reservation: { open: boolean; updatedAt: string | null },
  now: string,
): GuardSummary {
  const updated = reservation.updatedAt !== null && reservation.updatedAt > roster.updated_at ? reservation.updatedAt : roster.updated_at;
  return {
    guard_id: roster.guard_id,
    status: deriveGuardStatus(roster, reservation.open, now),
    current_location: roster.current_location,
    updated_at: updated,
  };
}

function unsupported(): never {
  return fail("PROVIDER_INVALID_RESPONSE", "Roster có trạng thái ngoài bảng ánh xạ GuardStatus.");
}
