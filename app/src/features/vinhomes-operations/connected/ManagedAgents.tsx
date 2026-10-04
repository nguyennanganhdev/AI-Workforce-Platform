import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconPlus } from "@tabler/icons-react";
import { AbstractAvatar } from "@/components/agents/abstract-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { managedAgentsQueryOptions, type AgentManagement, type ManagedAgent, type EvaluationInput } from "@/lib/agent-management/queries";
import { configureManagedAgentMutationOptions, constructManagedAgentMutationOptions, createManagedAgentMutationOptions,
  decideManagedAgentMutationOptions, evaluateManagedAgentMutationOptions, revokeManagedAgentMutationOptions } from "@/lib/agent-management/mutations";
import { roomsQueryOptions } from "@/lib/rooms/queries";
import { queryClient } from "@/query-client";

const SERVERS: Record<string, string> = { reporting: "Báo cáo", "security-tools": "An ninh", "technical-tools": "Kỹ thuật" };

/** Where an agent stands, in one phrase: what management needs to know before opening it. */
export function agentStanding(agent: ManagedAgent): { label: string; live: boolean } {
  if (agent.purpose === "supervisor") return { label: "Supervisor của nhóm", live: true };
  if (agent.published) return { label: `Đang phát hành · bản ${agent.latest_version?.number ?? 1}`, live: true };
  if (agent.review?.status === "pending") return { label: "Chờ quyết định phát hành", live: false };
  return { label: agent.latest_version ? "Đã thu hồi" : "Nháp", live: false };
}

function AgentCard({ agent, categories, onOpen }: { agent: ManagedAgent; categories: AgentManagement["categories"]; onOpen: () => void }) {
  const standing = agentStanding(agent);
  const serves = (agent.configuration.service_categories || []).map((code) => categories.find((c) => c.code === code)?.name || code);
  const tools = agent.configuration.mcp_tools?.length || 0;
  return (
    <button type="button" onClick={onOpen}
      className="flex flex-col items-stretch gap-3 rounded-lg border border-border bg-card p-4 text-left transition-colors hover:border-primary/40 focus-visible:border-ring focus-visible:outline-none">
      <span className="flex items-center gap-3">
        <AbstractAvatar name={agent.name} seed={agent.name} size={40} />
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-foreground">{agent.name}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {agent.purpose === "supervisor" ? "Điều phối các phiên" : serves.length ? `Tham gia phiên ${serves.join(", ")}` : "Trả lời khi được nhắc trong nhóm"}
          </span>
        </span>
      </span>
      <span className="line-clamp-2 min-h-10 text-sm leading-snug text-muted-foreground">{agent.configuration.description || "Chưa có mô tả nhiệm vụ."}</span>
      <span className="flex flex-wrap items-center gap-2">
        <Badge variant={standing.live ? "default" : "secondary"}>{standing.label}</Badge>
        {tools > 0 && <span className="text-xs text-muted-foreground">{tools} công cụ</span>}
      </span>
    </button>
  );
}

