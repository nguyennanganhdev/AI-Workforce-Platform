import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { Bot, Check, FileText, FolderOpen, History, MessageSquarePlus, Plug, Send, Settings2 } from 'lucide-react';
import { Streamdown } from 'streamdown';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { roomsQueryOptions } from '@/lib/rooms/queries';
import { businessHeaders } from '@/lib/coordination/queries';
import { tryClient } from '@/lib/client';
import { ActivityLog, OpsSelect, StatusBadge } from './ui';
import { unsigned } from './coordination/model';
import './ask-agent.css';

type Chat = { id: string; room_id: string; name: string; updated_at: string; created_at: string };
type Agent = { id: string; name: string; purpose: string; published: boolean; status: string };
type Source = { id: string; title: string; status?: string; last_error?: string; tools: { name: string; effect?: string; description?: string; allowed?: boolean }[] };
type Used = { tool: string; name: string; external: boolean; effect: string };
type Message = { id: string; sender_user_id?: string; sender_agent_id?: string; created_at: string; mention_status?: string; files?: { id: string; name: string }[]; body: { text?: string; mentionAgentId?: string }; used_sources?: Used[]; route?: {automatic: boolean} };
type ChatDetail = { id: string; room_id: string; name: string; agents: Agent[]; messages: Message[]; sources: { server_id: string; enabled: boolean }[] };
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await tryClient(`/api/business${path}`, { method: init.method, body: typeof init.body === 'string' ? JSON.parse(init.body) : init.body,
    headers: { ...businessHeaders(), ...Object.fromEntries(new Headers(init.headers).entries()) } });
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Không thực hiện được thao tác. Thử lại.');
  return body as T;
}
const toolLabel = (source: Used) => {
  if (source.external) return source.name;
  if (source.tool.startsWith('reporting.')) return 'Tra cứu báo cáo';
  if (source.tool.startsWith('knowledge.')) return 'Tìm kiếm tri thức';
  return ({ 'security.camera.read': 'Tra danh mục camera', 'security.contact.read': 'Tra đầu mối an ninh' }[source.tool] || (source.name.includes('.') || source.name === source.tool ? 'Tra cứu dữ liệu vận hành' : source.name));
};

