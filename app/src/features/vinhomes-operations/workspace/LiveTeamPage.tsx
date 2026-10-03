import { useEffect, useRef, useState } from "react";
import { TeamView } from "./TeamPage";
import type { WorkflowCase, RoomMessage } from "./model";

type Room = {id: string; name: string};
// A coordination session of this room: one ticket the Supervisor is working on.
type Session = {id: string; ticket_code: string; ticket_title: string; status: string; runtime?: {phase: string; pauseReason?: string | null} | null};
const sessionStatus: Record<string, string> = {queued: 'chờ Supervisor', running: 'đang điều phối', waiting: 'chờ phản hồi', completed: 'đã đóng', failed: 'lỗi điều phối', cancelled: 'đã hủy'};
const sessionPause: Record<string, string> = {
  'planner:analysis_ready': 'agent đã phân tích xong, chờ BQL lập phương án',
  'planner:no_specialist_available': 'chưa có agent chuyên môn, BQL xử lý',
  'planner:planner_model_not_configured': 'Supervisor chưa có model, BQL xử lý',
  AGENT_FAILURE: 'agent không trả lời được, BQL xử lý',
};
type Message = {id: string; seq: number; sender_user_id: string | null; sender_name?: string; sender_agent_id: string | null; body: {text?: string}; created_at: string};
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/business${path}`, {...init, credentials: "include", headers: {"Content-Type": "application/json"}});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Không thực hiện được thao tác.");
  return data;
}

export function LiveTeamPage({userId, tickets}: {userId: string; tickets: (Pick<WorkflowCase, 'id' | 'title' | 'stage'> & {severity: string})[]}) {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomId, setRoomId] = useState("");
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [agents, setAgents] = useState<{id: string; name: string}[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const pending = useRef<{body: string; key: string} | null>(null);
  const sending = useRef(false);
  useEffect(() => {
    let active = true;
    api<{items: Room[]}>("/rooms").then(data => {
      if (active) {setRooms(data.items); setRoomId(data.items[0]?.id || "");}
    }).catch(e => {if (active) setError(e.message);});
    return () => {active = false;};
  }, []);
  useEffect(() => {
    const current = ++generation.current;
    setMessages([]); setAgents([]); setSessions([]); pending.current = null;
    if (!roomId) return;
    let loading = false;
    async function refresh() {
      if (loading) return;
      loading = true;
      try {
        const all: Message[] = [];
        let seq = 0;
        while (true) {
          const data = await api<{items: Message[]}>(`/rooms/${encodeURIComponent(roomId)}/messages?afterSeq=${seq}&limit=100`);
          if (current !== generation.current) return;
          all.push(...data.items);
          if (data.items.length < 100) break;
          const next = data.items.at(-1)!.seq;
          if (next <= seq) throw new Error("Không đọc được trang tin nhắn tiếp theo.");
          seq = next;
        }
        const members = await api<{items: {id: string; name: string}[]}>(`/rooms/${encodeURIComponent(roomId)}/agents`);
        if (current !== generation.current) return;
        setAgents(members.items);
        const teams = await api<{items: Session[]}>(`/rooms/${encodeURIComponent(roomId)}/teams`);
        if (current !== generation.current) return;
        setSessions(teams.items);
        setMessages(all.map(m => ({id: m.id, at: m.created_at, author: m.sender_user_id === userId ? 'Bạn' : m.sender_name || members.items.find(a => a.id === m.sender_agent_id)?.name || 'Thành viên', text: m.body.text || ''})));
      } catch (e) {if (current === generation.current) setError(e instanceof Error ? e.message : "Không tải được nhóm.");}
      finally {loading = false;}
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => {generation.current++; clearInterval(timer);};
  }, [roomId, userId]);
  async function send(text: string, agentId: string) {
    if (sending.current) return false;
    sending.current = true; setError("");
    const current = generation.current;
    const body = JSON.stringify({text: text.trim(), mention_agent_id: agentId || null});
    if (pending.current?.body !== body) pending.current = {body, key: crypto.randomUUID()};
    try {
      const result = await api<Message>(`/rooms/${encodeURIComponent(roomId)}/messages`, {method: "POST", body: JSON.stringify({...JSON.parse(body), client_message_id: pending.current.key})});
      if (generation.current === current) {
        setMessages(previous => previous.some(m => m.id === result.id) ? previous : [...previous, {id: result.id, at: result.created_at, author: 'Bạn', text: text.trim()}]);
        pending.current = null;
      }
      return true;
    } catch (e) {if (generation.current === current) setError(e instanceof Error ? e.message : "Không gửi được tin nhắn."); return false;}
    finally {sending.current = false;}
  }
  const room = rooms.find(r => r.id === roomId);
  return <>
    {error && <p role="alert" className="ws-notice error">{error}</p>}
    <label>Nhóm điều phối<select value={roomId} onChange={e => setRoomId(e.target.value)}>
      {!rooms.length && <option value="">Chưa có nhóm được cấp</option>}
      {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select></label>
    {!!sessions.length && <section aria-label="Phiên điều phối của nhóm">
      <h3>Phiên điều phối ({sessions.length})</h3>
      <ul>{sessions.slice(0, 20).map(s => <li key={s.id}>
        {s.ticket_code} · {s.ticket_title} · {sessionStatus[s.status] || s.status}
        {s.runtime?.phase === 'paused' && ` · ${sessionPause[s.runtime.pauseReason || ''] || 'Supervisor tạm dừng, BQL xử lý tiếp'}`}
      </li>)}</ul>
    </section>}
    {room ? <TeamView key={roomId} room={{...room, scope: 'thành viên trong nhóm', messages}} agents={agents} tickets={tickets}
      connectedAccount={{role: 'manager', scope: 'thành viên trong nhóm'}} onSend={send} /> :
      <p className="ws-empty">Tài khoản chưa được thêm vào nhóm điều phối. Không có tin nhắn mẫu.</p>}
  </>;
}
