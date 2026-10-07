import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

let cleanup: typeof import("@testing-library/react")["cleanup"];
let render: typeof import("@testing-library/react")["render"];
let waitFor: typeof import("@testing-library/react")["waitFor"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3020/operations/agents" });
  ({ cleanup, render, waitFor, fireEvent } = await import("@testing-library/react/pure"));
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; history.replaceState(null, "", "/operations/agents"); });
afterAll(() => new Promise<void>((done) => setTimeout(() => { GlobalRegistrator.unregister(); done(); }, 50)));

const HASH = "c".repeat(64);
const RUBRIC = { score1_description: "1", score2_description: "2", score3_description: "3", score4_description: "4", score5_description: "5" };
const kase = (n: number) => ({ id: `case-${n}`, ordinal: n, name: `Ca ${n}`, kind: "boundary", source: "manual",
  input: { message: "Hỏi giờ hồ bơi", follow_up_messages: [], fixture_profile_id: "resident-a" },
  expectations: { required_agents: [], forbidden_agents: [], required_tools: [], forbidden_tools: [], required_sources: [], ticket: "optional", terminal_state: "reply_only" },
  rubric: RUBRIC, metric_policy: {} });
const CHECKS = Object.fromEntries(["required_agents", "forbidden_agents", "required_tools", "forbidden_tools", "required_sources", "valid_output",
  "runtime_guards", "context_integrity", "internal_leakage"].map(k => [k, { passed: k !== "internal_leakage", reason: k === "internal_leakage" ? "Phản hồi lộ mã nội bộ." : "ok", evidence_refs: [] }]));

function backend(ready: boolean, sent: { url: string; body: unknown }[]) {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost").pathname;
    if (init?.method === "POST") { sent.push({ url, body: JSON.parse(String(init.body ?? "null")) }); return Response.json({ runId: "run-1", status: "queued" }, { status: 202 }); }
    if (url.endsWith("/rooms")) return Response.json({ items: [{ id: "room-1", name: "Ban quản lý Sapphire" }] });
    if (url.endsWith("/connections") || url.endsWith("/models")) return Response.json({ items: [], canManage: true });
    if (url.endsWith("/routines")) return Response.json({ items: [], timezone: "Asia/Ho_Chi_Minh" });
    if (url.endsWith("/eval-suites")) return Response.json({ items: ready ? [{ id: "suite-1", revision: 2, status: "approved", version: 1, problems: [],
      configuration_hash: HASH, suite_hash: "d".repeat(64), created_at: "2026-10-07T00:00:00Z", cases: [1, 2, 3, 4].map(kase) }] : [],
      environment: { ready, fixtures: [{ fixture_profile_id: "resident-a", description: "Chủ hộ căn 0101" }], documents: [] } });
    const run = { id: "run-1", status: "completed", passed: false, summary: { passed: 3, failure_layers: ["code"] }, error: null, configuration_hash: HASH,
      suite_hash: "d", snapshot_hash: "e", suite_revision: 2, judge_model: { provider: "openai", model_name: "gpt-judge" }, metric_profile: "none",
      created_at: "2026-10-07T00:00:00Z", started_at: "2026-10-07T00:00:00Z", finished_at: "2026-10-07T00:02:00Z" };
    if (url.endsWith("/eval-runs")) return Response.json({ items: sent.length ? [run] : [] });
    if (url.endsWith("/eval-runs/run-1")) return Response.json({ ...run, cases: [1, 2, 3, 4].map(n => ({ case_id: `case-${n}`, ordinal: n, name: `Ca ${n}`, kind: "boundary",
      status: n === 4 ? "failed" : "passed", final_response: "Hồ bơi mở 6h-21h.", terminal_state: "reply_only", checks: CHECKS, metrics: [],
      judge: { status: "scored", model_profile: "openai/gpt-judge", threshold: 4, error: null, criteria: { bam_nguon: { score: 5, reason: "Có căn cứ", evidence_refs: ["final_response"] },
        dung_quy_trinh: { score: 4, reason: "ok", evidence_refs: ["final_response"] }, dung_pham_vi: { score: 5, reason: "ok", evidence_refs: ["final_response"] },
        phan_hoi_nguoi_bao: { score: 3, reason: "Lộ mã yêu cầu", evidence_refs: ["final_response"] } } },
      environment: { safe: true, reason: "Sandbox cô lập" }, failure_layers: n === 4 ? [{ layer: "code", kind: "failed", detail: "internal_leakage" }] : [],
      error: null, latency_ms: 30000, trace: { messages: [{ id: "m-1", role: "resident", text: "Hỏi giờ hồ bơi" }, { id: "m-2", role: "reception", text: "Hồ bơi mở 6h-21h.", visible_to_resident: true }],
        routing: [{ id: "r-1", selected_agent_ids: ["a1", "0db82e23-1dc9-54fa-99e0-4f7cb2269875"] }],
        tool_calls: [{ id: "t-1", agent_id: "a1", server_id: "technical-tools", name: "asset.read", status: "NOT_FOUND" }], retrievals: [] } })) });
    return Response.json({ canManage: true, tools: [], categories: [], items: [{ id: "a1", name: "Agent Tiện ích", purpose: "specialist", status: "draft",
      configuration: { instructions: "x", description: "Tiện ích", service_categories: [], mcp_tools: [] }, configurationHash: HASH, latest_version: null, published: false, review: null }] });
  }) as typeof fetch;
}

