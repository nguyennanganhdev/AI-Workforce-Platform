import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/agents" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
// The last query's refetch timer would otherwise fire after the window is gone.
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

test("management reads an agent's schedules in plain words, sets a weekly one, and sees why one was refused", async () => {
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("../src/query-client");
  const { AgentSchedules } = await import("../src/features/vinhomes-operations/connected/AgentSchedules");
  const sent: { method: string; url: string; body: unknown }[] = [];
  const routine = { id: "routine_1", agent_id: "report", agent_name: "Agent Báo cáo", owner_name: "Trần Thị Bình", instruction: "Tóm tắt yêu cầu hôm qua.",
    cron: "0 8 * * 1,2,3,4,5", enabled: true, next_run_at: "2026-10-06T01:00:00Z", schedule: { hour: 8, minute: 0, days: [1, 2, 3, 4, 5] },
    last_status: "failed", last_run_at: "2026-10-05T01:00:00Z", last_error: "Agent không trả lời được." };
  let items = [routine, { ...routine, id: "routine_other", agent_id: "security", instruction: "Của agent khác." }];
  let full = true;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    const method = init?.method || "GET";
    if (method === "GET") return Response.json({ items, timezone: "Asia/Ho_Chi_Minh" });
    sent.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (method === "POST" && full) { full = false; return Response.json({ detail: "Người đặt lịch đã có 20 lịch đang bật. Tắt bớt một lịch trước." }, { status: 409 }); }
    if (method === "PUT") items = items.map((item) => item.id === "routine_1" ? { ...item, enabled: false } : item);
    if (method === "DELETE") items = items.filter((item) => item.id !== "routine_1");
    return Response.json({ id: "routine_2" }, { status: method === "POST" ? 201 : 200 });
  }) as typeof fetch;
  const view = render(<QueryClientProvider client={queryClient}><AgentSchedules roomId="room-1" agentId="report" /></QueryClientProvider>);

  const list = await view.findByRole("list", { name: "Lịch đã đặt" });
  expect(list.textContent).toContain("Thứ Hai đến Thứ Sáu lúc 08:00");
  // 01:00 UTC is read as 08:00 in Việt Nam whatever the browser's own zone.
  expect(list.textContent).toContain("Lần tới: 08:00 Thứ Ba, 06/10");
  expect(list.textContent).toContain("lỗi · Agent không trả lời được.");
  expect(list.textContent).toContain("Đặt bởi Trần Thị Bình");
  // Only this agent's schedules, and never the expression itself.
  expect(list.textContent).not.toContain("Của agent khác");
  expect(document.body.textContent).not.toContain("* *");

  const submit = view.getByRole("button", { name: "Đặt lịch" }) as HTMLButtonElement;
  expect(submit.disabled).toBe(true);
  fireEvent.change(view.getByLabelText("Chỉ dẫn gửi cho agent mỗi lần chạy"), { target: { value: " Báo cáo tuần. " } });
  fireEvent.change(view.getByLabelText("Lặp lại"), { target: { value: "weekly" } });
  fireEvent.change(view.getByLabelText("Vào"), { target: { value: "5" } });
  fireEvent.change(view.getByLabelText("Lúc"), { target: { value: "16:30" } });
  fireEvent.click(submit);
  expect((await view.findByRole("alert")).textContent).toContain("đã có 20 lịch đang bật");
  // The refused instruction is still there to send again.
  fireEvent.click(view.getByRole("button", { name: "Đặt lịch" }));
  await waitFor(() => expect((view.getByLabelText("Chỉ dẫn gửi cho agent mỗi lần chạy") as HTMLTextAreaElement).value).toBe(""));
  expect(sent.at(-1)).toEqual({ method: "POST", url: "/api/business/rooms/room-1/routines",
    body: { agent_id: "report", instruction: "Báo cáo tuần.", hour: 16, minute: 30, days: [5] } });

  fireEvent.click(view.getByRole("button", { name: "Tắt" }));
  await view.findByRole("button", { name: "Bật" });
  expect(sent.at(-1)).toEqual({ method: "PUT", url: "/api/business/rooms/room-1/routines/routine_1/enabled", body: { enabled: false } });
  expect(view.getByRole("list", { name: "Lịch đã đặt" }).textContent).not.toContain("Lần tới");
  fireEvent.click(view.getByRole("button", { name: /Xóa lịch/ }));
  await view.findByText("Agent này chưa có lịch nào.");
  expect(sent.at(-1)).toEqual({ method: "DELETE", url: "/api/business/rooms/room-1/routines/routine_1", body: undefined });
});
