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
/** Management's three decisions inside a session. Each one changes what the session waits for. */
function sessionAction<T>(queryClient: QueryClient, send: (input: T) => Promise<unknown>) {
  return mutationOptions({mutationFn: send, onSuccess: () => queryClient.invalidateQueries({queryKey: roomKeys.all})});
}
export function decidePlanMutationOptions(queryClient: QueryClient) {
  return sessionAction(queryClient, ({planId, decision, version, note}: {planId: string; decision: "approve" | "reject"; version: number; note: string}) =>
    client(`/api/business/plans/${encodeURIComponent(planId)}/management-decision`, {method: "POST", headers: businessHeaders(),
      body: {decision, version, note}, fallback: "Không ghi được quyết định."}));
}
export function askSessionAgentMutationOptions(queryClient: QueryClient) {
  return sessionAction(queryClient, ({ticketId, text, agentId, requestId}: {ticketId: string; text: string; agentId?: string; requestId: string}) =>
    client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/questions`, {method: "POST", headers: businessHeaders(),
      body: {text, client_message_id: requestId, ...(agentId ? {agent_id: agentId} : {})}, fallback: "Không gửi được câu hỏi cho agent."}));
}
export function closeSessionMutationOptions(queryClient: QueryClient) {
  return sessionAction(queryClient, ({ticketId, version}: {ticketId: string; version: number}) =>
    client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/close-approval`, {method: "POST", headers: businessHeaders(),
      body: {version}, fallback: "Không đóng được phiên."}));
}
