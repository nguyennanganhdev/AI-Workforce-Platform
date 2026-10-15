import { expect, test } from "vitest";
import { approvalOf, type Message } from "../src/services/resident-api";

const now = Date.parse("2026-10-11T03:00:00Z");
const body = (over: Partial<NonNullable<Message["body"]["platform"]>> = {}): Message["body"] => ({
  text: "Trợ lý cần bạn đồng ý.",
  platform: { kind: "approval", approval_id: "ap-1", summary: { text: "Đồng ý báo giá thay vòi nước?" }, expires_at: "2026-10-11T03:10:00Z", status: "pending", ...over },
});

test("an approval is answered while it is pending and in time; afterwards it only shows what happened", () => {
  expect(approvalOf(body(), new Map(), now)).toEqual({ id: "ap-1", text: "Đồng ý báo giá thay vòi nước?", status: "pending" });
  expect(approvalOf(body({ expires_at: "2026-10-11T02:59:00Z" }), new Map(), now)?.status).toBe("expired");
  expect(approvalOf(body({ status: "expired" }), new Map(), now)?.status).toBe("expired");
  expect(approvalOf(body({ status: "approved", expires_at: "2026-10-11T02:59:00Z" }), new Map(), now)?.status).toBe("approved");
  // What the resident chose here shows at once, until the platform has recorded it.
  expect(approvalOf(body(), new Map([["ap-1", false]]), now)?.status).toBe("rejected");
  expect(approvalOf(body({ status: "approved" }), new Map([["ap-1", false]]), now)?.status).toBe("approved");
});

test("the card takes its costs from the summary and falls back to the message's own text", () => {
  const items = [{ label: "Vòi nước", amount: 150000 }, { label: "Tiền công", amount: 50000 }];
  expect(approvalOf(body({ summary: { arguments: { items, total: 200000 } } }), new Map(), now)).toEqual({
    id: "ap-1", text: "Trợ lý cần bạn đồng ý.", items, total: 200000, status: "pending" });
  expect(approvalOf({ text: "Xin chào" }, new Map(), now)).toBeUndefined();
});
