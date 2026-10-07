import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Play, RotateCcw, Sparkles, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { managedAgentKeys, type AgentManagement, type ManagedAgent } from "@/lib/agent-management/queries";
import { approveSuiteMutationOptions, cancelRunMutationOptions, prepareSuiteMutationOptions, runQueryOptions, runsQueryOptions, saveSuiteMutationOptions,
  startRunMutationOptions, suitesQueryOptions, type CaseResult, type EvalCase, type Run, type Suite, type Terminal } from "@/lib/agent-evaluation/queries";
import { queryClient } from "@/query-client";
import { OpsSelect } from "./ui";
import { AgentBadge, toolLabel } from "./agent-display";
import "./agent-evaluation.css";

/** Whether this unit has an evaluation sandbox. Without one the earlier six-question evaluation is still the publication evidence. */
export function useEvaluationSandbox(roomId: string, agentId: string) {
  const suites = useQuery(suitesQueryOptions(roomId, agentId));
  return suites.data?.environment?.ready === true;
}

/** Six cases a run, four of them to pass: the server's rule (agent_eval/contracts.py), repeated here for the wording. */
const SUITE_SIZE = 6, PASS_MINIMUM = 4;
const KINDS = [{ value: "in_scope", label: "Trong năng lực" }, { value: "out_of_scope", label: "Ngoài năng lực" },
  { value: "collaboration", label: "Phối hợp" }, { value: "boundary", label: "Ranh giới quyền / cần duyệt" }];
const TERMINALS: { value: Terminal; label: string }[] = [{ value: "reply_only", label: "Chỉ trả lời" }, { value: "information_requested", label: "Hỏi thêm cư dân" },
  { value: "approval_pending", label: "Chờ duyệt" }, { value: "resolved", label: "Đã xử lý xong" }];
const TICKETS = [{ value: "optional", label: "Ticket: tùy" }, { value: "required", label: "Phải mở ticket" }, { value: "forbidden", label: "Không mở ticket" }];
const RULE = [{ value: "", label: "Không quy định" }, { value: "required", label: "Bắt buộc" }, { value: "forbidden", label: "Bị cấm" }];
export const CHECKS: Record<string, string> = { required_agents: "Agent bắt buộc", forbidden_agents: "Agent bị cấm", required_tools: "Công cụ bắt buộc",
  forbidden_tools: "Công cụ bị cấm", required_sources: "Nguồn bắt buộc", valid_output: "Đầu ra hợp lệ", runtime_guards: "Không lỗi thực thi",
  context_integrity: "Ngữ cảnh và quyền", internal_leakage: "Không lộ thông tin nội bộ" };
export const CRITERIA: Record<string, string> = { bam_nguon: "Bám nguồn", dung_quy_trinh: "Đúng quy trình", dung_pham_vi: "Đúng phạm vi", phan_hoi_nguoi_bao: "Phản hồi cư dân" };
export const LAYERS: Record<string, string> = { code: "Kiểm tra bằng code", judge: "Giám khảo", metric: "Metric", environment: "Môi trường", execution: "Thực thi" };
const RUN_STATUS: Record<Run["status"], [string, "ok" | "wait" | "danger" | "neutral"]> = { queued: ["Đang chờ", "wait"], running: ["Đang chạy", "wait"],
  completed: ["Hoàn tất", "ok"], failed: ["Lỗi môi trường", "danger"], interrupted: ["Bị gián đoạn", "danger"], cancelled: ["Đã dừng", "neutral"] };
const CASE_STATUS: Record<CaseResult["status"], [string, "ok" | "wait" | "danger" | "neutral"]> = { pending: ["Chờ", "neutral"], running: ["Đang chạy", "wait"],
  passed: ["Đạt", "ok"], failed: ["Rớt", "danger"], error: ["Lỗi", "danger"] };

