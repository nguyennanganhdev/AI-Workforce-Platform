import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { roomKeys } from "@/lib/rooms/queries";
export function postRoomMessageMutationOptions(queryClient: QueryClient) {
  return mutationOptions({mutationFn: async ({roomId, text, agentId, requestId}: {roomId: string; text: string; agentId: string; requestId: string}) => {
    await client(`/api/business/rooms/${encodeURIComponent(roomId)}/messages`, {method: "POST", headers: businessHeaders(),
      body: {text, mention_agent_id: agentId || null, client_message_id: requestId}, fallback: "Không gửi được tin nhắn nhóm."});
  }, onSuccess: (_, {roomId}) => queryClient.invalidateQueries({queryKey: roomKeys.detail(roomId)})});
}
