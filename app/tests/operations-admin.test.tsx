import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/accounts" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
// React still has a scheduled callback right after the last unmount; it must find a window.
afterAll(async () => { await new Promise((done) => setTimeout(done, 50)); GlobalRegistrator.unregister(); });

const accounts = [
  { id: "u1", name: "Nguyễn Văn An", email: "an@example.com", role: "management", status: "active", administrator: false, management_unit_id: "unit-1" },
  { id: "u2", name: "Trần Thị Bình", email: "binh@example.com", role: "customer", status: "pending", administrator: false, management_unit_id: null },
  { id: "u3", name: "Quản trị", email: "admin@example.com", role: "management", status: "active", administrator: true, management_unit_id: null },
];

async function mount(page: "AccountsPage" | "ModelsPage" | "AuditPage", respond: (url: string, init?: RequestInit) => Response) {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const sent: { method: string; url: string; body: unknown }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const parsed = new URL(String(input), "http://localhost");
    const url = parsed.pathname + parsed.search;
    if (init?.method && init.method !== "GET") sent.push({ method: init.method, url, body: init.body ? JSON.parse(String(init.body)) : undefined });
    return respond(url, init);
  }) as typeof fetch;
  const Page = page === "AccountsPage" ? (await import("../src/features/vinhomes-operations/connected/admin/Accounts")).AccountsPage
    : (await import("../src/features/vinhomes-operations/connected/admin/Platform"))[page];
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { view: render(<QueryClientProvider client={client}><Page /></QueryClientProvider>), sent };
}

test("the administrator finds an account, approves it and moves a manager to another unit", async () => {
  const { view, sent } = await mount("AccountsPage", (url, init) => {
    if (init?.method === "PATCH") return Response.json({ ok: true });
    if (url.endsWith("/auth/management-units")) return Response.json({ items: [{ id: "unit-1", name: "BQL Sapphire" }, { id: "unit-2", name: "BQL Ruby" }] });
    return Response.json({ items: accounts });
  });
  expect((await view.findByText("3 tài khoản · 1 chờ duyệt")).textContent).toBeTruthy();
  expect(view.getByRole("button", { name: /Nguyễn Văn An/ }).textContent).toContain("Ban quản lý · BQL Sapphire");
  // The administrator's own account is listed and cannot be edited from here.
  expect((view.getByRole("button", { name: /admin@example.com/ }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(view.getByLabelText("Tìm tài khoản"), { target: { value: "binh" } });
  expect(view.getByText("1 tài khoản · 1 chờ duyệt")).toBeTruthy();
  fireEvent.click(view.getByRole("button", { name: /Trần Thị Bình/ }));
  fireEvent.click(await view.findByRole("button", { name: "Duyệt tài khoản" }));
  await waitFor(() => expect(sent).toEqual([{ method: "PATCH", url: "/api/business/auth/accounts/u2", body: { role: "customer", status: "active" } }]));
  fireEvent.change(view.getByLabelText("Tìm tài khoản"), { target: { value: "" } });
  fireEvent.click(await view.findByRole("button", { name: /Nguyễn Văn An/ }));
  fireEvent.change(await view.findByLabelText("Đơn vị quản lý"), { target: { value: "unit-2" } });
  fireEvent.click(view.getByRole("button", { name: "Lưu" }));
  await waitFor(() => expect(sent[1]).toEqual({ method: "PATCH", url: "/api/business/auth/accounts/u1",
    body: { role: "management", status: "active", management_unit_id: "unit-2" } }));
});

test("the model page says which model each role runs on and which service does not answer", async () => {
  const { view } = await mount("ModelsPage", () => Response.json({ items: [
    { role: "reception", configured: true, running: true, model: "gemini-3.8-flash", provider: "google" },
    { role: "supervisor", configured: true, running: false, model: null, provider: null },
    { role: "specialist", configured: true, running: false, model: null, provider: null },
    { role: "factory", configured: false, running: false, model: null, provider: null },
    { role: "embedding", configured: true, running: null, model: "text-embedding-3-large · 1536 chiều", provider: "openai" }] }));
  const rows = (await view.findAllByRole("listitem")).map((li) => li.textContent);
  expect(rows[0]).toContain("Lễ tân");
  expect(rows[0]).toContain("gemini-3.8-flash");
  expect(rows[0]).toContain("Google Gemini");
  expect(rows[0]).toContain("Dịch vụ đang chạy");
  expect(rows[1]).toContain("Dịch vụ không trả lời");
  expect(rows[3]).toContain("Chưa cấu hình");
  expect(rows[4]).toContain("Đang dùng");
  // No key and no address is ever part of this page.
  expect(document.body.textContent).not.toMatch(/https?:\/\/|sk-/);
});

test("the audit page names events in plain words and asks the server for one kind", async () => {
  const asked: string[] = [];
  const { view } = await mount("AuditPage", (url) => {
    asked.push(url);
    return Response.json({ kinds: ["agent", "connection"], items: [
      { id: "e1", created_at: "2026-10-04T16:00:00Z", event_type: "connection.created", initiator_kind: "person", actor: "Quản trị",
        target_type: "mcp_server", target_id: "sotay", payload: { hasToken: true } },
      { id: "e2", created_at: "2026-10-04T15:00:00Z", event_type: "agent.tool_called", initiator_kind: "agent", actor: "Agent Báo cáo",
        target_type: "agent_run", target_id: "run-1", payload: { tool: "reporting.filter_report_scope", status: "OK" } }] });
  });
  expect((await view.findByText("Thêm kết nối ngoài")).closest("li")!.textContent).toContain("Quản trị");
  expect(view.getByText("Agent gọi công cụ").closest("li")!.textContent).toContain("reporting.filter_report_scope");
  fireEvent.change(view.getByLabelText("Loại sự kiện"), { target: { value: "connection" } });
  await waitFor(() => expect(asked.at(-1)).toBe("/api/business/admin/audit-events?limit=50&kind=connection"));
});
