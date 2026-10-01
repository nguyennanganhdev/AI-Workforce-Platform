import { useState, type ReactNode } from "react";
import { useLocation } from "@tanstack/react-router";
import { OperationsSidebarView } from "./operations-sidebar";
import { OperationsHeaderView } from "./operations-header";
import type { MenuId } from "../types/persona";

export const connectedPages: Record<string, string> = {
  "": "Tổng quan vận hành",
  triage: "Tiếp nhận phản ánh",
  incidents: "Phản ánh & sự cố",
  kanban: "Phân công công việc",
  dispatch: "Ticket & hiện trường",
  "my-tasks": "Việc của tôi",
  "work-orders": "Hồ sơ công việc",
  "completed-tasks": "Công việc đã hoàn thành",
  qc: "Nghiệm thu chất lượng",
  team: "Nhóm ban quản lý",
  reports: "Báo cáo vận hành",
  evidence: "Hình ảnh bằng chứng",
  approvals: "Phê duyệt",
  accounts: "Quản lý tài khoản",
  security: "An ninh hiện trường",
  sanitation: "Vệ sinh",
  contractor: "Nhà thầu",
};

/** Uses the Operations shell and responsive navigation styles, with server identity. */
export function ConnectedOperationsShell({
  name,
  management,
  administrator,
  alerts = [],
  children,
}: {
  name?: string;
  management: boolean;
  administrator?: boolean;
  alerts?: {id: string; title: string; location_json: {towerCode?: string}}[];
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const path = useLocation().pathname.split("/")[2] || "";
  const roleLabel = administrator ? "Quản trị hệ thống" : management ? "Ban quản lý" : "Nhân viên hiện trường";
  const pages = management
    ? [
        "",
        "triage",
        "incidents",
        "kanban",
        "work-orders",
        "qc",
        "completed-tasks",
        "team",
        "reports",
      ]
    : ["my-tasks", "work-orders", "completed-tasks"];
  if (administrator) pages.unshift("accounts");
  return (
    <div
      lang="vi"
      translate="no"
      className="operations-app notranslate flex h-[100dvh] w-full overflow-hidden font-sans"
    >
      {open && (
        <div
          className="operations-sidebar-backdrop"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}
      <OperationsSidebarView open={open} onNavigate={() => setOpen(false)}
        account={{name: name || 'Đang tải tài khoản…', identifier: '', scope: 'Phạm vi được cấp', roleLabel}}
        workspaceItems={administrator ? [['accounts', 'Quản lý tài khoản']] : []}
        operationItems={pages.filter(page => !['accounts', 'team', 'reports', 'qc'].includes(page)).map(page => ({id: (page || 'dashboard') as MenuId, label: connectedPages[page], to: `/operations${page ? `/${page}` : ''}`, section: 'OPERATIONS'}))}
        managementItems={pages.filter(page => ['team', 'reports', 'qc'].includes(page)).map(page => ({id: page as MenuId, label: connectedPages[page], to: `/operations/${page}`, section: 'MANAGEMENT'}))} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <OperationsHeaderView menuOpen={open} onToggleMenu={() => setOpen(!open)}
          breadcrumb={{section: 'Vận hành đô thị', page: connectedPages[path] || 'Không gian làm việc'}}
          name={name || 'Đang tải tài khoản…'} roleTitle={roleLabel} p1Incidents={alerts} pendingApprovals={[]} />
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 xl:p-8">
          <div className="operations-content w-full min-w-0 max-w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
