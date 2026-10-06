import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({
    url: "http://localhost:3020/operations/accounts",
  });
  ({ cleanup, render, waitFor, fireEvent } = await import(
    "@testing-library/react/pure"
  ));
});
afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
});
// React still has a scheduled callback right after the last unmount; it must find a window.
afterAll(async () => {
  await new Promise((done) => setTimeout(done, 50));
  GlobalRegistrator.unregister();
});

const accounts = [
  {
    id: "u1",
    name: "Nguyễn Văn An",
    email: "an@example.com",
    role: "management",
    status: "active",
    administrator: false,
    management_unit_id: "unit-1",
  },
  {
    id: "u2",
    name: "Trần Thị Bình",
    email: "binh@example.com",
    role: "customer",
    status: "pending",
    administrator: false,
    management_unit_id: null,
  },
  {
    id: "u3",
    name: "Quản trị",
    email: "admin@example.com",
    role: "management",
    status: "active",
    administrator: true,
    management_unit_id: null,
  },
];
async function choose(
  view: ReturnType<typeof render>,
  label: string,
  option: string,
) {
  const { default: userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup({ document });
  await user.click(view.getByRole("combobox", { name: label }));
  await user.click(await view.findByRole("option", { name: option }));
}

async function mount(
  page: "AccountsPage" | "ModelsPage" | "AuditPage",
  respond: (url: string, init?: RequestInit) => Response,
) {
  const { QueryClientProvider, QueryClient } = await import(
    "@tanstack/react-query"
  );
  const sent: { method: string; url: string; body: unknown }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const parsed = new URL(String(input), "http://localhost");
    const url = parsed.pathname + parsed.search;
    if (init?.method && init.method !== "GET")
      sent.push({
        method: init.method,
        url,
        body: init.body ? JSON.parse(String(init.body)) : undefined,
      });
    return respond(url, init);
  }) as typeof fetch;
  const Page =
    page === "AccountsPage"
      ? (
          await import(
            "../src/features/vinhomes-operations/connected/admin/Accounts"
          )
        ).AccountsPage
      : (
          await import(
            "../src/features/vinhomes-operations/connected/admin/Platform"
          )
        )[page];
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    view: render(
      <QueryClientProvider client={client}>
        <Page />
      </QueryClientProvider>,
    ),
    sent,
  };
}

test("the administrator finds an account, approves it and moves a manager to another unit", async () => {
  const { view, sent } = await mount("AccountsPage", (url, init) => {
    if (init?.method === "PATCH") return Response.json({ ok: true });
    if (url.endsWith("/auth/management-units"))
      return Response.json({
        items: [
          { id: "unit-1", name: "BQL Sapphire" },
          { id: "unit-2", name: "BQL Ruby" },
        ],
      });
    return Response.json({ items: accounts });
  });
  expect((await view.findByText("3 tài khoản")).textContent).toBeTruthy();
  expect(
    view
      .getByRole("button", { name: /Nguyễn Văn An an@example.com/ })
      .closest("tr")!.textContent,
  ).toContain("BQL Sapphire");
  // The administrator's own account is listed and cannot be edited from here.
  fireEvent.click(view.getByRole("button", { name: /admin@example.com/ }));
  expect(
    await view.findByText("Quyền quản trị viên được quản lý riêng."),
  ).toBeTruthy();
  expect(view.queryByRole("button", { name: "Lưu thay đổi" })).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Hủy" }));
  await typeInto(view.getByLabelText("Tìm theo tên hoặc email"), "binh");
  expect(view.getByText("Hiển thị 1 trên 3 tài khoản")).toBeTruthy();
  fireEvent.click(
    view.getByRole("button", { name: /Trần Thị Bình binh@example.com/ }),
  );
  fireEvent.click(await view.findByRole("button", { name: "Duyệt tài khoản" }));
  await waitFor(() =>
    expect(sent).toEqual([
      {
        method: "PATCH",
        url: "/api/business/auth/accounts/u2",
        body: { role: "customer", status: "active" },
      },
    ]),
  );
  await typeInto(view.getByLabelText("Tìm theo tên hoặc email"), "");
  fireEvent.click(
    await view.findByRole("button", { name: /Nguyễn Văn An an@example.com/ }),
  );
  await choose(view, "Đơn vị quản lý", "BQL Ruby");
  fireEvent.click(view.getByRole("button", { name: "Lưu thay đổi" }));
  await waitFor(() =>
    expect(sent[1]).toEqual({
      method: "PATCH",
      url: "/api/business/auth/accounts/u1",
      body: {
        role: "management",
        status: "active",
        management_unit_id: "unit-2",
      },
    }),
  );
});

