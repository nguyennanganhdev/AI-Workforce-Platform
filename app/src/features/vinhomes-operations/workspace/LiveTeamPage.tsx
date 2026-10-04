import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { queryClient } from "@/query-client";
import { roomsQueryOptions, roomQueryOptions } from "@/lib/rooms/queries";
import { postRoomMessageMutationOptions } from "@/lib/rooms/mutations";
import { TeamView } from "@/features/vinhomes-operations/workspace/TeamPage";
import type { WorkflowCase } from "@/features/vinhomes-operations/workspace/model";
import { SessionControls } from "@/features/vinhomes-operations/connected/SessionControls";
import { ManagedAgents } from "@/features/vinhomes-operations/connected/ManagedAgents";

const sessionStatus: Record<string, string> = {queued: 'chờ Supervisor', running: 'đang điều phối', waiting: 'chờ phản hồi', completed: 'đã đóng', failed: 'lỗi điều phối', cancelled: 'đã hủy'};
const sessionPause: Record<string, string> = {
  'planner:analysis_ready': 'agent đã phân tích xong, chờ BQL lập phương án',
  'planner:no_specialist_available': 'chưa có agent chuyên môn, BQL xử lý',
  'planner:planner_model_not_configured': 'Supervisor chưa có model, BQL xử lý',
  AGENT_FAILURE: 'agent không trả lời được, BQL xử lý',
};
export function LiveTeamPage({userId, tickets}: {userId: string; tickets: (Pick<WorkflowCase, 'id' | 'title' | 'stage'> & {severity: string})[]}) {
  const listed = useQuery(roomsQueryOptions());
  const rooms = listed.data?.items || [];
  const [selected, setRoomId] = useState("");
  const roomId = selected || rooms[0]?.id || "";
  const details = useQuery(roomQueryOptions(roomId));
  const posting = useMutation(postRoomMessageMutationOptions(queryClient));
  const pending = useRef<{signature: string; requestId: string} | null>(null);
  const agents = details.data?.agents || [];
  const sessions = details.data?.sessions || [];
  const mentionLabels: Record<string, string> = {queued: "Chờ agent", running: "Agent đang trả lời", done: "Đã trả lời", failed: "Lượt chạy thất bại; gửi câu hỏi mới để thử lại", refused: "Agent chưa được phát hành hoặc đã thu hồi"};
  const messages = (details.data?.messages || []).map(m => ({id: m.id, at: m.created_at,
    author: m.sender_user_id === userId ? "Bạn" : m.sender_name || agents.find(a => a.id === m.sender_agent_id)?.name || "Thành viên",
    text: (m.body.text || "") + (m.mention_status ? `\n${mentionLabels[m.mention_status] || m.mention_status}` : ""), agentId: m.body.mentionAgentId}));
  const error = listed.error || details.error || posting.error;
  async function send(text: string, agentId: string) {
    if (posting.isPending) return false;
    // Resolve typed mentions only among published room members. Explicit selection
    // disambiguates agents with the same display name; the backend rechecks authority.
    if (!agentId) {
      const mentioned = agents.filter(a => a.published && a.status === 'active' && text.includes(`@${a.name}`));
      if (mentioned.length === 1) agentId = mentioned[0].id;
    }
    const signature = JSON.stringify([roomId, text.trim(), agentId]);
    if (pending.current?.signature !== signature) pending.current = {signature, requestId: crypto.randomUUID()};
    try {
      await posting.mutateAsync({roomId, text: text.trim(), agentId, requestId: pending.current.requestId});
      pending.current = null;
      return true;
    } catch { return false; }
  }
  const room = rooms.find(r => r.id === roomId);
  return <>
    {error && <p role="alert" className="ws-notice error">{error.message}</p>}
    <label>Nhóm điều phối<select value={roomId} onChange={e => setRoomId(e.target.value)}>
      {!rooms.length && <option value="">Chưa có nhóm được cấp</option>}
      {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select></label>
    {roomId && <ManagedAgents key={`agents:${roomId}`} roomId={roomId} />}
    {!!sessions.length && <section aria-label="Phiên điều phối của nhóm">
      <h3>Phiên điều phối ({sessions.length})</h3>
      <ul>{sessions.slice(0, 20).map(s => <li key={s.id}>
        {s.ticket_code} · {s.ticket_title} · {sessionStatus[s.status] || s.status}
        {s.runtime?.phase === 'paused' && ` · ${sessionPause[s.runtime.pauseReason || ''] || 'Supervisor tạm dừng, BQL xử lý tiếp'}`}
        <SessionControls teamId={s.id} />
      </li>)}</ul>
    </section>}
    {room ? <TeamView key={`chat:${roomId}`} contentOnly room={{...room, scope: 'thành viên trong nhóm', messages}} agents={agents.filter(a => a.published && a.status === 'active')} tickets={tickets}
      connectedAccount={{role: 'manager', scope: 'thành viên trong nhóm'}} onSend={send} /> :
      <p className="ws-empty">Tài khoản chưa được thêm vào nhóm điều phối. Không có tin nhắn mẫu.</p>}
  </>;
}
