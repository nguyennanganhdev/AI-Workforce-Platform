import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3023/operations/my-tasks" });
  ({ cleanup, render } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

test("someone on site gets their own frame: who they are, the work newly offered, a way out, and nothing of management's", async () => {
  const { FieldShell } = await import("../src/features/vinhomes-operations/layout/field-shell");
  const view = render(
    <FieldShell name="Kỹ thuật viên Sapphire" notices={[{ id: "job-1", title: "Vòi nước bếp bị rò", note: "Việc mới chờ bạn nhận", to: "/operations/my-tasks?ticket=t1" }]}>
      <p>Việc của tôi</p>
    </FieldShell>,
  );
  expect(view.getByText("Kỹ thuật viên Sapphire")).toBeTruthy();
  expect(view.getByText("Vòi nước bếp bị rò").closest("a")?.getAttribute("href")).toBe("/operations/my-tasks?ticket=t1");
  expect(view.getByRole("button", { name: "Đăng xuất" })).toBeTruthy();
  for (const absent of ["Kết nối cá nhân", "Quản lý vận hành", "Điều phối", "Agent", "Tài khoản"]) expect(view.queryByText(absent)).toBeNull();
  expect(view.container.querySelector("aside")).toBeNull();
});

test("someone on site filters their work by progress only; management also by department", async () => {
  const { WorkListView } = await import("../src/features/vinhomes-operations/workspace/WorkPage");
  const rows = [{ key: "t1", ticket: "t1", ticketId: "", title: "Vòi nước bếp bị rò", place: "S1.01", severity: "P2" as const, department: "Kỹ thuật",
    assignee: "", status: "Đang xử lý", updatedAt: "2026-10-05T03:00:00Z", phase: "active" as const }];
  const list = (manager: boolean, history = false) => render(
    <WorkListView rows={rows} manager={manager} history={history} onHistory={() => undefined} onOpen={() => undefined}
      connectedAccount={{ role: manager ? "manager" : "staff", scope: "được cấp trên hệ thống" }} />);
  const staff = list(false);
  expect(staff.getByText("Lọc theo tiến độ")).toBeTruthy();
  expect(staff.queryByText("Bộ phận")).toBeNull();
  expect(staff.getByPlaceholderText("Nội dung hoặc vị trí")).toBeTruthy();
  cleanup();
  // Finished work has no progress to filter by, so the filter is not offered at all.
  expect(list(false, true).queryByText("Lọc theo tiến độ")).toBeNull();
  cleanup();
  const manager = list(true);
  expect(manager.getByText("Bộ lọc bộ phận và tiến độ")).toBeTruthy();
  expect(manager.getByText("Bộ phận")).toBeTruthy();
});

test("an account that signs in at the other staff address is told so, and its sign-in here is ended", async () => {
  const { staffAuthService } = await import("../src/features/vinhomes-operations/auth/auth-service");
  const called: string[] = [];
  globalThis.fetch = (async (url: RequestInfo | URL) => {
    called.push(String(url));
    if (String(url).endsWith("/operations/me"))
      return Response.json({ detail: { code: "WRONG_DOOR", message: "Địa chỉ này dành cho nhân viên hiện trường." } }, { status: 403 });
    return Response.json({ ok: true });
  }) as typeof fetch;
  await expect(staffAuthService.signIn({ identifier: "bql@example.test", password: "testpassword" })).rejects.toThrow("dành cho nhân viên hiện trường");
  expect(called.at(-1)).toBe("/api/business/auth/logout");
});
