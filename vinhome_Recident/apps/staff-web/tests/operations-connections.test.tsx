import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/connections" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
afterAll(() => GlobalRegistrator.unregister());

test("an administrator opens a connection, sees what the server offers and allows only what reads", async () => {
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("../src/query-client");
  const { ConnectionsPage } = await import("../src/features/vinhomes-operations/connected/Connections");
  const sent: { method: string; url: string; body: unknown }[] = [];
  let allowed: string[] = [];
  let readNames: string[] = [];
  let inUse = true;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    const method = init?.method || "GET";
    if (method !== "GET") sent.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url.endsWith("/check")) return Response.json({ ok: true, error: null, tools: [
      { name: "sotay.tra_cuu", tool: "tra_cuu", description: "Tra cứu sổ tay vận hành.", destructive: false, usable: true, allowed: allowed.includes("sotay.tra_cuu") },
      { name: "sotay.xoa_muc", tool: "xoa_muc", description: "Xóa một mục.", destructive: true, usable: true, allowed: false }] });
    if (method === "PUT") {
      if (inUse) { inUse = false; return Response.json({ detail: { code: "CONNECTION_IN_USE", agents: ["Agent Sổ tay"] } }, { status: 409 }); }
      const chosen = JSON.parse(String(init!.body)) as { names: string[]; read_names: string[] };
      allowed = chosen.names;
      readNames = chosen.read_names;
      return Response.json({ id: "sotay", allowed });
    }
    return Response.json({ workspaces: [{ id: "w1", name: "Phòng Ban quản lý Sapphire" }], items: [{ id: "sotay", title: "Sổ tay vận hành",
      url: "https://handbook.example/mcp", workspace_id: "w1", workspace: "Phòng Ban quản lý Sapphire", has_token: true, tools_refreshed_at: null, last_error: null,
      tools: allowed.map((name) => ({ name, description: "", effect: readNames.includes(name) ? "read" : "write" })) }] });
  }) as typeof fetch;
  const view = render(<QueryClientProvider client={queryClient}><ConnectionsPage /></QueryClientProvider>);
  const card = await view.findByRole("button", { name: /Sổ tay vận hành/ });
  expect(card.textContent).not.toContain("handbook.example");
  expect(card.closest('tr')!.textContent).toContain("Phòng Ban quản lý Sapphire");
  // The token is never part of what this screen receives or shows.
  expect(document.body.textContent).not.toContain("encrypted");
  fireEvent.click(card);
  expect(await view.findByText('https://handbook.example/mcp')).toBeTruthy();
  const read = await view.findByRole("checkbox", { name: "tra_cuu" }) as HTMLInputElement;
  const destructive = view.getByRole("checkbox", { name: "xoa_muc" }) as HTMLInputElement;
  expect(destructive.getAttribute('aria-disabled')).toBe('true');
  expect(destructive.closest(".agent-capability-row")!.textContent).toContain("phá hủy dữ liệu");
  const save = view.getByRole("button", { name: "Lưu công cụ được phép" }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  const {default:userEvent}=await import('@testing-library/user-event');
  const user=userEvent.setup({document});
  await user.click(read);
  await user.click(view.getByRole('checkbox',{name:'Đánh dấu tra_cuu chỉ đọc'}));
  await waitFor(()=>expect(save.disabled).toBe(false));
  await user.click(save);
  // A refusal names the agents that still use the tool, so the administrator knows what to do next.
  expect((await view.findByRole("alert")).textContent).toContain("Agent đang phát hành còn dùng: Agent Sổ tay");
  fireEvent.click(view.getByRole("button", { name: "Lưu công cụ được phép" }));
  await waitFor(() => expect(view.getByRole("status").textContent).toContain("Đã lưu"));
  expect(sent.filter((s) => s.method === "PUT").at(-1)).toEqual({ method: "PUT", url: "/api/business/admin/connections/sotay/tools", body: { names: ["sotay.tra_cuu"], read_names: ['sotay.tra_cuu'] } });
  // Changing only the effect must also be saved; the permitted tool list stays identical.
  await user.click(view.getByRole('checkbox', {name:'Đánh dấu tra_cuu chỉ đọc'}));
  await waitFor(() => expect(save.disabled).toBe(false));
  await user.click(save);
  await waitFor(() => expect(view.getByRole('status').textContent).toContain('Đã lưu'));
  expect(sent.filter(s => s.method === 'PUT').at(-1)?.body).toEqual({names:['sotay.tra_cuu'], read_names:[]});
});