test("the model page says which model each role runs on and which service does not answer", async () => {
  const { view } = await mount("ModelsPage", (url) =>
    url.endsWith("/model-registry")
      ? Response.json({ items: [], defaults: [] })
      : Response.json({
          items: [
            {
              role: "reception",
              configured: true,
              running: true,
              model: "gemini-3.8-flash",
              provider: "google",
            },
            {
              role: "supervisor",
              configured: true,
              running: false,
              model: null,
              provider: null,
            },
            {
              role: "specialist",
              configured: true,
              running: false,
              model: null,
              provider: null,
            },
            {
              role: "factory",
              configured: false,
              running: false,
              model: null,
              provider: null,
            },
            {
              role: "embedding",
              configured: true,
              running: null,
              model: "text-embedding-3-large · 1536 chiều",
              provider: "openai",
            },
          ],
        }),
  );
  await view.findByText("Lễ tân");
  const rows = Array.from(view.container.querySelectorAll("tbody tr")).map(
    (li) => li.textContent,
  );
  expect(rows[0]).toContain("Lễ tân");
  expect(rows[0]).toContain("gemini-3.8-flash");
  expect(rows[0]).toContain("Dịch vụ đang chạy");
  expect(rows[1]).toContain("Dịch vụ không trả lời");
  expect(rows[3]).toContain("Chưa cấu hình");
  expect(rows[4]).toContain("Đã cấu hình");
  // No key and no address is ever part of this page.
  expect(document.body.textContent).not.toMatch(/https?:\/\/|sk-/);
});

test("a configured Factory with no model name reports an unavailable name", async () => {
  const { view } = await mount("ModelsPage", (url) =>
    url.endsWith("/model-registry")
      ? Response.json({ items: [], defaults: [] })
      : Response.json({
          items: [
            {
              role: "factory",
              configured: true,
              running: true,
              model: null,
              provider: null,
            },
          ],
        }),
  );
  const selector = await view.findByRole("combobox", {
    name: "Model cho Factory",
  });
  const row = selector.closest("tr")!;
  expect(row.textContent).toContain("Dịch vụ chưa báo tên model");
  expect(row.textContent).toContain("Dịch vụ đang chạy");
  expect(row.textContent).not.toContain("Chưa cấu hình");
});

test("the audit page names events in plain words and asks the server for one kind", async () => {
  const asked: string[] = [];
  const { view } = await mount("AuditPage", (url) => {
    asked.push(url);
    return Response.json({
      kinds: ["agent", "connection"],
      items: [
        {
          id: "e1",
          created_at: "2026-10-04T16:00:00Z",
          event_type: "connection.created",
          initiator_kind: "person",
          actor: "Quản trị",
          target_type: "mcp_server",
          target_id: "sotay",
          payload: { hasToken: true },
        },
        {
          id: "e2",
          created_at: "2026-10-04T15:00:00Z",
          event_type: "agent.tool_called",
          initiator_kind: "agent",
          actor: "Agent Báo cáo",
          target_type: "agent_run",
          target_id: "run-1",
          payload: { tool: "reporting.filter_report_scope", status: "OK" },
        },
      ],
    });
  });
  expect(
    (await view.findByText("Thêm kết nối ngoài")).closest("tr")!.textContent,
  ).toContain("Quản trị");
  expect(view.getByText("Gọi công cụ").closest("tr")!.textContent).toContain(
    "Agent Báo cáo",
  );
  expect(view.container.textContent).not.toContain(
    "reporting.filter_report_scope",
  );
  await choose(view, "Loại đối tượng", "Kết nối");
  await waitFor(() =>
    expect(asked.at(-1)).toBe(
      "/api/business/admin/audit-events?limit=50&kind=connection",
    ),
  );
});

test("the audit page takes the trail of a span of days as a file, and says why when the span is too large", async () => {
  const asked: string[] = [];
  let tooMany = true;
  const { view } = await mount("AuditPage", (url) => {
    asked.push(url);
    if (!url.includes("/export"))
      return Response.json({ kinds: ["agent"], items: [] });
    if (tooMany) {
      tooMany = false;
      return Response.json(
        {
          detail:
            "Khoảng này có 60000 sự kiện, nhiều hơn mức 50000 của một tệp. Chọn khoảng ngắn hơn.",
        },
        { status: 413 },
      );
    }
    return new Response("\ufeffThời điểm\n", {
      headers: { "content-type": "text/csv; charset=utf-8" },
    });
  });
  const saved: { name: string; href: string }[] = [];
  const make = URL.createObjectURL,
    drop = URL.revokeObjectURL,
    click = HTMLAnchorElement.prototype.click;
  URL.createObjectURL = () => "blob:trail";
  URL.revokeObjectURL = () => {};
  HTMLAnchorElement.prototype.click = function () {
    saved.push({ name: this.download, href: this.href });
  };
  try {
    await view.findByText(
      "Không có sự kiện trong bộ lọc này. Thử đổi khoảng ngày hoặc từ khóa.",
    );
    await typeInto(view.getByLabelText("Nhật ký từ ngày"), "2026-09-01");
    await typeInto(view.getByLabelText("Nhật ký đến ngày"), "2026-09-30");
    fireEvent.click(view.getByRole("button", { name: "Xuất CSV" }));
    expect((await view.findByRole("alert")).textContent).toContain(
      "Chọn khoảng ngắn hơn",
    );
    expect(saved).toEqual([]);
    await typeInto(view.getByLabelText("Nhật ký đến ngày"), "2026-09-07");
    fireEvent.click(view.getByRole("button", { name: "Xuất CSV" }));
    await waitFor(() =>
      expect(saved).toEqual([{ name: "nhat-ky.csv", href: "blob:trail" }]),
    );
    const params = new URL("http://localhost" + asked.at(-1)).searchParams;
    expect(params.get("from")).toBe("2026-09-01");
    expect(params.get("to")).toBe("2026-09-07");
  } finally {
    URL.createObjectURL = make;
    URL.revokeObjectURL = drop;
    HTMLAnchorElement.prototype.click = click;
  }
});

