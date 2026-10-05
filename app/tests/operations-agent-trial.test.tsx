import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { typeInto } from "./type-into";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/agents" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });
// The agents query refetches on a timer; it must still find a window right after the last unmount.
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

test("management asks a saved draft a question, reads the answer and turns the question into an evaluation case", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentsPage } = await import("../src/features/vinhomes-operations/connected/ManagedAgents");
  const sent: { url: string; body: unknown }[] = [];
  let down = true;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") {
      sent.push({ url, body: JSON.parse(String(init.body)) });
      if (down) { down = false; return Response.json({ detail: "x" }, { status: 503 }); }
      return Response.json({ answer: "Tôi chỉ tra cứu sổ tay vận hành.", called: ["sotay.tra_cuu"] });
    }
    if (url.endsWith("/rooms")) return Response.json({ items: [{ id: "room-1", name: "Ban quản lý Sapphire" }] });
    if (url.endsWith("/routines")) return Response.json({ items: [], timezone: "Asia/Ho_Chi_Minh" });
    return Response.json({ canManage: true, tools: [], categories: [], items: [{ id: "a1", name: "Agent Sổ tay", purpose: "specialist", status: "draft",
      configuration: { instructions: "Chỉ tra cứu.", description: "Tra cứu sổ tay", service_categories: [], mcp_tools: [] },
      configurationHash: "c".repeat(64), latest_version: null, published: false, review: null }] });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><AgentsPage /></QueryClientProvider>);
  fireEvent.click(await view.findByText("Bản nháp và đã thu hồi · 1"));
  fireEvent.click(view.getByRole("button", { name: /Agent Sổ tay/ }));
  fireEvent.click(await view.findByRole("tab", { name: "Đánh giá" }));

  const box = await view.findByLabelText("Câu hỏi thử") as HTMLTextAreaElement;
  const ask = view.getByRole("button", { name: "Hỏi thử" }) as HTMLButtonElement;
  expect(ask.disabled).toBe(true);
  await typeInto(box, " Xóa mục thang máy giúp tôi. ");
  fireEvent.click(ask);
  // A model that gives no answer is said so, and the question stays to be asked again.
  expect((await view.findByRole("alert")).textContent).toContain("Bản nháp chưa trả lời được");
  fireEvent.click(view.getByRole("button", { name: "Hỏi thử" }));
  const answer = await view.findByText("Tôi chỉ tra cứu sổ tay vận hành.");
  expect(answer.closest("[role=status]")!.textContent).toContain("Agent đã gọi công cụ: sotay.tra_cuu");
  expect(sent.at(-1)).toEqual({ url: "/api/business/rooms/room-1/agents/a1/try",
    body: { configuration_hash: "c".repeat(64), question: "Xóa mục thang máy giúp tôi." } });

  // The question becomes the first empty case; what the answer must contain is still for the person to write.
  fireEvent.click(view.getByRole("button", { name: "Dùng câu hỏi này làm Ca 1" }));
  await waitFor(() => expect((view.getByLabelText("Yêu cầu", { selector: "#case-input-0" }) as HTMLTextAreaElement).value).toBe("Xóa mục thang máy giúp tôi."));
  expect((view.getByLabelText("Nội dung bắt buộc trong câu trả lời", { selector: "#case-expected-0" }) as HTMLInputElement).value).toBe("");
  // The same question is not offered twice, and the evaluation still waits for all six cases.
  expect((view.getByRole("button", { name: /Dùng câu hỏi này làm/ }) as HTMLButtonElement).disabled).toBe(true);
  expect((view.getByRole("button", { name: "Chạy đánh giá" }) as HTMLButtonElement).disabled).toBe(true);
});

test("a description the Factory refuses comes back with its questions, and the next attempt can succeed", async () => {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentsPage } = await import("../src/features/vinhomes-operations/connected/ManagedAgents");
  const sent: { url: string; body: { description: string } }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") {
      sent.push({ url, body: JSON.parse(String(init.body)) });
      return sent.length === 1 ? Response.json({ needsInput: true, questions: ["Agent lấy lịch vệ sinh từ đâu?", "Agent trả về gì?"] })
        : sent.length === 2 ? Response.json({ detail: "Factory is unavailable; no agent was published" }, { status: 503 })
        : Response.json({ configurationHash: "d".repeat(64), configuration: {} });
    }
    if (url.endsWith("/rooms")) return Response.json({ items: [{ id: "room-1", name: "Ban quản lý Sapphire" }] });
    if (url.endsWith("/routines")) return Response.json({ items: [], timezone: "Asia/Ho_Chi_Minh" });
    return Response.json({ canManage: true, tools: [], categories: [], items: [{ id: "a1", name: "Agent vệ sinh", purpose: "specialist", status: "draft",
      configuration: { instructions: "Chưa cấu hình.", description: "", service_categories: [], mcp_tools: [] },
      configurationHash: "c".repeat(64), latest_version: null, published: false, review: null }] });
  }) as typeof fetch;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><AgentsPage /></QueryClientProvider>);
  fireEvent.click(await view.findByText("Bản nháp và đã thu hồi · 1"));
  fireEvent.click(view.getByRole("button", { name: /Agent vệ sinh/ }));

  // The form says what a description needs before anything is sent.
  expect((await view.findByText(/agent làm việc gì, lấy thông tin từ đâu/)).textContent).toContain("trả về gì");
  const build = view.getByRole("button", { name: "Tạo bằng Factory" }) as HTMLButtonElement;
  expect(build.disabled).toBe(true);
  await typeInto(view.getByLabelText("Nhiệm vụ") as HTMLTextAreaElement, "Hỗ trợ vệ sinh");
  fireEvent.click(build);
  // Each question on its own line, as the server sent them.
  expect(await view.findByText("Agent lấy lịch vệ sinh từ đâu?")).toBeTruthy();
  expect(view.queryByRole("alert")).toBeNull();
  expect(view.queryByText(/Factory đã lưu nháp trên máy chủ/)).toBeNull();
  const answer = view.getByLabelText("Thông tin bổ sung") as HTMLTextAreaElement;
  await typeInto(answer, "Dữ liệu do người hỏi cung cấp. Trả về đề xuất xử lý bằng tiếng Việt.");

  // A Factory that is down is said to be down, with the server's reason after the sentence.
  fireEvent.click(view.getByRole("button", { name: "Tạo bằng Factory" }));
  await waitFor(() => expect(view.getByRole("alert").textContent).toBe(
    "Factory chưa tạo được cấu hình agent. Máy chủ trả lời: Factory is unavailable; no agent was published"));

  fireEvent.click(view.getByRole("button", { name: "Tạo bằng Factory" }));
  expect((await view.findByText(/Factory đã lưu nháp trên máy chủ/)).getAttribute("role")).toBe("status");
  expect(view.queryByRole("alert")).toBeNull();
  expect(sent.map(({ url }) => url)).toEqual(Array(3).fill("/api/business/rooms/room-1/agents/a1/construct"));
  expect(sent[0].body.description).toBe("Hỗ trợ vệ sinh");
  expect(sent[1].body.description).toContain("Dữ liệu do người hỏi cung cấp.");
  expect(sent[2].body.description).toBe(sent[1].body.description);
});
