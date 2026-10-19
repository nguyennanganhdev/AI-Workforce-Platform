import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from "@testing-library/react";
import { App } from "../../resident-web/src/app/App";
import { Assistant, Composer } from "../../resident-web/src/features/assistant/Assistant";
import type { PlatformApproval, ResidentState } from "../../resident-web/src/services/types";
import { typeInto } from "./type-into";
import type { ConnectedResident } from "../../resident-web/src/services/use-connected-resident";

beforeAll(() => GlobalRegistrator.register({ url: "http://localhost:3011" }));
afterEach(cleanup);
afterAll(() => GlobalRegistrator.unregister());

test("connected resident keeps original shell and renders required ticket fields, without simulation controls", () => {
  location.hash = "/chat/chat-1";
  const live = {
    state: {
      version: 1,
      requests: [],
      messages: [],
      conversations: [],
      activeConversationId: "chat-1",
      draft: {
        step: "review",
        description: "Ổ điện hỏng",
        location: "Phòng khách",
        photos: [],
      },
    },
    profile: {
      user: { id: "user-1", name: "Nguyễn Hà", email: "ha@example.invalid" },
      dataMode: "database",
      units: [
        {
          id: "unit-1",
          code: "1208",
          building_id: "building-1",
          building_name: "Tòa A",
          site_name: "Khu A",
          domain_id: "domain-1",
        },
      ],
      categories: [{ id: "category-1", code: "technical", name: "Kỹ thuật" }],
    },
    contact: { unit: "", category: "", phone: "" },
    error: "",
    busy: false,
    archivedChats: [],
    notifications: [],
    notificationUnread: 0,
    notificationOffset: null,
    archiveChat: async () => true,
    restoreChat: async () => true,
    markNotificationsRead: async () => true,
    moreNotifications: async () => true,
    setContact: () => {},
    setError: () => {},
    question: () => undefined,
  } as unknown as ConnectedResident;
  const view = render(<App live={live} />);
  expect(view.container.querySelector(".desktop-sidebar")).not.toBeNull();
  expect(view.getByLabelText("Số điện thoại liên hệ")).toBeTruthy();
  expect(view.getByLabelText("Nhóm dịch vụ")).toBeTruthy();
  expect(view.container.textContent).not.toContain("Chỉ lưu trên thiết bị");
  expect(view.container.textContent).not.toContain("Mô phỏng đã điều phối");
  expect(view.container.textContent).toContain("Nguyễn Hà");
});

test("failed async send retains composer text, successful send clears it", async () => {
  let accepted = false;
  const view = render(
    <Composer
      connected
      draft={null}
      initialInput={{ text: "Tin nhắn chưa gửi", photos: [] }}
      onSend={async () => accepted}
    />,
  );
  const input = view.getByLabelText(
    "Tin nhắn cho trợ lý",
  ) as HTMLTextAreaElement;
  await act(async () => {
    fireEvent.submit(view.container.querySelector("form")!);
  });
  await waitFor(() => expect(input.value).toBe("Tin nhắn chưa gửi"));
  accepted = true;
  await act(async () => {
    fireEvent.submit(view.container.querySelector("form")!);
  });
  await waitFor(() => expect(input.value).toBe(""));
});

const chat = (over: Partial<ResidentState>, handlers: { onApproval?: (id: string, approve: boolean) => unknown; onResolve?: (id: string, accepted: boolean, reason?: string) => unknown } = {}) =>
  render(<Assistant connected conversation state={{ version: 1, requests: [], messages: [], draft: null, activeConversationId: "chat-1", ...over }}
    onResume={() => {}} onSend={() => true} onOpen={() => {}} onRequests={() => {}} onSubmit={() => {}} onEditDraft={() => {}} onCancelDraft={() => {}} {...handlers} />);