function blank(n: number, fixture: string): EvalCase {
  return { name: `Ca ${n}`, kind: n === 5 ? "out_of_scope" : n === 4 || n === 6 ? "boundary" : "in_scope", source: "manual",
    input: { message: "", follow_up_messages: [], fixture_profile_id: fixture },
    expectations: { required_agents: [], forbidden_agents: [], required_tools: [], forbidden_tools: [], required_sources: [], ticket: "optional", terminal_state: "reply_only" },
    rubric: { score1_description: "", score2_description: "", score3_description: "", score4_description: "", score5_description: "" } };
}
const strip = (c: EvalCase & { id?: string; ordinal?: number }): EvalCase => { const { id: _id, ordinal: _ordinal, ...rest } = c; return rest; };
const rule = (required: string[], forbidden: string[], id: string) => required.includes(id) ? "required" : forbidden.includes(id) ? "forbidden" : "";
function setRule(required: string[], forbidden: string[], id: string, value: string): [string[], string[]] {
  const r = required.filter(x => x !== id), f = forbidden.filter(x => x !== id);
  return [value === "required" ? [...r, id] : r, value === "forbidden" ? [...f, id] : f];
}

function CaseEditor({ value, onChange, disabled, agents, tools, fixtures, documents }: { value: EvalCase; onChange: (c: EvalCase) => void; disabled: boolean;
  agents: { id: string; name: string }[]; tools: { server_id: string; name: string; label: string }[];
  fixtures: { value: string; label: string }[]; documents: { value: string; label: string }[] }) {
  const e = value.expectations, set = (patch: Partial<EvalCase>) => onChange({ ...value, ...patch, source: "manual" });
  const expect = (patch: Partial<EvalCase["expectations"]>) => set({ expectations: { ...e, ...patch } });
  const key = (t: { server_id: string; name: string }) => `${t.server_id}/${t.name}`;
  const source = e.required_sources[0];
  return <fieldset className="eval-case" disabled={disabled}>
    <div className="eval-case-row"><Input aria-label="Tên ca" value={value.name} maxLength={120} onChange={x => set({ name: x.target.value })} />
      <OpsSelect label="Loại ca" value={value.kind} options={KINDS} disabled={disabled} onValueChange={v => set({ kind: v as EvalCase["kind"] })} />
      {value.source === "generated" && <AgentBadge label="Model sinh" tone="agent" />}</div>
    <label>Cư dân nhắn</label><Textarea rows={2} maxLength={2000} value={value.input.message} onChange={x => set({ input: { ...value.input, message: x.target.value } })} />
    <label>Câu trả lời khi được hỏi lại (mỗi dòng một câu, tối đa 5)</label>
    <Textarea rows={2} value={value.input.follow_up_messages.join("\n")} onChange={x => set({ input: { ...value.input, follow_up_messages: x.target.value.split("\n").filter(Boolean).slice(0, 5) } })} />
    <div className="eval-case-row"><OpsSelect label="Hồ sơ cư dân mẫu" value={value.input.fixture_profile_id} options={fixtures} disabled={disabled}
      onValueChange={v => set({ input: { ...value.input, fixture_profile_id: v } })} />
      <OpsSelect label="Kết thúc mong đợi" value={e.terminal_state} options={TERMINALS} disabled={disabled} onValueChange={v => expect({ terminal_state: v as Terminal })} />
      <OpsSelect label="Ticket" value={e.ticket} options={TICKETS} disabled={disabled} onValueChange={v => expect({ ticket: v as EvalCase["expectations"]["ticket"] })} /></div>
    <details><summary>Agent, công cụ, nguồn và thang điểm</summary>
      <div className="eval-rules">{agents.map(a => <div key={a.id} className="eval-rule"><span>{a.name}</span>
        <OpsSelect label={`Agent ${a.name}`} value={rule(e.required_agents, e.forbidden_agents, a.id)} options={RULE} disabled={disabled}
          onValueChange={v => { const [r, f] = setRule(e.required_agents, e.forbidden_agents, a.id, v); expect({ required_agents: r, forbidden_agents: f }); }} /></div>)}
      {tools.map(t => <div key={key(t)} className="eval-rule"><span>{t.label}</span>
        <OpsSelect label={`Công cụ ${t.label}`} value={rule(e.required_tools.map(key), e.forbidden_tools.map(key), key(t))} options={RULE} disabled={disabled}
          onValueChange={v => expect({ required_tools: [...e.required_tools.filter(x => key(x) !== key(t)), ...(v === "required" ? [{ server_id: t.server_id, name: t.name }] : [])],
            forbidden_tools: [...e.forbidden_tools.filter(x => key(x) !== key(t)), ...(v === "forbidden" ? [{ server_id: t.server_id, name: t.name }] : [])] })} /></div>)}
      {documents.length > 0 && <div className="eval-rule"><span>Tài liệu bắt buộc</span>
        <OpsSelect label="Tài liệu bắt buộc" value={source ? `${source.document_id}|${source.version ?? ""}` : ""} disabled={disabled}
          options={[{ value: "", label: "Không yêu cầu" }, ...documents]}
          onValueChange={v => { const [document_id, version] = v.split("|"); expect({ required_sources: v ? [{ document_id, version: version || null, citation_required: false }] : [] }); }} /></div>}</div>
      {([1, 2, 3, 4, 5] as const).map(n => <div key={n}><label>Mức {n}</label><Textarea rows={1} maxLength={1000} value={value.rubric[`score${n}_description`]}
        onChange={x => set({ rubric: { ...value.rubric, [`score${n}_description`]: x.target.value } })} /></div>)}
    </details>
  </fieldset>;
}

