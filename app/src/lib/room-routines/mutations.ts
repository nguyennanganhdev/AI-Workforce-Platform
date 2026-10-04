import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { tryClient, type ClientOptions } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { roomRoutineKeys } from "@/lib/room-routines/queries";

const base = (roomId: string) => `/api/business/rooms/${encodeURIComponent(roomId)}/routines`;

/** A refusal here says what to do next (the cap, an agent no longer published), so it is shown as it came. */
async function ask(path: string, options: ClientOptions, fallback: string): Promise<Response> {
  const response = await tryClient(path, { ...options, headers: businessHeaders() });
  if (response.ok) return response;
  const detail = (await response.json().catch(() => ({}))).detail;
  throw new Error(typeof detail === "string" && [403, 409, 422, 503].includes(response.status) ? detail : fallback);
}
const refresh = (queryClient: QueryClient, roomId: string) => queryClient.invalidateQueries({ queryKey: roomRoutineKeys.room(roomId) });

export function createRoomRoutineMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({ roomId, ...body }: { roomId: string; agent_id: string; instruction: string; hour: number; minute: number; days: number[] }) => {
    await ask(base(roomId), { method: "POST", body }, "Không đặt được lịch.");
  }, onSuccess: (_, { roomId }) => refresh(queryClient, roomId) });
}
export function switchRoomRoutineMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({ roomId, id, enabled }: { roomId: string; id: string; enabled: boolean }) => {
    await ask(`${base(roomId)}/${encodeURIComponent(id)}/enabled`, { method: "PUT", body: { enabled } }, enabled ? "Không bật được lịch." : "Không tắt được lịch.");
  }, onSuccess: (_, { roomId }) => refresh(queryClient, roomId) });
}
export function removeRoomRoutineMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({ roomId, id }: { roomId: string; id: string }) => {
    await ask(`${base(roomId)}/${encodeURIComponent(id)}`, { method: "DELETE" }, "Không xóa được lịch.");
  }, onSuccess: (_, { roomId }) => refresh(queryClient, roomId) });
}
