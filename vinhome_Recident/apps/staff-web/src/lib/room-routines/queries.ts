import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

/**
 * A schedule of one agent in a management room: at that time the instruction is posted in the room
 * under its owner's name, mentioning the agent. `schedule` is null for an expression this screen did
 * not make. `last_status` null with a `last_run_at` means the agent has not answered yet.
 */
export type RoomRoutine = { id: string; agent_id: string; agent_name: string; owner_name: string; instruction: string; cron: string;
  enabled: boolean; next_run_at: string; schedule: { hour: number; minute: number; days: number[] } | null;
  last_status: "succeeded" | "failed" | "skipped" | null; last_run_at: string | null; last_error: string | null };

export const roomRoutineKeys = { room: (roomId: string) => ["room-routines", roomId] as const };
export function roomRoutinesQueryOptions(roomId: string) {
  return queryOptions({ queryKey: roomRoutineKeys.room(roomId), enabled: !!roomId, refetchInterval: 30000,
    queryFn: async (): Promise<{ items: RoomRoutine[]; timezone: string }> =>
      (await client(`/api/business/rooms/${encodeURIComponent(roomId)}/routines`,
        { headers: businessHeaders(), fallback: "Không tải được lịch chạy." })).json() });
}