async function open(ready: boolean, sent: { url: string; body: unknown }[]) {
  const { QueryClientProvider, QueryClient } = await import("@tanstack/react-query");
  const { AgentsPage } = await import("../src/features/vinhomes-operations/connected/ManagedAgents");
  globalThis.fetch = backend(ready, sent);
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AgentsPage /></QueryClientProvider>);
  fireEvent.click(await view.findByRole("button", { name: "Danh sách" }));
  fireEvent.click(await view.findByRole("tab", { name: /Bản nháp/ }));
  fireEvent.click(view.getByRole("button", { name: /Agent Tiện ích/ }));
  fireEvent.click(await view.findByRole("tab", { name: /Thử/ }));
  return view;
}

test("with a sandbox, management runs the approved four cases and reads the report summary first", async () => {
  const sent: { url: string; body: unknown }[] = [];
  const view = await open(true, sent);
  expect(await view.findByText("Bộ 4 ca đánh giá")).toBeTruthy();
  expect(view.queryByText("Bộ câu hỏi thử")).toBeNull();
  fireEvent.click(view.getByRole("button", { name: "Chạy đánh giá" }));
  await waitFor(() => expect(sent.at(-1)?.url).toBe("/api/business/rooms/room-1/agents/a1/eval-runs"));
  expect(sent.at(-1)?.body).toMatchObject({ suite_id: "suite-1", configuration_hash: HASH });
  expect(await view.findByText("Kết quả đánh giá")).toBeTruthy();
  expect(await view.findByText(/3\/4 ca đạt/)).toBeTruthy();
  expect(view.getByText("Chưa đạt")).toBeTruthy();
  expect(view.getByText(/Lỗi chính: Kiểm tra bằng code/)).toBeTruthy();
  expect(view.getAllByText("Không lộ thông tin nội bộ").length).toBeGreaterThan(0);
  expect(view.getAllByText("Phản hồi cư dân").length).toBeGreaterThan(0);
  // Names, never ids: the agent by its name, an agent this screen does not know and a tool without a label by plain words.
  expect(view.getAllByText("Supervisor chọn: Agent Tiện ích, agent khác").length).toBeGreaterThan(0);
  expect(view.getAllByText("Agent Tiện ích dùng công cụ khác: không có dữ liệu").length).toBeGreaterThan(0);
  expect(view.container.textContent).not.toContain("0db82e23");
  expect(view.container.textContent).not.toContain("asset.read");
  // Publication stays closed: no review is pending for a run that did not pass.
  expect((view.getByRole("button", { name: /Tiếp: phát hành/ }) as HTMLButtonElement).disabled).toBe(true);
});

test("without a sandbox the earlier six-question evaluation is still offered", async () => {
  const view = await open(false, []);
  expect(await view.findByText("Bộ câu hỏi thử")).toBeTruthy();
  expect(view.queryByText("Bộ 4 ca đánh giá")).toBeNull();
});
