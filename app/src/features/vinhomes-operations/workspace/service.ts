import {
  type WorkspaceState,
  type Account,
  type Role,
  type Scope,
  type Agent,
  type ReportJob,
  scopes,
  stageLabels,
  newId,
  seedWorkspace,
} from "./model";
export const WORKSPACE_KEY = "vinhomes.frontend-workspace.v1";
export function readWorkspace(
  storage: Pick<Storage, "getItem"> = localStorage,
): WorkspaceState {
  const raw = storage.getItem(WORKSPACE_KEY);
  if (!raw) return seedWorkspace();
  const s = JSON.parse(raw) as WorkspaceState;
  if (
    !s ||
    s.version !== 1 ||
    ![s.accounts, s.agents, s.rooms, s.cases, s.reports, s.audit].every(
      Array.isArray,
    ) ||
    !s.accounts.every(
      (a) =>
        a &&
        typeof a.id === "string" &&
        typeof a.name === "string" &&
        [
          "admin",
          "manager",
          "technical",
          "security",
          "sanitation",
          "resident",
        ].includes(a.role) &&
        ["active", "pending", "suspended"].includes(a.status) &&
        typeof a.identifier === "string" &&
        scopes.includes(a.scope) &&
        typeof a.available === "boolean",
    ) ||
    !s.rooms.every(
      (r) =>
        r &&
        typeof r.id === "string" &&
        typeof r.name === "string" &&
        scopes.includes(r.scope) &&
        Array.isArray(r.messages) &&
        Array.isArray(r.agentIds) &&
        r.messages.every(
          (m) =>
            m &&
            typeof m.id === "string" &&
            typeof m.author === "string" &&
            typeof m.text === "string" &&
            Number.isFinite(Date.parse(m.at)),
        ),
    ) ||
    !s.cases.every(
      (c) =>
        c &&
        typeof c.id === "string" &&
        typeof c.title === "string" &&
        typeof c.phone === "string" &&
        typeof c.resident === "string" &&
        typeof c.apartment === "string" &&
        scopes.includes(c.scope) &&
        ["electric", "water", "security"].includes(c.domain) &&
        ["P0", "P1", "P2", "P3"].includes(c.severity) &&
        Object.hasOwn(stageLabels, c.stage) &&
        Number.isFinite(Date.parse(c.createdAt)) &&
        Number.isFinite(Date.parse(c.dueAt)) &&
        Number.isFinite(c.amount) &&
        Array.isArray(c.events) &&
        c.events.every(
          (e) =>
            e &&
            typeof e.label === "string" &&
            typeof e.actor === "string" &&
            Number.isFinite(Date.parse(e.at)),
        ) &&
        Array.isArray(c.evidence) &&
        c.evidence.length <= 3 &&
        c.evidence.every(
          (p) =>
            typeof p === "string" &&
            /^data:image\/(jpeg|png|webp);base64,/.test(p),
        ),
    ) ||
    !s.agents.every(
      (a) =>
        a &&
        typeof a.id === "string" &&
        typeof a.name === "string" &&
        scopes.includes(a.scope),
    ) ||
    !s.reports.every(
      (r) =>
        r &&
        typeof r.id === "string" &&
        typeof r.name === "string" &&
        scopes.includes(r.scope) &&
        ["revenue", "frequency"].includes(r.kind) &&
        ["queued", "ready", "failed"].includes(r.status) &&
        Number.isFinite(Date.parse(r.from)) &&
        Number.isFinite(Date.parse(r.to)),
    ) ||
    !s.audit.every(
      (e) =>
        e &&
        typeof e.label === "string" &&
        typeof e.actor === "string" &&
        Number.isFinite(Date.parse(e.at)),
    )
  )
    throw new Error(
      "Dữ liệu workspace mẫu không hợp lệ. Hãy đặt lại bản mẫu trước khi tiếp tục.",
    );
  return s;
}
export function writeWorkspace(
  s: WorkspaceState,
  storage: Pick<Storage, "setItem"> = localStorage,
) {
  try {
    storage.setItem(WORKSPACE_KEY, JSON.stringify(s));
  } catch {
    throw new Error(
      "Chưa lưu được dữ liệu. Bộ nhớ bị chặn hoặc đã đầy; thay đổi chưa được áp dụng.",
    );
  }
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("operations-workspace-change"));
}
export function actorOf(s: WorkspaceState, id: string) {
  const a = s.accounts.find((a) => a.id === id && a.status === "active");
  if (!a)
    throw new Error(
      "Tài khoản không còn hoạt động. Vui lòng quay lại đăng nhập.",
    );
  return a;
}
function manager(s: WorkspaceState, id: string, scope: Scope) {
  const a = actorOf(s, id);
  if (a.role !== "manager" || a.scope !== scope)
    throw new Error("Bạn không có quyền thao tác trong phạm vi này.");
  return a;
}
function audit(s: WorkspaceState, a: Account, label: string) {
  s.audit.unshift({
    id: newId(),
    at: new Date().toISOString(),
    actor: a.name,
    label,
  });
}
export function createAccount(
  state: WorkspaceState,
  actorId: string,
  input: { name: string; identifier: string; role: Role; scope: Scope },
) {
  const s = structuredClone(state),
    a = actorOf(s, actorId);
  if (a.role !== "admin") throw new Error("Chỉ admin được cấp tài khoản.");
  if (
    input.name.trim().length < 2 ||
    input.name.length > 100 ||
    !input.identifier.trim() ||
    input.identifier.length > 128
  )
    throw new Error("Nhập họ tên (2–100 ký tự) và định danh hợp lệ.");
  if (
    ![
      "admin",
      "manager",
      "technical",
      "security",
      "sanitation",
      "resident",
    ].includes(input.role) ||
    !["S2.01", "S2.02", "Cọ Xanh"].includes(input.scope)
  )
    throw new Error("Vai trò hoặc phạm vi không hợp lệ.");
  if (
    s.accounts.some(
      (a) =>
        a.identifier.toLowerCase() === input.identifier.trim().toLowerCase(),
    )
  )
    throw new Error("Định danh đã được sử dụng.");
  s.accounts.unshift({
    ...input,
    id: newId(),
    name: input.name.trim(),
    identifier: input.identifier.trim(),
    status: input.role === "resident" ? "pending" : "active",
    available: true,
  });
  audit(s, a, `Tạo tài khoản mẫu ${input.identifier}`);
  return s;
}
export function changeAccount(
  state: WorkspaceState,
  actorId: string,
  id: string,
  action: "approve" | "activate" | "suspend" | "delete",
  confirmation = "",
) {
  const s = structuredClone(state),
    a = actorOf(s, actorId);
  if (a.role !== "admin") throw new Error("Chỉ admin quản lý tài khoản.");
  const target = s.accounts.find((a) => a.id === id);
  if (!target) throw new Error("Không tìm thấy tài khoản.");
  if (id === actorId && (action === "suspend" || action === "delete"))
    throw new Error("Không thể tự khóa hoặc xóa tài khoản đang sử dụng.");
  if (
    target.role === "admin" &&
    target.status === "active" &&
    ["suspend", "delete"].includes(action) &&
    s.accounts.filter((a) => a.role === "admin" && a.status === "active")
      .length <= 1
  )
    throw new Error("Phải giữ ít nhất một admin hoạt động.");
  if (action === "delete") {
    if (confirmation !== target.identifier)
      throw new Error("Nhập đúng định danh để xác nhận xóa.");
    if (
      s.cases.some(
        (c) =>
          c.workerId === id && !["completed", "cancelled"].includes(c.stage),
      )
    )
      throw new Error(
        "Cần bàn giao công việc đang mở trước khi xóa nhân viên.",
      );
    s.accounts = s.accounts.filter((a) => a.id !== id);
  } else {
    target.status = action === "suspend" ? "suspended" : "active";
  }
  audit(s, a, `${action} · ${target.identifier}`);
  return s;
}
export function createAgent(
  state: WorkspaceState,
  actorId: string,
  name: string,
  specialty: Agent["specialty"],
) {
  const s = structuredClone(state);
  const a = actorOf(s, actorId);
  manager(s, actorId, a.scope);
  if (name.trim().length < 2 || name.length > 50)
    throw new Error("Tên agent cần từ 2 đến 50 ký tự.");
  if (
    s.agents.some(
      (g) =>
        g.scope === a.scope &&
        g.name.toLocaleLowerCase() === name.trim().toLocaleLowerCase(),
    )
  )
    throw new Error("Tên agent đã tồn tại trong nhóm.");
  const agent = { id: newId(), name: name.trim(), scope: a.scope, specialty };
  s.agents.push(agent);
  const room = s.rooms.find((r) => r.scope === a.scope)!;
  room.agentIds.push(agent.id);
  room.messages.push({
    id: newId(),
    at: new Date().toISOString(),
    author: "Hệ thống mẫu",
    text: `Đã thêm @${agent.name} vào nhóm.`,
  });
  return s;
}
export function sendRoomMessage(
  state: WorkspaceState,
  actorId: string,
  roomId: string,
  text: string,
  agentId?: string,
  ticketId?: string,
) {
  const s = structuredClone(state);
  const room = s.rooms.find((r) => r.id === roomId);
  if (!room) throw new Error("Không tìm thấy phòng.");
  const a = manager(s, actorId, room.scope);
  if (!text.trim() || text.length > 2000)
    throw new Error("Nội dung cần từ 1 đến 2.000 ký tự.");
  const agent = agentId
    ? s.agents.find((g) => g.id === agentId && room.agentIds.includes(g.id))
    : undefined;
  if (agentId && !agent) throw new Error("Agent không thuộc nhóm này.");
  const ticket = ticketId
    ? s.cases.find((c) => c.id === ticketId && c.scope === room.scope)
    : undefined;
  if (ticketId && !ticket) throw new Error("Ticket không thuộc phạm vi nhóm.");
  const context = JSON.stringify({
    roomId,
    scope: room.scope,
    recentMessageIds: room.messages.slice(-8).map((m) => m.id),
    ticketId: ticket?.id,
    stage: ticket?.stage,
  });
  room.messages.push({
    id: newId(),
    at: new Date().toISOString(),
    author: a.name,
    text: text.trim(),
    agentId,
    ticketId,
    context,
  });
  if (agent)
    room.messages.push({
      id: newId(),
      at: new Date().toISOString(),
      author: `${agent.name} · mô phỏng`,
      text: `Đã nhận lời nhắc trong phòng ${room.name}${ticket ? ` cùng ticket ${ticket.id}` : ""}. Backend sẽ chọn ngữ cảnh và trả kết quả thật tại đây.`,
      agentId,
      ticketId,
    });
  return s;
}
export function createReport(
  state: WorkspaceState,
  actorId: string,
  input: Pick<ReportJob, "kind" | "from" | "to" | "name">,
) {
  const s = structuredClone(state),
    a = actorOf(s, actorId);
  manager(s, actorId, a.scope);
  if (
    !input.name.trim() ||
    input.name.length > 120 ||
    !/^\d{4}-\d{2}-\d{2}$/.test(input.from) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(input.to) ||
    !Number.isFinite(Date.parse(input.from)) ||
    !Number.isFinite(Date.parse(input.to)) ||
    input.from > input.to
  )
    throw new Error("Nhập tên và khoảng thời gian hợp lệ.");
  s.reports.unshift({
    ...input,
    name: input.name.trim(),
    id: newId(),
    scope: a.scope,
    status: "queued",
    createdAt: new Date().toISOString(),
  });
  return s;
}
export function finishReport(
  state: WorkspaceState,
  actorId: string,
  id: string,
  fail = false,
) {
  const s = structuredClone(state),
    r = s.reports.find((r) => r.id === id);
  if (!r) throw new Error("Không tìm thấy báo cáo.");
  manager(s, actorId, r.scope);
  r.status = fail ? "failed" : "ready";
  r.error = fail
    ? "Mô phỏng không lấy được dữ liệu. Bạn có thể thử tạo lại."
    : undefined;
  return s;
}
export function reportRows(s: WorkspaceState, r: ReportJob) {
  return s.cases.filter(
    (c) =>
      c.scope === r.scope &&
      c.createdAt.slice(0, 10) >= r.from &&
      c.createdAt.slice(0, 10) <= r.to &&
      (r.kind !== "revenue" ||
        (c.domain !== "security" && c.stage === "completed")),
  );
}
export type CaseAction =
  | "assign"
  | "arrive"
  | "ask-consent"
  | "resident-consent"
  | "request-isolation"
  | "approve-isolation"
  | "notify-outage"
  | "isolate"
  | "start"
  | "restore"
  | "submit"
  | "resident-confirm"
  | "acknowledge"
  | "escalate"
  | "raise-emergency"
  | "request-cancel"
  | "approve-cancel"
  | "manager-close"
  | "evidence"
  | "classify-water";
