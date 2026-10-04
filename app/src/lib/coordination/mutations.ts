import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders, coordinationKeys } from "@/lib/coordination/queries";

export type ControlInput = { teamId: string; operation: "pause" | "resume" | "stop"; expected_version: number; request_id: string };
export function controlSessionMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async ({ teamId, ...body }: ControlInput): Promise<void> => {
      await client(`/api/business/teams/${encodeURIComponent(teamId)}/controls`,
        { method: "POST", body, headers: businessHeaders(), fallback: "Không điều khiển được phiên. Hãy tải lại trạng thái." });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: coordinationKeys.all }),
  });
}
