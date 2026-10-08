import { useRef } from "react";
import { IconArrowLeft } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { useMutation } from "@tanstack/react-query";
import { postRoomMessageMutationOptions, ROOM_FILE_ACCEPT, roomFilesRefusal } from "@/lib/rooms/mutations";
import { roomFileUrl, type RoomMessage } from "@/lib/rooms/queries";
import { queryClient } from "@/query-client";
import { askedLine, unsigned } from "./model";
import { Composer, Said, Transcript } from "./parts";

type RoomAgent = { id: string; name: string; published: boolean; status: string };

/** The room's own conversation: management and the room's agents, without the sessions' traffic. */
export function RoomThread({ roomId, name, messages, agents, userId, onBack }: {
  roomId: string; name: string; messages: RoomMessage[]; agents: RoomAgent[]; userId: string; onBack?: () => void;
}) {
  const post = useMutation(postRoomMessageMutationOptions(queryClient));
  const request = useRef<{ signature: string; id: string } | null>(null);
  const active = agents.filter((a) => a.published && a.status === "active");
  const own = messages.filter((m) => !m.body.sessionId);
  async function send(text: string, agentId: string, files: File[]) {
    // A typed @name counts when it names exactly one agent; the backend rechecks who may be asked.
    if (!agentId) {
      const named = active.filter((a) => text.includes(`@${a.name}`));
      if (named.length === 1) agentId = named[0].id;
    }
    const signature = JSON.stringify([roomId, text, agentId, files.map((file) => [file.name, file.size, file.lastModified])]);
    if (request.current?.signature !== signature) request.current = { signature, id: crypto.randomUUID() };
    try {
      await post.mutateAsync({ roomId, text, agentId, requestId: request.current.id, files });
      request.current = null;
      return true;
    } catch { return false; }
  }
  return (
    <>
      <header className="coord-header">
        {onBack && <Button size="icon" variant="ghost" className="md:hidden" aria-label="Về danh sách phiên" onClick={onBack}><IconArrowLeft /></Button>}
        <h2 className="truncate text-[15px] font-semibold text-foreground">{name}</h2>
        <p className="basis-full truncate text-xs text-muted-foreground">{active.length ? `${active.length} agent sẵn sàng trả lời` : "Nhóm chưa có agent nào được phát hành"}</p>
      </header>
      <Transcript label="Tin nhắn nhóm" count={own.length}>
        {!own.length && <div className="coord-welcome"><h2>Bạn cần hỗ trợ điều gì?</h2><p>Chọn một agent để hỏi, hoặc mở một phiên đang chờ bạn ở thanh bên.</p></div>}
        {own.map((m) => {
          const agent = agents.find((a) => a.id === m.sender_agent_id);
          const mine = m.sender_user_id === userId;
          const asked = agents.find((a) => a.id === m.body.mentionAgentId);
          return (
            <Said key={m.id} at={m.created_at} mine={mine} agent={!!agent} who={mine ? "Bạn" : agent?.name || m.sender_name || "Thành viên"}
              footer={asked ? `${m.body.routineRunId ? "Theo lịch · " : ""}${askedLine(asked.name, m.mention_status)}` : undefined}
              files={m.files?.map((file) => ({ id: file.id, name: file.name, bytes: file.size_bytes, href: roomFileUrl(roomId, file.id),
                image: file.mime_type.startsWith("image/") ? roomFileUrl(roomId, file.id, true) : undefined }))}>
              {agent ? unsigned(m.body.text || "", agent.name) : m.body.text || ""}
            </Said>
          );
        })}
      </Transcript>
      <Composer agents={active} agentLabel="Cả nhóm" error={post.error?.message} onSend={send} attach={{ accept: ROOM_FILE_ACCEPT, refusal: roomFilesRefusal }}
        placeholder="Nhắn cho nhóm, hoặc chọn một agent để hỏi…" />
    </>
  );
}
