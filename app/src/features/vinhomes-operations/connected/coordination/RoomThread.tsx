import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { IconArrowLeft } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { postRoomMessageMutationOptions } from "@/lib/rooms/mutations";
import type { RoomMessage } from "@/lib/rooms/queries";
import { queryClient } from "@/query-client";
import { mentionStatus } from "./model";
import { Composer, Said, Transcript } from "./parts";

type RoomAgent = { id: string; name: string; published: boolean; status: string };

/** The room's own conversation: management and the room's agents, without the sessions' traffic. */
export function RoomThread({ roomId, name, messages, agents, userId, onBack }: {
  roomId: string; name: string; messages: RoomMessage[]; agents: RoomAgent[]; userId: string; onBack: () => void;
}) {
  const post = useMutation(postRoomMessageMutationOptions(queryClient));
  const request = useRef<{ signature: string; id: string } | null>(null);
  const active = agents.filter((a) => a.published && a.status === "active");
  const own = messages.filter((m) => !m.body.sessionId);
  async function send(text: string, agentId: string) {
    // A typed @name counts when it names exactly one agent; the backend rechecks who may be asked.
    if (!agentId) {
      const named = active.filter((a) => text.includes(`@${a.name}`));
      if (named.length === 1) agentId = named[0].id;
    }
    const signature = JSON.stringify([roomId, text, agentId]);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    try {
      await post.mutateAsync({ roomId, text, agentId, requestId: request.current.id });
      request.current = null;
      return true;
    } catch { return false; }
  }
  return (
    <>
      <header className="flex items-center gap-3 border-b border-border px-4 py-3 md:px-6">
        <Button size="icon" variant="ghost" className="md:hidden" aria-label="Về danh sách phiên" onClick={onBack}><IconArrowLeft /></Button>
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">{name}</h2>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {active.length ? `Trao đổi chung của nhóm · ${active.map((a) => a.name).join(", ")}` : "Trao đổi chung của nhóm"}
          </p>
        </div>
      </header>
      <Transcript label="Tin nhắn nhóm" count={own.length}>
        {!own.length && <p className="py-12 text-center text-sm text-muted-foreground">Chưa có tin nhắn. Chọn một agent rồi đặt câu hỏi đầu tiên.</p>}
        {own.map((m) => {
          const agent = agents.find((a) => a.id === m.sender_agent_id);
          const mine = m.sender_user_id === userId;
          const asked = agents.find((a) => a.id === m.body.mentionAgentId);
          return (
            <Said key={m.id} at={m.created_at} mine={mine} agent={!!agent} who={mine ? "Bạn" : agent?.name || m.sender_name || "Thành viên"}
              footer={asked ? `${m.body.routineRunId ? "Theo lịch · " : ""}Hỏi @${asked.name}${m.mention_status ? ` · ${mentionStatus[m.mention_status] || m.mention_status}` : ""}` : undefined}>
              {m.body.text || ""}
            </Said>
          );
        })}
      </Transcript>
      <Composer agents={active} agentLabel="Cả nhóm" error={post.error?.message} onSend={send}
        placeholder="Nhắn cho nhóm, hoặc chọn một agent để hỏi…" hint="Enter để gửi · Shift+Enter để xuống dòng" />
    </>
  );
}
