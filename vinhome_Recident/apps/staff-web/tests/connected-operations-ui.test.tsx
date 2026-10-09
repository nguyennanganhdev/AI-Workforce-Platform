import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";
let cleanup: typeof import('@testing-library/react')['cleanup'];
let fireEvent: typeof import('@testing-library/react')['fireEvent'];
let render: typeof import('@testing-library/react')['render'];
let waitFor: typeof import('@testing-library/react')['waitFor'];
let WorkListView: typeof import('../src/features/vinhomes-operations/workspace/WorkPage')['WorkListView'];
let LiveReportsPage: typeof import('../src/features/vinhomes-operations/workspace/LiveReportsPage')['LiveReportsPage'];

const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/kanban" });
  ({cleanup, fireEvent, render, waitFor} = await import('@testing-library/react/pure'));
  ({WorkListView} = await import('../src/features/vinhomes-operations/workspace/WorkPage'));
  ({LiveReportsPage} = await import('../src/features/vinhomes-operations/workspace/LiveReportsPage'));
});
afterEach(() => {cleanup(); globalThis.fetch = originalFetch; localStorage.clear();});
afterAll(async () => {await new Promise(done=>setTimeout(done,50));GlobalRegistrator.unregister();});

test("original work list renders server rows without needing the preview provider", async () => {
  localStorage.setItem("vinhomes.frontend-workspace.v1", "invalid-preview-data");
  let opened = "";
  const page = render(<WorkListView manager history={false} onHistory={() => {}} connectedAccount={{role: "manager", scope: "assigned"}}
    rows={[{key: "server-ticket", ticket: "server-ticket", ticketId: "T-42", title: "Server repair", severity: "P2", place: "Tower A", department: "Electric", assignee: "", phase: "active", status: "Đang xử lý", updatedAt: "2026-10-01"}]}
    onOpen={row => {opened = row.ticket!;}} />);
  fireEvent.click(page.getByRole("button", {name: /Server repair/}));
  expect(opened).toBe("server-ticket");
  expect(page.queryByText(/Dữ liệu và hành động mô phỏng/)).toBeNull();
  await typeInto(page.getByPlaceholderText("Nội dung, mã ticket, vị trí, nhân viên"), "not found");
  expect(page.queryByRole("button", {name: /Server repair/}) === null).toBe(true);
});

test("original report form requests persisted report data with an inclusive final day", async () => {
  let requested = "";
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    requested = String(input);
    return Response.json({items: [{month: "2026-10-01", incident_type: "Electrical", incident_count: 3}]});
  }) as typeof fetch;
  const page = render(<LiveReportsPage buildings={[{id: "building-real", name: "Tower A"}]} categories={[]} />);
  const {selectOption} = await import('./type-into');
  await selectOption(page.getByRole('combobox',{name:'Tòa nhà'}),'Tower A');
  await typeInto(page.getByLabelText("Từ ngày"), "2026-10-01");
  await typeInto(page.getByLabelText("Đến ngày"), "2026-10-02");
  fireEvent.click(page.getByRole("button", {name: "Xem báo cáo"}));
  await waitFor(() => expect(page.getByText("Electrical")).toBeTruthy());
  const url = new URL(requested, "http://localhost");
  expect(url.pathname).toBe("/api/business/reports/incident-frequency");
  expect(url.searchParams.get("buildingId")).toBe("building-real");
  expect(url.searchParams.get("toDate")).toBe("2026-10-03");
  expect(page.queryByText("Hoàn tất bản mẫu")).toBeNull();
});

test("original resident registration submits real contract and shows pending without preview controls", async () => {
  const {AuthPage} = await import('../../resident-web/src/features/auth/AuthPage');
  let payload: Record<string, string> = {};
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    payload = JSON.parse(String(init?.body));
    return Response.json({nextStep: 'membership-pending'}, {status: 201});
  }) as typeof fetch;
  const page = render(<AuthPage mode="register" />);
  expect(page.container.querySelector('a[href="http://localhost:3010/sign"]') === null).toBe(true);
  expect(page.container.textContent?.includes('M? ?ng d?ng')).toBe(false);
  expect(page.container.querySelector('.resident-auth-story') !== null).toBe(true);
  expect(page.queryByText(/Khám phá bản trải nghiệm/) === null).toBe(true);
  await typeInto(page.getByLabelText('Họ và tên'), 'Resident Name');
  await typeInto(page.getByLabelText('Email'), 'resident@example.test');
  await typeInto(page.getByLabelText('Mật khẩu', {exact: true}), 'secure-password-123');
  await typeInto(page.getByLabelText('Nhập lại mật khẩu', {exact: true}), 'secure-password-123');
  fireEvent.submit(page.container.querySelector('form')!);
  await waitFor(() => expect(page.queryByText('Chờ liên kết căn hộ') !== null).toBe(true));
  expect(payload.email).toBe('resident@example.test');
  expect(payload.name).toBe('Resident Name');
  expect('role' in payload).toBe(false);
});

test("original staff login shows backend permission denial without reading preview workspace", async () => {
  const {StaffLoginPage} = await import('../src/features/vinhomes-operations/auth/StaffLoginPage');
  localStorage.setItem('vinhomes.frontend-workspace.v1', 'corrupt');
  globalThis.fetch = (async (url: RequestInfo | URL) => String(url).endsWith('/login') ? Response.json({user: {id: 'resident'}}) : Response.json({detail: 'Forbidden'}, {status: 403})) as typeof fetch;
  const page = render(<StaffLoginPage />);
  expect(page.container.querySelector('.staff-auth-brand') !== null).toBe(true);
  expect(page.queryByText(/Xem bản trải nghiệm/) === null).toBe(true);
  await typeInto(page.getByLabelText('Tài khoản được cấp'), 'resident@example.test');
  await typeInto(page.getByLabelText('Mật khẩu', {exact: true}), 'secure-password-123');
  fireEvent.submit(page.container.querySelector('form')!);
  await waitFor(() => expect(page.queryByText(/Tài khoản chưa được cấp quyền nhân viên/) !== null).toBe(true));
});

test("all original resident auth screens omit retired platform links and unavailable reset submission", async () => {
  const {AuthPage} = await import('../../resident-web/src/features/auth/AuthPage');
  for (const mode of ['login', 'register', 'forgot-password'] as const) {
    const page = render(<AuthPage mode={mode} />);
    expect(page.container.querySelector('.resident-auth-hero') !== null).toBe(true);
    expect(page.container.querySelector('a[href*="3010"]') === null).toBe(true);
    expect(page.container.textContent?.includes('M? ?ng d?ng')).toBe(false);
    if (mode === 'forgot-password') {
      expect(page.container.querySelector('form') === null).toBe(true);
      expect(page.queryByText(/Hệ thống chưa hỗ trợ gửi mã khôi phục/) !== null).toBe(true);
    }
    cleanup();
  }
});
