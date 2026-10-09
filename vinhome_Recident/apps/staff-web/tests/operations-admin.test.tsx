import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
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
  page: "AccountsPage" | "AuditPage",
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

test("the administrator sets a new password for a person who lost theirs, never for an administrator", async () => {
  const { view, sent } = await mount("AccountsPage", (url, init) => {
    if (init?.method === "POST") return Response.json({ ok: true });
    if (url.endsWith("/auth/management-units")) return Response.json({ items: [] });
    return Response.json({ items: accounts });
  });
  fireEvent.click(await view.findByRole("button", { name: /admin@example.com/ }));
  expect(view.queryByRole("form", { name: "Đặt lại mật khẩu" })).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Hủy" }));
  fireEvent.click(await view.findByRole("button", { name: /Nguyễn Văn An an@example.com/ }));
  const submit = view.getByRole("button", { name: "Đặt lại mật khẩu" }) as HTMLButtonElement;
  expect(submit.disabled).toBe(true);
  fireEvent.click(view.getByRole("button", { name: "Tạo mật khẩu" }));
  const password = (view.getByLabelText("Mật khẩu mới") as HTMLInputElement).value;
  expect(password).toMatch(/^[A-HJ-NP-Za-km-z2-9]{16}$/);
  fireEvent.click(submit);
  expect(await view.findByText(/Đã đặt lại mật khẩu/)).toBeTruthy();
  expect(sent).toEqual([{ method: "POST", url: "/api/business/auth/accounts/u1/password", body: { new_password: password } }]);
});

test("an account with history cannot be removed and the refusal is shown as the server says it", async () => {
  const { view, sent } = await mount("AccountsPage", (url, init) => {
    if (init?.method === "DELETE") return Response.json({ detail: "Tài khoản đã có lịch sử trên hệ thống. Dùng Khóa truy cập để giữ lịch sử." }, { status: 409 });
    if (url.endsWith("/auth/management-units")) return Response.json({ items: [] });
    return Response.json({ items: accounts });
  });
  fireEvent.click(await view.findByRole("button", { name: /Nguyễn Văn An an@example.com/ }));
  fireEvent.click(view.getByRole("button", { name: "Xóa tài khoản" }));
  const { within } = await import("@testing-library/react/pure");
  const confirm = await view.findByRole("dialog", { name: /Xóa Nguyễn Văn An/ });
  fireEvent.click(within(confirm).getByRole("button", { name: "Xóa tài khoản" }));
  expect(await view.findByText(/Dùng Khóa truy cập để giữ lịch sử/)).toBeTruthy();
  expect(sent).toEqual([{ method: "DELETE", url: "/api/business/auth/accounts/u1", body: undefined }]);
});

test("a signed-in person changes their own password and is sent to sign in again", async () => {
  const { ChangePasswordDialog } = await import("../src/features/vinhomes-operations/layout/change-password");
  const sent: unknown[] = [];
  globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    sent.push(JSON.parse(String(init?.body)));
    return Response.json({ detail: "Mật khẩu hiện tại không đúng." }, { status: 401 });
  }) as typeof fetch;
  const view = render(<ChangePasswordDialog onClose={() => {}} />);
  await typeInto(view.getByLabelText("Mật khẩu hiện tại") as HTMLInputElement, "old-password-1");
  await typeInto(view.getByLabelText("Mật khẩu mới") as HTMLInputElement, "new-password-12");
  await typeInto(view.getByLabelText("Nhập lại mật khẩu mới") as HTMLInputElement, "new-password-1");
  expect(view.getByText("Hai lần nhập mật khẩu mới chưa khớp.")).toBeTruthy();
  expect((view.getByRole("button", { name: "Đổi mật khẩu" }) as HTMLButtonElement).disabled).toBe(true);
  await typeInto(view.getByLabelText("Nhập lại mật khẩu mới") as HTMLInputElement, "new-password-12");
  fireEvent.click(view.getByRole("button", { name: "Đổi mật khẩu" }));
  expect(await view.findByText("Mật khẩu hiện tại không đúng.")).toBeTruthy();
  expect(sent).toEqual([{ current_password: "old-password-1", new_password: "new-password-12" }]);
});

test("the audit page names events in plain words and asks the server for one kind", async () => {
  const asked: string[] = [];
  const { view } = await mount("AuditPage", (url) => {
    asked.push(url);
    return Response.json({
      kinds: ["plan", "visitor_pass"],
      items: [
        {
          id: "e1",
          created_at: "2026-10-04T16:00:00Z",
          event_type: "visitor_pass.created",
          initiator_kind: "person",
          actor: "Quản trị",
          target_type: "visitor_pass",
          target_id: "pass-1",
          payload: { code: "VP-261004-ABC" },
        },
        {
          id: "e2",
          created_at: "2026-10-04T15:00:00Z",
          event_type: "plan.proposed",
          initiator_kind: "agent",
          actor: "Agent",
          target_type: "ticket_plan",
          target_id: "plan-1",
          payload: { tool: "integration.plans.propose", status: "OK" },
        },
      ],
    });
  });
  expect(
    (await view.findByText("Đăng ký khách")).closest("tr")!.textContent,
  ).toContain("Quản trị");
  expect(view.getByText("Đề xuất phương án").closest("tr")!.textContent).toContain(
    "Agent",
  );
  expect(view.container.textContent).not.toContain("integration.plans.propose");
  await choose(view, "Loại đối tượng", "Khách đến thăm");
  await waitFor(() =>
    expect(asked.at(-1)).toBe(
      "/api/business/admin/audit-events?limit=50&kind=visitor_pass",
    ),
  );
});

test("the audit page takes the trail of a span of days as a file, and says why when the span is too large", async () => {
  const asked: string[] = [];
  let tooMany = true;
  const { view } = await mount("AuditPage", (url) => {
    asked.push(url);
    if (!url.includes("/export"))
      return Response.json({ kinds: ["plan"], items: [] });
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

test("audit events the domain records have readable names and cursor keeps the row id", async () => {
  const { eventLabel } = await import(
    "../src/features/vinhomes-operations/connected/admin/Audit"
  );
  const { filteredAuditOptions } = await import(
    "../src/features/vinhomes-operations/connected/admin/queries"
  );
  const items = Array.from({ length: 50 }, (_, i) => ({
    id: `event-${i}`,
    created_at: "2026-10-06T10:00:00Z",
    event_type: "visitor_pass.created",
    initiator_kind: "person",
    actor: "BQL",
    target_type: "visitor_pass",
    target_id: "pass-1",
    payload: {},
  }));
  expect(eventLabel(items[0])).toBe("Đăng ký khách");
  expect(eventLabel({ ...items[0], event_type: "visitor_pass.rejected" })).toBe("Từ chối khách");
  expect(eventLabel({ ...items[0], event_type: "access_card.reported_lost" })).toBe("Báo mất thẻ");
  // An event nobody has named yet is still read as an update to the kind of thing it was about.
  expect(eventLabel({ ...items[0], event_type: "ticket.something_new" })).toBe("Cập nhật yêu cầu");
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

