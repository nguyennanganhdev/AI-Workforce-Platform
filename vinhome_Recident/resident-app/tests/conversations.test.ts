import { expect, test } from "bun:test";
import { initialState } from "../src/mocks/seed";
import {
  normalizeConversations,
  activeRoom,
  newConversation,
  selectConversation,
  reply,
  reconcileConversations,
  submitDraft,
  receiveTicketEvent,
  resolveRequest,
  loadConversations,
  saveState,
} from "../src/services/conversations";
import type { ResidentState } from "../src/services/types";
const send = (s: ResidentState, text: string) =>
  reconcileConversations(s, reply(s, text));
test("migration preserves historical transcript and creates one room per old ticket", () => {
  const old = initialState(),
    next = normalizeConversations(old);
  expect(next.messages).toEqual(old.messages);
  expect(next.requests).toEqual(old.requests);
  expect(next.conversations!.filter((c) => c.requestId)).toHaveLength(
    old.requests.length,
  );
  expect(normalizeConversations(next)).toBe(next);
});
test("conversation drafts and transcripts remain isolated on switch", () => {
  let s = send(
    normalizeConversations(initialState()),
    "Sự cố rò nước trong bếp",
  );
  const first = activeRoom(s),
    messages = s.messages;
  s = newConversation(s);
  expect(s.draft).toBeNull();
  expect(s.messages).toHaveLength(0);
  s = send(s, "Giờ mở cửa bể bơi?");
  const second = activeRoom(s);
  s = selectConversation(s, first.id);
  expect(s.draft).toEqual(first.draft);
  expect(s.messages).toEqual(messages);
  s = selectConversation(s, second.id);
  expect(s.draft).toBeNull();
  expect(s.messages).toEqual(second.messages);
});
test("a room owns exactly one submitted ticket and further messages cannot submit another", () => {
  let s = send(
    normalizeConversations(initialState()),
    "Sự cố rò nước trong bếp",
  );
  s = send(s, "Căn hộ S2.01 1208");
  s = reconcileConversations(s, submitDraft(s));
  const ticket = activeRoom(s).requestId;
  s = send(s, "Báo sự cố mất điện");
  expect(s.draft).toBeNull();
  expect(activeRoom(s).requestId).toBe(ticket);
  expect(() => submitDraft(s)).toThrow("Mỗi hội thoại");
});
test("events and confirmations target their ticket room, unread survives reload and clears on open", () => {
  let s = normalizeConversations(initialState());
  const ticket = s.requests[0].id;
  const originalMessages = s.messages;
  s = receiveTicketEvent(s, ticket, "Đã xử lý, chờ xác nhận", "confirmation");
  expect(s.messages).toEqual(originalMessages);
  const room = s.conversations!.find((c) => c.requestId === ticket)!;
  expect(room.unread).toBe(1);
  s = resolveRequest(s, ticket, true);
  expect(s.messages).toEqual(originalMessages);
  expect(
    s.conversations!.find((c) => c.id === room.id)!.messages.at(-1)!.requestId,
  ).toBe(ticket);
  let raw = "";
  saveState(
    {
      setItem: (_, value) => {
        raw = value;
      },
    },
    s,
  );
  s = loadConversations({ getItem: () => raw });
  expect(s.conversations!.find((c) => c.id === room.id)!.unread).toBe(2);
  s = selectConversation(s, room.id);
  expect(activeRoom(s).unread).toBe(0);
  expect(s.requests[0].status).toBe("completed");
});
test("invalid conversation references or unsafe nested photos are rejected", () => {
  const s = normalizeConversations(initialState());
  s.activeConversationId = "missing";
  expect(() =>
    loadConversations({ getItem: () => JSON.stringify(s) }),
  ).toThrow();
  s.activeConversationId = s.conversations![0].id;
  s.conversations![0].messages = [
    {
      id: "bad",
      role: "resident",
      text: "",
      photos: [{ id: "bad", name: "bad", url: "javascript:alert(1)" }],
    },
  ];
  expect(() =>
    loadConversations({ getItem: () => JSON.stringify(s) }),
  ).toThrow();
});
