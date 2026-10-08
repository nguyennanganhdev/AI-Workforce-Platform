import type { RoomFile, RoomMessage, RoomSession, TicketSession } from "@/lib/rooms/queries";

export type SessionGroup = "attention" | "running" | "done";
export type SessionState = { group: SessionGroup; label: string };

/**
 * Who a session waits for, in the words management reads.
 *
 * The plan's own status is asked before the runtime's phase: the phase is what the Supervisor last
 * reported and can lag behind a decision the backend already recorded.
 */
export function sessionState(s: RoomSession): SessionState {
  if (s.status === "completed") return { group: "done", label: "Đã đóng" };
  if (s.status === "cancelled") return { group: "done", label: "Đã dừng" };
  if (s.status === "failed") return { group: "attention", label: "Agent chưa xử lý được yêu cầu" };
  if (s.ticket_status === "closed") return { group: "attention", label: "Cư dân đã xác nhận, chờ bạn duyệt đóng" };
  if (s.manual) return ["in_progress", "assigned"].includes(s.ticket_status) ? { group: "running", label: "Đang thi công" } : s.ticket_status === "resolved" ? { group: "running", label: "Chờ cư dân xác nhận" } : { group: "attention", label: "Mới tiếp nhận" };
  if (s.work_status === "completed" && !["resolved", "closed"].includes(s.ticket_status)) return { group: "attention", label: "Chờ nghiệm thu" };
  if (s.runtime?.phase === "paused")
    return { group: "attention", label: s.runtime.pauseReason === "management_pause" ? "Bạn đã tạm dừng phiên" : handbackReason(s.runtime.pauseReason) };
  if (s.plan_status === "management_pending") return { group: "attention", label: "Chờ bạn duyệt phương án" };
  if (s.plan_status === "rejected") return { group: "attention", label: s.plan_resident_rejected ? "Cư dân từ chối phương án" : "Phương án cần sửa" };
  if (s.plan_status === "resident_pending") return { group: "running", label: "Chờ cư dân đồng ý" };
  if (s.plan_status === "approved" && s.work_status === "queued") return { group: "attention", label: "Chưa tìm được thợ rảnh" };
  if (s.plan_status === "approved") return { group: "running", label: "Đang thi công" };
  if (s.runtime?.phase === "waiting_information") return { group: "running", label: "Chờ cư dân trả lời" };
  return { group: "running", label: s.status === "queued" ? "Mới tiếp nhận" : "Agent đang lập phương án" };
}

const AGO = new Intl.RelativeTimeFormat("vi", { numeric: "auto", style: "narrow" });
const SPANS: [number, number, Intl.RelativeTimeFormatUnit][] = [[3_600_000, 60_000, "minute"], [86_400_000, 3_600_000, "hour"], [Infinity, 86_400_000, "day"]];
/** How long ago, in Vietnamese whatever the browser's language. */
export function ago(iso: string, now = Date.now()): string {
  const elapsed = now - new Date(iso).getTime();
  if (!Number.isFinite(elapsed)) return "";
  if (elapsed < 60_000) return "vừa xong";
  const [, size, unit] = SPANS.find(([limit]) => elapsed < limit)!;
  return AGO.format(-Math.floor(elapsed / size), unit);
}

/** Why the Supervisor stopped and left the next step to management. */
const PAUSES: Record<string, string> = {
  "planner:no_specialist_available": "Phòng chưa có agent chuyên môn cho loại yêu cầu này. Bạn xử lý trực tiếp trong yêu cầu này.",
  "planner:analysis_ready": "Agent đã phân tích xong nhưng Supervisor chưa lập được phương án. Bạn lập phương án từ phân tích bên dưới.",
  "planner:planner_model_not_configured": "Supervisor chưa được cấu hình model. Bạn xử lý trực tiếp trong yêu cầu này.",
  AGENT_FAILURE: "Agent không trả lời được sau nhiều lần thử. Bạn xử lý trực tiếp trong yêu cầu này.",
  model_unavailable: "Supervisor không gọi được model (hết hạn mức hoặc mất kết nối). Bấm Chạy tiếp khi model hoạt động lại, hoặc xử lý trực tiếp trong yêu cầu này.",
  model_timeout: "Model trả lời quá chậm nên Supervisor dừng lại. Bấm Chạy tiếp để thử lại.",
  outcome_unknown: "Một bước của phiên chưa rõ kết quả nên Supervisor dừng lại.",
  management_pause: "Bạn đã tạm dừng phiên. Bấm Chạy tiếp để Supervisor làm tiếp.",
};
export function pauseText(reason?: string | null): string {
  if (!reason) return "";
  // A reason the planner wrote itself is a sentence for management already.
  return PAUSES[reason] || (reason.startsWith("planner:") ? reason.slice(8) : "Supervisor dừng lại, bạn xử lý tiếp.");
}