export function caseAction(
  state: WorkspaceState,
  actorId: string,
  id: string,
  action: CaseAction,
  value = "",
) {
  const s = structuredClone(state),
    a = actorOf(s, actorId),
    c = s.cases.find((c) => c.id === id);
  if (!c || a.scope !== c.scope)
    throw new Error("Không tìm thấy ticket trong phạm vi được cấp.");
  const isManager = a.role === "manager",
    isWorker =
      c.workerId === a.id && ["technical", "security"].includes(a.role);
  if (!isManager && !isWorker)
    throw new Error(
      "Chỉ BQL hoặc nhân viên được phân công mới thao tác ticket này.",
    );
  if (["completed", "cancelled"].includes(c.stage))
    throw new Error("Ticket đã đóng, không thể cập nhật.");
  const urgent = c.domain === "security" && ["P0", "P1"].includes(c.severity);
  const requireStage = (stages: string[]) => {
    if (!stages.includes(c.stage))
      throw new Error("Thao tác không phù hợp với trạng thái hiện tại.");
  };
  const management = () => {
    if (!isManager) throw new Error("Cần ban quản lý xác nhận.");
  };
  let label = "";
  switch (action) {
    case "assign": {
      management();
      requireStage(["queued", "assigned"]);
      const worker = s.accounts.find(
        (w) =>
          w.id === value &&
          w.scope === c.scope &&
          w.status === "active" &&
          w.role === (c.domain === "security" ? "security" : "technical"),
      );
      if (!worker)
        throw new Error(
          "Chọn nhân viên đang hoạt động, đúng bộ phận và phạm vi.",
        );
      const busy =
        !worker.available ||
        s.cases.some(
          (t) =>
            t.id !== c.id &&
            t.workerId === worker.id &&
            !["completed", "cancelled"].includes(t.stage),
        );
      if (busy) {
        c.stage = "queued";
        c.workerId = undefined;
        label =
          "Nhân viên đang bận · đã xếp hàng chờ và tạo thông báo mẫu cho cư dân";
      } else {
        c.workerId = worker.id;
        c.stage = "assigned";
        label = `Phân công ${worker.name}${urgent ? " · cảnh báo khẩn đang chờ xác nhận" : ""}`;
      }
      break;
    }
    case "arrive":
      requireStage(["assigned"]);
      c.stage = "on-site";
      label = "Nhân viên đã đến hiện trường";
      break;
    case "classify-water":
      requireStage(["on-site"]);
      if (c.domain !== "water") throw new Error("Chỉ áp dụng sự cố nước.");
      c.majorWater = value === "major";
      label = c.majorWater
        ? "Đánh giá cần khóa nước khu vực"
        : "Đánh giá không cần khóa nước khu vực";
      break;
    case "ask-consent":
      requireStage(["on-site"]);
      if (c.domain === "security")
        throw new Error("An ninh không cần bước đồng ý sửa chữa.");
      c.stage = "awaiting-consent";
      label = "Đã gửi đề nghị sửa chữa mẫu cho cư dân";
      break;
    case "resident-consent":
      requireStage(["awaiting-consent"]);
      c.consent = true;
      c.stage = "on-site";
      label = "Mô phỏng cư dân đồng ý phương án sửa chữa";
      break;
    case "request-isolation":
      requireStage(["on-site"]);
      if (c.domain !== "water" || !c.majorWater || !c.consent)
        throw new Error("Cần sự cố nước lớn và cư dân đồng ý phương án.");
      c.stage = "isolation-requested";
      label = "Đề nghị BQL phê duyệt khóa nước";
      break;
    case "approve-isolation":
      management();
      requireStage(["isolation-requested"]);
      c.stage = "isolation-approved";
      label = "BQL duyệt khóa nước khu vực";
      break;
    case "notify-outage":
      management();
      requireStage(["isolation-approved"]);
      c.stage = "outage-notified";
      label =
        "Đã tạo thông báo cắt nước mẫu cho cư dân trong phạm vi ảnh hưởng";
      break;
    case "isolate":
      requireStage(["outage-notified"]);
      c.stage = "isolated";
      label = "Xác nhận đã khóa van khu vực";
      break;
    case "start":
      requireStage(["on-site", "isolated"]);
      if (c.domain !== "security" && !c.consent)
        throw new Error("Cần cư dân đồng ý sửa chữa.");
      if (c.domain === "water" && c.majorWater && c.stage !== "isolated")
        throw new Error("Cần duyệt, thông báo và khóa nước trước khi sửa.");
      if (urgent && !c.alertAcknowledged)
        throw new Error("Cần người trực xác nhận cảnh báo khẩn.");
      c.stage = "working";
      label = "Bắt đầu xử lý hiện trường";
      break;
    case "evidence":
      requireStage(["working", "restored", "controlled", "on-site"]);
      if (
        !/^data:image\/(jpeg|png|webp);base64,/.test(value) ||
        value.length > 900000
      )
        throw new Error("Ảnh bằng chứng chưa hợp lệ hoặc quá lớn.");
      if (c.evidence.length >= 3)
        throw new Error("Tối đa 3 ảnh trong bản mẫu.");
      c.evidence.push(value);
      label = "Đã bổ sung ảnh bằng chứng";
      break;
    case "restore":
      requireStage(["working"]);
      if (c.domain !== "water" || !c.majorWater || !c.evidence.length)
        throw new Error("Cần ảnh hoàn thành trước khi xác nhận mở nước.");
      c.stage = "restored";
      label = "Xác nhận mở nước và tạo thông báo cấp nước trở lại (mẫu)";
      break;
    case "submit":
      requireStage(["working", "restored"]);
      if (!c.evidence.length)
        throw new Error("Cần ít nhất một ảnh bằng chứng.");
      if (c.domain === "water" && c.majorWater && c.stage !== "restored")
        throw new Error("Cần xác nhận mở nước trở lại.");
      c.stage = urgent ? "controlled" : "awaiting-confirmation";
      label = urgent
        ? "Sự cố đã kiểm soát · chờ BQL xác nhận"
        : "Đã gửi đề nghị cư dân xác nhận kết quả (mẫu)";
      break;
    case "resident-confirm":
      requireStage(["awaiting-confirmation"]);
      c.stage = "completed";
      label = "Mô phỏng cư dân xác nhận hoàn tất";
      break;
    case "acknowledge":
      if (!urgent) throw new Error("Chỉ áp dụng cảnh báo an ninh khẩn.");
      c.alertAcknowledged = true;
      label = "Người trực xác nhận đã nhận cảnh báo";
      break;
    case "escalate":
      if (c.stage === "queued" && Date.parse(c.dueAt) > Date.now())
        throw new Error("Ticket chưa quá hạn chờ.");
      if (c.stage !== "queued" && (!urgent || c.alertAcknowledged))
        throw new Error(
          "Chỉ chuyển cấp khi quá hạn hoặc cảnh báo khẩn chưa được xác nhận.",
        );
      c.escalation++;
      label = `Báo người tiếp theo / trưởng ca · lần ${c.escalation}. Ticket vẫn đang mở`;
      break;
    case "raise-emergency":
      requireStage([
        "queued",
        "assigned",
        "on-site",
        "working",
        "awaiting-confirmation",
      ]);
      if (c.domain !== "security")
        throw new Error("Chỉ áp dụng sự cố an ninh.");
      if (value.trim().length < 8)
        throw new Error("Nhập lý do nâng mức độ (ít nhất 8 ký tự).");
      c.severity = "P0";
      c.alertAcknowledged = false;
      if (c.stage === "working" || c.stage === "awaiting-confirmation")
        c.stage = "on-site";
      label = `Nâng lên P0 · ${value.trim()} · kích hoạt cảnh báo người trực`;
      break;
    case "request-cancel":
      requireStage(["queued", "assigned", "on-site"]);
      if (urgent)
        throw new Error(
          "Sự cố khẩn phải xử lý và BQL xác nhận, không hủy điều động.",
        );
      if (value.trim().length < 8)
        throw new Error("Nhập lý do đề nghị hủy (ít nhất 8 ký tự).");
      c.stage = "cancel-requested";
      label = `Đề nghị hủy: ${value.trim()}`;
      break;
    case "approve-cancel":
      management();
      requireStage(["cancel-requested"]);
      if (urgent)
        throw new Error("Không thể duyệt hủy sự cố an ninh khẩn cấp.");
      c.stage = "cancelled";
      label = "BQL duyệt hủy điều động";
      break;
    case "manager-close":
      management();
      requireStage(["controlled"]);
      if (!urgent || !c.alertAcknowledged || !c.evidence.length)
        throw new Error("Thiếu xác nhận cảnh báo hoặc bằng chứng.");
      c.stage = "completed";
      label = "BQL xác nhận đóng sự cố khẩn";
      break;
  }
  c.events.push({
    id: newId(),
    at: new Date().toISOString(),
    actor: action.startsWith("resident-") ? "Cư dân · mô phỏng" : a.name,
    label,
  });
  return s;
}
