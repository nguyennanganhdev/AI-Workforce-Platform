import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

export type AgentConfiguration = { instructions: string; description: string; service_categories: string[];
  mcp_tools: { server_id: string; name: string }[]; knowledge_namespace_ids?: string[]; framework_version?: string; revision_of?: string | null };
export type ManagedAgent = { id: string; name: string; purpose: string; status: string; configuration: AgentConfiguration;
  configurationHash: string; latest_version: { id: string; number: number; hash: string } | null;
  published: boolean; review: { id: string; status: string; version: number; config_hash: string; evaluation: { cases: EvaluationResult[] } } | null };
export type EvaluationInput = { name: string; instruction: string; expected: string; ticket?: Record<string, unknown>; must?: string[];
  must_not?: string[]; must_call?: string[]; must_not_call?: string[]; tool_results?: Record<string, unknown> };
export type EvaluationResult = { name: string; expected: string; actual: string; passed: boolean; explanation: string };
export type AgentManagement = { canManage: boolean; items: ManagedAgent[];
  tools: { server_id: string; name: string; description: string }[]; categories: { code: string; name: string }[] };
export const managedAgentKeys = { all: ["managed-agents"] as const, room: (roomId: string) => ["managed-agents", "room", roomId] as const };
export function managedAgentsQueryOptions(roomId: string) {
  return queryOptions({ queryKey: managedAgentKeys.room(roomId), enabled: !!roomId, refetchInterval: 5000,
    queryFn: async (): Promise<AgentManagement> => (await client(`/api/business/rooms/${encodeURIComponent(roomId)}/agent-management`,
      { headers: businessHeaders(), fallback: "Không tải được agent của nhóm." })).json() });
}
