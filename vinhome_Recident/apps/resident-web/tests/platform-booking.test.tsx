import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { bookingOf, type Message } from "../src/services/resident-api";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3011/#/chat" });
  ({ cleanup, render, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => cleanup());
afterAll(() => GlobalRegistrator.unregister());

const now = Date.parse("2026-10-12T03:00:00Z");
const body = (over: Partial<NonNullable<Message["body"]["platform"]>> = {}): Message["body"] => ({
  text: "Đặt Sân tennis (main).",
  platform: {
    kind: "booking", card_id: "cr_1", amenity: "Sân tennis", area: "main", start_at: "2026-10-14T10:00:00+07:00",
    end_at: "2026-10-14T11:00:00+07:00", guests: 2, total: 120000, expires_at: "2026-10-12T03:15:00Z", status: "pending", ...over,
  },
});
const card = async (over: Parameters<typeof body>[0] = {}, booked = new Set<string>()) => {
  const { BookingCard } = await import("../src/features/assistant/PlatformCards");
  const calls: unknown[][] = [];
  const view = render(<BookingCard booking={bookingOf(body(over), booked, now)!} onConfirm={(...args) => calls.push(args)} />);
  return { view, calls };
};

test("a booking card can be confirmed while it is pending and in time; other cards are not bookings", () => {
  expect(bookingOf(body(), new Set(), now)?.status).toBe("pending");
  expect(bookingOf(body({ expires_at: "2026-10-12T02:59:00Z" }), new Set(), now)?.status).toBe("expired");
  expect(bookingOf(body({ status: "booked", booking_status: "pending_payment", expires_at: "2026-10-12T02:59:00Z" }), new Set(), now))
    .toMatchObject({ status: "booked", bookingStatus: "pending_payment" });
  expect(bookingOf(body(), new Set(["cr_1"]), now)?.status).toBe("booked");
  expect(bookingOf(body({ kind: "quote" }), new Set(), now)).toBeUndefined();
  expect(bookingOf({ text: "Xin chào" }, new Set(), now)).toBeUndefined();
});

test("the card shows what is booked and its fee, and only the resident's tap asks for the booking", async () => {
  const { view, calls } = await card();
  expect(view.getByText("Đặt Sân tennis")).toBeTruthy();
  expect(view.getByText(/10:00 đến 11:00/)).toBeTruthy();
  expect(view.getByText("120.000đ")).toBeTruthy();
  expect(calls).toEqual([]);
  fireEvent.click(view.getByRole("button", { name: "Xác nhận đặt chỗ" }));
  expect(calls).toEqual([["cr_1"]]);
});

test("a free booking says so; a booked or an expired card has no button", async () => {
  expect((await card({ total: 0 })).view.getByText("Miễn phí")).toBeTruthy();
  cleanup();
  const paid = await card({ status: "booked", booking_status: "pending_payment" });
  expect(paid.view.queryByRole("button")).toBeNull();
  expect(paid.view.getByRole("status").textContent).toContain("thanh toán");
  cleanup();
  const done = await card({ status: "booked", booking_status: "confirmed" });
  expect(done.view.getByRole("status").textContent).toBe("Bạn đã đặt chỗ.");
  cleanup();
  const late = await card({ status: "expired" });
  expect(late.view.queryByRole("button")).toBeNull();
  expect(late.view.getByRole("status").textContent).toContain("hết hạn");
});
