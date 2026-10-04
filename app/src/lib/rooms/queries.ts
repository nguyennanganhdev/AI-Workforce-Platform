import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

export type ManagementRoom = {id: string; name: string};
export type RoomSession = {id: string; ticket_id: string; ticket_code: string; ticket_title: string; status: string;
  created_at: string; updated_at: string; ticket_status: string; plan_status: string | null;
  runtime?: {phase: string; pauseReason?: string | null} | null};
// A message the Supervisor's room mirrored here carries its session and what kind of step it was.
export type RoomMessage = {id: string; seq: number; sender_user_id: string | null; sender_name?: string;
  sender_agent_id: string | null; body: {text?: string; mentionAgentId?: string; sessionId?: string; kind?: string; routineRunId?: string}; created_at: string;
  mention_status?: string | null};
export type SessionPlan = {id: string; title: string; status: string; version: number; management_note?: string | null;
  proposal: {steps: string[]; performer_role: string; expected_duration: string; conditions: string;
    cost?: {amount: number; currency: string} | null}};
export type TicketSession = {
  session: {id: string; status: string; state_version: number; supervisor_name: string} | null;
  room?: {members: string[]; tasks: {description: string; status: string; agent: string}[]; plan?: SessionPlan | null};
  awaitingManagementApproval?: boolean;
  conversation: {id: string; sender_kind: string; text: string; created_at: string}[];
};
export const roomKeys = {all: ["management-rooms"] as const, detail: (id: string) => ["management-rooms", id] as const,
  session: (ticketId: string) => ["management-rooms", "session", ticketId] as const};
/** Only the sessions of a room: what the menu badge and the bell count, without the room's messages. */
export function roomSessionsQueryOptions(roomId: string) {
  return queryOptions({queryKey: [...roomKeys.detail(roomId), "sessions"] as const, enabled: !!roomId, refetchInterval: 10000,
    queryFn: async (): Promise<RoomSession[]> => (await (await client(`/api/business/rooms/${encodeURIComponent(roomId)}/teams`,
      {headers: businessHeaders(), fallback: "Không tải được phiên điều phối."})).json()).items});
}
/** One ticket's session as management reads it: the plan, who took part, and what the resident said. */
export function ticketSessionQueryOptions(ticketId: string) {
  return queryOptions({queryKey: roomKeys.session(ticketId), enabled: !!ticketId, refetchInterval: 4000,
    queryFn: async (): Promise<TicketSession> => {
      const base = `/api/business/tickets/${encodeURIComponent(ticketId)}`;
      const [session, conversation] = await Promise.all([
        client(`${base}/session`, {headers: businessHeaders(), fallback: "Không tải được phiên."}).then(r => r.json()),
        client(`${base}/conversation`, {headers: businessHeaders(), fallback: "Không tải được trao đổi của cư dân."}).then(r => r.json()),
      ]);
      return {...session, conversation: conversation.items};
    }});
}
export function roomsQueryOptions() {
  return queryOptions({queryKey: roomKeys.all, queryFn: async (): Promise<{items: ManagementRoom[]}> =>
    (await client("/api/business/rooms", {headers: businessHeaders(), fallback: "Không tải được nhóm."})).json()});
}
export function roomQueryOptions(roomId: string) {
  return queryOptions({queryKey: roomKeys.detail(roomId), enabled: !!roomId, refetchInterval: 3000,
    queryFn: async () => {
      const base = `/api/business/rooms/${encodeURIComponent(roomId)}`;
      const messages: RoomMessage[] = [];
      let seq = 0;
      // Read all pages without silently truncating conversations at 100 messages.
      for (;;) {
        const page: {items: RoomMessage[]} = await (await client(`${base}/messages?afterSeq=${seq}&limit=100`,
          {headers: businessHeaders(), fallback: "Không tải được tin nhắn nhóm."})).json();
        messages.push(...page.items);
        if (page.items.length < 100) break;
        const next = page.items.at(-1)!.seq;
        if (next <= seq) throw new Error("Trang tin nhắn không hợp lệ.");
        seq = next;
      }
      const [agents, sessions] = await Promise.all([
        client(`${base}/agents`, {headers: businessHeaders(), fallback: "Không tải được agent."}).then(r => r.json() as Promise<{items: {id: string; name: string; published: boolean; status: string}[]}>),
        client(`${base}/teams`, {headers: businessHeaders(), fallback: "Không tải được phiên điều phối."}).then(r => r.json() as Promise<{items: RoomSession[]}>),
      ]);
      return {messages, agents: agents.items, sessions: sessions.items};
    }});
}
