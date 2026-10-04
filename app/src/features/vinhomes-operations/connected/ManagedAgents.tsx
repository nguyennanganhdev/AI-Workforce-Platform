import { Fragment, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconRobot, IconChevronRight, IconPlus } from "@tabler/icons-react";
import { PageEmpty, PageRows, PageSection } from "@/components/layout/page-shell";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { managedAgentsQueryOptions, type AgentManagement, type ManagedAgent, type EvaluationInput } from "@/lib/agent-management/queries";
import { configureManagedAgentMutationOptions, constructManagedAgentMutationOptions, createManagedAgentMutationOptions,
  decideManagedAgentMutationOptions, evaluateManagedAgentMutationOptions, revokeManagedAgentMutationOptions } from "@/lib/agent-management/mutations";
import { queryClient } from "@/query-client";

export function ManagedAgents({ roomId }: { roomId: string }) {
  const agents = useQuery(managedAgentsQueryOptions(roomId));
  const create = useMutation(createManagedAgentMutationOptions(queryClient));
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [createId, setCreateId] = useState(() => crypto.randomUUID());
  return <PageSection title="Agent của nhóm" description="BQL cấu hình, đánh giá và phát hành agent trong workspace được giao. Admin có thể kiểm tra và thu hồi toàn hệ thống."
    action={agents.data?.canManage ? <Button size="sm" onClick={() => setCreating(true)}><IconPlus />Tạo agent</Button> : undefined}>
    {agents.isPending ? null : agents.error ? <p role="alert">{agents.error.message}</p> : !agents.data?.items.length ?
      <PageEmpty>Chưa có agent. Tạo nháp và đánh giá trước khi đưa vào phòng.</PageEmpty> : <PageRows>
        {agents.data.items.map((agent, i) => <Fragment key={agent.id}>{i > 0 && <Separator />}
          <Item size="sm" render={<button type="button" onClick={() => setSelected(agent.id)} />}>
            <ItemMedia variant="icon"><IconRobot /></ItemMedia><ItemContent><ItemTitle>{agent.name}</ItemTitle>
              <ItemDescription>{agent.purpose === "supervisor" ? "Supervisor" : "Agent chuyên môn"} / {agent.latest_version ? `Phiên bản ${agent.latest_version.number}` : "Nháp"} / {agent.published ? "Đã phát hành" : "Chưa phát hành"}</ItemDescription>
            </ItemContent><ItemActions><IconChevronRight className="size-4" /></ItemActions>
          </Item></Fragment>)}
      </PageRows>}
    <Dialog open={creating} onOpenChange={setCreating}><DialogContent><DialogHeader><DialogTitle>Tạo agent cho nhóm</DialogTitle>
      <DialogDescription>Nháp chỉ chạy trong đánh giá. Cần phát hành để Supervisor mời vào phiên.</DialogDescription></DialogHeader>
      <DialogBody><label htmlFor="agent-name">Tên agent</label><Input id="agent-name" value={name} maxLength={160} onChange={e => setName(e.target.value)} />
        {create.error && <p role="alert" className="text-destructive">{create.error.message}</p>}</DialogBody>
      <DialogFooter><Button disabled={!name.trim() || create.isPending} onClick={async () => {
        try { const result = await create.mutateAsync({roomId, name: name.trim(), purpose: "specialist", requestId: createId});
          setCreating(false); setName(""); setCreateId(crypto.randomUUID()); setSelected(result.id); } catch { /* visible mutation error */ }
      }}>{create.isPending ? "Đang tạo…" : "Tạo nháp"}</Button></DialogFooter></DialogContent></Dialog>
    {!!agents.data && !!selected && <AgentEditor key={`${roomId}:${selected}`} roomId={roomId} agent={agents.data.items.find(a => a.id === selected)}
      catalogue={agents.data} onClose={() => setSelected("")} />}
  </PageSection>;
}

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
  async function saveConfiguration() {
    if (!agent) return;
    try { await save.mutateAsync({roomId, agentId: agent.id, configuration: {instructions, description,
      service_categories: categories, mcp_tools: tools, knowledge_namespace_ids: agent.configuration.knowledge_namespace_ids || [],
      framework_version: "openbot-chat-completions", revision_of: baseVersion}}); } catch { /* visible mutation error */ }
  }
  return <Dialog open onOpenChange={open => {if (!open && !busy) onClose();}}><DialogContent>
    <DialogHeader><DialogTitle>{agent.name}</DialogTitle><DialogDescription>
      {baseVersion ? `Cấu hình nháp cho phiên bản ${Number(agent.latest_version?.number) + 1}. Phiên đang chạy giữ bản đã ghim.` : "Cấu hình nháp, đánh giá rồi quyết định phát hành."}
    </DialogDescription></DialogHeader>
    <DialogBody className="overflow-y-auto space-y-5">
      <div className="space-y-2"><label htmlFor="agent-description">Nhiệm vụ</label><Textarea id="agent-description" value={description} maxLength={2000} disabled={!edit} onChange={e => setDescription(e.target.value)} />
        <label htmlFor="agent-role">Vai trò cho Factory</label><Input id="agent-role" value={role} disabled={!edit} onChange={e => setRole(e.target.value)} />
        <Button size="sm" variant="outline" disabled={!edit || !description.trim() || !role.trim()} onClick={async () => {
          try { await construct.mutateAsync({roomId, agentId: agent.id, role, description, service_categories: categories,
            configuration_hash: agent.configurationHash, revision_of: baseVersion, request_id: constructionId});
            setConstructionId(crypto.randomUUID()); } catch { /* visible mutation error */ }
        }}>{construct.isPending ? "Factory đang tạo…" : "Tạo bằng Factory"}</Button>
        {construct.isSuccess && <p role="status">Factory đã lưu nháp trên máy chủ. Kiểm tra chỉ dẫn trước khi đánh giá.</p>}
      </div>
      <fieldset disabled={!edit}><legend className="font-medium mb-2">Danh mục phục vụ</legend>
        {catalogue.categories.map(c => <label key={c.code} className="flex items-center gap-2 mb-2"><input type="checkbox" checked={categories.includes(c.code)} onChange={e => setCategories(e.target.checked ? [...categories, c.code] : categories.filter(x => x !== c.code))} />{c.name}</label>)}
      </fieldset>
      <fieldset disabled={!edit}><legend className="font-medium mb-2">Tool đọc được cấp</legend>
        {catalogue.tools.length ? catalogue.tools.map(t => <label key={`${t.server_id}/${t.name}`} className="flex gap-2 mb-2"><input type="checkbox"
          checked={tools.some(g => g.server_id === t.server_id && g.name === t.name)} onChange={e => setTools(e.target.checked ? [...tools, {server_id: t.server_id, name: t.name}] : tools.filter(g => !(g.server_id === t.server_id && g.name === t.name)))} />
          <span>{t.name}<span className="block text-muted-foreground">{t.description}</span></span></label>) : <p>Chưa có tool đọc được đăng ký.</p>}
      </fieldset>
      <div className="space-y-2"><label htmlFor="agent-instructions">Chỉ dẫn</label><Textarea id="agent-instructions" rows={8} value={instructions} maxLength={50000} disabled={!edit} onChange={e => setInstructions(e.target.value)} />
        <Button size="sm" variant="outline" disabled={!edit || !instructions.trim() || !description.trim()} onClick={() => void saveConfiguration()}>{save.isPending ? "Đang lưu…" : "Lưu cấu hình"}</Button>
        {save.isSuccess && <p role="status">Đã lưu. Đánh giá sẽ chạy trên cấu hình đã lưu ở máy chủ.</p>}</div>
      <section><h3 className="font-medium">Ca đánh giá</h3><p className="text-muted-foreground mb-3">Nhập ít nhất 6 tình huống. Kết quả phải chứa nguyên văn nội dung bắt buộc. Model chạy thật; kết quả tool trong bộ đánh giá là dữ liệu ca kiểm thử, không thực hiện hành động.</p>
        {cases.map((c, i) => <fieldset key={c.name} className="space-y-2 mb-4" disabled={!edit}><legend>{c.name}</legend>
          <label htmlFor={`case-input-${i}`}>Yêu cầu</label><Textarea id={`case-input-${i}`} value={c.instruction} onChange={e => setCases(cases.map((x, j) => j === i ? {...x, instruction: e.target.value} : x))} />
          <label htmlFor={`case-expected-${i}`}>Nội dung bắt buộc trong câu trả lời</label><Input id={`case-expected-${i}`} value={c.expected} onChange={e => setCases(cases.map((x, j) => j === i ? {...x, expected: e.target.value} : x))} />
        </fieldset>)}
        <Button size="sm" disabled={!edit || cases.some(c => !c.instruction.trim() || !c.expected.trim())} onClick={async () => {
          try { await evaluate.mutateAsync({roomId, agentId: agent.id, configuration_hash: agent.configurationHash, request_id: evaluationId, cases});
            setEvaluationId(crypto.randomUUID()); } catch { /* visible mutation error */ }
        }}>{evaluate.isPending ? "Đang đánh giá…" : "Chạy đánh giá"}</Button>
        {results?.map(c => <details key={c.name} className="mt-3"><summary>{c.name}: {c.passed ? "Đạt" : "Chưa đạt"}</summary><p className="whitespace-pre-wrap">{c.actual}</p><p>{c.explanation}</p></details>)}
      </section>
      {(pendingReview || agent.published) && <div className="space-y-2"><label htmlFor="agent-decision-note">Lý do quyết định</label><Textarea id="agent-decision-note" value={note} disabled={busy} onChange={e => setNote(e.target.value)} />
        {pendingReview && <div className="flex gap-2 flex-wrap">{([['approve', 'Phát hành'], ['reject', 'Từ chối']] as const).map(([decision, label]) =>
          <Button key={decision} size="sm" variant={decision === "approve" ? "default" : "outline"} disabled={busy || !note.trim()} onClick={async () => {
            try { await decide.mutateAsync({roomId, reviewId: agent.review!.id, decision, version: agent.review!.version, note}); } catch { /* visible mutation error */ }
          }}>{label}</Button>)}</div>}
        {agent.published && <Button size="sm" variant="destructive" disabled={busy || !note.trim()} onClick={async () => {
          try { await revoke.mutateAsync({roomId, agentId: agent.id, note}); } catch { /* visible mutation error */ }
        }}>Thu hồi</Button>}</div>}
      {error && <p role="alert" className="text-destructive">{error.message}</p>}
    </DialogBody><DialogFooter><Button size="sm" variant="outline" disabled={busy} onClick={onClose}>Đóng</Button></DialogFooter>
  </DialogContent></Dialog>;
}
