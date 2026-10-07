import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import type { FieldActions } from "../src/features/vinhomes-operations/connected/field/FieldJob";
import type { FieldOrder, FieldPhoto, FieldTicket } from "../src/features/vinhomes-operations/connected/field/model";
import { ownOrders, stepOf, tabOf } from "../src/features/vinhomes-operations/connected/field/model";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3022/operations/my-tasks" });
  ({ cleanup, render, fireEvent, waitFor } = await import("@testing-library/react/pure"));
});
afterEach(() => cleanup());
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

// The API also sends the request's code; nothing on these screens may show it.
const ticket = (over: Partial<FieldTicket> = {}): FieldTicket => ({ id: "t1", code: "VH-AAAAAAAAAAAA", title: "Vòi nước bếp bị rò", description: "Rò ở chân vòi.",
  status: "in_progress", priority: "normal", building_id: "b1", updated_at: "2026-10-05T03:00:00Z", ...over } as FieldTicket);
const order = (over: Partial<FieldOrder> = {}): FieldOrder => ({ id: "o1", ticket_id: "t1", status: "accepted", version: 3, description: "", assignment_id: "a1", assignment_status: "accepted", ...over });
const photo = (purpose: string, work_order_id = "o1"): FieldPhoto => ({ id: `${work_order_id}-${purpose}`, name: `${purpose}.png`, purpose, work_order_id, src: `/files/${work_order_id}-${purpose}` });

test("a job moves through four steps, and what was sent in waits for the resident before it is history", () => {
  expect(stepOf("offered")).toBe(0);
  expect(stepOf("en_route")).toBe(1);
  expect(stepOf("awaiting_approval")).toBe(2);
  // Reporting starts once the photos the report needs are there.
  expect(stepOf("in_progress")).toBe(2);
  expect(stepOf("in_progress", true)).toBe(3);
  expect(stepOf("completed")).toBe(4);
  expect(tabOf("offered", "triaging")).toBe("new");
  expect(tabOf("accepted", "assigned")).toBe("new");
  expect(tabOf("en_route", "assigned")).toBe("doing");
  expect(tabOf("arrived", "in_progress")).toBe("doing");
  expect(tabOf("completed", "resolved")).toBe("waiting");
  expect(tabOf("completed", "closed")).toBe("history");
});

test("a rejected or cancelled latest assignment cannot expose another worker's live task or an older offer", () => {
  expect(ownOrders([
    order({ assignment_id: "latest", assignment_status: "rejected" }),
    order({ assignment_id: "old", assignment_status: "offered" }),
    order({ id: "cancelled-live", assignment_status: "cancelled", status: "in_progress" }),
    order({ id: "cancelled-history", assignment_status: "cancelled", status: "cancelled" }),
    order({ id: "current", assignment_status: "accepted" }),
  ]).map((o) => o.id)).toEqual(["cancelled-history", "current"]);
});

test("the work list keeps the active job first while additional assigned work stays in its queue", async () => {
  const { FieldWorkList } = await import("../src/features/vinhomes-operations/connected/field/FieldWorkList");
  let opened = "";
  const view = render(<FieldWorkList buildings={[{ id: "b1", name: "Sapphire 1 - S1.01" }]} onOpen={(id) => { opened = id; }}
    tickets={[ticket(), ticket({ id: "t2", title: "Đèn hành lang hỏng", unit_code: "1201" }), ticket({ id: "t3", title: "Thay vòi sen", status: "closed" })]}
    orders={[order({ status: "in_progress" }), order({ id: "o2", ticket_id: "t2", status: "queued", assignment_status: "offered" }),
      order({ id: "o3", ticket_id: "t3", status: "completed", assignment_status: "completed" })]} />);
  expect(view.getByRole("tab", { name: /Đang làm/ }).getAttribute("aria-selected")).toBe("true");
  expect(view.getByText("Vòi nước bếp bị rò")).toBeTruthy();
  expect(view.queryByText("Đèn hành lang hỏng")).toBeNull();
  fireEvent.click(view.getByRole("tab", { name: /Hàng đợi/ }));
  expect(view.getByText("Đèn hành lang hỏng")).toBeTruthy();
  expect(view.getByText("Sapphire 1 - S1.01 · Căn 1201")).toBeTruthy();
  expect(view.queryByText("Vòi nước bếp bị rò")).toBeNull();
  fireEvent.click(view.getByRole("tab", { name: /Đang làm/ }));
  fireEvent.click(view.getByRole("button", { name: /Vòi nước bếp bị rò/ }));
  expect(opened).toBe("t1");
  fireEvent.click(view.getByRole("tab", { name: /Lịch sử/ }));
  expect(view.getByText("Cư dân đã xác nhận hoàn tất")).toBeTruthy();
  fireEvent.click(view.getByRole("tab", { name: "Chờ xác nhận" }));
  expect(view.getByText("Không có việc chờ xác nhận")).toBeTruthy();
  expect(view.container.textContent).not.toContain("VH-");
});

