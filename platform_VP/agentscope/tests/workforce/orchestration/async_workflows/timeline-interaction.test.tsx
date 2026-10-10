import { afterEach, beforeEach, expect, test } from "bun:test";
import { Window } from "happy-dom";
import type { Root } from "../../../../examples/web_ui/frontend/node_modules/react-dom/client";

const browser = new Window({ url: "http://localhost/phase-b-test" });
const installDom = () =>
  Object.assign(globalThis, {
    window: browser,
    document: browser.document,
    navigator: browser.navigator,
    HTMLElement: browser.HTMLElement,
    Node: browser.Node,
    Event: browser.Event,
    MouseEvent: browser.MouseEvent,
    MutationObserver: browser.MutationObserver,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
installDom();
const { act } =
  await import("../../../../examples/web_ui/frontend/node_modules/react");
const { createRoot } =
  await import("../../../../examples/web_ui/frontend/node_modules/react-dom/client");
const { TicketTimeline } =
  await import("../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/TicketTimeline");
const { createTimeline } =
  await import("../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/state");
import type { TicketTimelineProps } from "../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/TicketTimeline";
import type { TimelineState } from "../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/state";
import type { ApprovalView } from "../../../../examples/web_ui/frontend/src/features/workforce/approvals";

let host: HTMLDivElement;
let root: Root;
beforeEach(() => {
  installDom();
  browser.document.body.innerHTML = "";
  host = browser.document.createElement("div") as unknown as HTMLDivElement;
  browser.document.body.append(host as never);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  await browser.happyDOM.cancelAsync();
});

function timeline(
  ticket = "A",
  changes: Partial<TimelineState> = {},
): TimelineState {
  return {
    ...createTimeline({
      identityKey: "owner-1",
      conversationId: `conversation-${ticket}`,
      workflowId: `workflow-${ticket}`,
      externalUserId: "user-1",
      externalConversationId: `chat-${ticket}`,
      externalTicketId: `ticket-${ticket}`,
    }),
    state: "awaiting_confirmation",
    nextAction: "confirm_close",
    revision: 3,
    connection: "live",
    ...changes,
  };
}
async function render(props: TicketTimelineProps) {
  await act(async () => root.render(<TicketTimeline {...props} />));
}
function closeButton(): HTMLButtonElement {
  const button = [...host.querySelectorAll("button")].find((item) =>
    /Đóng yêu cầu|Đang đóng|Đã đóng yêu cầu/.test(item.textContent ?? ""),
  );
  if (!button) throw new Error("Close button missing");
  return button;
}
function checkbox(): HTMLInputElement {
  const input = host.querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!input) throw new Error("Stop-tracking checkbox missing");
  return input;
}
function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}
const approval: ApprovalView = {
  approval_id: "approval-A",
  call_id: "call-A",
  status: "pending",
  arguments_hash: "arguments-A",
  quote_hash: "quote-A",
  expires_at: "2099-10-10T09:00:00Z",
  quote: {
    provider: "Provider A",
    option: "Option A",
    dates: ["10/10/2099"],
    amount: { amount_minor: 100, currency: "VND" },
    fees: { amount_minor: 0, currency: "VND" },
    cancellation_terms: "Terms A",
    quote_ref: "quote-A",
    quote_version: "1",
  },
  decision_history: [],
};

test("UI053 stop tracking while awaiting approval closes without consent", async () => {
  const closes: unknown[][] = [];
  const decisions: unknown[] = [];
  await render({
    state: timeline("A", {
      state: "awaiting_approval",
      approvalIds: ["approval-A"],
    }),
    approvals: [approval],
    onDecide: async (...args) => {
      decisions.push(args);
    },
    onClose: async (...args) => {
      closes.push(args);
    },
  });
  expect(closeButton().disabled).toBe(true);
  await act(async () => checkbox().click());
  expect(closeButton().disabled).toBe(false);
  await act(async () => closeButton().click());
  expect(closes).toEqual([[timeline().binding, 3, true]]);
  expect(decisions).toHaveLength(0);
});

test("UI054 unresolved approval never enables an ordinary completion close", async () => {
  let calls = 0;
  await render({
    state: timeline("A", {
      state: "awaiting_approval",
      approvalIds: ["approval-A"],
    }),
    onClose: async () => {
      calls++;
    },
  });
  await act(async () => closeButton().click());
  expect(closeButton().disabled).toBe(true);
  expect(calls).toBe(0);
});

test("UI055 repeated close clicks submit once and show pending state", async () => {
  const pending = deferred();
  let calls = 0;
  await render({
    state: timeline(),
    onClose: async () => {
      calls++;
      await pending.promise;
    },
  });
  await act(async () => {
    closeButton().click();
    closeButton().click();
  });
  expect(calls).toBe(1);
  expect(closeButton().textContent).toBe("Đang đóng…");
  expect(closeButton().disabled).toBe(true);
  await act(async () => pending.resolve());
  expect(closeButton().disabled).toBe(false);
});