export function AskAgent({ userId }: { userId: string }) {
  const cache = useQueryClient();
  const rooms = useQuery(roomsQueryOptions());
  const [roomId, setRoom] = useState(() => new URLSearchParams(location.search).get('room') || '');
  const parent = roomId || rooms.data?.items[0]?.id || '';
  const [chatId, setChat] = useState(() => new URLSearchParams(location.search).get('chat') || '');
  const [agentId, setAgent] = useState('');
  const [text, setText] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const requestId = useRef<string>('');
  const createId = useRef(crypto.randomUUID());
  const transcript = useRef<HTMLDivElement>(null);
  const history = useQuery({ queryKey: ['personal-chats', parent], enabled: !!parent, queryFn: () => api<{ items: Chat[] }>(`/personal-chats?roomId=${encodeURIComponent(parent)}`) });
  const detail = useQuery({ queryKey: ['personal-chat', chatId], enabled: !!chatId, refetchInterval: 3000, queryFn: () => api<ChatDetail>(`/personal-chats/${encodeURIComponent(chatId)}`) });
  const available = useQuery({ queryKey: ['ask-agents', parent], enabled: !!parent, queryFn: () => api<{ items: Agent[] }>(`/rooms/${encodeURIComponent(parent)}/agents`) });
  const connections = useQuery({ queryKey: ['ask-connections', parent], enabled: !!parent, queryFn: () => api<{ items: Source[] }>(`/rooms/${encodeURIComponent(parent)}/connections`) });
  const confirmations = useQuery({ queryKey: ['ask-confirmations', chatId], enabled: !!chatId, refetchInterval: 3000, queryFn: () => api<{ items: { id: string; connection_title?: string; tool_name: string; description?: string; arguments: unknown; status: string; result?: {text?: string; error?: string} }[] }>(`/rooms/${encodeURIComponent(chatId)}/external-calls`) });
  const allAgents = detail.data?.agents || available.data?.items || [];
  const agents = allAgents.filter(a => a.status === 'active' && a.published);
  const selectedSources = detail.data?.sources.filter(s => s.enabled) || [];
  function select(id: string) { setChat(id); setHistoryOpen(false); historyUrl(id); }
  function historyUrl(id: string, scope = parent) { const params = new URLSearchParams(location.search); if (id) params.set('chat', id); else params.delete('chat'); if (scope) params.set('room', scope); window.history.replaceState(null, '', `${location.pathname}${params.size ? '?' + params : ''}`); }
  async function ensureChat() {
    if (chatId) return chatId;
    const created = await api<{ id: string }>('/personal-chats', { method: 'POST', body: JSON.stringify({ room_id: parent, request_id: createId.current }) });
    setChat(created.id); historyUrl(created.id); return created.id;
  }
  const send = useMutation({ mutationFn: async () => {
    const id = await ensureChat();
    if (!requestId.current) requestId.current = crypto.randomUUID();
    let selected = agentId;
    const mentioned = agents.filter(a => text.includes(`@${a.name}`));
    if (!selected && mentioned.length === 1) selected = mentioned[0].id;
    await api(`/personal-chats/${encodeURIComponent(id)}/messages`, { method: 'POST', body: JSON.stringify({ text: text.trim(), mention_agent_id: selected || null, client_message_id: requestId.current }) });
    requestId.current = ''; setText('');
    await Promise.all([cache.invalidateQueries({ queryKey: ['personal-chat', id] }), cache.invalidateQueries({ queryKey: ['personal-chats'] })]);
  } });
  const sourceChange = useMutation({ mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => { const chat = await ensureChat(); await api(`/personal-chats/${encodeURIComponent(chat)}/sources`, { method: 'PUT', body: JSON.stringify({ server_id: id, enabled }) }); await cache.invalidateQueries({ queryKey: ['personal-chat', chat] }); } });
  const decide = useMutation({ mutationFn: async ({ id, decision }: { id: string; decision: 'approve' | 'cancel' }) => { await api(`/rooms/${encodeURIComponent(chatId)}/external-calls/${encodeURIComponent(id)}/decision`, { method: 'POST', body: JSON.stringify({ decision }) }); await Promise.all([cache.invalidateQueries({ queryKey: ['ask-confirmations'] }), cache.invalidateQueries({ queryKey: ['personal-chat'] })]); } });
  useEffect(() => { transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: 'instant' }); }, [chatId, detail.data?.messages.length]);
  const error = rooms.error || history.error || detail.error || available.error || confirmations.error || send.error || sourceChange.error || decide.error;
  const newChat = (scope = parent) => { setChat(''); setHistoryOpen(false); historyUrl('', scope); createId.current = crypto.randomUUID(); requestId.current = ''; setText(''); setAgent(''); };
  const historyView = <><Button variant="outline" onClick={() => newChat()}><MessageSquarePlus size={16} />Cuộc trò chuyện mới</Button>{(rooms.data?.items.length || 0) > 1 && <OpsSelect label="Đơn vị" value={parent} options={(rooms.data?.items || []).map(r => ({ value: r.id, label: r.name }))} onValueChange={id => { setRoom(id); newChat(id); }} />}
    {history.isPending ? <Skeleton className="h-32" /> : !history.data?.items.length ? <p className="ask-muted">Chưa có cuộc trò chuyện. Gửi câu hỏi đầu tiên cho agent.</p> : ['Hôm nay', '7 ngày qua', 'Trước đó'].map((label, index) => {
      const now = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' });
      const rows = history.data.items.filter(c => { const today = new Date(c.updated_at).toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }) === now; const recent = Date.now() - Date.parse(c.updated_at) < 7 * 86400000; return index === 0 ? today : index === 1 ? !today && recent : !recent; });
      return rows.length > 0 && <section key={label}><h2>{label}</h2>{rows.map(c => <button key={c.id} className="ask-history-item" aria-current={chatId === c.id ? 'page' : undefined} onClick={() => select(c.id)}>{c.name}</button>)}</section>;
    })}</>;
  const sourcesView = <><section><h2>Agent trả lời được</h2>{available.isPending ? <Skeleton className="h-28" /> : agents.length ? agents.map(a => <button key={a.id} className="ask-agent-item" onClick={() => setAgent(a.id)} aria-pressed={agentId === a.id}><span className="ops-icon-tile" data-agent><Bot size={16} /></span><span><strong>{a.name}</strong><small>{a.purpose === 'supervisor' ? 'Điều phối câu hỏi' : 'Trả lời theo nhiệm vụ và khả năng đã cấp'}</small></span></button>) : <p className="ask-muted">Chưa có agent được phát hành.</p>}</section><section><h2>Nguồn ngoài (MCP)</h2>{connections.isPending ? <Skeleton className="h-28" /> : connections.error ? <div role="alert" className="ask-muted">Không tải được nguồn ngoài.<Button variant="ghost" onClick={() => void connections.refetch()}>Thử lại</Button></div> : (connections.data?.items || []).map(s => <div className="ask-source" key={s.id}><span className="ops-icon-tile"><FolderOpen size={16} /></span><span><strong>{s.title}</strong><small>{s.tools?.some(t => t.effect === 'write' || t.effect === 'external-write') ? 'Đọc, thao tác ghi cần bạn duyệt' : 'Chỉ đọc'}</small>{s.status === 'suspended' ? <StatusBadge tone="wait">Tạm ngưng</StatusBadge> : s.status === 'pending' ? <StatusBadge tone="wait">Chờ duyệt</StatusBadge> : s.last_error && <StatusBadge tone="danger">Không kết nối được</StatusBadge>}</span><Switch aria-label={`Dùng ${s.title} cho hội thoại này`} checked={selectedSources.some(item => item.server_id === s.id)} disabled={sourceChange.isPending || s.status === 'suspended' || s.status === 'pending'} onCheckedChange={enabled => sourceChange.mutate({ id: s.id, enabled })} /></div>)}<Link to="/operations/agents" search={{ view: 'library', room: parent } as never} className="ask-add-source"><Plug size={16} />Thêm nguồn ngoài</Link></section></>;
  const last = detail.data?.messages.at(-1);
  return <div className="ask-workspace"><aside className="ask-history">{historyView}</aside><div className="ask-main"><div className="ask-mobile-tools"><Button variant="outline" onClick={() => setHistoryOpen(true)}><History size={16} />Hội thoại</Button><Button variant="outline" onClick={() => setSourcesOpen(true)}><Settings2 size={16} />Agent và nguồn</Button></div>
    {error && <div className="live-error" role="alert">{error.message}<Button variant="outline" onClick={() => { void detail.refetch(); void history.refetch(); }}>Thử lại</Button></div>}
    <div className="ask-transcript" ref={transcript}>{detail.isPending && chatId ? <Skeleton className="h-40" /> : !detail.data?.messages.length ? <div className="ask-welcome"><span className="ops-icon-tile" data-agent><Bot size={20} /></span><h2>Bạn cần hỗ trợ điều gì?</h2><p>Hỏi số liệu, tìm tài liệu hoặc nhờ agent soạn nội dung trong phạm vi đơn vị của bạn.</p></div> : detail.data.messages.map(m => {
      const answering = allAgents.find(a => a.id === m.sender_agent_id);
      const mine = m.sender_user_id === userId;
      return <article key={m.id} className={mine ? 'ask-question' : 'ask-answer'}>{answering && m.route && <ActivityLog agent={m.route.automatic ? "Supervisor" : "Bạn"} time={m.created_at}>{m.route.automatic ? "chuyển câu hỏi cho " : "hỏi "}<strong>{answering.name}</strong></ActivityLog>}{!mine && <div className="ask-answer-author"><span className="ask-bot-avatar"><Bot size={16} /></span><strong>{answering?.name || 'Agent'}</strong><time>{new Date(m.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</time></div>}<div className={mine ? 'ask-question-bubble' : 'ask-answer-bubble'}>{mine ? m.body.text : <Streamdown>{unsigned(m.body.text || '', answering?.name || '')}</Streamdown>}{m.files?.map(f => <a key={f.id} href={`/api/business/rooms/${encodeURIComponent(chatId)}/files/${f.id}/content`} className="ask-file"><FileText size={16} />{f.name}</a>)}</div>{answering && <div className="ask-used"><span>Đã dùng</span>{m.used_sources?.length ? m.used_sources.map((source, i) => <span key={`${source.tool}-${i}`} className="ask-source-chip" data-external={source.external}>{source.external ? <Plug size={14} /> : <FileText size={14} />}{toolLabel(source)}</span>) : <span>Không dùng nguồn dữ liệu</span>}{m.used_sources?.some(s => s.external) && <span>nguồn ngoài nền tảng</span>}</div>}</article>;
    })}{last?.sender_user_id && ['queued', 'running'].includes(last.mention_status || '') && <div className="ask-wait"><Bot size={16} />Agent đang chuẩn bị câu trả lời…</div>}
    {confirmations.data?.items.filter(c => c.status === 'pending').map(c => <article key={c.id} className="ask-write-confirmation"><StatusBadge tone="wait">Thao tác ghi chờ bạn cho phép</StatusBadge><h3>{c.connection_title || 'Nguồn ngoài'}</h3><strong>{c.description || c.tool_name.split('.').at(-1)?.replace(/_/g, ' ')}</strong><p>Chỉ cho phép thao tác này với dữ liệu dưới đây:</p><pre>{JSON.stringify(c.arguments, null, 2)}</pre><div><Button variant="outline" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, decision: 'cancel' })}>Hủy</Button><Button disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, decision: 'approve' })}><Check size={16} />Cho phép</Button></div></article>)}{confirmations.data?.items.filter(c => c.status !== "pending").map(c => <article key={c.id} className="ask-write-result"><StatusBadge tone={c.status === "succeeded" ? "ok" : c.status === "failed" || c.status === "uncertain" ? "danger" : "neutral"}>{({succeeded:"Đã thực hiện",cancelled:"Đã hủy",failed:"Thao tác không thành công",uncertain:"Chưa xác định được kết quả",executing:"Đang thực hiện",expired:"Xác nhận đã hết hạn"} as Record<string,string>)[c.status] || c.status}</StatusBadge><strong>{c.connection_title}</strong><p>{c.description}</p>{c.result?.text && <p>{c.result.text}</p>}{c.result?.error && <p>{c.result.error}</p>}{c.status === "uncertain" && <p>Kiểm tra kết quả ở nguồn ngoài trước khi yêu cầu thao tác mới.</p>}</article>)}</div>
    <form className="ask-composer" onSubmit={e => { e.preventDefault(); if (text.trim() && !send.isPending) send.mutate(); }}><Textarea aria-label="Câu hỏi cho agent" value={text} onChange={e => { setText(e.target.value); requestId.current = ''; }} placeholder="Hỏi bất cứ điều gì. Gõ @ để chọn agent, gõ / để dùng nguồn ngoài." maxLength={10000} disabled={send.isPending || !parent} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (text.trim() && !send.isPending) send.mutate(); } if (e.key === '/') setSourcesOpen(true); }} /><div className="ask-composer-footer"><OpsSelect label="Agent trả lời" value={agentId || 'auto'} options={[{ value: 'auto', label: 'Supervisor tự chọn' }, ...agents.map(a => ({ value: a.id, label: a.name }))]} onValueChange={id => setAgent(id === 'auto' ? '' : id)} /><Button variant="outline" type="button" onClick={() => setSourcesOpen(true)}><Plug size={16} />{selectedSources.length} nguồn ngoài</Button><Button type="submit" size="icon" aria-label="Gửi câu hỏi" disabled={send.isPending || !text.trim() || !parent}><Send size={18} /></Button></div></form>
  </div><aside className="ask-sources">{sourcesView}</aside><Sheet open={historyOpen} onOpenChange={setHistoryOpen}><SheetContent side="left" className="ops-ui ask-sheet"><SheetHeader><SheetTitle>Hội thoại riêng</SheetTitle></SheetHeader>{historyView}</SheetContent></Sheet><Sheet open={sourcesOpen} onOpenChange={setSourcesOpen}><SheetContent side="right" className="ops-ui ask-sheet"><SheetHeader><SheetTitle>Agent và nguồn ngoài</SheetTitle></SheetHeader>{sourcesView}</SheetContent></Sheet></div>;
}
