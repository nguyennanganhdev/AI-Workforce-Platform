/**
 * Multi-Agent Coordination Session & Workflow Types
 * Matches the complete resident-agent-human-manager end-to-end lifecycle
 */

export type AgentRole =
  | 'AGENT_CSKH'         // Agent CSKH: Tiếp nhận, xác nhận, làm rõ thông tin & giao tiếp với cư dân
  | 'AGENT_DISPATCHER'   // Agent Điều Phối (Supervisor): Tạo session, phân tích case, triệu tập các agent
  | 'AGENT_TECHNICAL'    // Agent Kỹ Thuật: Đánh giá phương án kỹ thuật, điều phối thợ, lưu báo giá vật tư
  | 'AGENT_BILLING';     // Agent Báo Cáo / Hóa Đơn: Lập báo giá, làm hóa đơn tạm tính, kiểm tra thông tin thanh toán

export type SessionStatus =
  | 'INITIALIZING'                   // Khởi tạo session từ ticket của Agent CSKH
  | 'DISPATCHING'                    // Agent Điều phối đang triệu tập Agent Kỹ thuật & phân công thợ
  | 'QUOTING'                        // Thợ đang khảo sát, nhập chi phí vật tư gửi cho Agent Kỹ thuật
  | 'WAITING_RESIDENT_PRICE_APPROVAL'// Agent Điều phối ping báo giá sang Agent CSKH để cư dân xem giá
  | 'EXECUTING'                      // Cư dân đã đồng ý giá, thợ đang thi công sửa chữa
  | 'WAITING_RESIDENT_CONFIRMATION'  // Thợ sửa xong, chụp ảnh nghiệm thu, chờ cư dân xác nhận
  | 'RESIDENT_CONFIRMED'             // Cư dân xác nhận ticket DONE, đóng conversation với cư dân, chờ BQL duyệt
  | 'CLOSED';                        // BQL duyệt case và đóng session điều phối

export interface MaterialItem {
  id: string;
  part_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
}

export interface QuotationInvoice {
  id: string;
  session_id: string;
  work_order_id: string;
  items: MaterialItem[];
  labor_cost: number;
  total_amount: number;
  warranty_months: number;
  invoice_code: string;
  created_by_agent: string;
  resident_approved: boolean;
  approved_at?: string | null;
}

export type SessionMessageSenderType =
  | 'AGENT_CSKH'
  | 'AGENT_DISPATCHER'
  | 'AGENT_TECHNICAL'
  | 'AGENT_BILLING'
  | 'HUMAN_WORKER'
  | 'HUMAN_MANAGER'
  | 'RESIDENT';

export type SessionActionType =
  | 'CLARIFY_INFO'
  | 'CREATE_TICKET'
  | 'CREATE_SESSION'
  | 'DISPATCH_WORKER'
  | 'SUBMIT_QUOTE'
  | 'CREATE_INVOICE'
  | 'PING_RESIDENT_PRICE'
  | 'RESIDENT_APPROVE_PRICE'
  | 'WORK_COMPLETED_EVIDENCE'
  | 'RESIDENT_CONFIRM_DONE'
  | 'BQL_APPROVE_CLOSE';

export interface VhSessionMessage {
  id: string;
  session_id: string;
  sender_type: SessionMessageSenderType;
  sender_name: string;
  sender_avatar?: string;
  content: string;
  action_type?: SessionActionType;
  payload?: Record<string, unknown>;
  created_at: string;
}

export interface VhCoordinationSession {
  id: string;
  incident_id: string;
  case_id?: string;
  work_order_id?: string;
  title: string;
  status: SessionStatus;
  resident_ticket_status: 'OPEN' | 'DONE';
  resident_conversation_status: 'ACTIVE' | 'CLOSED';
  active_agents: AgentRole[];
  human_worker_id?: string;
  human_worker_name?: string;
  resident_name: string;
  resident_phone?: string;
  resident_apartment: string;
  quotation?: QuotationInvoice | null;
  evidence_photo_urls?: string[];
  bql_approved_by?: string;
  bql_approved_at?: string | null;
  bql_note?: string;
  created_at: string;
  updated_at: string;
}
