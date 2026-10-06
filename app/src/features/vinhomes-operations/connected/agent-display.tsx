import type { AgentConfiguration, AgentManagement, ManagedAgent } from "@/lib/agent-management/queries";
export const SERVER_LABELS: Record<string, string> = { reporting: "Báo cáo", "security-tools": "An ninh", "technical-tools": "Kỹ thuật", knowledge: "Tri thức" };
const TOOL_LABELS: Record<string, string> = {
  "asset.read": "Xem hồ sơ thiết bị", "maintenance_history.read": "Xem lịch sử bảo trì", "sensor.read": "Đọc cảm biến tòa nhà", "sop_kb.retrieve": "Tra quy trình xử lý", "utility_schedule.read": "Tra lịch cắt điện nước", "technical.get_active_outage": "Tra sự cố điện nước đang diễn ra", "technical.verify_resolution": "Kiểm tra kết quả xử lý", "camera.read": "Tra danh mục camera", "security.camera.read": "Tra danh mục camera", "security.contact.read": "Tra đầu mối khẩn cấp", "reporting.filter_report_scope": "Chọn phạm vi báo cáo", "reporting.get_repair_bill_summary": "Báo cáo hóa đơn sửa chữa", "reporting.get_ticket_frequency_summary": "Báo cáo tần suất yêu cầu", "reporting.get_employee_star_summary": "Báo cáo đánh giá nhân viên", "knowledge.search": "Tìm trong kho tri thức"
};
type Tool = AgentManagement["tools"][number];
export function serverLabel(tool: Pick<Tool, "server_id" | "server_title">) { return SERVER_LABELS[tool.server_id] || tool.server_title || "Kết nối ngoài"; }
export function toolLabel(tool: Tool) { return TOOL_LABELS[tool.name] || (tool.external && tool.effect !== 'read' ? `Thao tác với ${serverLabel(tool)}` : /[À-ỹ]/.test(tool.name) ? tool.name : `Tra cứu ${serverLabel(tool).toLocaleLowerCase("vi")}`); }
export function toolDescription(tool: Tool) { return tool.external ? tool.effect === 'read' ? "Đọc dữ liệu từ nguồn ngoài được cấp cho đơn vị." : "Thao tác ghi ở nguồn ngoài, cần bạn cho phép từng lần." : `Đọc dữ liệu ${serverLabel(tool).toLocaleLowerCase("vi")} trong phạm vi được cấp.`; }
export function factoryInstructionPreview(configuration: AgentConfiguration, instructions: string, catalogue: Pick<AgentManagement,"tools"|"skills">) {
  const artifact = configuration.factory?.artifact;
  // A saved or local prompt edit must be shown as written, never hidden behind an old generated skill.
  if (!artifact || instructions !== artifact.systemPrompt) return null;
  const tools = configuration.mcp_tools.map(grant => {
    const tool = catalogue.tools.find(tool => tool.server_id === grant.server_id && tool.name === grant.name);
    return tool ? toolLabel(tool) : toolLabel({...grant,description:""});
  });
  const skills = configuration.skill_snapshots ?? (configuration.skill_ids || []).flatMap(id => {
    const skill = catalogue.skills?.find(skill => skill.id === id);
    return skill ? [skill] : [];
  });
  return {description:configuration.description, tools, skills};
}
export function agentDisplayConfiguration(agent: ManagedAgent) { return agent.published && agent.latest_version?.config ? agent.latest_version.config : agent.configuration; }
export function agentRole(agent: ManagedAgent, categories: AgentManagement["categories"]) { if (agent.purpose === "supervisor") return "Supervisor"; const names = (agentDisplayConfiguration(agent).service_categories || []).map(code => categories.find(c => c.code === code)?.name).filter(Boolean); return names.length ? names.join(", ") : "Trả lời khi được hỏi"; }
export function agentStanding(agent: ManagedAgent): { label: string; live: boolean; tone: "ok" | "wait" | "neutral" } { if (agent.published) return {label: "Đang phát hành", live: true, tone: "ok"}; if (agent.review?.status === "pending") return {label: "Chờ duyệt", live: false, tone: "wait"}; return {label: agent.latest_version ? "Đã thu hồi" : "Bản nháp", live: false, tone: "neutral"}; }
export function AgentBadge({label, tone = "neutral"}: {label: string; tone?: "ok" | "wait" | "danger" | "neutral" | "agent"}) { return <span className={`agent-status agent-status--${tone}`}><span aria-hidden="true" />{label}</span>; }
