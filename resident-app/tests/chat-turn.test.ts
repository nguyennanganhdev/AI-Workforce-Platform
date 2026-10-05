import { expect, test } from "bun:test";
import { chatTurn, formOffered } from "../src/services/chat-turn";
import type { ChatMessage, Draft, Photo } from "../src/services/types";

const photo: Photo = { id: "p1", name: "ro-nuoc.png", url: "blob:p1" };
const form = (step: Draft["step"], more: Partial<Draft> = {}): Draft => ({
  step,
  description: "",
  location: "",
  photos: [],
  ...more,
});
const said = (role: ChatMessage["role"], text: string, requestId?: string): ChatMessage => ({
  id: text,
  role,
  text,
  ...(requestId ? { requestId } : {}),
});

test("the report button opens the conversation and sends nothing in the resident's name", () => {
  expect(chatTurn("Báo sự cố", [], null)).toEqual({ kind: "open" });
  // Also while the form is open: the button never becomes a line of the form.
  expect(chatTurn("Báo sự cố", [], form("description"))).toEqual({ kind: "open" });
});

test("what the resident writes goes to Reception as written, and starts no form beside it", () => {
  expect(chatTurn("  Nhà tắm của tôi bị rò nước ", [photo], null)).toEqual({
    kind: "message",
    text: "Nhà tắm của tôi bị rò nước",
  });
});

test("photos alone are sent without any words", () => {
  expect(chatTurn("", [photo], null)).toEqual({ kind: "message", text: "" });
});

test("while the form is open its lines are its fields, not messages", () => {
  const described = chatTurn("Vòi bếp rò", [photo], form("description"));
  expect(described).toEqual({
    kind: "form",
    draft: form("location", { description: "Vòi bếp rò", photos: [photo] }),
  });
  const placed = chatTurn(" Bếp, dưới chậu ", [], form("location", { description: "Vòi bếp rò", photos: [photo] }));
  expect(placed).toEqual({
    kind: "form",
    draft: form("review", { description: "Vòi bếp rò", location: "Bếp, dưới chậu", photos: [photo] }),
  });
  // At most three photos stay on the form.
  const many = chatTurn("x", [photo, photo, photo], form("description", { photos: [photo] }));
  expect(many.kind === "form" && many.draft.photos).toHaveLength(3);
});

test("the form is offered only after Reception could not answer, and never beside a request", () => {
  const failed = "Xin lỗi, tôi chưa xử lý được tin nhắn này. Bạn thử lại sau ít phút hoặc gửi phản ánh bằng biểu mẫu nhé.";
  const down = "Trợ lý lễ tân tạm thời chưa phản hồi được. Bạn có thể gửi phản ánh bằng biểu mẫu trong cuộc trò chuyện này.";
  expect(formOffered([])).toBe(false);
  expect(formOffered([said("resident", "Vòi bếp rò"), said("assistant", "Bạn thấy nước rò ở đâu?")])).toBe(false);
  expect(formOffered([said("resident", "Vòi bếp rò"), said("assistant", failed)])).toBe(true);
  expect(formOffered([said("resident", "Vòi bếp rò"), said("assistant", down)])).toBe(true);
  // Reception answered again afterwards: the conversation is back with it.
  expect(formOffered([said("assistant", failed), said("resident", "Alo"), said("assistant", "Mình đây, bạn cần gì?")])).toBe(false);
  // The request card is not a reply, and a conversation with a request needs no form.
  expect(formOffered([said("assistant", failed), said("assistant", "Theo dõi tiến độ phản ánh của bạn.", "t1")])).toBe(false);
});

test("several questions become one card to answer in one go, and one message back", async () => {
  const { answerText, questionItems } = await import("../src/services/chat-turn");
  const asked = "Để kiểm tra an toàn, xin xác nhận:\n1. Có mùi khét hoặc tia lửa không?\n2. CB có bị nhảy không?\n- Có nước gần dây điện không?";
  const { lead, items } = questionItems(asked);
  expect(lead).toBe("Để kiểm tra an toàn, xin xác nhận:");
  expect(items).toEqual(["Có mùi khét hoặc tia lửa không?", "CB có bị nhảy không?", "Có nước gần dây điện không?"]);
  // What was left empty is said to be unknown rather than dropped.
  expect(answerText(items, ["Không", " Có, nhảy từ sáng ", ""])).toBe("1. Không\n2. Có, nhảy từ sáng\n3. Chưa rõ");
  // The same list written on one line, as the model often does.
  expect(questionItems("1. Các ổ cắm khác có điện không? 2. Ổ cắm có nóng hay mùi khét không? 3. Sự cố bắt đầu từ khi nào?").items).toEqual([
    "Các ổ cắm khác có điện không?", "Ổ cắm có nóng hay mùi khét không?", "Sự cố bắt đầu từ khi nào?"]);
  expect(questionItems("1. Ổ cắm có nóng hoặc mùi khét không; các ổ cắm khác có điện không; và CB có bị nhảy không?").items).toEqual([
    "Ổ cắm có nóng hoặc mùi khét không?", "Các ổ cắm khác có điện không?", "CB có bị nhảy không?"]);
  // A single sentence stays one question and its answer is sent as written.
  const one = questionItems("Dây điện hỏng ở vị trí nào? Có khói hay mùi khét không?");
  expect(one.items).toHaveLength(1);
  expect(answerText(one.items, [" Gần phòng ngủ, không có khói "])).toBe("Gần phòng ngủ, không có khói");
});
