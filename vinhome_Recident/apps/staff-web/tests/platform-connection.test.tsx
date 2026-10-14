import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";
import type { Connection } from "../src/features/vinhomes-operations/connected/admin/PlatformConnection";

let render: typeof import("@testing-library/react")["render"];
let cleanup: typeof import("@testing-library/react")["cleanup"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/platform-connection" });
  ({ render, cleanup, fireEvent, waitFor } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
afterAll(async () => { await new Promise(done => setTimeout(done, 50)); GlobalRegistrator.unregister(); });

const config: Connection = {
  version: 1, source: "admin", enabled: false, url: "https://platform.test", signing_key_id: "sig_test_01",
  encryption_ready: true, secrets_configured: { customer_key: true, provider_key: true, signing_secret: true },
  updated_at: null, worker_seen_at: null, worker_version: null, last_check: null,
  counts: { active_workflows: 0, pending_commands: 0, failed_commands: 0, pending_events: 0, rejected_events: 0 },
  units: [{ code: "local-management", name: "Local Management", route: null }],
  mcp: { url: "https://vinhomes.example.com/mcp", transport: "streamable_http", configured: true,
    grant_path: "/api/business/platform/mcp-grants", ttl_seconds: 3600,
    tools: ["vh_ticket_get", "vh_knowledge_search", "vh_staff_available", "vh_work_order_dispatch", "vh_work_order_reschedule", "vh_ticket_cancel", "vh_ticket_add_note"] },
};

async function mount(respond?: (url: string, init?: RequestInit) => Response) {
  const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
  const { PlatformConnectionPage } = await import("../src/features/vinhomes-operations/connected/admin/PlatformConnection");
  const sent: { url: string; body: Record<string, unknown> }[] = [];
  globalThis.fetch = (async (url, init) => {
    if (init?.method && init.method !== "GET") sent.push({ url: String(url), body: init.body ? JSON.parse(String(init.body)) : {} });
    return respond?.(String(url), init) || Response.json(config);
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const view = render(<QueryClientProvider client={client}><PlatformConnectionPage /></QueryClientProvider>);
  await view.findByLabelText("URL Platform");
  return { view, sent };
}

test("saved keys stay blank and switching tabs supports keyboard navigation", async () => {
  const { view } = await mount();
  expect((view.getByLabelText("Customer key") as HTMLInputElement).value).toBe("");
  expect(view.getByRole("button", { name: "Bật kết nối" }).hasAttribute("disabled")).toBe(true);
  fireEvent.keyDown(view.getByRole("tab", { name: "Cấu hình kết nối" }), { key: "End" });
  expect(view.getByRole("tab", { name: "Bàn giao MCP" }).getAttribute("aria-selected")).toBe("true");
  expect(view.getByText("vh_work_order_dispatch")).toBeTruthy();
  expect(view.getByRole("button", { name: "Tải bộ kết nối MCP" })).toBeTruthy();
});

test("save replaces one key while leaving other saved keys unchanged", async () => {
  const { view, sent } = await mount((_, init) => init?.method === "PUT" ? Response.json({ ...config, version: 2 }) : Response.json(config));
  await typeInto(view.getByLabelText("Customer key"), "replacement-secret-key-1234");
  fireEvent.click(view.getByRole("button", { name: "Lưu cấu hình" }));
  await view.findByText("Đã lưu. API áp dụng ngay; worker tự đồng bộ cấu hình.");
  expect(sent[0].body.customer_key).toBe("replacement-secret-key-1234");
  expect(sent[0].body).not.toHaveProperty("provider_key");
  expect(sent[0].body).not.toHaveProperty("signing_secret");
  expect((view.getByLabelText("Customer key") as HTMLInputElement).value).toBe("");
});

test("validation errors stay near their field and retain unsaved input", async () => {
  const { view } = await mount((_, init) => init?.method === "PUT" ? Response.json({ detail: "Kiểm tra lại các trường cấu hình.", errors: [{ field: "customer_key", message: "Khóa chưa đủ độ dài." }] }, { status: 422 }) : Response.json(config));
  await typeInto(view.getByLabelText("Customer key"), "short");
  fireEvent.click(view.getByRole("button", { name: "Lưu cấu hình" }));
  await view.findByText("Khóa chưa đủ độ dài.");
  expect(view.getByLabelText("Customer key").getAttribute("aria-invalid")).toBe("true");
  expect((view.getByLabelText("Customer key") as HTMLInputElement).value).toBe("short");
});

test("route confirmation sends the selected unit and preserves server revision", async () => {
  const { view, sent } = await mount((url, init) => url.endsWith("/routes/confirm") && init?.method === "POST" ? Response.json({ ...config, version: 2, units: [{ ...config.units[0], route: { route_id: "route_new", revision: 2, status: "active", confirmed_at: "2026-10-14T08:00:00Z" } }] }) : Response.json(config));
  fireEvent.click(view.getByRole("tab", { name: "Tuyến đơn vị" }));
  await typeInto(view.getByLabelText("Mã tuyến Platform"), "route_new");
  fireEvent.click(view.getByRole("button", { name: "Xác nhận tuyến" }));
  await waitFor(() => expect(sent.length).toBe(1));
  expect(sent[0].body).toEqual({ version: 1, management_ref: "local-management", route_id: "route_new", revision: 1 });
  await view.findByText("Đã xác nhận · v2");
});
