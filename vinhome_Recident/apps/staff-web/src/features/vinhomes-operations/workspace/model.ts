export type Role =
  | "admin"
  | "manager"
  | "technical"
  | "security"
  | "sanitation"
  | "resident";
export const roleLabels: Record<Role, string> = {
  admin: "Quản trị hệ thống",
  manager: "Ban quản lý",
  technical: "Kỹ thuật",
  security: "An ninh",
  sanitation: "Vệ sinh",
  resident: "Cư dân",
};
export const scopes = ["S2.01", "S2.02", "Cọ Xanh"] as const;
export type Scope = (typeof scopes)[number];
export type Account = {
  id: string;
  name: string;
  identifier: string;
  role: Role;
  scope: Scope;
  status: "pending" | "active" | "suspended";
  available: boolean;
};
export type Agent = {
  id: string;
  name: string;
  specialty: "reception" | "technical" | "security" | "report";
  scope: Scope;
};
export type RoomMessage = {
  id: string;
  at: string;
  author: string;
  text: string;
  agentId?: string;
  ticketId?: string;
  context?: string;
};
export type Room = {
  id: string;
  scope: Scope;
  name: string;
  agentIds: string[];
  messages: RoomMessage[];
};
export type Severity = "P0" | "P1" | "P2" | "P3";
export type CaseStage =
  | "queued"
  | "assigned"
  | "on-site"
  | "awaiting-consent"
  | "isolation-requested"
  | "isolation-approved"
  | "outage-notified"
  | "isolated"
  | "working"
  | "restored"
  | "awaiting-confirmation"
  | "controlled"
  | "completed"
  | "cancel-requested"
  | "cancelled";
