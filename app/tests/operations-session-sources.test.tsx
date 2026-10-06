import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import type { RoomSession } from "../src/lib/rooms/queries";

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
afterAll(async () => { await new Promise(done => setTimeout(done, 50)); GlobalRegistrator.unregister(); });

test("request source consent and each exact write have separate persisted actions", async () => {
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("../src/query-client");
  const { SessionThread } = await import("../src/features/vinhomes-operations/connected/coordination/SessionThread");
  queryClient.clear();
  const sent: { url: string; body: unknown }[] = [];
  let enabled = false, status = "pending";
  const source = { id: "calendar", title: "Lịch bảo trì", status: "active", tools: [{ name: "calendar.create_event", description: "Tạo lịch kiểm tra thiết bị", effect: "write" }] };
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "PUT" && url.endsWith("/sources")) { const body = JSON.parse(String(init.body)); sent.push({ url, body }); enabled = body.enabled; return Response.json({ enabled }); }
    if (init?.method === "POST" && url.endsWith("/decision")) { const body = JSON.parse(String(init.body)); sent.push({ url, body }); status = "succeeded"; return Response.json({ status }); }
    if (url.endsWith("/session/sources")) return Response.json({ items: [{ ...source, enabled }] });
    if (url.endsWith("/session/external-calls")) return Response.json({ items: [{ id: "confirmation", agent_id: "tech", tool_name: "calendar.create_event", connection_title: "Lịch bảo trì", description: "Tạo lịch kiểm tra thiết bị", arguments: { title: "Kiểm tra căn 1201", starts_at: "2026-10-08T18:00:00+07:00" }, status, created_at: "2026-10-06T10:00:00Z" }] });
    if (url.endsWith("/session")) return Response.json({ session: { id: "s1", status: "running" }, room: { members: ["Agent Kỹ thuật"], tasks: [], replies: [], questions: [], plan: null }, awaitingManagementApproval: false });
    if (url.endsWith("/conversation")) return Response.json({ items: [] });
    if (url.endsWith("/presentation")) return Response.json({ participants: [], events: [] });
    if (url === "/api/business/tickets/t1") return Response.json({ ticket: { id: "t1", title: "Máy nước nóng không nóng", status: "open" }, workOrders: [], events: [] });
    return Response.json({ detail: "not found" }, { status: 404 });
  }) as typeof fetch;
  const session: RoomSession = { id: "s1", ticket_id: "t1", ticket_code: "VH-AAAAAAAAAAAA", ticket_title: "Máy nước nóng không nóng", status: "running", ticket_status: "open", created_at: "2026-10-06T10:00:00Z", updated_at: "2026-10-06T10:00:00Z", plan_status: null, runtime: { phase: "planning" } };
  const page = render(<QueryClientProvider client={queryClient}><SessionThread roomId="room" session={session} messages={[]} agents={[{ id: "tech", name: "Agent Kỹ thuật", published: true, status: "active" }]} userId="manager" /></QueryClientProvider>);
  const card = await waitFor(() => page.getByRole("region", { name: "Thao tác ghi chờ xác nhận" }));
  expect(card.textContent).toContain("Tạo lịch kiểm tra thiết bị");
  expect(card.textContent).toContain("Kiểm tra căn 1201");
  expect(card.textContent).toContain("2026-10-08T18:00:00+07:00");
  fireEvent.click(await waitFor(() => page.getByRole("switch", { name: "Dùng Lịch bảo trì cho câu hỏi của bạn trong yêu cầu này" })));
  await waitFor(() => expect(sent[0]).toEqual({ url: "/api/business/tickets/t1/session/sources", body: { server_id: "calendar", enabled: true } }));
  fireEvent.click(page.getByRole("button", { name: "Cho phép" }));
  await waitFor(() => expect(sent[1]).toEqual({ url: "/api/business/tickets/t1/session/external-calls/confirmation/decision", body: { decision: "approve" } }));
  await waitFor(() => expect(page.getByRole("region", { name: "Kết quả thao tác ghi" }).textContent).toContain("Đã thực hiện"));
  expect(page.queryByRole("button", { name: "Cho phép" })).toBeNull();
  expect(page.container.textContent).not.toContain("calendar.create_event");
  queryClient.clear();
});
