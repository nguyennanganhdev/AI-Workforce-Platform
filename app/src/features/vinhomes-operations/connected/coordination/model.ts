import type { RoomMessage, RoomSession, TicketSession } from "@/lib/rooms/queries";

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
  if (s.status === "failed") return { group: "done", label: "Lỗi điều phối" };
  if (s.ticket_status === "closed") return { group: "attention", label: "Cư dân đã xác nhận, chờ bạn duyệt đóng" };
  if (s.runtime?.phase === "paused")
    return { group: "attention", label: s.runtime.pauseReason === "management_pause" ? "Bạn đã tạm dừng phiên" : "Supervisor dừng lại, cần bạn xử lý" };
  if (s.plan_status === "management_pending") return { group: "attention", label: "Chờ bạn duyệt phương án" };
  if (s.plan_status === "resident_pending") return { group: "running", label: "Chờ cư dân đồng ý phương án" };
  if (s.plan_status === "approved") return { group: "running", label: "Đã duyệt, đang thi công" };
  if (s.runtime?.phase === "waiting_information") return { group: "running", label: "Chờ cư dân trả lời" };
  return { group: "running", label: "Supervisor đang điều phối" };
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
  "planner:no_specialist_available": "Phòng chưa có agent chuyên môn cho loại yêu cầu này. Bạn xử lý trực tiếp ở mục Công việc.",
  "planner:analysis_ready": "Agent đã phân tích xong nhưng Supervisor chưa lập được phương án. Bạn lập phương án từ phân tích bên dưới.",
  "planner:planner_model_not_configured": "Supervisor chưa được cấu hình model. Bạn xử lý trực tiếp ở mục Công việc.",
  AGENT_FAILURE: "Agent không trả lời được sau nhiều lần thử. Bạn xử lý trực tiếp ở mục Công việc.",
  model_unavailable: "Supervisor không gọi được model (hết hạn mức hoặc mất kết nối). Bấm Chạy tiếp khi model hoạt động lại, hoặc xử lý trực tiếp ở mục Công việc.",
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

export type FeedItem =
  | { type: "note"; id: string; at: string; text: string }
  | { type: "resident"; id: string; at: string; text: string }
  | { type: "supervisor"; id: string; at: string; text: string }
  | { type: "agent"; id: string; at: string; author: string; text: string }
  | { type: "asked"; id: string; at: string; author: string; agent: string; text: string; status: string }
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
  const invited = detail?.room?.members.join(", ");
  const items: FeedItem[] = (detail?.conversation || [])
    .filter((m) => m.sender_kind === "user")
    .map((m) => ({ type: "resident", id: m.id, at: m.created_at, text: plain(m.text) }));
  for (const m of own) {
    const base = { id: m.id, at: m.created_at }, text = plain(m.body.text || "");
    const kind = m.body.kind || "";
    if (kind === "supervisor_accepted") items.push({ ...base, type: "note", text: invited ? `Supervisor đã tiếp nhận và mời ${invited}` : "Supervisor đã tiếp nhận yêu cầu" });
    else if (kind === "supervisor_plan")
      items.push(m.id === lastPlan && detail?.room?.plan ? { ...base, type: "plan" } : { ...base, type: "note", text: "Supervisor đã đề xuất một phương án trước đó" });
    else if (kind === "supervisor_plan_approval_requested") items.push({ ...base, type: "note", text: "Đã gửi phương án cho cư dân" });
    else if (kind === "supervisor_information_requested") items.push({ ...base, type: "supervisor", text });
    else if (kind === "inquiry") items.push({ ...base, type: "resident", text });
    else if (kind === "session_question")
      items.push({ ...base, type: "asked", author: m.sender_user_id === userId ? "Bạn" : m.sender_name || "Ban quản lý",
        agent: name(m.body.mentionAgentId), text, status: m.mention_status || "" });
    else if (m.sender_agent_id && kind.startsWith("supervisor")) items.push({ ...base, type: "note", text });
    else if (m.sender_agent_id) items.push({ ...base, type: "agent", author: name(m.sender_agent_id), text });
  }
  // The backend stores a plan a moment before it mirrors the reply the plan was built from.
  const when = (item: FeedItem) => new Date(item.at).getTime() + (item.type === "plan" || (item.type === "note" && item.text.includes("phương án trước đó")) ? 5000 : 0);
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
