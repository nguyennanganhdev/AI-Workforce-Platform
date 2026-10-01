import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from "@testing-library/react";
import { App } from "../../resident-app/src/app/App";
import { Composer } from "../../resident-app/src/features/assistant/Assistant";
import type { ConnectedResident } from "../../resident-app/src/services/use-connected-resident";

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
    setContact: () => {},
    setError: () => {},
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
