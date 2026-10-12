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
export type ChatMessage = {
  id: string;
  role: "resident" | "assistant";
  text: string;
  photos?: Photo[];
  requestId?: string;
  approval?: PlatformApproval;
  quote?: PlatformQuote;
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
};
export type ResidentConversation = {
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
