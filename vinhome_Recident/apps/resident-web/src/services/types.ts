export type RequestStatus =
  | "received"
  | "processing"
  | "confirmation"
  | "completed"
  | "cancelled";
export type Photo = { id: string; name: string; url: string };
export type RequestEvent = { label: string; at: string; note?: string };
export type ResidentRequest = {
  code?: string;
  id: string;
  title: string;
  description: string;
  location: string;
  status: RequestStatus;
  createdAt: string;
  photos: Photo[];
  events: RequestEvent[];
};
/** What the platform's agent asks the resident to agree to before it acts. */
export type PlatformApproval = {
  id: string;
  text: string;
  items?: { label: string; amount: number }[];
  total?: number;
  status: "pending" | "approved" | "rejected" | "expired";
};
/** A repair quote the resident answers in the chat, as a bill. */
export type PlatformQuote = {
  id: string;
  lines: { name: string; quantity: string | number; unit: string; amount: number }[];
  laborCost: number;
  warrantyMonths: number;
  total: number;
  status: PlatformApproval["status"];
};
/** An amenity booking the assistant offers: nothing is booked until the resident taps the card. */
export type PlatformBooking = {
  id: string;
  amenity: string;
  area: string;
  startAt: string;
  endAt: string;
  guests: number;
  total: number;
  status: "pending" | "booked" | "expired";
  /** Once booked: where the booking stands (confirmed, or waiting for payment). */
  bookingStatus?: string;
};
export type ChatMessage = {
  id: string;
  role: "resident" | "assistant";
  text: string;
  photos?: Photo[];
  requestId?: string;
  approval?: PlatformApproval;
  quote?: PlatformQuote;
  booking?: PlatformBooking;
  createdAt?: string;
  delivery?: "sent" | "answered";
  reception?: ReceptionExperience;
};
export type ReceptionStage = { stage: "context" | "searching" | "request" | "status" | "responding"; at: string };
export type ReceptionExperience = {
  latencyMs?: number | null;
  steps?: ReceptionStage[];
  citations?: { title: string; excerpt: string; documentId?: string | null; status: "reference" | "approved"; effectiveFrom?: string | null; documentReference?: string | null }[];
};
export type TurnState = { messageId?: string; status: "idle" | "queued" | "processing" | "completed" | "unavailable" | "waiting_platform"; startedAt?: string; elapsedMs?: number; steps: ReceptionStage[] };
export type ResidentNotification = {
  id: string; created_at: string; read_at: string | null; channel_id?: string | null; ticket_id?: string | null;
  payload: { title?: string; message?: string; text?: string; type?: string; channelId?: string; ticketId?: string };
};
export type Draft = {
  step: "description" | "location" | "review";
  description: string;
  location: string;
  photos: Photo[];
};
export type ResidentState = {
  version: 1;
  requests: ResidentRequest[];
  messages: ChatMessage[];
  draft: Draft | null;
  conversations?: ResidentConversation[];
  activeConversationId?: string;
  /** The resident's last message has no reply yet. */
  awaitingReply?: boolean;
  turnState?: TurnState;
};
export type ResidentConversation = {
  archived?: boolean;
  id: string;
  title: string;
  messages: ChatMessage[];
  draft: Draft | null;
  requestId?: string;
  /** Status of the linked request, as the resident reads it. */
  requestStatus?: string;
  /** The platform's agent has asked the resident to confirm the result here. */
  confirmClose?: boolean;
  /** Last message of the conversation, for lists that do not load its messages. */
  preview?: string;
  unread: number;
  updatedAt: string;
};
export const statusLabels: Record<RequestStatus, string> = {
  cancelled: "Đã hủy",
  received: "Đã tiếp nhận",
  processing: "Đang xử lý",
  confirmation: "Chờ bạn xác nhận",
  completed: "Hoàn tất",
};
