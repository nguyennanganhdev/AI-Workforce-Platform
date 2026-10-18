import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { quoteOf, type Message } from "../src/services/resident-api";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3011/#/chat" });
  ({ cleanup, render, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => cleanup());
afterAll(() => GlobalRegistrator.unregister());

const now = Date.parse("2026-10-11T03:00:00Z");
const body = (over: Partial<NonNullable<Message["body"]["platform"]>> = {}): Message["body"] => ({
  text: "Kỹ thuật viên đã gửi báo giá.",
  platform: {
    kind: "quote", approval_id: "wa-1", status: "pending", expires_at: null,
    lines: [{ name: "Vòi nước", quantity: "2", unit: "cái", amount: 1500000 }], labor_cost: 250000, warranty_months: 6, total: 1750000, ...over,
  },
});
const card = async (over: Parameters<typeof body>[0] = {}) => {
  const { QuoteCard } = await import("../src/features/assistant/PlatformCards");
  const calls: unknown[][] = [];
  const view = render(<QuoteCard quote={quoteOf(body(over), now)!} onDecide={(...args) => calls.push(args)} />);
  return { view, calls };
};

test("a quote is answered while it is pending and in time; the other approval card is not a quote", () => {
  expect(quoteOf(body(), now)).toEqual({ id: "wa-1", lines: [{ name: "Vòi nước", quantity: "2", unit: "cái", amount: 1500000 }],
    laborCost: 250000, warrantyMonths: 6, total: 1750000, status: "pending" });
  expect(quoteOf(body({ expires_at: "2026-10-11T03:10:00Z" }), now)?.status).toBe("pending");
  expect(quoteOf(body({ expires_at: "2026-10-11T02:59:00Z" }), now)?.status).toBe("expired");
  expect(quoteOf(body({ status: "approved", expires_at: "2026-10-11T02:59:00Z" }), now)?.status).toBe("approved");
  expect(quoteOf(body({ kind: "approval" }), now)).toBeUndefined();
  expect(quoteOf({ text: "Xin chào" }, now)).toBeUndefined();
});

test("a pending quote reads as a bill, and agreeing sends the resident's own answer for that quote", async () => {
  const { view, calls } = await card();
  expect(view.getByRole("region", { name: "Báo giá sửa chữa" })).toBeTruthy();
  const rows = [...view.container.querySelectorAll("li")].map((li) => [...li.children].map((c) => c.textContent?.replace(/\s+/g, " ").trim()));
  expect(rows).toEqual([["Vòi nước × 2 cái", "1.500.000đ"], ["Tiền công", "250.000đ"], ["Tổng cộng", "1.750.000đ"]]);
  expect(view.container.querySelector("li:last-child strong")).toBeTruthy();
  expect(view.getByText("Bảo hành 6 tháng")).toBeTruthy();
  fireEvent.click(view.getByRole("button", { name: "Đồng ý báo giá" }));
  expect(calls).toEqual([["wa-1", true, undefined]]);
  // Nothing internal reaches the resident.
  expect(view.container.textContent).not.toContain("wa-1");
});

test("refusing a quote needs a reason of at least 8 characters", async () => {
  const { view, calls } = await card({ warranty_months: 0 });
  expect(view.queryByText(/Bảo hành/)).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Không đồng ý" }));
  const send = view.getByRole("button", { name: "Gửi" }) as HTMLButtonElement;
  fireEvent.change(view.getByLabelText("Vì sao bạn không đồng ý?"), { target: { value: " đắt " } });
  expect(send.disabled).toBe(true);
  fireEvent.submit(send.form!);
  expect(calls).toEqual([]);
  fireEvent.change(view.getByLabelText("Vì sao bạn không đồng ý?"), { target: { value: " Giá vòi nước cao quá. " } });
  expect(send.disabled).toBe(false);
  fireEvent.submit(send.form!);
  expect(calls).toEqual([["wa-1", false, "Giá vòi nước cao quá."]]);
});

test("an answered or expired quote only says what happened: no buttons", async () => {
  for (const [over, said] of [
    [{ status: "approved" }, "Bạn đã đồng ý báo giá"],
    [{ status: "rejected" }, "Bạn không đồng ý báo giá"],
    [{ status: "expired" }, "Báo giá đã hết hạn"],
    [{ expires_at: "2026-10-11T02:59:00Z" }, "Báo giá đã hết hạn"],
  ] as const) {
    const { view } = await card(over);
    expect(view.getByRole("status").textContent).toBe(said);
    expect(view.queryAllByRole("button")).toHaveLength(0);
    expect(view.getByText("Tổng cộng")).toBeTruthy();
    cleanup();
  }
});
