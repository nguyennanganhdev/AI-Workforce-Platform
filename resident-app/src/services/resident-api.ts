import type { ResidentRequest, RequestStatus } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/business${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(typeof init.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof body?.detail === "string"
        ? body.detail
        : `Không thể hoàn thành (${response.status}). Vui lòng kiểm tra rồi thử lại.`,
    );
  return body as T;
}
export async function allPages<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let offset: number | null = 0;
  while (offset !== null) {
    const page: { items: T[]; nextOffset: number | null } = await api(
      `${path}?limit=100&offset=${offset}`,
    );
    items.push(...page.items);
    offset = page.nextOffset;
  }
  return items;
}
export type Profile = {
  user: { id: string; name: string; email: string };
  dataMode: string;
  units: {
    id: string;
    code: string;
    building_id: string;
    building_name: string;
    site_name: string;
    domain_id: string;
  }[];
  categories: { id: string; code: string; name: string }[];
};
export type Chat = {
  id: string;
  name: string;
  /** The request's title, else the resident's first words, else `name`. */
  title: string;
  last_message: string | null;
  last_message_at: string | null;
  created_at: string;
  ticket_id?: string;
  ticket_code?: string;
  unread_count: number;
};
export type Message = {
  id: string;
  seq: number;
  sender_kind: string;
  body: { text?: string };
  created_at: string;
};
export type Ticket = {
  id: string;
  code: string;
  title: string;
  description: string;
  status: string;
  version: number;
  created_at: string;
  address_snapshot?: { location?: string; building?: string; unit?: string };
};
export type TicketDetail = {
  ticket: Ticket;
  events: { id: string; event_type: string; occurred_at: string }[];
  photos: { id: string; name: string }[];
};
export type Approval = {
  id: string;
  ticket_id: string;
  kind: string;
  status: string;
  request_detail: {
    note?: string;
    lines?: { name: string; quantity: string; unit: string; amount: number }[];
    labor_cost?: number;
    warranty_months?: number;
    total?: number;
  };
};
export function requestView(
  detail: TicketDetail,
  canConfirm: boolean,
): ResidentRequest {
  const t = detail.ticket;
  const statuses: Record<string, RequestStatus> = {
    open: "received",
    triaging: "received",
    assigned: "received",
    in_progress: "processing",
    resolved: canConfirm ? "confirmation" : "processing",
    closed: "completed",
    cancelled: "cancelled",
  };
  const labels: Record<string, string> = {
    "ticket.created": "Đã tiếp nhận phản ánh",
    "ticket.routing_accepted": "Ban quản lý đã tiếp nhận",
    "work_order.offered": "Đã phân công nhân viên",
    "work_assignment.responded": "Nhân viên phản hồi phân công",
    "work_order.status_changed": "Cập nhật tiến độ thi công",
    "ticket.resolution_published": "Kết quả đã đạt nghiệm thu",
    "work_approval.decided": "Đã ghi nhận phản hồi của bạn",
    "ticket.status_changed": "Cập nhật trạng thái",
  };
  return {
    id: t.id,
    code: t.code,
    title: t.title,
    description: t.description,
    location:
      t.address_snapshot?.location ??
      [t.address_snapshot?.building, t.address_snapshot?.unit]
        .filter(Boolean)
        .join(" · "),
    status: statuses[t.status] ?? "processing",
    createdAt: t.created_at,
    photos: detail.photos.map((p) => ({
      ...p,
      url: `/api/business/resident/photos/${p.id}`,
    })),
    events: [...detail.events]
      .reverse()
      .map((e) => ({
        at: e.occurred_at,
        label: labels[e.event_type] ?? "Cập nhật yêu cầu",
      })),
  };
}
