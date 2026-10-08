import type { Account, WorkspaceState, Role } from "./model";
import { stageLabels } from "./model";
import type { VhTask } from "../types/task";
import type { VhIncident } from "../types/incident";
import type { VhWorkOrder } from "../types/work-order";
import type { VhEvidenceRef } from "../types/evidence";
import { getTechnicianStep } from "../lib/field-flow";

export type WorkPhase = "new" | "active" | "waiting" | "history";
export type WorkItem = {
  key: string;
  ticketId: string;
  title: string;
  place: string;
  severity: string;
  department: string;
  assignee: string;
  phase: WorkPhase;
  status: string;
  ticket?: string;
  job?: string;
  task?: string;
  updatedAt: string;
};
export type LegacyWork = {
  tasks: VhTask[];
  incidents: VhIncident[];
  workOrders: VhWorkOrder[];
  evidence: VhEvidenceRef[];
};
export const workPath = (role: Role) =>
  role === "manager" ? "/operations/kanban" : "/operations/my-tasks";
export function ticketHref(role: Role, ticketId: string) {
  return `${workPath(role)}?ticket=${encodeURIComponent(ticketId)}`;
}
// Explicit fixture identities, never infer ownership merely from having the same role.
export const legacyExecutor = (account: Account) =>
  (
    ({
      "demo-tech": "usr-tech-01",
      "demo-security": "usr-sec-01",
      "demo-cleaning": "usr-cleaner-01",
    }) as Record<string, string>
  )[account.id] ?? account.id;
export function ticketPhase(stage: string): WorkPhase {
  if (["completed", "cancelled"].includes(stage)) return "history";
  if (["queued", "assigned"].includes(stage)) return "new";
  if (
    [
      "awaiting-consent",
      "isolation-requested",
      "isolation-approved",
      "awaiting-confirmation",
      "controlled",
      "cancel-requested",
    ].includes(stage)
  )
    return "waiting";
  return "active";
}
const departments: Record<string, string> = {
  electric: "Kỹ thuật",
  water: "Kỹ thuật",
  security: "An ninh",
  TECHNICAL: "Kỹ thuật",
  MEP: "Kỹ thuật",
  SECURITY: "An ninh",
  SANITATION: "Vệ sinh",
  LANDSCAPE: "Cảnh quan",
  ELEVATOR: "Thang máy",
  GENERAL: "Tổng hợp",
};
/** A single read model; references original records rather than copying them into another store. */
export function workItems(
  account: Account,
  state: WorkspaceState,
  legacy: LegacyWork,
): WorkItem[] {
  if (
    !["manager", "technical", "security", "sanitation"].includes(
      account.role,
    ) ||
    account.status !== "active"
  )
    return [];
  const manager = account.role === "manager";
  const rows: WorkItem[] = state.cases
    .filter(
      (c) =>
        c.scope === account.scope && (manager || c.workerId === account.id),
    )
    .map((c) => ({
      key: `ticket:${c.id}`,
      ticket: c.id,
      ticketId: c.id,
      title: c.title,
      place: `${c.scope} · ${c.apartment}`,
      severity: c.severity,
      department: departments[c.domain],
      assignee:
        state.accounts.find((a) => a.id === c.workerId)?.name ??
        "Chưa phân công",
      phase: ticketPhase(c.stage),
      status: stageLabels[c.stage],
      updatedAt: c.events.at(-1)?.at ?? c.createdAt,
    }));
  const inScope = (incident?: VhIncident) =>
    incident?.location_json.towerCode === account.scope;
  const append = (task: VhTask, incident: VhIncident, wo?: VhWorkOrder) => {
    const step = wo
      ? getTechnicianStep(
          wo,
          legacy.evidence.filter((e) => e.work_order_id === wo.id),
          incident.category,
          task,
        )
      : undefined;
    const phase: WorkPhase = step
      ? (
          {
            NEW: "new",
            ACTIVE: "active",
            WAITING: "waiting",
            HISTORY: "history",
          } as const
        )[step.tab]
      : ["DONE", "CANCELLED"].includes(task.status)
        ? "history"
        : task.status === "BLOCKED"
          ? "waiting"
          : task.status === "IN_PROGRESS"
            ? "active"
            : "new";
    rows.push({
      key: manager ? `task:${task.id}` : `job:${wo!.id}`,
      task: manager ? task.id : undefined,
      job: manager ? undefined : wo!.id,
      ticketId: incident.id,
      title: task.title,
      place: [
        incident.location_json.towerCode,
        incident.location_json.apartmentCode || incident.location_json.areaCode,
      ]
        .filter(Boolean)
        .join(" · "),
      severity: incident.severity,
      department: departments[task.domain_type] ?? task.domain_type,
      assignee: wo?.executor_name || task.assignee_name || "Chưa phân công",
      phase,
      status:
        step?.label ??
        {
          OPEN: "Chờ phân công",
          ASSIGNED: "Đã phân công",
          IN_PROGRESS: "Đang làm",
          BLOCKED: "Tạm hoãn",
          DONE: "Hoàn tất",
          CANCELLED: "Đã hủy",
        }[task.status],
      updatedAt: wo?.updated_at ?? task.updated_at,
    });
  };
  if (manager) {
    for (const task of legacy.tasks) {
      const incident = legacy.incidents.find((i) => i.id === task.incident_id);
      if (!inScope(incident)) continue;
      const latest = legacy.workOrders
        .filter((w) => w.task_id === task.id)
        .sort(
          (a, b) =>
            b.attempt_no - a.attempt_no ||
            b.updated_at.localeCompare(a.updated_at),
        )[0];
      append(task, incident!, latest);
    }
  } else {
    for (const wo of legacy.workOrders.filter(
      (w) => w.executor_id === legacyExecutor(account),
    )) {
      const task = legacy.tasks.find((t) => t.id === wo.task_id),
        incident = legacy.incidents.find((i) => i.id === wo.incident_id);
      if (task && inScope(incident)) append(task, incident!, wo);
    }
  }
  return rows.sort(
    (a, b) =>
      a.severity.localeCompare(b.severity) ||
      b.updatedAt.localeCompare(a.updatedAt),
  );
}
