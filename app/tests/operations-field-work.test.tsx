import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import type { FieldActions } from "../src/features/vinhomes-operations/connected/field/FieldJob";
import type { FieldOrder, FieldPhoto, FieldTicket } from "../src/features/vinhomes-operations/connected/field/model";
import { stepOf, tabOf } from "../src/features/vinhomes-operations/connected/field/model";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3023/operations/my-tasks" });
  ({ cleanup, render, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => cleanup());
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

// The API also sends the request's code; nothing on these screens may show it.
const ticket = (over: Partial<FieldTicket> = {}): FieldTicket => ({ id: "t1", code: "VH-AAAAAAAAAAAA", title: "Vòi nước bếp bị rò", description: "Rò ở chân vòi.",
  status: "in_progress", priority: "normal", building_id: "b1", updated_at: "2026-10-05T03:00:00Z", ...over } as FieldTicket);
const order = (over: Partial<FieldOrder> = {}): FieldOrder => ({ id: "o1", ticket_id: "t1", status: "accepted", version: 3, description: "", assignment_id: "a1", assignment_status: "accepted", ...over });
const photo = (purpose: string): FieldPhoto => ({ id: purpose, name: `${purpose}.png`, purpose, src: `/files/${purpose}` });

test("a job moves through four steps, and what was sent in waits for the resident before it is history", () => {
  expect(stepOf("offered")).toBe(0);
  expect(stepOf("en_route")).toBe(1);
  expect(stepOf("awaiting_approval")).toBe(2);
  // Reporting starts once the photos the report needs are there.
  expect(stepOf("in_progress")).toBe(2);
  expect(stepOf("in_progress", true)).toBe(3);
  expect(stepOf("completed")).toBe(4);
  expect(tabOf("offered", "triaging")).toBe("new");
  expect(tabOf("arrived", "in_progress")).toBe("doing");
  expect(tabOf("completed", "resolved")).toBe("waiting");
  expect(tabOf("completed", "closed")).toBe("history");
});

test("the work list opens on what was newly offered, says where to go, and never shows a request code", async () => {
  const { FieldWorkList } = await import("../src/features/vinhomes-operations/connected/field/FieldWorkList");
  let opened = "";
  const view = render(<FieldWorkList buildings={[{ id: "b1", name: "Sapphire 1 - S1.01" }]} onOpen={(id) => { opened = id; }}
    tickets={[ticket(), ticket({ id: "t2", title: "Đèn hành lang hỏng", unit_code: "1201" }), ticket({ id: "t3", title: "Thay vòi sen", status: "closed" })]}
    orders={[order({ status: "in_progress" }), order({ id: "o2", ticket_id: "t2", status: "queued", assignment_status: "offered" }),
      order({ id: "o3", ticket_id: "t3", status: "completed", assignment_status: "completed" })]} />);
  expect(view.getByRole("tab", { name: /Mới giao/ }).getAttribute("aria-selected")).toBe("true");
  expect(view.getByText("Đèn hành lang hỏng")).toBeTruthy();
  expect(view.getByText("Sapphire 1 - S1.01 · Căn 1201")).toBeTruthy();
  expect(view.queryByText("Vòi nước bếp bị rò")).toBeNull();
  fireEvent.click(view.getByRole("tab", { name: /Đang làm/ }));
  fireEvent.click(view.getByRole("button", { name: /Vòi nước bếp bị rò/ }));
  expect(opened).toBe("t1");
  fireEvent.click(view.getByRole("tab", { name: "Lịch sử" }));
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
  fireEvent.change(view.getByLabelText("Thêm ảnh sau khi sửa"), { target: { files: [new File(["x"], "sau.png", { type: "image/png" })] } });
  expect(calls).toEqual([["photo", "o1", "sau.png", "after"]]);
  cleanup();

  view = job(order({ status: "in_progress" }), [photo("before"), photo("after")]);
  expect(current(view)).toContain("Báo cáo");
  fireEvent.click(view.getByRole("button", { name: "Gửi kết quả" }));
  expect(calls.at(-1)).toEqual(["advance", "o1", "completed", ""]);
});
