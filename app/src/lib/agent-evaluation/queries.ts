import { mutationOptions, queryOptions, type QueryClient } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { managedAgentKeys } from "@/lib/agent-management/queries";

/** Agent evaluation V1: four approved cases run end to end in the sandbox (services/vinhomes-api v3_agent_evals.py). */
export type ToolRef = { server_id: string; name: string };
export type Terminal = "reply_only" | "information_requested" | "approval_pending" | "resolved";
export type EvalCase = {
  name: string; kind: "in_scope" | "out_of_scope" | "collaboration" | "boundary"; source?: "generated" | "manual";
  input: { message: string; follow_up_messages: string[]; fixture_profile_id: string };
  expectations: { required_agents: string[]; forbidden_agents: string[]; required_tools: (ToolRef & { arguments?: Record<string, unknown> })[];
    forbidden_tools: ToolRef[]; required_sources: { document_id: string; version?: string | null; agent_id?: string | null; citation_required?: boolean }[];
    ticket: "required" | "forbidden" | "optional"; terminal_state: Terminal };
  rubric: { score1_description: string; score2_description: string; score3_description: string; score4_description: string; score5_description: string };
  metric_policy?: Record<string, "apply" | "not_applicable">;
};
export type Suite = { id: string; revision: number; status: "draft" | "approved" | "archived"; version: number; problems: string[];
  configuration_hash: string; suite_hash: string | null; created_at: string; cases: (EvalCase & { id: string; ordinal: number })[] };
export type Fixture = { fixture_profile_id: string; description: string; unit_code?: string; building_code?: string };
export type SourceDocument = { document_id: string; version: string; title: string };
export type Suites = { items: Suite[]; environment: { ready: boolean; fixtures: Fixture[]; documents: SourceDocument[] } };
export type Check = { passed: boolean; reason: string; evidence_refs: string[] };
export type Judge = { status: "scored" | "error"; model_profile: string; threshold: number;
  criteria: Record<"bam_nguon" | "dung_quy_trinh" | "dung_pham_vi" | "phan_hoi_nguoi_bao", { score: number; reason: string; evidence_refs: string[] }> | null;
  error: { code: string; message: string } | null };
export type Metric = { name: string; status: "scored" | "not_applicable" | "error"; value: number | null; threshold: number | null; reason: string; error: string | null };
export type TraceMessage = { id: string; role: string; agent_id?: string | null; text: string; visible_to_resident?: boolean };
export type CaseResult = { case_id: string; ordinal: number; name: string; kind: EvalCase["kind"]; status: "pending" | "running" | "passed" | "failed" | "error";
  final_response: string | null; terminal_state: Terminal | null; checks: Record<string, Check> | null; judge: Judge | null; metrics: Metric[];
  environment: { safe: boolean; reason: string } | null; failure_layers: { layer: string; kind: "failed" | "error"; detail: string }[];
  error: { code: string; message?: string } | null; latency_ms: number | null;
  trace: { messages: TraceMessage[]; routing: { id: string; selected_agent_ids: string[] }[];
    tool_calls: { id: string; agent_id: string; server_id: string; name: string; status: string }[];
    retrievals: { id: string; document_id: string; rank: number; content: string }[] } | null };
export type Run = { id: string; status: "queued" | "running" | "completed" | "failed" | "interrupted" | "cancelled"; passed: boolean | null;
  summary: { cases?: number; passed?: number; failed?: number; errors?: number; failure_layers?: string[]; latency_ms?: number };
  error: { code: string; message?: string } | null; configuration_hash: string; suite_hash: string; snapshot_hash: string;
  suite_revision: number | null; judge_model: { provider: string; model_name: string } | null; metric_profile: string | null;
  created_at: string; started_at: string | null; finished_at: string | null; cases?: CaseResult[] };

const agentPath = (room: string, agent: string) => `/api/business/rooms/${encodeURIComponent(room)}/agents/${encodeURIComponent(agent)}`;
export const evaluationKeys = {
  suites: (room: string, agent: string) => ["agent-evaluation", room, agent, "suites"] as const,
  runs: (room: string, agent: string) => ["agent-evaluation", room, agent, "runs"] as const,
  run: (room: string, agent: string, run: string) => ["agent-evaluation", room, agent, "run", run] as const,
};
const live = (status?: string) => status === "queued" || status === "running";