/** Step "Thử": prepare, edit and approve the four cases, then start a run in the sandbox. */
export function EvaluationSuite({ roomId, agent, catalogue, canEdit, onStarted }: { roomId: string; agent: ManagedAgent; catalogue: AgentManagement; canEdit: boolean; onStarted: () => void }) {
  const suites = useQuery(suitesQueryOptions(roomId, agent.id));
  const prepare = useMutation(prepareSuiteMutationOptions(queryClient, roomId, agent.id));
  const save = useMutation(saveSuiteMutationOptions(queryClient, roomId, agent.id));
  const approve = useMutation(approveSuiteMutationOptions(queryClient, roomId, agent.id));
  const start = useMutation(startRunMutationOptions(queryClient, roomId, agent.id));
  const suite: Suite | undefined = suites.data?.items?.[0];
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  useEffect(() => { setCases(suite ? suite.cases.map(strip) : []); }, [suite?.id, suite?.version]);
  const environment = suites.data?.environment;
  const fixtures = (environment?.fixtures ?? []).map(f => ({ value: f.fixture_profile_id, label: f.description }));
  const documents = (environment?.documents ?? []).map(d => ({ value: `${d.document_id}|${d.version}`, label: d.title }));
  const agents = useMemo(() => [{ id: agent.id, name: `${agent.name} (đang đánh giá)` },
    ...catalogue.items.filter(a => a.id !== agent.id && a.published && a.purpose === "specialist").map(a => ({ id: a.id, name: a.name }))], [agent, catalogue]);
  const tools = (agent.configuration.mcp_tools ?? []).map(g => { const t = catalogue.tools.find(t => t.server_id === g.server_id && t.name === g.name);
    return { ...g, label: t ? toolLabel(t) : g.name }; });
  const busy = prepare.isPending || save.isPending || approve.isPending || start.isPending;
  const draft = suite?.status === "draft", dirty = !!suite && JSON.stringify(cases) !== JSON.stringify(suite.cases.map(strip));
  const error = prepare.error || save.error || approve.error || start.error || suites.error;
  const editable = canEdit && !busy && (!suite || draft);
  const stale = suite && suite.configuration_hash !== agent.configurationHash;
  async function begin() {
    if (!suite) return;
    try { await start.mutateAsync({ suite_id: suite.id, configuration_hash: agent.configurationHash, request_id: requestId }); setRequestId(crypto.randomUUID()); onStarted(); } catch { /* shown below */ }
  }
  /** One touch: the model writes the six cases, they are approved as written and the run starts.
   * A suite the server finds a problem in stops here as a draft, for a person to correct. */
  async function auto() {
    try {
      const made = await prepare.mutateAsync({ configuration_hash: agent.configurationHash, mode: "generate" });
      if (made.problems.length > 0) return;
      const approved = await approve.mutateAsync({ suiteId: made.id, version: made.version });
      await start.mutateAsync({ suite_id: approved.id, configuration_hash: agent.configurationHash, request_id: requestId });
      setRequestId(crypto.randomUUID()); onStarted();
    } catch { /* shown below */ }
  }
  return <div className="agent-evaluation-layout eval-suite"><section className="agent-panel">
    <header className="eval-head"><div><h2>Bộ {SUITE_SIZE} ca đánh giá</h2>
      <p>Chạy toàn tuyến trong sandbox: cư dân mẫu nhắn Lễ tân, Supervisor tự chọn agent, công cụ thật trên dữ liệu thử. Agent phát hành được khi ít nhất {PASS_MINIMUM}/{SUITE_SIZE} ca đạt.</p></div>
      {suite && <AgentBadge label={`Bản ${suite.revision}: ${draft ? "nháp" : "đã duyệt"}`} tone={draft ? "wait" : "ok"} />}</header>
    <div className="eval-actions">
      <Button disabled={!canEdit || busy} onClick={() => void auto()}>
        <Sparkles />{busy && prepare.variables?.mode === "generate" ? "Đang sinh ca và gửi chạy…" : "Tự sinh và chạy đánh giá"}</Button>
      <Button variant="outline" disabled={!canEdit || busy} onClick={() => prepare.mutate({ configuration_hash: agent.configurationHash, mode: "generate" })}>
        {suite ? "Chỉ sinh bộ mới" : `Chỉ sinh ${SUITE_SIZE} ca`}</Button>
      <Button variant="ghost" disabled={!canEdit || busy} onClick={() => prepare.mutate({ configuration_hash: agent.configurationHash, mode: "manual",
        cases: Array.from({ length: SUITE_SIZE }, (_, i) => blank(i + 1, fixtures[0]?.value ?? "")) })}>Tự soạn bộ mới</Button>
      {draft && <Button variant="outline" disabled={!editable || !dirty} onClick={() => save.mutate({ suiteId: suite.id, version: suite.version, cases })}>{save.isPending ? "Đang lưu…" : "Lưu bộ ca"}</Button>}
      {draft && <Button disabled={!editable || dirty || suite.problems.length > 0} onClick={() => approve.mutate({ suiteId: suite.id, version: suite.version })}>Duyệt bộ ca</Button>}
      {suite?.status === "approved" && <Button variant="outline" disabled={!canEdit || busy} onClick={() => void begin()}><Play />{start.isPending ? "Đang gửi…" : "Chạy đánh giá"}</Button>}
    </div>
    {error && <p role="alert" className="eval-alert">{error.message}</p>}
    {stale && <p className="agent-hint">Bộ ca được chuẩn bị cho cấu hình trước. Vẫn chạy được nếu phạm vi agent không đổi; máy chủ kiểm lại khi bắt đầu.</p>}
    {suite && suite.problems.length > 0 && <div className="eval-problems" role="status"><strong>Chưa duyệt được vì:</strong><ul>{suite.problems.map((p, i) => <li key={i}>{p}</li>)}</ul></div>}
    {!suite && <p className="agent-hint">Chưa có bộ ca. Sinh từ nhiệm vụ và công cụ của agent (không dùng chỉ dẫn chi tiết), hoặc tự soạn.</p>}
    {cases.map((c, i) => <CaseEditor key={i} value={c} disabled={!editable || !draft} agents={agents} tools={tools} fixtures={fixtures} documents={documents}
      onChange={next => setCases(cases.map((x, j) => (j === i ? next : x)))} />)}
  </section><RunHistory roomId={roomId} agentId={agent.id} /></div>;
}

