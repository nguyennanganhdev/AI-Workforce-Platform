import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let AgentReviews: typeof import("../src/features/vinhomes-operations/connected/AgentReviews")["AgentReviews"];

const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({
    url: "http://localhost:3020/operations/accounts",
  });
  ({ cleanup, fireEvent, render, waitFor } = await import(
    "@testing-library/react/pure"
  ));
  ({ AgentReviews } = await import(
    "../src/features/vinhomes-operations/connected/AgentReviews"
  ));
});
afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
});
afterAll(() => GlobalRegistrator.unregister());

/** The business API as the screen uses it: one pending review, one published agent. */
function backend() {
  const posted: { path: string; body: unknown }[] = [];
  let pending = [
    {
      id: "review-1",
      version: 0,
      name: "Agent Kỹ thuật A2",
      created_at: "2026-10-04T02:00:00Z",
      configuration: {
        instructions: "Bạn là Agent Kỹ thuật.",
        description: "Phân loại sự cố kỹ thuật.",
        service_categories: ["technical"],
        mcp_tools: [{ name: "sop_kb.retrieve" }],
      },
      evaluation: {
        evaluator: "vinhomes.publish",
        cases: [
          {
            name: "voi-bep-ro",
            expected: "Level 3",
            actual: "Mức: Level 3",
            passed: true,
            explanation: "ok",
          },
        ],
      },
    },
  ];
  let published = [
    {
      agent_id: "agent-old",
      name: "Agent An ninh",
      version_no: 1,
      published_at: "2026-10-03T02:00:00Z",
      workspace: "BQL Sapphire",
      service_categories: ["security"],
      tools: [],
    },
  ];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace("/api/business", "");
    if (init?.method === "POST") {
      posted.push({ path, body: JSON.parse(String(init.body)) });
      if (path.includes("/decision")) pending = [];
      if (path.includes("/revoke")) published = [];
      return Response.json({ ok: true });
    }
    return Response.json({
      items: path.startsWith("/admin/agent-reviews") ? pending : published,
    });
  }) as typeof fetch;
  return posted;
}

test("an admin reads what is under review and approves it with a note", async () => {
  const posted = backend();
  const page = render(<AgentReviews />);
  await waitFor(() => page.getByText("Agent chờ duyệt (1)"));
  expect(
    page.getByText(
      /Danh mục phục vụ: technical · Tool được cấp: sop_kb.retrieve/,
    ),
  ).toBeTruthy();
  expect(page.getByText(/Kết quả đánh giá: 1\/1 ca đạt/)).toBeTruthy();
  expect(page.getByText("Bạn là Agent Kỹ thuật.")).toBeTruthy();
  // No decision without a note: the backend requires one, so the button waits for it.
  const approve = page.getByRole("button", { name: "Duyệt và phát hành" });
  expect(approve.hasAttribute("disabled")).toBe(true);
  fireEvent.change(page.getByLabelText("Ghi chú quyết định"), {
    target: { value: "Đạt đủ ca" },
  });
  fireEvent.click(approve);
  await waitFor(() => page.getByText("Agent chờ duyệt (0)"));
  expect(posted).toEqual([
    {
      path: "/admin/agent-reviews/review-1/decision",
      body: { decision: "approve", version: 0, note: "Đạt đủ ca" },
    },
  ]);
});

test("an admin revokes a published agent with a reason", async () => {
  const posted = backend();
  const page = render(<AgentReviews />);
  await waitFor(() => page.getByText("Agent đã phát hành (1)"));
  expect(page.getByText(/Agent An ninh · phiên bản 1/)).toBeTruthy();
  fireEvent.change(page.getByLabelText("Lý do thu hồi"), {
    target: { value: "Trả lời sai quy trình" },
  });
  fireEvent.click(page.getByRole("button", { name: "Thu hồi" }));
  await waitFor(() => page.getByText("Agent đã phát hành (0)"));
  expect(posted).toEqual([
    {
      path: "/admin/agents/agent-old/release/revoke",
      body: { note: "Trả lời sai quy trình" },
    },
  ]);
});