const approval = (over: Partial<PlatformApproval> = {}): PlatformApproval => ({ id: "ap-1", text: "Đồng ý báo giá thay vòi nước?", status: "pending", ...over });
const asking = (item: PlatformApproval) => ({ messages: [{ id: "m1", role: "assistant" as const, text: item.text, approval: item }] });

test("an approval of the platform's agent is a card the resident answers once, with its costs in đồng", () => {
  const decided: [string, boolean][] = [];
  const onApproval = (id: string, approve: boolean) => decided.push([id, approve]);
  const view = chat(asking(approval({ items: [{ label: "Vòi nước", amount: 150000 }, { label: "Tiền công", amount: 50000 }], total: 200000 })), { onApproval });
  expect(view.getByText("Đồng ý báo giá thay vòi nước?")).toBeTruthy();
  expect(view.getByText("150.000đ")).toBeTruthy();
  expect(view.getByText("200.000đ")).toBeTruthy();
  fireEvent.click(view.getByRole("button", { name: "Đồng ý" }));
  fireEvent.click(view.getByRole("button", { name: "Không đồng ý" }));
  expect(decided).toEqual([["ap-1", true], ["ap-1", false]]);
  cleanup();

  for (const [status, outcome] of [["approved", "Bạn đã đồng ý."], ["rejected", "Bạn đã không đồng ý."], ["expired", "Yêu cầu này đã hết hạn trả lời."]] as const) {
    const done = chat(asking(approval({ status })), { onApproval });
    expect(done.getByText(outcome)).toBeTruthy();
    expect(done.queryByRole("button", { name: "Đồng ý" })).toBeNull();
    expect(done.queryByRole("button", { name: "Không đồng ý" })).toBeNull();
    cleanup();
  }
});

test("a request waiting for the resident is confirmed in its conversation through the existing decision", async () => {
  const calls: unknown[][] = [];
  const onResolve = (id: string, accepted: boolean, reason?: string) => calls.push([id, accepted, reason]);
  const request = { id: "t1", title: "Vòi nước bếp bị rò", description: "", location: "", createdAt: "2026-10-11T03:00:00Z", photos: [], events: [] };
  const plain = [{ id: "chat-1", title: "Vòi nước", messages: [], draft: null, requestId: "t1", unread: 0, updatedAt: "2026-10-11T03:00:00Z" }];
  // Not until the platform's agent has asked: a chat without it (or with the bridge off) shows no card.
  const quiet = chat({ conversations: plain, requests: [{ ...request, status: "confirmation" }] }, { onResolve });
  expect(quiet.queryByRole("button", { name: "Xác nhận hoàn thành" })).toBeNull();
  cleanup();
  const conversations = [{ ...plain[0], confirmClose: true }];
  const view = chat({ conversations, requests: [{ ...request, status: "confirmation" }] }, { onResolve });
  expect(view.getByText("Nhân viên đã gửi kết quả nghiệm thu. Bạn xác nhận hoàn thành chứ?")).toBeTruthy();
  fireEvent.click(view.getByRole("button", { name: "Xác nhận hoàn thành" }));
  expect(calls).toEqual([["t1", true, undefined]]);
  fireEvent.click(view.getByRole("button", { name: "Chưa đạt" }));
  const send = view.getByRole("button", { name: "Gửi" }) as HTMLButtonElement;
  await typeInto(view.getByLabelText("Điều gì chưa đạt?"), "Còn rò");
  expect(send.disabled).toBe(true);
  await typeInto(view.getByLabelText("Điều gì chưa đạt?"), "Vòi vẫn còn rò nước");
  expect(send.disabled).toBe(false);
  fireEvent.submit(view.container.querySelector("form.question-item")!);
  expect(calls.at(-1)).toEqual(["t1", false, "Vòi vẫn còn rò nước"]);
  cleanup();

  // Nothing to confirm while the work is still going on.
  const working = chat({ conversations, requests: [{ ...request, status: "processing" }] }, { onResolve });
  expect(working.queryByRole("button", { name: "Xác nhận hoàn thành" })).toBeNull();
});
