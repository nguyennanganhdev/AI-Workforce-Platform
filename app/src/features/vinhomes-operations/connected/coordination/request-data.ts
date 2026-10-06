import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

export type RequestTicket = { id: string; code: string; title: string; description: string; status: string; version: number;
  priority: string; category_id: string; management_unit_id: string; building_id: string | null; unit_code?: string | null;
  resolution_due_at?: string | null; created_at?: string; updated_at: string };
export type RequestCatalog = { buildings: { id: string; name: string; code: string }[]; serviceCategories: { id: string; name: string }[];
  staff: { id: string; name?: string; employee_code: string }[] };
export type RequestOrder = { id: string; status: string; version: number; description: string; assigned_staff_id?: string | null; expected_start_at?: string | null };
export type RequestDetail = { ticket: RequestTicket; workOrders: RequestOrder[]; events: { id: string; event_type: string; occurred_at: string }[] };
export type RequestPresentation = { resident?: { name: string; phone?: string; availability_note?: string }; participants: { id: string; name: string; kind: string; joined_at: string; active: boolean; left_at?: string }[];
  events: { id: string; kind: string; agent?: string; at: string; reason?: string }[];
  schedule?: { performer_staff_id?: string; performer_name?: string; appointment_at?: string }; apartment_history?: { id: string; title: string; status: string }[]; photos?: { id: string; name: string }[] };
export const requestKeys = { all: ["operations-requests"] as const, detail: (id: string) => ["operations-requests", id] as const,
  presentation: (id: string) => ["operations-requests", id, "presentation"] as const };
export function requestsQueryOptions() {
  return queryOptions({ queryKey: requestKeys.all, refetchInterval: 10000, queryFn: async () => {
    const tickets: RequestTicket[] = [];
    let offset: number | null = 0;
    while (offset !== null) {
      const page: { items: RequestTicket[]; nextOffset: number | null } = await (await client(`/api/business/tickets?limit=100&offset=${offset}`,
        { headers: businessHeaders(), fallback: "Không tải được yêu cầu. Hãy thử lại." })).json();
      tickets.push(...page.items);
      const next = page.nextOffset ?? null;
      if (next !== null && next <= offset) throw new Error("Không tải được trang yêu cầu tiếp theo. Hãy thử lại.");
      offset = next;
    }
    return tickets;
  } });
}
export function requestCatalogQueryOptions() {
  return queryOptions({ queryKey: ["operations-request-catalog"], queryFn: async (): Promise<RequestCatalog> =>
    (await client("/api/business/catalogs", { headers: businessHeaders(), fallback: "Không tải được danh mục tòa và loại yêu cầu." })).json() });
}
export function requestDetailQueryOptions(id: string) {
  return queryOptions({ queryKey: requestKeys.detail(id), enabled: !!id, refetchInterval: 5000,
    queryFn: async (): Promise<RequestDetail> => (await client(`/api/business/tickets/${encodeURIComponent(id)}`,
      { headers: businessHeaders(), fallback: "Không tải được chi tiết yêu cầu. Hãy thử lại." })).json() });
}
export function requestPresentationQueryOptions(id: string) {
  return queryOptions({ queryKey: requestKeys.presentation(id), enabled: !!id, refetchInterval: 5000,
    queryFn: async (): Promise<RequestPresentation> => (await client(`/api/business/tickets/${encodeURIComponent(id)}/presentation`,
      { headers: businessHeaders(), fallback: "Không tải được thông tin cư dân và người tham gia phiên." })).json() });
}
export function requestPlace(ticket: Pick<RequestTicket, "unit_code" | "building_id"> | undefined, catalog?: RequestCatalog) {
  if (!ticket) return "";
  const building = catalog?.buildings?.find(item => item.id === ticket.building_id);
  return [ticket.unit_code ? `Căn ${ticket.unit_code}` : "", building ? `tòa ${building.code || building.name}` : ""].filter(Boolean).join(", ");
}

export type SessionSource = { id: string; title: string; enabled: boolean; status: string; suspension_reason?: string;
  tools: { name: string; description: string; effect: string }[] };
export type SessionExternalCall = { id: string; agent_id: string; tool_name: string; description?: string; connection_title: string;
  arguments: unknown; status: string; result?: { text?: string; error?: string }; created_at: string };
export function requestSessionSourcesQueryOptions(ticketId: string, userId: string, enabled = true) {
  return queryOptions({ queryKey: [...requestKeys.detail(ticketId), "sources", userId], enabled, refetchInterval: 5000,
    queryFn: async (): Promise<{ items: SessionSource[] }> => (await client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/sources`,
      { headers: businessHeaders(), fallback: "Không tải được nguồn ngoài của yêu cầu." })).json() });
}
export function requestSessionCallsQueryOptions(ticketId: string, userId: string, enabled = true) {
  return queryOptions({ queryKey: [...requestKeys.detail(ticketId), "external-calls", userId], enabled, refetchInterval: 3000,
    queryFn: async (): Promise<{ items: SessionExternalCall[] }> => (await client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/external-calls`,
      { headers: businessHeaders(), fallback: "Không tải được thao tác ghi chờ bạn cho phép." })).json() });
}