test("the model role returns to deployment fallback and persists the clear", async () => {
  let saved = true;
  const { view, sent } = await mount("ModelsPage", (url, init) => {
    if (init?.method === "DELETE") {
      saved = false;
      return Response.json({ ok: true, role: "supervisor", model_id: null });
    }
    if (url.endsWith("/model-registry"))
      return Response.json({
        items: [
          {
            id: "registered",
            name: "Registered model",
            kind: "chat",
            provider: "openai",
            allowed: true,
            check_status: "ok",
          },
        ],
        defaults: saved
          ? [
              {
                role: "supervisor",
                model_id: "registered",
                updated_at: "2026-10-06T10:00:00Z",
              },
            ]
          : [],
      });
    return Response.json({
      items: [
        {
          role: "supervisor",
          configured: true,
          running: true,
          model: "deployment-model",
          provider: "openai",
        },
      ],
    });
  });
  const roleSelector = await view.findByRole("combobox", {
    name: "Model cho Supervisor",
  });
  await waitFor(() =>
    expect(roleSelector.textContent).toContain("Registered model"),
  );
  await choose(view, "Model cho Supervisor", "Theo bản triển khai");
  await waitFor(() =>
    expect(sent).toEqual([
      {
        method: "DELETE",
        url: "/api/business/admin/model-defaults/supervisor",
        body: undefined,
      },
    ]),
  );
  expect(
    await view.findByText("Vai trò đã quay lại model của bản triển khai"),
  ).toBeTruthy();
  expect(
    view.getByRole("combobox", { name: "Model cho Supervisor" }).textContent,
  ).toContain("Theo bản triển khai");
});

test("external audit events have readable names and cursor keeps the row id", async () => {
  const { eventLabel } = await import(
    "../src/features/vinhomes-operations/connected/admin/Audit"
  );
  const { filteredAuditOptions } = await import(
    "../src/features/vinhomes-operations/connected/admin/queries"
  );
  const items = Array.from({ length: 50 }, (_, i) => ({
    id: `event-${i}`,
    created_at: "2026-10-06T10:00:00Z",
    event_type: "external-source-used",
    initiator_kind: "person",
    actor: "BQL",
    target_type: "mcp_server",
    target_id: "calendar",
    payload: {},
  }));
  expect(eventLabel(items[0])).toBe("Dùng nguồn ngoài");
  expect(
    eventLabel({ ...items[0], event_type: "external-write-requested" }),
  ).toBe("Yêu cầu ghi nguồn ngoài");
  expect(
    eventLabel({ ...items[0], event_type: "external-write-decided" }),
  ).toBe("Quyết định ghi nguồn ngoài");
  const options = filteredAuditOptions({
    kind: "",
    from: "",
    to: "",
    actor: "",
    action: "",
    search: "",
    result: "",
  });
  expect(
    options.getNextPageParam!({ items, kinds: [], actions: [] }, [], null, []),
  ).toEqual({ at: items[49].created_at, id: items[49].id });
});

test("deleting a connector shows the API history refusal", async () => {
  const { QueryClient } = await import("@tanstack/react-query");
  const { removeConnectionMutationOptions } = await import(
    "../src/lib/connections/mutations"
  );
  globalThis.fetch = (async (_input: RequestInfo | URL, _init?: RequestInit) =>
    Response.json(
      {
        detail:
          "Kết nối đã có lịch sử xác nhận công cụ. Hãy tạm ngưng kết nối để giữ lịch sử kiểm toán.",
      },
      { status: 409 },
    )) as typeof fetch;
  const mutation = removeConnectionMutationOptions(new QueryClient());
  await expect(mutation.mutationFn!("calendar", {} as never)).rejects.toThrow(
    "Hãy tạm ngưng kết nối",
  );
});
