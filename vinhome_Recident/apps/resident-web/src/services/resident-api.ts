import type { PlatformApproval, PlatformBooking, PlatformQuote, ReceptionExperience, ResidentRequest, RequestStatus } from "./types";

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
      `${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`,
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
  /** The platform's agent has asked the resident to confirm the result of this chat's request. */
  confirm_close?: boolean;
  unread_count: number;
};
export type Message = {
  id: string;
  seq: number;
  sender_kind: string;
  reply_to_id?: string | null;
  /** `fileIds`: photos the resident sent with this message, stored with the chat before it was posted. */
  body: {
    text?: string;
    fileIds?: string[];
    reception?: ReceptionExperience;
    /** Written by the platform bridge: an approval or a repair quote the resident answers on a card. */
    platform?: {
      kind: string;
      /** Of an approval and of a quote. */
      approval_id?: string;
      /** Of a booking card. */
      card_id?: string;
      amenity?: string;
      area?: string;
      start_at?: string;
      end_at?: string;
      guests?: number;
      booking_status?: string;
      summary?: { text?: string; arguments?: { items?: { label: string; amount: number }[]; total?: number } };
      /** Of a quote: the bill. */
      lines?: PlatformQuote["lines"];
      labor_cost?: number;
      warranty_months?: number;
      total?: number;
      expires_at?: string | null;
      status: PlatformApproval["status"] | PlatformBooking["status"];
    };
  };
  created_at: string;
};
/**
 * The approval card of a message. `answered` holds what the resident chose here, shown until the
 * platform has recorded it; a pending approval past its time can no longer be answered.
 */
export function approvalOf(
  body: Message["body"],
  answered: Map<string, boolean>,
  now = Date.now(),
): PlatformApproval | undefined {
  const p = body.platform;
  if (p?.kind !== "approval") return undefined;
  const mine = answered.get(p.approval_id!);
  const items = p.summary?.arguments?.items;
  return {
    id: p.approval_id!,
    text: withoutRequestCode(p.summary?.text || body.text || ""),
    ...(Array.isArray(items) && items.length ? { items, total: p.summary?.arguments?.total } : {}),
    status:
      p.status !== "pending"
        ? (p.status as PlatformApproval["status"])
        : mine !== undefined
          ? mine ? "approved" : "rejected"
          : p.expires_at && Date.parse(p.expires_at) <= now
            ? "expired"
            : "pending",
  };
}
/** The quote card of a message; a pending quote past its time can no longer be answered. */
export function quoteOf(body: Message["body"], now = Date.now()): PlatformQuote | undefined {
  const p = body.platform;
  if (p?.kind !== "quote") return undefined;
  return {
    id: p.approval_id!,
    lines: p.lines ?? [],
    laborCost: p.labor_cost ?? 0,
    warrantyMonths: p.warranty_months ?? 0,
    total: p.total ?? 0,
    status: p.status === "pending" && p.expires_at && Date.parse(p.expires_at) <= now ? "expired" : (p.status as PlatformApproval["status"]),
  };
}
/** The booking card of a message; `booked` holds the cards the resident confirmed here, until the backend says so. */
export function bookingOf(body: Message["body"], booked: Set<string>, now = Date.now()): PlatformBooking | undefined {
  const p = body.platform;
  if (p?.kind !== "booking" || !p.card_id) return undefined;
  return {
    id: p.card_id,
    amenity: p.amenity ?? "",
    area: p.area ?? "",
    startAt: p.start_at ?? "",
    endAt: p.end_at ?? "",
    guests: p.guests ?? 1,
    total: p.total ?? 0,
    status:
      p.status === "booked" || booked.has(p.card_id)
        ? "booked"
        : p.status === "expired" || (p.expires_at && Date.parse(p.expires_at) <= now)
          ? "expired"
          : "pending",
    ...(p.booking_status ? { bookingStatus: p.booking_status } : {}),
  };
}
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
/** Messages stored before request codes left resident-facing text still carry one. */
export const withoutRequestCode = (text: string) =>
  text
    .replace(/\s*Mã yêu cầu của bạn: \S+$/, "")
    .replace(/cho yêu cầu VH-\w+:/, "cho yêu cầu của anh/chị:");
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
    "ticket.resolution_published": "Đã có kết quả, chờ bạn xác nhận",
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