/** The agents of management's room: the ones at work, then drafts and revoked ones out of the way. */
export function AgentsPage() {
  const rooms = useQuery(roomsQueryOptions());
  const [chosen, setRoom] = useState("");
  const roomId = chosen || rooms.data?.items[0]?.id || "";
  const agents = useQuery(managedAgentsQueryOptions(roomId));
  const create = useMutation(createManagedAgentMutationOptions(queryClient));
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [createId, setCreateId] = useState(() => crypto.randomUUID());
  const items = agents.data?.items || [];
  const live = items.filter((a) => agentStanding(a).live);
  const idle = items.filter((a) => !agentStanding(a).live);
  const error = rooms.error || agents.error;
  return (
    <div className="mx-auto w-full max-w-5xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Agent</h1>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            Agent của nhóm làm việc trong các phiên do Supervisor điều phối và trả lời khi được nhắc. Bạn tự tạo và phát hành agent; mỗi bản phải đạt đánh giá trước khi phát hành.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(rooms.data?.items.length || 0) > 1 && (
            <select aria-label="Nhóm" value={roomId} onChange={(e) => setRoom(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground">
              {rooms.data!.items.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          )}
          {agents.data?.canManage && <Button onClick={() => setCreating(true)}><IconPlus />Tạo agent</Button>}
        </div>
      </header>
      {error && <p role="alert" className="mt-4 text-sm text-destructive">{error.message}</p>}
      {rooms.isPending || (roomId && agents.isPending) ? <Skeleton className="mt-6 h-40" /> : !roomId ? (
        <p className="mt-6 text-sm text-muted-foreground">Tài khoản chưa được thêm vào nhóm nào.</p>
      ) : (
        <>
          <section aria-label="Agent đang làm việc" className="mt-6">
            {live.length ? (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
                {live.map((agent) => <AgentCard key={agent.id} agent={agent} categories={agents.data!.categories} onOpen={() => setSelected(agent.id)} />)}
              </div>
            ) : <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">Chưa có agent nào được phát hành. Tạo một agent, đánh giá rồi phát hành để Supervisor mời vào phiên.</p>}
          </section>
          {!!idle.length && (
            <details className="mt-8">
              <summary className="cursor-pointer text-sm font-medium text-foreground">Bản nháp và đã thu hồi · {idle.length}</summary>
              <ul className="mt-3 divide-y divide-border rounded-lg border border-border bg-card">
                {idle.map((agent) => (
                  <li key={agent.id}>
                    <button type="button" onClick={() => setSelected(agent.id)} className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-muted">
                      <span className="min-w-0 truncate text-sm text-foreground">{agent.name}</span>
                      <Badge variant="secondary">{agentStanding(agent).label}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      <Dialog open={creating} onOpenChange={setCreating}><DialogContent><DialogHeader><DialogTitle>Tạo agent cho nhóm</DialogTitle>
        <DialogDescription>Agent mới là bản nháp. Bản nháp chỉ chạy trong đánh giá; phát hành xong Supervisor mới mời vào phiên.</DialogDescription></DialogHeader>
        <DialogBody><label htmlFor="agent-name" className="text-sm font-medium">Tên agent</label><Input id="agent-name" value={name} maxLength={160} onChange={e => setName(e.target.value)} />
          {create.error && <p role="alert" className="text-destructive">{create.error.message}</p>}</DialogBody>
        <DialogFooter><Button disabled={!name.trim() || create.isPending} onClick={async () => {
          try { const result = await create.mutateAsync({roomId, name: name.trim(), purpose: "specialist", requestId: createId});
            setCreating(false); setName(""); setCreateId(crypto.randomUUID()); setSelected(result.id); } catch { /* visible mutation error */ }
        }}>{create.isPending ? "Đang tạo…" : "Tạo nháp"}</Button></DialogFooter></DialogContent></Dialog>
      {!!agents.data && !!selected && <AgentEditor key={`${roomId}:${selected}`} roomId={roomId} agent={items.find(a => a.id === selected)}
        catalogue={agents.data} onClose={() => setSelected("")} />}
    </div>
  );
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x));

function AgentEditor({ roomId, agent, catalogue, onClose }: {roomId: string; agent?: ManagedAgent; catalogue: AgentManagement; onClose: () => void}) {
  const save = useMutation(configureManagedAgentMutationOptions(queryClient));
  const construct = useMutation(constructManagedAgentMutationOptions(queryClient));
  const evaluate = useMutation(evaluateManagedAgentMutationOptions(queryClient));
  const decide = useMutation(decideManagedAgentMutationOptions(queryClient));
  const revoke = useMutation(revokeManagedAgentMutationOptions(queryClient));
  const [instructions, setInstructions] = useState(agent?.configuration.instructions || "");
  const [description, setDescription] = useState(agent?.configuration.description || "");
  const [categories, setCategories] = useState(agent?.configuration.service_categories || []);
  const [tools, setTools] = useState(agent?.configuration.mcp_tools || []);
  const [role, setRole] = useState("Chuyên viên hỗ trợ Ban quản lý");
  const [note, setNote] = useState("");
  const [cases, setCases] = useState<EvaluationInput[]>(Array.from({length: 6}, (_, i) => ({name: `Ca ${i + 1}`, instruction: "", expected: ""})));
  const [evaluationId, setEvaluationId] = useState(() => crypto.randomUUID());
  const [constructionId, setConstructionId] = useState(() => crypto.randomUUID());
  useEffect(() => {
    if (!agent) return;
    setInstructions(agent.configuration.instructions || ""); setDescription(agent.configuration.description || "");
    setCategories(agent.configuration.service_categories || []); setTools(agent.configuration.mcp_tools || []);
    evaluate.reset(); setEvaluationId(crypto.randomUUID());
  }, [agent?.configurationHash]);
  const busy = save.isPending || construct.isPending || evaluate.isPending || decide.isPending || revoke.isPending;
  if (!agent) return null;
  const baseVersion = agent.status === "active" ? agent.latest_version?.id : undefined;
  const pendingReview = agent.review?.status === "pending";
  const error = save.error || construct.error || evaluate.error || decide.error || revoke.error;
  const edit = !pendingReview && !busy;
  const results = evaluate.data?.cases || (agent.review?.config_hash === agent.configurationHash ? agent.review.evaluation.cases : undefined);
  // Evaluation runs on what the server holds, so unsaved edits would be evaluated as the old text.
  const dirty = instructions !== (agent.configuration.instructions || "") || description !== (agent.configuration.description || "")
    || !sameSet(categories, agent.configuration.service_categories || [])
    || !sameSet(tools.map(t => `${t.server_id}/${t.name}`), (agent.configuration.mcp_tools || []).map(t => `${t.server_id}/${t.name}`));
  async function saveConfiguration() {
    if (!agent) return;
    try { await save.mutateAsync({roomId, agentId: agent.id, configuration: {instructions, description,
      service_categories: categories, mcp_tools: tools, knowledge_namespace_ids: agent.configuration.knowledge_namespace_ids || [],
      framework_version: "openbot-chat-completions", revision_of: baseVersion}}); } catch { /* visible mutation error */ }
  }
  const servers = [...new Set(catalogue.tools.map(t => t.server_id))];
  // A connection the administrator set up is named by its title; its tools by the server's own names.
  const serverLabel = (server: string) => { const tool = catalogue.tools.find(t => t.server_id === server);
    return SERVERS[server] || (tool?.external ? `${tool.server_title} · kết nối ngoài` : tool?.server_title) || server; };
  return <Dialog open onOpenChange={open => {if (!open && !busy) onClose();}}><DialogContent className="max-w-2xl">
    <DialogHeader><DialogTitle>{agent.name}</DialogTitle><DialogDescription>
      {pendingReview ? "Đánh giá đã đạt. Mở mục Phát hành để phát hành bản này."
        : baseVersion ? `Đang soạn bản ${Number(agent.latest_version?.number) + 1}. Phiên đang chạy vẫn dùng bản đã phát hành cho tới khi bản mới được phát hành.`
        : "Bản nháp: soạn cấu hình, chạy đánh giá, rồi phát hành."}
    </DialogDescription></DialogHeader>
    <DialogBody>
      <Tabs defaultValue={pendingReview ? "release" : "configuration"}>
        <TabsList className="w-full">
          <TabsTrigger value="configuration">Cấu hình</TabsTrigger>
          <TabsTrigger value="scope">Phạm vi và công cụ</TabsTrigger>
          <TabsTrigger value="evaluation">Đánh giá</TabsTrigger>
          <TabsTrigger value="release">Phát hành</TabsTrigger>
        </TabsList>
        <TabsContent value="configuration" className="space-y-4 pt-3">
          <div className="space-y-1.5"><label htmlFor="agent-description" className="text-sm font-medium">Nhiệm vụ</label>
            <Textarea id="agent-description" rows={2} value={description} maxLength={2000} disabled={!edit} onChange={e => setDescription(e.target.value)} /></div>
          <div className="space-y-1.5"><label htmlFor="agent-instructions" className="text-sm font-medium">Chỉ dẫn</label>
            <Textarea id="agent-instructions" rows={10} value={instructions} maxLength={50000} disabled={!edit} onChange={e => setInstructions(e.target.value)} /></div>
          <div className="space-y-2 rounded-lg border border-border p-3">
            <p className="text-sm font-medium">Soạn chỉ dẫn bằng Factory</p>
            <p className="text-xs text-muted-foreground">Factory viết chỉ dẫn từ nhiệm vụ và vai trò bên dưới, rồi lưu thành bản nháp. Đọc lại trước khi đánh giá.</p>
            <label htmlFor="agent-role" className="text-xs text-muted-foreground">Vai trò</label>
            <Input id="agent-role" value={role} disabled={!edit} onChange={e => setRole(e.target.value)} />
            <Button size="sm" variant="outline" disabled={!edit || !description.trim() || !role.trim()} onClick={async () => {
              try { await construct.mutateAsync({roomId, agentId: agent.id, role, description, service_categories: categories,
                configuration_hash: agent.configurationHash, revision_of: baseVersion, request_id: constructionId});
                setConstructionId(crypto.randomUUID()); } catch { /* visible mutation error */ }
            }}>{construct.isPending ? "Factory đang tạo…" : "Tạo bằng Factory"}</Button>
            {construct.isSuccess && <p role="status" className="text-xs text-muted-foreground">Factory đã lưu nháp trên máy chủ. Kiểm tra chỉ dẫn trước khi đánh giá.</p>}
          </div>
        </TabsContent>
        <TabsContent value="scope" className="space-y-5 pt-3">
          <fieldset disabled={!edit}><legend className="text-sm font-medium">Danh mục phục vụ</legend>
            <p className="mb-2 text-xs text-muted-foreground">Supervisor mời agent vào phiên của yêu cầu thuộc danh mục được chọn. Không chọn: agent chỉ trả lời khi được nhắc trong nhóm.</p>
            {catalogue.categories.map(c => <label key={c.code} className="mb-1.5 flex items-center gap-2 text-sm"><input type="checkbox" checked={categories.includes(c.code)} onChange={e => setCategories(e.target.checked ? [...categories, c.code] : categories.filter(x => x !== c.code))} />{c.name}</label>)}
          </fieldset>
          <fieldset disabled={!edit}><legend className="text-sm font-medium">Tool đọc được cấp</legend>
            <p className="mb-2 text-xs text-muted-foreground">Agent chỉ đọc dữ liệu trong phạm vi của nhóm. Thao tác ghi luôn cần người duyệt.</p>
            {catalogue.tools.length ? servers.map(server => <div key={server} className="mb-3">
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">{serverLabel(server)}</p>
              {catalogue.tools.filter(t => t.server_id === server).map(t => <label key={`${t.server_id}/${t.name}`} className="mb-2 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1"
                checked={tools.some(g => g.server_id === t.server_id && g.name === t.name)} onChange={e => setTools(e.target.checked ? [...tools, {server_id: t.server_id, name: t.name}] : tools.filter(g => !(g.server_id === t.server_id && g.name === t.name)))} />
                <span>{t.external ? t.name.slice(server.length + 1) : t.name}<span className="line-clamp-2 text-xs text-muted-foreground" title={t.description}>{t.description}</span></span></label>)}
            </div>) : <p className="text-sm text-muted-foreground">Chưa có tool đọc được đăng ký.</p>}
          </fieldset>
        </TabsContent>
        <TabsContent value="evaluation" className="pt-3">
          <p className="mb-3 text-xs text-muted-foreground">Nhập 6 tình huống. Câu trả lời phải chứa nguyên văn nội dung bắt buộc. Model chạy thật; tool trong đánh giá trả dữ liệu kiểm thử và không thực hiện hành động.</p>
          {cases.map((c, i) => <fieldset key={c.name} className="mb-3 grid gap-2 sm:grid-cols-[1fr_14rem]" disabled={!edit}><legend className="mb-1 text-xs font-medium text-muted-foreground">{c.name}</legend>
            <div><label htmlFor={`case-input-${i}`} className="sr-only">Yêu cầu</label><Textarea id={`case-input-${i}`} rows={2} placeholder="Yêu cầu gửi cho agent" value={c.instruction} onChange={e => setCases(cases.map((x, j) => j === i ? {...x, instruction: e.target.value} : x))} /></div>
            <div><label htmlFor={`case-expected-${i}`} className="sr-only">Nội dung bắt buộc trong câu trả lời</label><Input id={`case-expected-${i}`} placeholder="Nội dung bắt buộc" value={c.expected} onChange={e => setCases(cases.map((x, j) => j === i ? {...x, expected: e.target.value} : x))} /></div>
          </fieldset>)}
          <Button size="sm" disabled={!edit || dirty || cases.some(c => !c.instruction.trim() || !c.expected.trim())} onClick={async () => {
            try { await evaluate.mutateAsync({roomId, agentId: agent.id, configuration_hash: agent.configurationHash, request_id: evaluationId, cases});
              setEvaluationId(crypto.randomUUID()); } catch { /* visible mutation error */ }
          }}>{evaluate.isPending ? "Đang đánh giá…" : "Chạy đánh giá"}</Button>
          {dirty && <p className="mt-2 text-xs text-muted-foreground">Lưu cấu hình trước: đánh giá chạy trên bản đã lưu.</p>}
          {/* The runtime could not get an answer from the model at all: that says nothing about the agent. */}
          {!!results?.length && results.every(c => c.explanation === "openbot_run_error") && <p role="alert" className="mt-3 text-sm text-destructive">
            Chưa đánh giá được: model không trả lời. Đây không phải lỗi của agent. Báo quản trị viên kiểm tra khóa model rồi chạy lại.</p>}
          {results?.map(c => <details key={c.name} className="mt-3 text-sm"><summary>{c.name}: {c.passed ? "Đạt" : "Chưa đạt"}</summary><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{c.actual}</p><p className="text-muted-foreground">{c.explanation}</p></details>)}
        </TabsContent>
        <TabsContent value="release" className="space-y-3 pt-3">
          <p className="text-sm text-foreground">{agentStanding(agent).label}{pendingReview && agent.published ? " · có bản mới chờ quyết định" : ""}</p>
          {pendingReview || agent.published ? <>
            <label htmlFor="agent-decision-note" className="text-sm font-medium">Ghi chú</label>
            <p className="text-xs text-muted-foreground">Cần ghi lý do khi từ chối hoặc thu hồi.</p>
            <Textarea id="agent-decision-note" rows={2} value={note} disabled={busy} onChange={e => setNote(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              {pendingReview && ([['approve', 'Phát hành'], ['reject', 'Từ chối']] as const).map(([decision, label]) =>
                <Button key={decision} size="sm" variant={decision === "approve" ? "default" : "outline"} disabled={busy || (decision === "reject" && !note.trim())} onClick={async () => {
                  try { await decide.mutateAsync({roomId, reviewId: agent.review!.id, decision, version: agent.review!.version, note: note.trim() || "Phát hành sau khi đánh giá đạt."}); setNote(""); } catch { /* visible mutation error */ }
                }}>{label}</Button>)}
              {agent.published && <Button size="sm" variant="destructive" disabled={busy || !note.trim()} onClick={async () => {
                try { await revoke.mutateAsync({roomId, agentId: agent.id, note}); setNote(""); } catch { /* visible mutation error */ }
              }}>Thu hồi</Button>}
            </div>
          </> : <p className="text-sm text-muted-foreground">Chưa có bản nào để phát hành. Khi đánh giá đạt cả 6 ca, bạn phát hành ngay tại đây, không cần quản trị viên duyệt.</p>}
        </TabsContent>
      </Tabs>
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
    </DialogBody>
    <DialogFooter>
      {save.isSuccess && !dirty && <p role="status" className="mr-auto text-xs text-muted-foreground">Đã lưu cấu hình.</p>}
      <Button size="sm" variant="outline" disabled={busy} onClick={onClose}>Đóng</Button>
      <Button size="sm" disabled={!edit || !dirty || !instructions.trim() || !description.trim()} onClick={() => void saveConfiguration()}>{save.isPending ? "Đang lưu…" : "Lưu cấu hình"}</Button>
    </DialogFooter>
  </DialogContent></Dialog>;
}