/** The same sentence without the internal request code, which nobody reads in a conversation. */
export function plain(text: string): string {
  return text
    .replace(/\s*Mã yêu cầu của bạn:\s*VH-[0-9A-F]{12}\.?/g, "")
    .replace(/^VH-[0-9A-F]{12}:\s*/, "")
    .replace(/\s*VH-[0-9A-F]{12}/g, "")
    .trim();
}

/**
 * An agent's reply without the signature its instructions make it end with ("— Agent Tri thức"):
 * the conversation already names who wrote each message.
 */
export function unsigned(text: string, author: string): string {
  const lines = text.trimEnd().split("\n");
  const last = lines.at(-1)!.trim().replace(/^[—–-]+\s*/, "");
  return lines.length > 1 && /^[—–-]/.test(lines.at(-1)!.trim()) && last === author.trim() ? lines.slice(0, -1).join("\n").trimEnd() : text;
}

/** Who a question went to. Its progress is said only while there is something to wait for or redo. */
export function askedLine(agent: string, status?: string | null): string {
  return `Hỏi @${agent}${status && status !== "done" ? ` · ${mentionStatus[status] || status}` : ""}`;
}

export type FeedItem =
  | { type: "note"; id: string; at: string; text: string }
  | { type: "resident"; id: string; at: string; text: string }
  | { type: "supervisor"; id: string; at: string; text: string }
  | { type: "agent"; id: string; at: string; author: string; text: string }
  | { type: "asked"; id: string; at: string; author: string; agent: string; text: string; status: string; files: RoomFile[] }
  | { type: "plan"; id: string; at: string };

/**
 * One session as a conversation, oldest first: what the resident said, what the Supervisor and its
 * agents did, the plan, and what management asked. Only the newest plan is drawn as a card.
 */
export function sessionFeed(
  sessionId: string,
  messages: RoomMessage[],
  detail: Pick<TicketSession, "conversation" | "room"> | undefined,
  agents: { id: string; name: string }[],
  userId: string,
): FeedItem[] {
  const name = (id?: string | null) => agents.find((a) => a.id === id)?.name || "Agent";
  const own = messages.filter((m) => m.body.sessionId === sessionId);
  const lastPlan = own.findLast((m) => m.body.kind === "supervisor_plan")?.id;
  const items: FeedItem[] = (detail?.conversation || [])
    .filter((m) => m.sender_kind === "user")
    .map((m) => ({ type: "resident", id: m.id, at: m.created_at, text: plain(m.text) }));
  for (const m of own) {
    const base = { id: m.id, at: m.created_at }, text = plain(m.body.text || "");
    const kind = m.body.kind || "";
    if (kind === "supervisor_accepted") items.push({ ...base, type: "note", text: "Supervisor nhận điều phối yêu cầu" });
    else if (kind === "agent_joined_session" || kind === "agent_left_session") items.push({ ...base, type: "note", text });
    else if (kind === "supervisor_plan")
      items.push(m.id === lastPlan && detail?.room?.plan ? { ...base, type: "plan" } : { ...base, type: "note", text: "Supervisor đã soạn phương án và chuyển cho bạn duyệt" });
    else if (kind === "supervisor_plan_approval_requested") items.push({ ...base, type: "note", text: "Đã gửi phương án cho cư dân" });
    else if (kind === "supervisor_information_requested") items.push({ ...base, type: "supervisor", text });
    else if (kind === "inquiry") items.push({ ...base, type: "resident", text });
    else if (kind === "session_question")
      items.push({ ...base, type: "asked", author: m.sender_user_id === userId ? "Bạn" : m.sender_name || "Ban quản lý",
        agent: name(m.body.mentionAgentId), text, status: m.mention_status || "", files: m.files || [] });
    else if (m.sender_agent_id && kind.startsWith("supervisor")) items.push({ ...base, type: "note", text });
    else if (m.sender_agent_id) items.push({ ...base, type: "agent", author: name(m.sender_agent_id), text: unsigned(text, name(m.sender_agent_id)) });
  }
  // The backend stores a plan a moment before it mirrors the reply the plan was built from.
  const when = (item: FeedItem) => new Date(item.at).getTime() + (item.type === "plan" || (item.type === "note" && item.text.includes("đã soạn phương án")) ? 5000 : 0);
  return items.sort((a, b) => when(a) - when(b));
}

