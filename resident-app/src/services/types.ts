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
export type ChatMessage = {
  id: string;
  role: "resident" | "assistant";
  text: string;
  photos?: Photo[];
  requestId?: string;
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
};
export type ResidentConversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  draft: Draft | null;
  requestId?: string;
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