export type CaseEvent = {
  id: string;
  at: string;
  actor: string;
  label: string;
};
export type WorkflowCase = {
  id: string;
  title: string;
  scope: Scope;
  apartment: string;
  resident: string;
  phone: string;
  domain: "electric" | "water" | "security";
  severity: Severity;
  stage: CaseStage;
  workerId?: string;
  majorWater: boolean;
  consent: boolean;
  alertAcknowledged: boolean;
  escalation: number;
  evidence: string[];
  events: CaseEvent[];
  dueAt: string;
  createdAt: string;
  amount: number;
  camera: "online" | "offline" | "unknown";
};
export const stageLabels: Record<CaseStage, string> = {
  queued: "Chờ nhân viên",
  assigned: "Đã phân công",
  "on-site": "Đang khảo sát",
  "awaiting-consent": "Chờ cư dân đồng ý",
  "isolation-requested": "Chờ BQL duyệt khóa nước",
  "isolation-approved": "Đã duyệt khóa nước",
  "outage-notified": "Đã thông báo cắt nước",
  isolated: "Đã khóa nước",
  working: "Đang xử lý",
  restored: "Đã mở nước lại",
  "awaiting-confirmation": "Chờ cư dân xác nhận",
  controlled: "Đã kiểm soát · chờ BQL",
  completed: "Hoàn tất",
  "cancel-requested": "Chờ duyệt hủy",
  cancelled: "Đã hủy",
};
export type ReportJob = {
  id: string;
  name: string;
  kind: "revenue" | "frequency";
  scope: Scope;
  from: string;
  to: string;
  status: "queued" | "ready" | "failed";
  createdAt: string;
  error?: string;
};
export type WorkspaceState = {
  version: 1;
  accounts: Account[];
  agents: Agent[];
  rooms: Room[];
  cases: WorkflowCase[];
  reports: ReportJob[];
  audit: CaseEvent[];
};
export const newId = () => crypto.randomUUID();
export function seedWorkspace(): WorkspaceState {
  const now = new Date();
  const at = now.toISOString();
  const agents: Agent[] = [
    {
      id: "agent-reception",
      name: "Lễ tân",
      specialty: "reception",
      scope: "S2.01",
    },
    {
      id: "agent-technical",
      name: "Kỹ thuật",
      specialty: "technical",
      scope: "S2.01",
    },
    {
      id: "agent-report",
      name: "Báo cáo",
      specialty: "report",
      scope: "S2.01",
    },
  ];
  return {
    version: 1,
    accounts: [
      {
        id: "demo-admin",
        name: "Admin mẫu",
        identifier: "ADMIN-01",
        role: "admin",
        scope: "S2.01",
        status: "active",
        available: true,
      },
      {
        id: "demo-manager",
        name: "Nguyễn Minh Anh",
        identifier: "BQL-01",
        role: "manager",
        scope: "S2.01",
        status: "active",
        available: true,
      },
      {
        id: "demo-tech",
        name: "Nguyễn Văn Hùng",
        identifier: "KT-01",
        role: "technical",
        scope: "S2.01",
        status: "active",
        available: true,
      },
      {
        id: "demo-security",
        name: "Trần Văn Nam",
        identifier: "AN-01",
        role: "security",
        scope: "S2.01",
        status: "active",
        available: true,
      },
      {
        id: "demo-cleaning",
        name: "Lê Thị Hà",
        identifier: "VS-01",
        role: "sanitation",
        scope: "S2.01",
        status: "active",
        available: true,
      },
      {
        id: "demo-manager2",
        name: "BQL S2.02",
        identifier: "BQL-02",
        role: "manager",
        scope: "S2.02",
        status: "active",
        available: true,
      },
      {
        id: "demo-resident",
        name: "Trần Minh An",
        identifier: "0900000000",
        role: "resident",
        scope: "S2.01",
        status: "pending",
        available: false,
      },
    ],
    agents,
    rooms: scopes.map((scope) => ({
      id: `room-${scope}`,
      scope,
      name: `Điều phối ${scope}`,
      agentIds: agents.filter((a) => a.scope === scope).map((a) => a.id),
      messages: [
        {
          id: newId(),
          at,
          author: "Hệ thống mẫu",
          text: "Không gian trao đổi riêng theo phạm vi quản lý. Tin nhắn và phản hồi agent ở đây là mô phỏng UI.",
        },
      ],
    })),
    cases: [
      {
        id: "DEMO-1001",
        title: "Mất điện khu vực bếp",
        scope: "S2.01",
        apartment: "1206",
        resident: "Trần Minh An",
        phone: "0900000000",
        domain: "electric",
        severity: "P2",
        stage: "queued",
        majorWater: false,
        consent: false,
        alertAcknowledged: false,
        escalation: 0,
        evidence: [],
        createdAt: at,
        dueAt: new Date(now.getTime() + 3600000).toISOString(),
        events: [
          {
            id: newId(),
            at,
            actor: "Lễ tân mẫu",
            label: "Tiếp nhận đủ thông tin cư dân",
          },
        ],
        amount: 250000,
        camera: "unknown",
      },
      {
        id: "DEMO-1002",
        title: "Vỡ đường ống cấp nước tầng 12",
        scope: "S2.01",
        apartment: "Tầng 12",
        resident: "Cư dân tầng 12",
        phone: "0900000001",
        domain: "water",
        severity: "P1",
        stage: "queued",
        majorWater: true,
        consent: false,
        alertAcknowledged: false,
        escalation: 0,
        evidence: [],
        createdAt: at,
        dueAt: new Date(now.getTime() + 900000).toISOString(),
        events: [
          {
            id: newId(),
            at,
            actor: "Lễ tân mẫu",
            label: "Cần đánh giá ảnh hưởng cấp nước",
          },
        ],
        amount: 530000,
        camera: "unknown",
      },
      {
        id: "DEMO-1003",
        title: "Ồn ào tại sảnh tầng 1",
        scope: "S2.01",
        apartment: "Sảnh tầng 1",
        resident: "Nguyễn Thị Mai",
        phone: "0900000002",
        domain: "security",
        severity: "P2",
        stage: "queued",
        majorWater: false,
        consent: false,
        alertAcknowledged: false,
        escalation: 0,
        evidence: [],
        createdAt: at,
        dueAt: new Date(now.getTime() - 60000).toISOString(),
        events: [
          {
            id: newId(),
            at,
            actor: "Lễ tân mẫu",
            label: "Tiếp nhận phản ánh an ninh",
          },
        ],
        amount: 0,
        camera: "online",
      },
      {
        id: "DEMO-2001",
        title: "Bảo trì ổ điện căn hộ",
        scope: "S2.02",
        apartment: "0805",
        resident: "Phạm Lan",
        phone: "0900000003",
        domain: "electric",
        severity: "P3",
        stage: "completed",
        majorWater: false,
        consent: true,
        alertAcknowledged: false,
        escalation: 0,
        evidence: [],
        createdAt: at,
        dueAt: at,
        events: [
          {
            id: newId(),
            at,
            actor: "Dữ liệu mẫu",
            label: "Cư dân xác nhận hoàn tất",
          },
        ],
        amount: 180000,
        camera: "unknown",
      },
    ],
    reports: [],
    audit: [],
  };
}
export function landing(role: Role) {
  return role === "admin"
    ? "/operations/accounts"
    : role === "manager"
      ? "/operations/kanban"
      : role === "resident"
        ? "/login"
        : "/operations/my-tasks";
}
export function canViewPath(role: Role, path: string) {
  if (role === "resident") return false;
  if (role === "admin") return path === "/operations/accounts";
  if (path === "/operations/accounts") return false;
  if (["/operations/reports"].includes(path))
    return role === "manager";
  if (role === "manager") return true;
  return [
    "/operations/my-tasks",
    "/operations/completed-tasks",
    "/operations/dispatch",
    ...(role === "security" ? ["/operations/security"] : []),
    ...(role === "sanitation" ? ["/operations/sanitation"] : []),
  ].includes(path);
}