export const mentionStatus: Record<string, string> = {
  queued: "Đang chờ agent trả lời",
  running: "Agent đang trả lời",
  done: "Đã trả lời",
  failed: "Agent không trả lời được. Gửi lại câu hỏi để thử lại.",
  refused: "Agent chưa được phát hành hoặc đã thu hồi",
};

export const planStatus: Record<string, string> = {
  management_pending: "Chờ bạn duyệt",
  resident_pending: "Chờ cư dân đồng ý",
  approved: "Cư dân đã đồng ý",
  rejected: "Đã bị từ chối",
};

/** A concrete hand-back reason; internal runtime keys never become visible copy. */
export function handbackReason(reason?: string | null): string {
  const reasons: Record<string, string> = {
    "planner:no_specialist_available": "Chưa có agent chuyên môn phù hợp",
    "planner:analysis_ready": "Cần hoàn thiện phương án xử lý",
    "planner:planner_model_not_configured": "Chưa cấu hình model điều phối",
    AGENT_FAILURE: "Agent chưa trả lời được", model_unavailable: "Model điều phối mất kết nối",
    model_timeout: "Model điều phối trả lời quá chậm", outcome_unknown: "Cần kiểm tra kết quả xử lý",
    management_pause: "Bạn đã tạm dừng phiên",
  };
  if (!reason) return "Cần bạn kiểm tra yêu cầu";
  if (reasons[reason]) return reasons[reason];
  const text = reason.replace(/^planner:/, "").trim();
  return /^[\p{L}\p{N}\s.,():!?–-]+$/u.test(text) && !text.includes("_") ? plain(text) : "Cần bạn kiểm tra yêu cầu";
}
export const LIFECYCLE = ["Tiếp nhận", "Phương án", "Bạn duyệt", "Cư dân đồng ý", "Thi công", "Nghiệm thu"];
export function lifecycleStep(s: RoomSession): number {
  if (s.manual && !["assigned", "in_progress", "resolved", "closed"].includes(s.ticket_status)) return 0;
  if (s.status === "completed" || s.ticket_status === "closed" || s.ticket_status === "resolved" || s.work_status === "completed") return 5;
  if (s.plan_status === "rejected" || s.plan_status === "management_pending" || s.runtime?.phase === "paused") return 2;
  if (s.plan_status === "resident_pending") return 3;
  if (s.plan_status === "approved" || s.ticket_status === "in_progress" || s.ticket_status === "assigned") return 4;
  return s.status === "queued" ? 0 : 1;
}
export function stateTone(s: RoomSession): "ok" | "wait" | "danger" | "neutral" | "agent" {
  const state = sessionState(s);
  if (s.status === "failed" || s.status === "cancelled") return "danger";
  if (state.group === "done") return "neutral";
  if (state.group === "attention" || s.plan_status === "resident_pending") return "wait";
  return s.plan_status === "approved" ? "ok" : "agent";
}
/** Due time uses full Vietnamese units and is omitted when the API has no deadline. */
export function dueText(iso?: string | null, now = Date.now()): { label: string; tone: "danger" | "wait" | "neutral" } | null {
  if (!iso) return null;
  const difference = Date.parse(iso) - now;
  if (!Number.isFinite(difference)) return null;
  const total = Math.max(1, Math.ceil(Math.abs(difference) / 60000));
  const days = Math.floor(total / 1440), hours = Math.floor((total % 1440) / 60), minutes = total % 60;
  const time = [days ? `${days} ngày` : "", hours ? `${hours} giờ` : "", !days && minutes ? `${minutes} phút` : ""].filter(Boolean).join(" ");
  return { label: `${difference < 0 ? "Quá hạn" : "Còn"} ${time}`, tone: difference < 0 ? "danger" : difference < 4 * 3600000 ? "wait" : "neutral" };
}