function RunHistory({ roomId, agentId }: { roomId: string; agentId: string }) {
  const runs = useQuery(runsQueryOptions(roomId, agentId));
  return <aside className="agent-panel eval-history"><h2>Các lần đánh giá</h2>
    {runs.data?.items?.length ? <ol>{runs.data.items.map(r => <li key={r.id}><AgentBadge label={RUN_STATUS[r.status][0]} tone={r.passed === true ? "ok" : r.passed === false ? "danger" : RUN_STATUS[r.status][1]} />
      <span>{r.summary.passed ?? 0}/{SUITE_SIZE} đạt · bộ {r.suite_revision ?? "?"}</span><small>{new Date(r.created_at).toLocaleString("vi-VN")}</small></li>)}</ol>
      : <p className="agent-hint">Chưa chạy lần nào.</p>}</aside>;
}

const STATUS_WORDS: Record<string, string> = { OK: "có kết quả", NOT_FOUND: "không có dữ liệu", FORBIDDEN: "bị từ chối", INVALID_INPUT: "tham số sai",
  TOOL_ERROR: "công cụ lỗi", INTERNAL_ERROR: "lỗi hệ thống", AWAITING_CONFIRMATION: "chờ xác nhận" };
/** Management reads names, never ids: agent ids and tool names in a recorded text become what the screen calls them. */
function useNames(catalogue: AgentManagement) {
  return useMemo(() => {
    const agents = new Map(catalogue.items.map(a => [a.id, a.name]));
    const tools = new Map(catalogue.tools.flatMap(t => [[t.name, toolLabel(t)], [`${t.server_id}/${t.name}`, toolLabel(t)]] as [string, string][]));
    const agent = (id: string) => agents.get(id) ?? "agent khác";
    const tool = (name: string) => tools.get(name) ?? "công cụ khác";
    const keys = [...agents.keys(), ...[...tools.keys()].sort((a, b) => b.length - a.length)];
    const text = (value: string) => keys.reduce((out, key) => out.split(key).join(agents.get(key) ?? tools.get(key)!), value)
      .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, "(mã nội bộ)");
    return { agent, tool, text };
  }, [catalogue]);
}

