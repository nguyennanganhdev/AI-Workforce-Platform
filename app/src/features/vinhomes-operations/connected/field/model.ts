/**
 * How someone on site reads their work, after docs/vinhomes-operations-staff-field-flow.md:
 * the list has the tabs "Mới giao / Đang làm / Chờ xác nhận" and the history, and one job is a
 * stepper "Nhận việc → Đến nơi → Thực hiện → Báo cáo".
 */
export type FieldTicket = { id: string; title: string; description: string; status: string; priority: string; building_id: string | null;
  /** The apartment, when the API returns it (an older API does not). */
  unit_code?: string | null; updated_at: string };
export type FieldOrder = { id: string; ticket_id: string; status: string; version: number; description: string;
  assignment_id?: string; assignment_status?: string; completed_at?: string | null };
export type FieldPhoto = { id: string; name: string; purpose: string; src: string };
export type FieldPlan = { title: string; proposal: { steps: string[]; expected_duration: string; conditions: string } };

/** Where an order stands for the person it was offered to: the offer comes before the order's own status. */
export const stateOf = (order: Pick<FieldOrder, "status" | "assignment_status">) => order.assignment_status === "offered" ? "offered" : order.status;
export const ended = (state: string) => state === "completed" || state === "cancelled";

export const STEPS = ["Nhận việc", "Đến nơi", "Thực hiện", "Báo cáo"];
/** Which step is being done. `ready` is whether the photos needed for the report are there. */
export function stepOf(state: string, ready = false): number {
  if (state === "offered" || state === "queued") return 0;
  if (state === "accepted" || state === "en_route") return 1;
  if (ended(state)) return STEPS.length;
  return state === "in_progress" && ready ? 3 : 2;
}

/** The state in the worker's words, then what they are asked to do next. */
export const STATE: Record<string, { label: string; next: string; guide: string }> = {
  queued: { label: "Chờ phân công", next: "", guide: "Ban quản lý đang phân công công việc này." },
  offered: { label: "Việc mới giao", next: "Nhận việc", guide: "Xem phản ánh của cư dân, hẹn thời gian đến rồi nhận việc. Nếu không nhận được, từ chối để Ban quản lý giao người khác." },
  accepted: { label: "Đã nhận việc", next: "Bắt đầu di chuyển", guide: "Khi sẵn sàng, bấm bắt đầu di chuyển để cư dân biết bạn đang đến." },
  en_route: { label: "Đang di chuyển", next: "Tôi đã đến", guide: "Đến đúng vị trí phản ánh rồi bấm xác nhận." },
  arrived: { label: "Khảo sát hiện trường", next: "Gửi phương án cho cư dân", guide: "Kiểm tra thực tế, ghi hiện trạng, lập vật tư và chi phí để cư dân xem trước khi sửa." },
  awaiting_approval: { label: "Chờ cư dân đồng ý", next: "Bắt đầu thi công", guide: "Chỉ thi công khi cư dân đã đồng ý phương án và chi phí." },
  in_progress: { label: "Đang thi công", next: "Gửi kết quả", guide: "Chụp ảnh trước khi sửa, thi công, chụp ảnh sau khi sửa rồi gửi kết quả." },
  completed: { label: "Đã gửi kết quả", next: "", guide: "Ban quản lý nghiệm thu, sau đó cư dân xác nhận hoàn tất." },
  cancelled: { label: "Đã hủy", next: "", guide: "Công việc này đã được hủy." },
};
export const stateText = (state: string) => STATE[state] || { label: "Đang xử lý", next: "", guide: "" };

export type FieldTab = "new" | "doing" | "waiting" | "history";
export const TABS: [FieldTab, string][] = [["new", "Mới giao"], ["doing", "Đang làm"], ["waiting", "Chờ xác nhận"], ["history", "Lịch sử"]];
/** A job that was sent in waits for acceptance until its request is closed; then it is history. */
export function tabOf(state: string, ticketStatus: string): FieldTab {
  if (state === "offered" || state === "queued") return "new";
  if (!ended(state)) return "doing";
  return state === "completed" && !["closed", "cancelled"].includes(ticketStatus) ? "waiting" : "history";
}
/** What a job that was sent in waits for, read from its request: the state, then what happens next. */
export const AFTER: Record<string, [string, string]> = {
  in_progress: ["Chờ Ban quản lý nghiệm thu", "Bạn đã gửi kết quả. Ban quản lý kiểm tra rồi báo cư dân xác nhận."],
  resolved: ["Chờ cư dân xác nhận", "Ban quản lý đã nghiệm thu đạt. Việc khép lại khi cư dân xác nhận."],
  closed: ["Cư dân đã xác nhận hoàn tất", "Công việc đã khép lại."],
  cancelled: ["Yêu cầu đã hủy", "Yêu cầu này đã được hủy."],
};

export const REJECTIONS: [string, string][] = [["BUSY", "Đang bận việc khác"], ["WRONG_SKILL", "Không đúng chuyên môn"], ["OFF_SHIFT", "Đã hết ca"], ["OTHER", "Lý do khác"]];

/** "Sapphire 1 - S1.01 · Căn 1201": the building, and the apartment when it is known. */
export const placeOf = (ticket: FieldTicket, buildings: { id: string; name: string }[]) =>
  [buildings.find((b) => b.id === ticket.building_id)?.name, ticket.unit_code && `Căn ${ticket.unit_code}`].filter(Boolean).join(" · ") || "Vị trí ghi trong phản ánh";
