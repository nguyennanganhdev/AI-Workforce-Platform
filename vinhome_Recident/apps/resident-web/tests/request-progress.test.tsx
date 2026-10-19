import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import type { ResidentRequest } from "../src/services/types";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3011/#/chat" });
  ({ cleanup, render } = await import("@testing-library/react/pure"));
});
afterEach(() => cleanup());
afterAll(() => GlobalRegistrator.unregister());

const request = (status: ResidentRequest["status"]): ResidentRequest => ({
  id: "r1", title: "Vòi bếp bị rò nước", description: "", location: "", status, createdAt: "2026-10-18T02:00:00Z", photos: [],
  events: [{ label: "Nhân viên đã nhận việc", at: "2026-10-18T03:15:00Z", note: "Trần Bình" }],
});

const progress = async (status: ResidentRequest["status"], extra: { working?: boolean; needsYou?: string } = {}) => {
  const { RequestProgress } = await import("../src/features/assistant/RequestProgress");
  return render(<RequestProgress request={request(status)} {...extra} />);
};

test("the step the request is at is the current one, the earlier ones are done", async () => {
  const view = await progress("processing");
  const steps = [...view.container.querySelectorAll(".request-steps li")];
  expect(steps.map((li) => li.className)).toEqual(["done", "done", "current", "", ""]);
  expect(view.container.querySelector('[aria-current="step"]')?.textContent).toContain("Đang xử lý");
  expect(view.getByText("Nhân viên đã nhận việc")).toBeTruthy();
});

test("what waits for the resident wins over the live note; a finished request has every step done", async () => {
  const waiting = await progress("confirmation", { working: true, needsYou: "xác nhận kết quả sửa chữa" });
  expect(waiting.getByRole("status").textContent).toContain("Cần bạn: xác nhận kết quả sửa chữa");
  cleanup();
  const live = await progress("received", { working: true });
  expect(live.getByRole("status").textContent).toContain("Ban quản lý đang xử lý");
  cleanup();
  const done = await progress("completed");
  expect([...done.container.querySelectorAll(".request-steps li")].every((li) => li.className === "done")).toBe(true);
  expect(done.queryByRole("status")).toBeNull();
});

test("a cancelled request shows no steps", async () => {
  const view = await progress("cancelled");
  expect(view.container.querySelector(".request-steps")).toBeNull();
  expect(view.getByText(/Yêu cầu đã hủy/)).toBeTruthy();
});
