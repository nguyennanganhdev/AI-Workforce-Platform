import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { managedAgentKeys, type AgentConfiguration, type EvaluationInput, type EvaluationResult } from "@/lib/agent-management/queries";
import { roomKeys } from "@/lib/rooms/queries";

const base = (room: string) => `/api/business/rooms/${encodeURIComponent(room)}`;
export function createManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, name, purpose, requestId}: {roomId: string; name: string; purpose: "specialist" | "supervisor"; requestId: string}): Promise<{id: string}> =>
    (await client(`${base(roomId)}/agents`, {method: "POST", body: {name, purpose, instructions: "Chưa cấu hình. Agent này chưa được phép chạy.", idempotency_key: requestId}, headers: businessHeaders(), fallback: "Không tạo được nháp agent."})).json(),
    onSuccess: () => queryClient.invalidateQueries({queryKey: managedAgentKeys.all}) });
}
export function configureManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, agentId, configuration}: {roomId: string; agentId: string; configuration: AgentConfiguration}): Promise<void> => {
    await client(`${base(roomId)}/agents/${encodeURIComponent(agentId)}/configuration`, {method: "PUT", body: configuration, headers: businessHeaders(), fallback: "Không lưu được cấu hình agent."});
  }, onSuccess: () => queryClient.invalidateQueries({queryKey: managedAgentKeys.all}) });
}
export function constructManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, agentId, ...body}: {roomId: string; agentId: string; role: string; description: string; service_categories: string[]; configuration_hash: string; revision_of?: string | null; request_id: string}): Promise<void> => {
    await client(`${base(roomId)}/agents/${encodeURIComponent(agentId)}/construct`, {method: "POST", body, headers: businessHeaders(), fallback: "Factory chưa tạo được cấu hình agent."});
  }, onSuccess: () => queryClient.invalidateQueries({queryKey: managedAgentKeys.all}) });
}
export function evaluateManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, agentId, ...body}: {roomId: string; agentId: string; configuration_hash: string; request_id: string; cases: EvaluationInput[]}): Promise<{passed: boolean; cases: EvaluationResult[]}> =>
    (await client(`${base(roomId)}/agents/${encodeURIComponent(agentId)}/evaluate`, {method: "POST", body, headers: businessHeaders(), fallback: "Đánh giá chưa hoàn tất."})).json(),
    onSuccess: () => queryClient.invalidateQueries({queryKey: managedAgentKeys.all}) });
}
export function decideManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, reviewId, ...body}: {roomId: string; reviewId: string; decision: "approve" | "reject"; version: number; note: string}): Promise<void> => {
    await client(`${base(roomId)}/agent-reviews/${encodeURIComponent(reviewId)}/decision`, {method: "POST", body, headers: businessHeaders(), fallback: "Không quyết định được bản agent này."});
  }, onSuccess: async () => {
    await Promise.all([queryClient.invalidateQueries({queryKey: managedAgentKeys.all}),
      queryClient.invalidateQueries({queryKey: roomKeys.all})]);
  } });
}
export function revokeManagedAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({roomId, agentId, note}: {roomId: string; agentId: string; note: string}): Promise<void> => {
    await client(`${base(roomId)}/agents/${encodeURIComponent(agentId)}/release/revoke`, {method: "POST", body: {note}, headers: businessHeaders(), fallback: "Không thu hồi được agent."});
  }, onSuccess: async () => {
    await Promise.all([queryClient.invalidateQueries({queryKey: managedAgentKeys.all}),
      queryClient.invalidateQueries({queryKey: roomKeys.all})]);
  } });
}
