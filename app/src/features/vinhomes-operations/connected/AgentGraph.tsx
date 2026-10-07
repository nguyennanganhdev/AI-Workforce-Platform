import { memo, useEffect, useMemo, useRef, useState } from "react";
import { Background, BaseEdge, EdgeLabelRenderer, Handle, Position, ReactFlow, ReactFlowProvider, getBezierPath, useReactFlow, type EdgeProps, type Node, type NodeProps, type Edge } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { Bot, MessagesSquare, Maximize2, Minimize2, Minus, Plus, Scan, ShieldCheck, UserRound, Workflow, X } from "lucide-react";
import { businessHeaders } from "@/lib/coordination/queries";
import { Button } from "@/components/ui/button";
import type { AgentManagement, ManagedAgent } from "@/lib/agent-management/queries";
import { AgentBadge, agentDisplayConfiguration, agentRole, agentStanding, toolLabel } from "./agent-display";
import "@xyflow/react/dist/style.css";

type Metric = {today:number;running:number;seven_days:number;response_seconds?:number;model_name?:string};
type LiveGraph = {metrics:Record<string,Metric>;sessions:{agent_id:string;id:string;title:string;location:string}[];summary:{running_sessions:number;received_today:number;waiting:number;response_seconds?:number}};
type GraphData = {metrics?:Metric; title: string; subtitle: string; agent?: ManagedAgent; catalogue: AgentManagement };
const GraphNode = memo(function GraphNode({data, type, selected}: NodeProps<Node<GraphData>>) {
  const Icon = type === "entry" ? data.title === "Cư dân" ? UserRound : MessagesSquare : type === "supervisor" ? Workflow : type === "human" ? ShieldCheck : Bot;
  const state = data.agent ? agentStanding(data.agent) : null;
  return <div className={`agent-graph-node agent-graph-node--${type}${selected ? " is-selected" : ""}`}>
    {type !== "entry" && <Handle type="target" position={Position.Left} />}
    <div className="agent-node-heading"><span className="agent-icon-tile"><Icon size={16} strokeWidth={1.75} /></span><span className="agent-node-text"><strong>{data.title}</strong><small>{data.subtitle}</small></span>{state && <span className={`agent-node-dot ${state.live ? "is-published" : ""}`} title={state.label} />}</div>
    {data.agent && <div className="agent-node-footer"><span>{data.metrics?.model_name || state?.label}</span>{data.metrics?.running ? <span className="agent-node-active">{data.metrics.running} phiên</span> : <span>{data.metrics ? "đang rảnh" : "đang tải số liệu"}</span>}</div>}
    {type !== "human" && <Handle type="source" position={Position.Right} />}
  </div>;
});
const FlowEdge = memo(function FlowEdge(props: EdgeProps) {
  const [path, x, y] = getBezierPath(props);
  const state = props.data?.state || "idle";
  return <><BaseEdge path={path} className={`agent-flow-edge agent-flow-edge--${state}`} style={{stroke:state==='live'?'var(--agent)':state==='human'?'var(--wait)':'var(--line-strong)',strokeWidth:state==='idle'?1.5:2,strokeDasharray:state==='idle'?'4 5':'none'}} />{state === "live" && <circle r={3} className="agent-flow-dot" style={{offsetPath:`path("${path}")`}} />}{props.data?.label && <EdgeLabelRenderer><span className={`agent-edge-label agent-edge-label--${state}`} style={{transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`}}>{String(props.data.label)}</span></EdgeLabelRenderer>}</>;
});
const nodeTypes = {entry: GraphNode, agent: GraphNode, supervisor: GraphNode, human: GraphNode};
const edgeTypes = {flow: FlowEdge};
function GraphControls() { const flow = useReactFlow(); return <div className="agent-graph-controls"><Button variant="outline" size="icon" aria-label="Phóng to" title="Phóng to" onClick={() => void flow.zoomIn()}><Plus /></Button><Button variant="outline" size="icon" aria-label="Thu nhỏ" title="Thu nhỏ" onClick={() => void flow.zoomOut()}><Minus /></Button><Button variant="outline" size="icon" aria-label="Vừa màn hình" title="Vừa màn hình" onClick={() => void flow.fitView({padding: .15})}><Scan /></Button></div>; }
export function AgentGraph({catalogue, roomId, onEdit}: {catalogue: AgentManagement; roomId:string; onEdit: (id: string) => void}) {
  const [metrics,setMetrics] = useState<Record<string,Metric>>({}); const [connected,setConnected] = useState(false);
  const [live,setLive]=useState<LiveGraph>();
  useEffect(() => {
    let disposed=false; let generation=0; let controller:AbortController|undefined; let retry:ReturnType<typeof setTimeout>|undefined;
    async function subscribe() {
      if(disposed || document.hidden) return;
      const requestGeneration=++generation; controller=new AbortController();
      try {
        const response=await fetch(`/api/business/rooms/${encodeURIComponent(roomId)}/agent-graph/events`,{headers:businessHeaders(),signal:controller.signal});
        if(!response.ok || !response.body) throw new Error("Graph is unavailable");
        const reader=response.body.getReader();const decoder=new TextDecoder();let buffer="";
        for(;;) {const chunk=await reader.read();if(chunk.done) break;buffer+=decoder.decode(chunk.value,{stream:true});let boundary;while((boundary=buffer.indexOf("\n\n"))>=0) {const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);const data=frame.split("\n").find(line=>line.startsWith("data: "));if(data) {const parsed=JSON.parse(data.slice(6));if(parsed.metrics) {setMetrics(parsed.metrics);setLive(parsed);setConnected(true);}}}}
      } catch {if(!disposed && requestGeneration === generation) setConnected(false);}
      if(!disposed && requestGeneration === generation && !document.hidden) retry=setTimeout(subscribe,5000);
    }
    const visibility=() => {generation++;controller?.abort();if(retry) clearTimeout(retry);setConnected(false);if(!document.hidden) void subscribe();};
    document.addEventListener("visibilitychange",visibility);void subscribe();
    return () => {disposed=true;controller?.abort();if(retry) clearTimeout(retry);document.removeEventListener("visibilitychange",visibility);};
  },[roomId]);
  useEffect(()=>{if(connected)return;const controller=new AbortController();const poll=async()=>{try{const r=await fetch(`/api/business/rooms/${encodeURIComponent(roomId)}/agent-graph`,{headers:businessHeaders(),signal:controller.signal});if(r.ok){const data=await r.json();setMetrics(data.metrics);setLive(data);}}catch{/* Subscription reconnects; preserve the last known figures. */}};void poll();const timer=setInterval(poll,10000);return()=>{controller.abort();clearInterval(timer);};},[roomId,connected]);
  const [selected, setSelected] = useState(""); const [full, setFull] = useState(false); const canvas = useRef<HTMLDivElement>(null);
  useEffect(() => { const close = (e: KeyboardEvent) => { if(e.key === "Escape") {setSelected(""); setFull(false);} }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  const visible = catalogue.items.filter(a=>a.purpose === 'supervisor' || a.published && a.status === 'active');
  const topology = visible.map(a => `${a.id}:${a.purpose}:${a.published}:${agentDisplayConfiguration(a).service_categories?.join(",")}`).join("|");
  const positions = useMemo(() => {
    const g = new dagre.graphlib.Graph(); g.setGraph({rankdir: "LR", ranksep: 64, nodesep: 40}); g.setDefaultEdgeLabel(() => ({}));
    const supervisor = visible.find(a => a.purpose === "supervisor"); const specialists = visible.filter(a => a.purpose !== "supervisor");
    const ids = [...visible.map(a => a.id), ...(supervisor ? ["entry-resident", "entry-ask", "reception", "approval"] : [])];
    for(const id of ids) g.setNode(id, {width: id === supervisor?.id ? 232 : id.startsWith("entry") || id === "approval" ? 160 : 208, height: 96});
    if(supervisor) {g.setEdge("entry-resident", "reception"); g.setEdge("reception", supervisor.id); g.setEdge("entry-ask", supervisor.id); for(const a of specialists) g.setEdge(supervisor.id, a.id);}
    dagre.layout(g); const result = new Map(ids.map(id => [id, {x: g.node(id).x - g.node(id).width / 2, y: g.node(id).y - 48}]));
    if(supervisor) {const p = result.get(supervisor.id)!; result.set("approval", {x: p.x + 36, y: p.y + 208});}
    return result;
  }, [topology]);
  const supervisor = catalogue.items.find(a => a.purpose === "supervisor");
  const nodes: Node<GraphData>[] = visible.map(a => ({id: a.id, type: a.purpose === "supervisor" ? "supervisor" : "agent", position: positions.get(a.id)!, selected: selected === a.id, data: {title: a.name, subtitle: agentRole(a, catalogue.categories), agent: a, catalogue,metrics:metrics[a.id]}, ariaLabel: `${a.name}, ${agentStanding(a).label}, ${metrics[a.id] ? `${metrics[a.id].running} phiên đang chạy` : "đang tải số liệu"}`, style: {width: a.purpose === "supervisor" ? 232 : 208}}));
  if(supervisor) nodes.push(...[{id:"entry-resident",type:"entry",title:"Cư dân",subtitle:"gửi yêu cầu"},{id:"reception",type:"agent",title:"Lễ tân",subtitle:"Tiếp nhận yêu cầu"},{id:"entry-ask",type:"entry",title:"Bạn hỏi agent",subtitle:"trò chuyện riêng"},{id:"approval",type:"human",title:"Bạn duyệt",subtitle:live?.summary ? `${live.summary.waiting} phương án chờ` : "phương án cần quyết định"}].map(n => ({id:n.id,type:n.type,position:positions.get(n.id)!,data:{title:n.title,subtitle:n.subtitle,catalogue},ariaLabel:n.title,style:{width:160}})));
  const edges: Edge[] = supervisor ? [{id:"entry",source:"entry-resident",target:"reception",type:"flow",data:{state:"idle"}},{id:"reception",source:"reception",target:supervisor.id,type:"flow",data:{state:"idle"}},{id:"ask",source:"entry-ask",target:supervisor.id,type:"flow",data:{state:"idle"}},...visible.filter(a => a.purpose !== "supervisor").map(a => ({id:`s-${a.id}`,source:supervisor.id,target:a.id,type:"flow",data:{state:metrics[a.id]?.running ? "live" : "idle",label:metrics[a.id]?.running ? `${metrics[a.id].running} phiên` : undefined}})),{id:"approval",source:supervisor.id,target:"approval",type:"flow",data:{state:live?.summary.waiting ? "human" : "idle",label:live?.summary.waiting ? `${live.summary.waiting} chờ duyệt` : undefined}}] : [];
  const agent = catalogue.items.find(a => a.id === selected); const standing = agent && agentStanding(agent);
  return <div ref={canvas} className={`agent-graph-canvas${full ? " is-fullscreen" : ""}`} onKeyDown={event => {if(!["ArrowLeft","ArrowRight"].includes(event.key)) return;const current=(event.target as HTMLElement).closest("[data-id]")?.getAttribute("data-id") || selected;const next=event.key === "ArrowRight" ? edges.find(e => e.source === current)?.target : edges.find(e => e.target === current)?.source;if(next) {event.preventDefault();setSelected(next);canvas.current?.querySelector<HTMLElement>(`[data-id="${CSS.escape(next)}"]`)?.focus();}}}>
    <div className="agent-graph-pills"><span>{visible.filter(a => a.published).length} agent đang phát hành</span><span>{connected ? "Trực tiếp" : "Đang kết nối số liệu"}</span>{live?.summary && <><span>{live.summary.running_sessions} phiên đang chạy</span>{live.summary.response_seconds !== undefined && <span>Phản hồi trung bình {live.summary.response_seconds.toLocaleString('vi-VN',{maximumFractionDigits:1})} giây</span>}</>}</div>
    <Button className="agent-graph-fullscreen" variant="outline" onClick={() => setFull(!full)}>{full ? <Minimize2 /> : <Maximize2 />}{full ? "Thu gọn" : "Toàn màn hình"}</Button>
    <ReactFlowProvider><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} nodesDraggable={false} nodesConnectable={false} elementsSelectable fitView minZoom={.5} maxZoom={1.5} onNodeClick={(_, n) => setSelected(n.data.agent ? n.id : "")} onPaneClick={() => setSelected("")}><Background gap={20} size={1} /><GraphControls /></ReactFlow></ReactFlowProvider>
    <div className="agent-graph-legend"><span className="agent-legend-line is-live" />đang có phiên chạy<span className="agent-legend-line" />phạm vi đã cấu hình</div>
    {agent && <aside className="agent-inspector" aria-label={`Chi tiết ${agent.name}`}><header><span className="agent-icon-tile"><Bot /></span><div><h2>{agent.name}</h2><AgentBadge label={standing!.label} tone={standing!.tone} /></div><Button variant="ghost" size="icon" title="Đóng chi tiết" aria-label="Đóng chi tiết" onClick={() => setSelected("")}><X /></Button></header>{metrics[agent.id] && <section><h3>Hôm nay</h3><div className="agent-inspector-metrics"><div><strong>{metrics[agent.id].today}</strong><small>phiên</small></div><div><strong>{metrics[agent.id].running}</strong><small>đang chạy</small></div>{metrics[agent.id].response_seconds !== undefined && <div><strong>{metrics[agent.id].response_seconds!.toLocaleString("vi-VN",{maximumFractionDigits:1})} giây</strong><small>phản hồi</small></div>}</div></section>}<section><h3>Nhiệm vụ</h3><p>{agentDisplayConfiguration(agent).description || "Chưa có mô tả nhiệm vụ."}</p></section><section><h3>Khả năng</h3>{(agentDisplayConfiguration(agent).mcp_tools || []).map(grant => {const tool = catalogue.tools.find(t => t.server_id === grant.server_id && t.name === grant.name); return tool ? <p key={tool.name}>{toolLabel(tool)}{tool.external && <span className="agent-owner-tag">MCP</span>}</p> : null;})}{!agentDisplayConfiguration(agent).mcp_tools?.length && <p>Chưa cấp công cụ.</p>}</section>{agentDisplayConfiguration(agent).skill_ids?.length ? <section><h3>Kỹ năng</h3>{catalogue.skills?.filter(s=>agentDisplayConfiguration(agent).skill_ids?.includes(s.id)).map(s=><p key={s.id}>{s.name}</p>)}</section> : null}<section><h3>Phiên đang chạy</h3>{live?.sessions.filter(s=>s.agent_id===agent.id).map(s=><a className="agent-session-link" key={s.id} href={`/operations/team?session=${s.id}`}>{s.title}<small>{s.location}</small></a>)}{!live?.sessions.some(s=>s.agent_id===agent.id) && <p>Chưa có phiên yêu cầu đang chạy.</p>}</section><footer><a href="/operations/team">Xem các phiên</a>{catalogue.canManage && <Button onClick={() => onEdit(agent.id)}>Mở trang soạn</Button>}</footer></aside>}
  </div>;
}
