import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import type { RoomMessage, RoomSession } from "../src/lib/rooms/queries";
import { ago, askedLine, pauseText, plain, sessionFeed, sessionState, unsigned } from "../src/features/vinhomes-operations/connected/coordination/model";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/team" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
afterAll(async () => { await new Promise(done=>setTimeout(done,50)); GlobalRegistrator.unregister(); });

const session = (over: Partial<RoomSession>): RoomSession => ({
  id: "s1", ticket_id: "t1", ticket_code: "VH-AAAAAAAAAAAA", ticket_title: "Vòi bếp rò nước", status: "running",
  created_at: "2026-10-04T10:00:00Z", updated_at: "2026-10-04T10:05:00Z", ticket_status: "open", plan_status: null, runtime: { phase: "planning" }, ...over });
const message = (over: Partial<RoomMessage> & { body: RoomMessage["body"] }): RoomMessage => ({
  id: crypto.randomUUID(), seq: 1, sender_user_id: null, sender_agent_id: "supervisor", created_at: "2026-10-04T10:01:00Z", ...over });

test("a session says who it waits for, and the plan's status wins over a lagging runtime phase", () => {
  expect(sessionState(session({}))).toEqual({ group: "running", label: "Agent đang lập phương án" });
  expect(sessionState(session({ plan_status: "management_pending" })).group).toBe("attention");
  // The runtime still reports that it waits for management; the backend already recorded the decision.
  expect(sessionState(session({ plan_status: "resident_pending", runtime: { phase: "waiting_management" } })))
    .toEqual({ group: "running", label: "Chờ cư dân đồng ý" });
  expect(sessionState(session({ runtime: { phase: "paused", pauseReason: "planner:analysis_ready" } })).group).toBe("attention");
  expect(sessionState(session({ ticket_status: "closed", plan_status: "approved" })).label).toBe("Cư dân đã xác nhận, chờ bạn duyệt đóng");
  expect(sessionState(session({ status: "completed", ticket_status: "closed" }))).toEqual({ group: "done", label: "Đã đóng" });
  expect(pauseText("planner:Cư dân từ chối phương án.")).toBe("Cư dân từ chối phương án.");
  expect(ago("2026-10-04T10:00:00Z", Date.parse("2026-10-04T13:20:00Z"))).toBe("3 giờ trước");
  expect(ago("2026-10-04T10:00:00Z", Date.parse("2026-10-04T10:00:20Z"))).toBe("vừa xong");
});

test("a conversation never shows the internal request code", () => {
  expect(plain("VH-17DF1C67A8EC: Yêu cầu đã được tiếp nhận.")).toBe("Yêu cầu đã được tiếp nhận.");
  expect(plain("Mình đã ghi nhận rồi bạn nhé. Mã yêu cầu của bạn: VH-B8F1E299CE24.")).toBe("Mình đã ghi nhận rồi bạn nhé.");
  expect(plain("phương án cho yêu cầu VH-43B4AE165EE9: Cử kỹ thuật viên")).toBe("phương án cho yêu cầu: Cử kỹ thuật viên");
});

test("a message shows what the reader does not already see: no signature under a named reply, no progress once a question is answered", () => {
  expect(unsigned("Phí gửi xe là 45.000 đồng.\n\n— Agent Tri thức", "Agent Tri thức")).toBe("Phí gửi xe là 45.000 đồng.");
  // A last line that is not the author's name is part of the answer.
  expect(unsigned("Liên hệ:\n- Lễ tân tòa S1.01", "Agent Tri thức")).toBe("Liên hệ:\n- Lễ tân tòa S1.01");
  expect(unsigned("— Agent Tri thức", "Agent Tri thức")).toBe("— Agent Tri thức");
  expect(askedLine("Agent Tri thức", "done")).toBe("Hỏi @Agent Tri thức");
  expect(askedLine("Agent Tri thức", "queued")).toBe("Hỏi @Agent Tri thức · Đang chờ agent trả lời");
});

