import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

export type ManagementRoom = {id: string; name: string};
export type RoomSession = {id: string; ticket_code: string; ticket_title: string; status: string;
  runtime?: {phase: string; pauseReason?: string | null} | null};
export type RoomMessage = {id: string; seq: number; sender_user_id: string | null; sender_name?: string;
  sender_agent_id: string | null; body: {text?: string; mentionAgentId?: string}; created_at: string;
  mention_status?: string | null};
export const roomKeys = {all: ["management-rooms"] as const, detail: (id: string) => ["management-rooms", id] as const};
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
