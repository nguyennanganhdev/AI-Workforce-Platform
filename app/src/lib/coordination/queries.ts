import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";

export const coordinationKeys = {
  all: ["coordination"] as const,
  controls: (teamId: string) => ["coordination", "controls", teamId] as const,
};
export type SessionControls = {
  canControl: boolean;
  runtime: { phase: string; pauseReason?: string | null; stateVersion: number } | null;
  items: { request_id: string; operation: string; status: string; result?: { reason?: string | null } }[];
};
export function businessHeaders(): Record<string, string> {
  return import.meta.env.VITE_ALLOW_DEMO_BACKEND === "true"
    ? { "X-Demo-Actor": sessionStorage.getItem("operations.local-actor") || "management" } : {};
}
export function sessionControlsQueryOptions(teamId: string) {
  return queryOptions({
    queryKey: coordinationKeys.controls(teamId), enabled: !!teamId, refetchInterval: 3000,
    queryFn: async (): Promise<SessionControls> => (await client(`/api/business/teams/${encodeURIComponent(teamId)}/controls`,
      { headers: businessHeaders(), fallback: "Không tải được điều khiển phiên." })).json(),
  });
}