test("a session reads as one conversation in time order, with only its newest plan as a card", () => {
  const messages = [
    message({ id: "m1", body: { text: "VH-AAAAAAAAAAAA: Yêu cầu đã được tiếp nhận.", sessionId: "s1", kind: "supervisor_accepted" }, created_at: "2026-10-04T10:01:00Z" }),
    message({ id: "m2", sender_agent_id: "tech", body: { text: "VH-AAAAAAAAAAAA: Cần thay gioăng.", sessionId: "s1", kind: "specialist_reply" }, created_at: "2026-10-04T10:02:00Z" }),
    message({ id: "m3", body: { text: "VH-AAAAAAAAAAAA: Phương án một", sessionId: "s1", kind: "supervisor_plan" }, created_at: "2026-10-04T10:03:00Z" }),
    message({ id: "m4", body: { text: "VH-AAAAAAAAAAAA: Phương án hai", sessionId: "s1", kind: "supervisor_plan" }, created_at: "2026-10-04T10:06:00Z" }),
    message({ id: "m5", sender_agent_id: null, sender_user_id: "me", body: { text: "VH-AAAAAAAAAAAA: Có cần khóa van không?", sessionId: "s1", kind: "session_question", mentionAgentId: "tech" },
      mention_status: "queued", created_at: "2026-10-04T10:07:00Z" }),
    message({ id: "other", body: { text: "VH-BBBBBBBBBBBB: phiên khác", sessionId: "s2", kind: "supervisor_accepted" } }),
    message({ id: "room", sender_agent_id: null, sender_user_id: "me", body: { text: "Tin nhắn chung" } }),
  ];
  const detail = { conversation: [
      { id: "c1", sender_kind: "user", text: "Vòi bếp nhà tôi rò nước.", created_at: "2026-10-04T10:00:00Z" },
      { id: "c2", sender_kind: "agent", text: "Mình đã ghi nhận. Mã yêu cầu của bạn: VH-AAAAAAAAAAAA.", created_at: "2026-10-04T10:00:05Z" }],
    room: { members: ["Agent Kỹ thuật"], tasks: [], plan: { id: "p", title: "Thay gioăng", status: "management_pending", version: 2,
      proposal: { steps: ["Khóa van", "Thay gioăng"], performer_role: "Kỹ thuật viên", expected_duration: "45 phút", conditions: "Cư dân có mặt" } } } };
  const feed = sessionFeed("s1", messages, detail, [{ id: "tech", name: "Agent Kỹ thuật" }], "me");
  expect(feed.map((i) => i.type)).toEqual(["resident", "note", "agent", "note", "plan", "asked"]);
  expect(feed[1]).toMatchObject({ text: "Supervisor nhận điều phối yêu cầu" });
  expect(feed[2]).toMatchObject({ author: "Agent Kỹ thuật", text: "Cần thay gioăng." });
  expect(feed[5]).toMatchObject({ author: "Bạn", agent: "Agent Kỹ thuật", status: "queued", text: "Có cần khóa van không?" });
  expect(JSON.stringify(feed)).not.toContain("VH-");
  // The backend stores the plan a moment before the reply it was built from; the reply still reads first.
  const late = sessionFeed("s1", [messages[3], { ...messages[1], created_at: "2026-10-04T10:06:01Z" }], detail, [{ id: "tech", name: "Agent Kỹ thuật" }], "me");
  expect(late.map((i) => i.type)).toEqual(["resident", "agent", "plan"]);
});

test('the coordination room lists sessions and management approves the plan', async () => {
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("../src/query-client");
  queryClient.clear();
  const { Coordination } = await import("../src/features/vinhomes-operations/connected/coordination/Coordination");
  const sent: { url: string; body: unknown }[] = [];
  const plan = { id: "plan-1", title: "Thay gioăng vòi bếp", status: "management_pending", version: 3,
    proposal: { steps: ["Khóa van nước", "Thay gioăng"], performer_role: "Kỹ thuật viên nước", expected_duration: "45 phút", conditions: "Cư dân có mặt", cost: null } };
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname + new URL(String(input), "http://localhost").search;
    if (init?.method === "POST") { sent.push({ url, body: JSON.parse(String(init.body)) }); return Response.json({ status: "resident_pending" }); }
    if (url === "/api/business/rooms") return Response.json({ items: [{ id: "room", name: "Ban quản lý Sapphire" }] });
    if (url.startsWith("/api/business/rooms/room/messages")) return Response.json({ items: [
      message({ id: "m1", body: { text: "VH-AAAAAAAAAAAA: Supervisor đề xuất phương án", sessionId: "s1", kind: "supervisor_plan" } }),
      message({ id: "m2", sender_agent_id: null, sender_user_id: "me", body: { text: "Chào cả nhóm" } })] });
    if (url === "/api/business/rooms/room/agents") return Response.json({ items: [{ id: "tech", name: "Agent Kỹ thuật", published: true, status: "active" }] });
    if (url === "/api/business/rooms/room/teams") return Response.json({ items: [
      session({ id: "s2", ticket_id: "t2", ticket_title: "Đèn hành lang hỏng", plan_status: "approved" }),
      session({ plan_status: "management_pending" })] });
    if (url === "/api/business/tickets/t1/session") return Response.json({ session: { id: "s1", status: "running", state_version: 4, supervisor_name: "Điều phối" },
      room: { members: ["Agent Kỹ thuật"], tasks: [], plan }, awaitingManagementApproval: false });
    if (url === "/api/business/tickets/t1/conversation") return Response.json({ items: [{ id: "c1", sender_kind: "user", text: "Vòi bếp nhà tôi rò nước.", created_at: "2026-10-04T09:59:00Z" }] });
    if (url === "/api/business/teams/s1/controls") return Response.json({ canControl: true, runtime: { phase: "waiting_management", stateVersion: 4 }, items: [] });
    return Response.json({ detail: "not found" }, { status: 404 });
  }) as typeof fetch;
  const page = render(<QueryClientProvider client={queryClient}><Coordination userId="me" tickets={[]} /></QueryClientProvider>);
  const attention = await waitFor(() => page.getByRole("region", { name: 'Cần bạn xử lý' }));
  expect(attention.textContent).toContain("Vòi bếp rò nước");
  expect(attention.textContent).toContain("Chờ bạn duyệt phương án");
  // Requests opens the session directly; shared room chatter stays outside the request list.
  expect(page.container.textContent).not.toContain("Chào cả nhóm");
  fireEvent.click(page.getByRole("button", { name: /Vòi bếp rò nước/ }));
  const card = await waitFor(() => page.getByRole("region", { name: "Phương án xử lý" }));
  expect(card.textContent).toContain("Thay gioăng vòi bếp");
  expect(page.container.textContent).not.toContain("VH-");
  fireEvent.click(page.getByRole("button", { name: "Duyệt và gửi cư dân" }));
  await waitFor(() => expect(sent).toEqual([{ url: "/api/business/plans/plan-1/management-decision",
    body: { decision: "approve", version: 3, note: "Đồng ý phương án." } }]));
  queryClient.clear();
});