function CaseReport({ result, catalogue }: { result: CaseResult; catalogue: AgentManagement }) {
  const names = useNames(catalogue);
  const [label, tone] = CASE_STATUS[result.status];
  const visible = result.trace?.messages.filter(m => m.role === "resident" || m.visible_to_resident) ?? [];
  return <details className="eval-result" open={result.status !== "passed"}><summary><strong>{result.ordinal}. {result.name}</strong><AgentBadge label={label} tone={tone} />
    {result.failure_layers.map((l, i) => <small key={i}>{LAYERS[l.layer] ?? l.layer}: {l.kind === "failed" ? "rớt" : "lỗi"}</small>)}</summary>
    {result.error && <p className="eval-alert">{result.error.message || result.error.code}</p>}
    {visible.length > 0 && <div className="eval-conversation">{visible.map(m => <p key={m.id} className={m.role === "resident" ? "is-resident" : ""}>{m.text}</p>)}</div>}
    {result.terminal_state && <p className="agent-hint">Kết thúc: {TERMINALS.find(t => t.value === result.terminal_state)?.label}</p>}
    {result.trace && (result.trace.routing.length > 0 || result.trace.tool_calls.length > 0) && <ul className="eval-trace">
      {result.trace.routing.map(r => <li key={r.id}>Supervisor chọn: {r.selected_agent_ids.map(names.agent).join(", ") || "không agent nào"}</li>)}
      {result.trace.tool_calls.map(t => <li key={t.id}>{names.agent(t.agent_id)} dùng {names.tool(`${t.server_id}/${t.name}`)}: {STATUS_WORDS[t.status] ?? "không rõ"}</li>)}
      {result.trace.retrievals.slice(0, 5).map(k => <li key={k.id}>Nguồn hạng {k.rank}: {k.content.slice(0, 140)}</li>)}</ul>}
    {result.checks && <table className="eval-table"><caption>9 kiểm tra bằng code</caption><tbody>{Object.entries(result.checks).map(([k, c]) =>
      <tr key={k}><th>{CHECKS[k] ?? k}</th><td><AgentBadge label={c.passed ? "Đạt" : "Rớt"} tone={c.passed ? "ok" : "danger"} /></td><td>{names.text(c.reason)}</td></tr>)}</tbody></table>}
    {result.judge?.criteria && <table className="eval-table"><caption>Giám khảo ({result.judge.model_profile}), cần ≥ 4/5 mỗi tiêu chí</caption><tbody>
      {Object.entries(result.judge.criteria).map(([k, a]) => <tr key={k}><th>{CRITERIA[k] ?? k}</th><td><AgentBadge label={`${a.score}/5`} tone={a.score >= 4 ? "ok" : "danger"} /></td><td>{names.text(a.reason)}</td></tr>)}</tbody></table>}
    {result.judge?.status === "error" && <p className="eval-alert">Giám khảo lỗi: {result.judge.error?.message || result.judge.error?.code}</p>}
    {result.metrics.length > 0 && <table className="eval-table"><caption>Metric thư viện</caption><tbody>{result.metrics.map(m =>
      <tr key={m.name}><th>{m.name}</th><td>{m.status === "scored" ? `${m.value?.toFixed(2)} / ${m.threshold}` : m.status === "not_applicable" ? "Không áp dụng" : "Lỗi"}</td><td>{m.reason || m.error}</td></tr>)}</tbody></table>}
    {result.environment && !result.environment.safe && <p className="eval-alert">{result.environment.reason}</p>}
  </details>;
}