test("UI056 failed close keeps the workflow open and permits explicit retry", async () => {
  let calls = 0;
  await render({
    state: timeline(),
    onClose: async () => {
      if (++calls === 1) throw new Error("409");
    },
  });
  await act(async () => closeButton().click());
  expect(host.querySelector('[role="alert"]')?.textContent).toContain(
    "Chưa đóng được",
  );
  expect(closeButton().disabled).toBe(false);
  expect(closeButton().textContent).toBe("Đóng yêu cầu");
  await act(async () => closeButton().click());
  expect(calls).toBe(2);
  expect(host.querySelector('[role="alert"]')).toBeNull();
});

test("UI057 changing ticket during a pending close isolates its late error", async () => {
  const pending = deferred();
  const calls: string[] = [];
  const onClose: TicketTimelineProps["onClose"] = async (binding) => {
    calls.push(binding.workflowId);
    if (binding.workflowId === "workflow-A") await pending.promise;
  };
  await render({ state: timeline(), onClose });
  await act(async () => closeButton().click());
  await render({ state: timeline("B"), onClose });
  expect(closeButton().disabled).toBe(false);
  await act(async () => pending.reject(new Error("Late A failure")));
  expect(host.querySelector('[role="alert"]')).toBeNull();
  await act(async () => closeButton().click());
  expect(calls).toEqual(["workflow-A", "workflow-B"]);
});

test("UI058 changing ticket resets the stop-tracking choice", async () => {
  const onClose = async () => {};
  await render({ state: timeline("A", { state: "awaiting_user" }), onClose });
  await act(async () => checkbox().click());
  expect(closeButton().disabled).toBe(false);
  await render({ state: timeline("B", { state: "awaiting_user" }), onClose });
  expect(checkbox().checked).toBe(false);
  expect(closeButton().disabled).toBe(true);
});

test("UI059 a closed SSE state stays closed after an in-flight close settles", async () => {
  const pending = deferred();
  const onClose = async () => pending.promise;
  await render({ state: timeline(), onClose });
  await act(async () => closeButton().click());
  await render({
    state: timeline("A", { state: "closed", nextAction: "none", revision: 4 }),
    onClose,
  });
  await act(async () => pending.resolve());
  expect(closeButton().textContent).toBe("Đã đóng yêu cầu");
  expect(closeButton().disabled).toBe(true);
  expect(host.querySelector('input[type="checkbox"]')).toBeNull();
});

test("UI060 stop tracking cannot bypass a blocked connection", async () => {
  let calls = 0;
  await render({
    state: timeline("A", {
      state: "awaiting_approval",
      approvalIds: ["approval-A"],
      connection: "blocked",
    }),
    onClose: async () => {
      calls++;
    },
  });
  await act(async () => checkbox().click());
  await act(async () => closeButton().click());
  expect(closeButton().disabled).toBe(true);
  expect(calls).toBe(0);
});

test("UI061 approval submits exact quote hashes once under repeated clicks", async () => {
  const pending = deferred();
  const decisions: unknown[] = [];
  await render({
    state: timeline("A", {
      state: "awaiting_approval",
      approvalIds: ["approval-A"],
    }),
    approvals: [approval],
    onClose: async () => {},
    onDecide: async (...args) => {
      decisions.push(args);
      await pending.promise;
    },
  });
  const button = [...host.querySelectorAll("button")].find(
    (item) => item.textContent === "Đồng ý giao dịch",
  )!;
  await act(async () => {
    button.click();
    button.click();
  });
  expect(decisions).toEqual([
    [
      "approval-A",
      {
        decision: "approve",
        arguments_hash: "arguments-A",
        quote_hash: "quote-A",
      },
    ],
  ]);
  expect(button.disabled).toBe(true);
  await act(async () => pending.resolve());
  expect(host.textContent).toContain("Đã ghi nhận quyết định");
});

test("UI062 failed approval permits retry with the same quote hashes", async () => {
  const decisions: unknown[] = [];
  await render({
    state: timeline("A", {
      state: "awaiting_approval",
      approvalIds: ["approval-A"],
    }),
    approvals: [approval],
    onClose: async () => {},
    onDecide: async (...args) => {
      decisions.push(args);
      if (decisions.length === 1) throw new Error("Network failure");
    },
  });
  const button = [...host.querySelectorAll("button")].find(
    (item) => item.textContent === "Từ chối",
  )!;
  await act(async () => button.click());
  expect(host.querySelector('[role="alert"]')?.textContent).toContain(
    "Chưa gửi được quyết định",
  );
  expect(button.disabled).toBe(false);
  await act(async () => button.click());
  expect(decisions).toHaveLength(2);
  expect(decisions[0]).toEqual(decisions[1]);
  expect(host.querySelector('[role="alert"]')).toBeNull();
});

test("UI063 completion close uses the latest rendered revision", async () => {
  const closes: unknown[] = [];
  const onClose: TicketTimelineProps["onClose"] = async (...args) => {
    closes.push(args);
  };
  await render({ state: timeline(), onClose });
  await render({ state: timeline("A", { revision: 4 }), onClose });
  await act(async () => closeButton().click());
  expect(closes).toEqual([[timeline().binding, 4, false]]);
});