export function suitesQueryOptions(room: string, agent: string) {
  return queryOptions({ queryKey: evaluationKeys.suites(room, agent), queryFn: async (): Promise<Suites> =>
    (await client(`${agentPath(room, agent)}/eval-suites`, { headers: businessHeaders(), fallback: "Không tải được bộ đánh giá." })).json() });
}
export function runsQueryOptions(room: string, agent: string) {
  return queryOptions({ queryKey: evaluationKeys.runs(room, agent), queryFn: async (): Promise<{ items: Run[] }> =>
    (await client(`${agentPath(room, agent)}/eval-runs`, { headers: businessHeaders(), fallback: "Không tải được lịch sử đánh giá." })).json(),
    refetchInterval: query => (query.state.data?.items?.some(r => live(r.status)) ? 3000 : false) });
}
export function runQueryOptions(room: string, agent: string, run: string) {
  return queryOptions({ queryKey: evaluationKeys.run(room, agent, run), queryFn: async (): Promise<Run> =>
    (await client(`${agentPath(room, agent)}/eval-runs/${encodeURIComponent(run)}`, { headers: businessHeaders(), fallback: "Không tải được kết quả đánh giá." })).json(),
    refetchInterval: query => (live(query.state.data?.status) ? 3000 : false) });
}

function refresh(queryClient: QueryClient, room: string, agent: string) {
  return Promise.all([queryClient.invalidateQueries({ queryKey: ["agent-evaluation", room, agent] }), queryClient.invalidateQueries({ queryKey: managedAgentKeys.all })]);
}
export function prepareSuiteMutationOptions(queryClient: QueryClient, room: string, agent: string) {
  return mutationOptions({ mutationFn: async (body: { configuration_hash: string; mode: "generate" | "manual"; cases?: EvalCase[] }): Promise<Suite> =>
    (await client(`${agentPath(room, agent)}/eval-suites`, { method: "POST", body, headers: businessHeaders(), fallback: "Không chuẩn bị được bộ ca đánh giá." })).json(),
    onSuccess: () => refresh(queryClient, room, agent) });
}
export function saveSuiteMutationOptions(queryClient: QueryClient, room: string, agent: string) {
  return mutationOptions({ mutationFn: async ({ suiteId, ...body }: { suiteId: string; version: number; cases: EvalCase[] }): Promise<Suite> =>
    (await client(`${agentPath(room, agent)}/eval-suites/${encodeURIComponent(suiteId)}`, { method: "PUT", body, headers: businessHeaders(), fallback: "Không lưu được bộ ca." })).json(),
    onSuccess: () => refresh(queryClient, room, agent) });
}
export function approveSuiteMutationOptions(queryClient: QueryClient, room: string, agent: string) {
  return mutationOptions({ mutationFn: async ({ suiteId, version }: { suiteId: string; version: number }): Promise<Suite> =>
    (await client(`${agentPath(room, agent)}/eval-suites/${encodeURIComponent(suiteId)}/approve`, { method: "POST", body: { version }, headers: businessHeaders(), fallback: "Chưa duyệt được bộ ca." })).json(),
    onSuccess: () => refresh(queryClient, room, agent) });
}
export function startRunMutationOptions(queryClient: QueryClient, room: string, agent: string) {
  return mutationOptions({ mutationFn: async (body: { suite_id: string; configuration_hash: string; request_id: string }): Promise<{ runId: string; status: string }> =>
    (await client(`${agentPath(room, agent)}/eval-runs`, { method: "POST", body, headers: businessHeaders(), fallback: "Chưa bắt đầu được lần đánh giá." })).json(),
    onSuccess: () => refresh(queryClient, room, agent) });
}
export function cancelRunMutationOptions(queryClient: QueryClient, room: string, agent: string) {
  return mutationOptions({ mutationFn: async (run: string): Promise<void> => {
    await client(`${agentPath(room, agent)}/eval-runs/${encodeURIComponent(run)}/cancel`, { method: "POST", headers: businessHeaders(), fallback: "Không dừng được lần đánh giá." });
  }, onSuccess: () => refresh(queryClient, room, agent) });
}