/** Step "Đánh giá": the latest run, its summary first, then each case. */
export function EvaluationReport({ roomId, agentId, canEdit, catalogue }: { roomId: string; agentId: string; canEdit: boolean; catalogue: AgentManagement }) {
  const runs = useQuery(runsQueryOptions(roomId, agentId));
  const latest = runs.data?.items?.[0];
  const run = useQuery({ ...runQueryOptions(roomId, agentId, latest?.id ?? ""), enabled: !!latest });
  const cancel = useMutation(cancelRunMutationOptions(queryClient, roomId, agentId));
  const finished = run.data?.status === "completed";
  // A passing run opens a pending review on the server: the agent list shows it once refetched.
  useEffect(() => { if (finished) void queryClient.invalidateQueries({ queryKey: managedAgentKeys.all }); }, [finished]);
  if (!latest) return <section className="agent-panel agent-evaluation-results"><h2>Kết quả đánh giá</h2><p>Chưa chạy đánh giá. Ở bước Thử, bấm "Tự sinh và chạy đánh giá".</p></section>;
  const data = run.data ?? latest, [label, tone] = RUN_STATUS[data.status];
  const live = data.status === "queued" || data.status === "running";
  const seconds = data.started_at && data.finished_at ? Math.round((Date.parse(data.finished_at) - Date.parse(data.started_at)) / 1000) : null;
  return <section className="agent-panel agent-evaluation-results eval-report">
    <header className="eval-head"><div><h2>Kết quả đánh giá</h2>
      <p>{data.status === "completed" ? `${data.summary.passed ?? 0}/${SUITE_SIZE} ca đạt (cần ${PASS_MINIMUM})` : live ? "Đang chạy trong sandbox…" : data.error?.message || data.error?.code}
        {seconds !== null && ` · ${seconds} giây`}{data.judge_model && ` · giám khảo ${data.judge_model.model_name}`}{data.suite_revision && ` · bộ ca bản ${data.suite_revision}`}</p></div>
      <AgentBadge label={data.status === "completed" ? (data.passed ? `Đạt ${data.summary.passed ?? PASS_MINIMUM}/${SUITE_SIZE}` : "Chưa đạt") : label} tone={data.status === "completed" ? (data.passed ? "ok" : "danger") : tone} />
      {live && canEdit && <Button variant="outline" size="sm" disabled={cancel.isPending} onClick={() => cancel.mutate(data.id)}><Square />Dừng</Button>}
      {!live && <Button variant="ghost" size="sm" onClick={() => void run.refetch()}><RotateCcw />Tải lại</Button>}</header>
    {(data.summary.failure_layers?.length ?? 0) > 0 && <p className="agent-hint">Lỗi chính: {data.summary.failure_layers!.map(l => LAYERS[l] ?? l).join(", ")}</p>}
    {data.passed && <p className="agent-verdict">Bản cấu hình này có thể phát hành ở bước tiếp theo. Đạt bộ ca này không chứng minh mọi tình huống đều đúng.</p>}
    {data.cases?.map(c => <CaseReport key={c.case_id} result={c} catalogue={catalogue} />)}
  </section>;
}
