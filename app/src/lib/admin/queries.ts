import { infiniteQueryOptions, mutationOptions, queryOptions, type QueryClient } from "@tanstack/react-query";
import { tryClient, type ClientOptions } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

export type Account = { id: string; name: string; email: string; role: string; status: string; administrator: boolean; management_unit_id: string | null };
export type Unit = { id: string; code: string; name: string; status: string; buildings: string[]; staff: number; open_tickets: number;
  groups: { id: string; name: string; members: number; agents: number; connections: number }[] };
export type RoleModel = { role: "reception" | "supervisor" | "specialist" | "factory" | "embedding"; configured: boolean;
  running: boolean | null; model: string | null; provider: string | null };
export type AuditEvent = { id: string; created_at: string; event_type: string; initiator_kind: string; actor: string | null;
  target_type: string; target_id: string; payload: Record<string, unknown> };

/** `spoken`: this endpoint words its refusals for the person (the account API does), so they are shown as they are. */
async function ask(path: string, options: ClientOptions, fallback: string, spoken = false): Promise<Response> {
  const response = await tryClient(`/api/business${path}`, { ...options, headers: businessHeaders() });
  if (response.ok) return response;
  const detail = spoken ? (await response.json().catch(() => ({}))).detail : undefined;
  throw new Error(typeof detail === "string" ? detail : fallback);
}

export const adminKeys = { accounts: ["admin", "accounts"] as const, units: ["admin", "units"] as const,
  models: ["admin", "models"] as const, audit: (kind: string) => ["admin", "audit", kind] as const };

export function accountsQueryOptions() {
  return queryOptions({ queryKey: adminKeys.accounts, queryFn: async (): Promise<{ accounts: Account[]; units: { id: string; name: string }[] }> => {
    const [accounts, units] = await Promise.all([ask("/auth/accounts", {}, "Không tải được danh sách tài khoản."),
      ask("/auth/management-units", {}, "Không tải được danh sách đơn vị.")]);
    return { accounts: (await accounts.json()).items, units: (await units.json()).items };
  } });
}
export function createAccountMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async (body: { name: string; email: string; password: string; role: string; management_unit_id?: string }) => {
    await ask("/auth/accounts", { method: "POST", body }, "Không tạo được tài khoản. Kiểm tra email đã dùng chưa và mật khẩu đủ 12 ký tự.", true);
  }, onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.accounts }) });
}
export function updateAccountMutationOptions(queryClient: QueryClient) {
  return mutationOptions({ mutationFn: async ({ id, ...body }: { id: string; role: string; status: "active" | "suspended"; management_unit_id?: string }) => {
    await ask(`/auth/accounts/${encodeURIComponent(id)}`, { method: "PATCH", body }, "Không cập nhật được tài khoản.", true);
  }, onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.accounts }) });
}
export function unitsQueryOptions() {
  return queryOptions({ queryKey: adminKeys.units, queryFn: async (): Promise<Unit[]> =>
    (await (await ask("/admin/units", {}, "Không tải được danh sách đơn vị quản lý.")).json()).items });
}
export function modelsQueryOptions() {
  return queryOptions({ queryKey: adminKeys.models, queryFn: async (): Promise<RoleModel[]> =>
    (await (await ask("/admin/models", {}, "Không tải được trạng thái model.")).json()).items });
}
export function auditQueryOptions(kind: string) {
  return infiniteQueryOptions({ queryKey: adminKeys.audit(kind), initialPageParam: "",
    queryFn: async ({ pageParam }): Promise<{ items: AuditEvent[]; kinds: string[] }> => {
      const query = new URLSearchParams({ limit: "50", ...(kind ? { kind } : {}), ...(pageParam ? { before: pageParam } : {}) });
      return (await ask(`/admin/audit-events?${query}`, {}, "Không tải được nhật ký.")).json();
    },
    getNextPageParam: (last) => (last.items.length === 50 ? last.items[last.items.length - 1].created_at : undefined) });
}