test("a job is one step at a time: accept with a time or refuse with a reason, and the result goes only with photos before and after", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const calls: unknown[][] = [];
  const actions: FieldActions = { accept: (o, minutes) => calls.push(["accept", o.id, minutes]), reject: (o, reason) => calls.push(["reject", o.id, reason]),
    advance: (o, status, note) => calls.push(["advance", o.id, status, note]), quote: () => undefined, consent: () => undefined,
    photo: (o, file, phase) => calls.push(["photo", o.id, file.name, phase]) };
  const job = (work: FieldOrder, photos: FieldPhoto[] = []) => render(<FieldJob ticket={ticket()} place="Sapphire 1 - S1.01" orders={[work]} photos={photos}
    conversation={[]} busy={false} request={async () => ({ approvals: [] }) as never} actions={actions} onBack={() => undefined} />);
  const current = (view: ReturnType<typeof job>) => view.container.querySelector('[aria-current="step"]')?.textContent;

  let view = job(order({ status: "queued", assignment_status: "offered" }));
  expect(current(view)).toContain("Nhận việc");
  fireEvent.click(view.getByRole("button", { name: "1 giờ" }));
  fireEvent.click(view.getByRole("button", { name: "Nhận việc" }));
  fireEvent.click(view.getByRole("button", { name: "Từ chối việc này" }));
  expect((view.getByRole("button", { name: "Xác nhận từ chối" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(view.getByLabelText("Đã hết ca"));
  fireEvent.click(view.getByRole("button", { name: "Xác nhận từ chối" }));
  expect(calls).toEqual([["accept", "o1", 60], ["reject", "o1", "Đã hết ca"]]);
  expect(view.container.textContent).not.toContain("VH-");
  cleanup();

  calls.length = 0;
  view = job(order({ status: "in_progress" }), [photo("before")]);
  expect(current(view)).toContain("Thực hiện");
  expect((view.getByRole("button", { name: "Gửi kết quả" }) as HTMLButtonElement).disabled).toBe(true);
  expect(view.getByRole("status").textContent).toContain("1 ảnh trước và 1 ảnh sau");
  fireEvent.change(view.getByLabelText("Thêm ảnh sau khi xử lý"), { target: { files: [new File(["x"], "sau.png", { type: "image/png" })] } });
  expect(calls).toEqual([["photo", "o1", "sau.png", "after"]]);
  cleanup();

  view = job(order({ status: "in_progress" }), [photo("before"), photo("after")]);
  expect(current(view)).toContain("Báo cáo");
  fireEvent.click(view.getByRole("button", { name: "Gửi kết quả" }));
  expect(calls.at(-1)).toEqual(["advance", "o1", "completed", ""]);
});

test("cancelled work on a closed request is history without claiming resident acceptance", async () => {
  const { FieldWorkList } = await import("../src/features/vinhomes-operations/connected/field/FieldWorkList");
  const view = render(<FieldWorkList tickets={[ticket({ status: "closed" })]} buildings={[]} history orders={[
    order({ status: "cancelled", assignment_status: "cancelled" }),
    order({ id: "o2", status: "completed" }),
  ]} onOpen={() => undefined} />);
  expect(view.getByText("Đã hủy")).toBeTruthy();
  expect(view.getAllByText("Cư dân đã xác nhận hoàn tất")).toHaveLength(1);
});

test("two orders on the same request remain independently visible in active work and queue", async () => {
  const { FieldWorkList } = await import("../src/features/vinhomes-operations/connected/field/FieldWorkList");
  const opened: string[][] = [];
  const view = render(<FieldWorkList tickets={[ticket()]} buildings={[]} orders={[
    order({ status: "in_progress", description: "Xử lý vòi nước" }),
    order({ id: "o2", status: "accepted", description: "Kiểm tra ống thoát nước" }),
  ]} onOpen={(ticketId, orderId) => opened.push([ticketId, orderId])} />);
  expect(view.getByText("Xử lý vòi nước")).toBeTruthy();
  fireEvent.click(view.getByRole("tab", { name: /Hàng đợi/ }));
  expect(view.queryByText("Xử lý vòi nước")).toBeNull();
  fireEvent.click(view.getByRole("button", { name: /Kiểm tra ống thoát nước/ }));
  expect(opened).toEqual([["t1", "o2"]]);
});

test("a queued offer can be accepted but its execution waits until the current job is finished", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const calls: string[] = [];
  const actions: FieldActions = { accept: () => calls.push("accepted"), reject: () => undefined, advance: () => calls.push("started"), quote: () => undefined, consent: () => undefined, photo: () => undefined };
  const props = { ticket: ticket(), place: "S1.01", photos: [], conversation: [], busy: false, request: async () => ({ approvals: [] }) as never,
    actions, onBack: () => undefined, currentWork: { orderId: "active-order", title: "Đang sửa đèn", onOpen: () => calls.push("continue") } };
  const view = render(<FieldJob {...props} orders={[order({ status: "queued", assignment_status: "offered" })]} />);
  fireEvent.click(view.getByRole("button", { name: "Nhận việc" }));
  expect(calls).toEqual(["accepted"]);
  view.rerender(<FieldJob {...props} orders={[order()]} />);
  expect((view.getByRole("button", { name: "Bắt đầu di chuyển" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(view.getByRole("button", { name: "Tiếp tục việc đang làm" }));
  expect(calls).toEqual(["accepted", "continue"]);
  view.rerender(<FieldJob {...props} currentWork={undefined} orders={[order()]} />);
  fireEvent.click(view.getByRole("button", { name: "Bắt đầu di chuyển" }));
  expect(calls).toEqual(["accepted", "continue", "started"]);
});

test("completion only uses evidence from this work order, including on a mixed-specialty ticket", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const actions: FieldActions = { accept: () => undefined, reject: () => undefined, advance: () => undefined, quote: () => undefined, consent: () => undefined, photo: () => undefined };
  const props = { ticket: ticket(), place: "S1.01", orders: [order({ status: "in_progress" })], conversation: [], busy: false,
    request: async () => ({ approvals: [] }) as never, actions, onBack: () => undefined };
  const view = render(<FieldJob {...props} photos={[photo("before", "other-worker"), photo("after", "other-worker")]} />);
  expect((view.getByRole("button", { name: "Gửi kết quả" }) as HTMLButtonElement).disabled).toBe(true);
  expect(view.queryByRole("img")).toBeNull();
  view.rerender(<FieldJob {...props} photos={[photo("before"), photo("after")]} />);
  expect((view.getByRole("button", { name: "Gửi kết quả" }) as HTMLButtonElement).disabled).toBe(false);
});

test("an approved Supervisor plan starts at the site without asking for the same quote again", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const calls: string[] = [];
  const actions: FieldActions = { accept: () => undefined, reject: () => undefined, advance: (_, status) => calls.push(status), quote: () => undefined, consent: () => undefined, photo: () => undefined };
  const view = render(<FieldJob ticket={ticket({ title: "Vệ sinh hành lang" })} place="S1.01" orders={[order({ status: "arrived" })]} photos={[]} conversation={[]}
    busy={false} request={async () => ({ approvals: [] }) as never} actions={actions} onBack={() => undefined}
    plan={{ title: "Dọn hành lang", proposal: { steps: ["Làm sạch sàn"], expected_duration: "30 phút", conditions: "Đặt biển cảnh báo" } }} />);
  expect(view.queryByText("Vật tư và chi phí")).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Bắt đầu xử lý" }));
  expect(calls).toEqual(["in_progress"]);
});

test("a planned task can quote new onsite costs and revise a rejected quote before starting", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const calls: unknown[][] = [];
  const actions: FieldActions = { accept: () => undefined, reject: () => undefined, advance: (_, status) => calls.push(["advance", status]),
    quote: (_, note, quote) => calls.push(["quote", note, quote.labor_cost]), consent: () => undefined, photo: () => undefined };
  const props = { ticket: ticket(), place: "S1.01", photos: [], conversation: [], busy: false, request: async () => ({ approvals: [] }) as never, actions, onBack: () => undefined,
    plan: { title: "Thay vòi", proposal: { steps: ["Kiểm tra và thay vòi"], expected_duration: "30 phút", conditions: "Cư dân có nhà" } } };
  const view = render(<FieldJob {...props} orders={[order({ status: "arrived" })]} />);
  expect(view.queryByText("Vật tư và chi phí")).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Có phát sinh, lập phương án mới" }));
  expect((view.getByRole("button", { name: "Bắt đầu xử lý" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(view.getByLabelText("Hiện trạng và cách xử lý"), { target: { value: "Cần thay thêm dây cấp nước." } });
  fireEvent.change(view.getByLabelText("Tiền công (đ)"), { target: { value: "50000" } });
  fireEvent.click(view.getByRole("button", { name: "Gửi phương án cho cư dân" }));
  expect(calls).toEqual([["quote", "Cần thay thêm dây cấp nước.", 50000]]);
  cleanup();

  const revision = render(<FieldJob {...props} orders={[order({ status: "arrived", repair_approval_status: "rejected" })]} />);
  expect(revision.getByText("Vật tư và chi phí")).toBeTruthy();
  expect((revision.getByRole("button", { name: "Bắt đầu xử lý" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(revision.getByLabelText("Hiện trạng và cách xử lý"), { target: { value: "Điều chỉnh phương án theo ý cư dân." } });
  fireEvent.click(revision.getByRole("button", { name: "Gửi phương án cho cư dân" }));
  expect(calls.at(-1)).toEqual(["quote", "Điều chỉnh phương án theo ý cư dân.", 0]);
  revision.rerender(<FieldJob {...props} orders={[order({ status: "arrived", repair_approval_status: "approved" })]} />);
  expect((revision.getByRole("button", { name: "Bắt đầu xử lý" }) as HTMLButtonElement).disabled).toBe(false);
});

test("a pending repair quote blocks work and an approved latest quote unlocks it", async () => {
  const { FieldJob } = await import("../src/features/vinhomes-operations/connected/field/FieldJob");
  const actions: FieldActions = { accept: () => undefined, reject: () => undefined, advance: () => undefined, quote: () => undefined, consent: () => undefined, photo: () => undefined };
  const props = { ticket: ticket(), place: "S1.01", orders: [order({ status: "awaiting_approval" })], photos: [], conversation: [], busy: false, actions, onBack: () => undefined };
  const pending = async () => ({ approvals: [{ kind: "customer_repair", status: "pending", created_at: "2026-10-07T10:00:00Z", request_detail: { note: "Thay vòi", total: 100000 } }] }) as never;
  const approved = async () => ({ approvals: [{ kind: "customer_repair", status: "approved", created_at: "2026-10-07T10:00:00Z", request_detail: { note: "Thay vòi", total: 100000 } }] }) as never;
  const view = render(<FieldJob {...props} request={pending} />);
  await waitFor(() => expect(view.getByRole("button", { name: "Cư dân đồng ý tại chỗ" })).toBeTruthy());
  expect((view.getByRole("button", { name: "Bắt đầu xử lý" }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<FieldJob {...props} request={approved} />);
  await waitFor(() => expect((view.getByRole("button", { name: "Bắt đầu xử lý" }) as HTMLButtonElement).disabled).toBe(false));
  expect(view.queryByRole("button", { name: "Cư dân đồng ý tại chỗ" })).toBeNull();
});

test("repair quote read failures retain a retry path and cannot unlock work", async () => {
  const { OnsiteConsent } = await import("../src/features/vinhomes-operations/connected/RepairQuote");
  let fail = true;
  const decisions: boolean[] = [];
  const request = async () => { if (fail) throw new Error("Mất kết nối"); return { approvals: [{ kind: "customer_repair", status: "pending", request_detail: { note: "Thay vòi" } }] } as never; };
  const view = render(<OnsiteConsent orderId="o1" disabled={false} request={request} onDecide={() => undefined} onApprovedChange={(value) => decisions.push(value)} />);
  await waitFor(() => expect(view.getByRole("alert").textContent).toContain("Mất kết nối"));
  expect(view.queryByRole("button", { name: "Cư dân đồng ý tại chỗ" })).toBeNull();
  expect(decisions).toEqual([false]);
  fail = false;
  fireEvent.click(view.getByRole("button", { name: "Thử lại tải phương án" }));
  await waitFor(() => expect(view.getByRole("button", { name: "Cư dân đồng ý tại chỗ" })).toBeTruthy());
  expect(view.queryByRole("alert")).toBeNull();
});
