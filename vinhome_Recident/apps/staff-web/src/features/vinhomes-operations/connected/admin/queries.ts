import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query";
import { tryClient, type ClientOptions } from "@/lib/client";
import { businessHeaders } from "@/lib/business-headers";
import type { AuditEvent } from "@/lib/admin/queries";
export type Overview = {
  open_tickets: number;
  overdue_tickets: number;
  pending_accounts: number;
  requests_per_day: { date: string; count: number }[];
  pending_accounts_preview: { name: string; email: string }[];
};
export type EnrichedAudit = AuditEvent & {
  target_label?: string;
  result?: "success" | "failed" | "recorded";
};
export async function adminRequest<T>(
  path: string,
  options: ClientOptions = {},
): Promise<T> {
  const response = await tryClient(`/api/business${path}`, {
    ...options,
    headers: businessHeaders(),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "Không thực hiện được thao tác. Thử lại hoặc liên hệ quản trị viên.",
    );
  return body as T;
}
export const overviewOptions = () =>
  queryOptions({
    queryKey: ["admin", "overview"],
    queryFn: () => adminRequest<Overview>("/admin/overview"),
    refetchInterval: 30_000,
  });
export type AuditFilters = {
  kind: string;
  from: string;
  to: string;
  actor: string;
  action: string;
  search: string;
  result: string;
};
export function filteredAuditOptions(filters: AuditFilters) {
  return infiniteQueryOptions({
    queryKey: ["admin", "audit", filters],
    initialPageParam: null as { at: string; id: string } | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({
        limit: "50",
        ...Object.fromEntries(
          Object.entries(filters).filter(([, value]) => value),
        ),
        ...(pageParam ? { before: pageParam.at, before_id: pageParam.id } : {}),
      });
      return adminRequest<{
        items: EnrichedAudit[];
        kinds: string[];
        actions: string[];
      }>(`/admin/audit-events?${params}`);
    },
    getNextPageParam: (last) => {
      const event = last.items.at(-1);
      return last.items.length === 50 && event
        ? { at: event.created_at, id: event.id }
        : undefined;
    },
  });
}
