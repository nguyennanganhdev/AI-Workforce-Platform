import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "@tanstack/react-router";
import { IconBolt, IconBuildingCommunity, IconChartBar, IconChecklist, IconCpu, IconHistory, IconMessages, IconPlugConnected, IconUsers } from "@tabler/icons-react";
import { OperationsSidebarView } from "./operations-sidebar";
import { OperationsHeaderView } from "./operations-header";
import { FieldShell } from "./field-shell";
import type { MenuId } from "../types/persona";

export const connectedPages: Record<string, string> = {
  "": "Tổng quan vận hành",
  agents: "Agent",
  triage: "Tiếp nhận phản ánh",
  incidents: "Phản ánh & sự cố",
  kanban: "Công việc",
  dispatch: "Ticket & hiện trường",
  "my-tasks": "Việc của tôi",
  "work-orders": "Hồ sơ công việc",
  "completed-tasks": "Công việc đã hoàn thành",
  qc: "Nghiệm thu chất lượng",
  team: "Điều phối",
  reports: "Báo cáo",
  evidence: "Hình ảnh bằng chứng",
  approvals: "Phê duyệt",
  accounts: "Tài khoản",
  connections: "Kết nối ngoài",
  units: "Đơn vị quản lý",
  models: "Model",
  audit: "Nhật ký",
  security: "An ninh hiện trường",
  sanitation: "Vệ sinh",
  contractor: "Nhà thầu",
};

// Management works from four places. The other pages still answer their address, without a menu entry.
const managementNav = [
  { page: "team", icon: <IconMessages className="size-4" stroke={1.75} /> },
  { page: "kanban", icon: <IconChecklist className="size-4" stroke={1.75} /> },
  { page: "agents", icon: <IconBolt className="size-4" stroke={1.75} /> },
  { page: "reports", icon: <IconChartBar className="size-4" stroke={1.75} /> },
];

// What an administrator sets up for management to work with.
const adminNav = [
  { page: "accounts", icon: <IconUsers className="size-4" stroke={1.75} /> },
  { page: "units", icon: <IconBuildingCommunity className="size-4" stroke={1.75} /> },
  { page: "connections", icon: <IconPlugConnected className="size-4" stroke={1.75} /> },
  { page: "models", icon: <IconCpu className="size-4" stroke={1.75} /> },
  { page: "audit", icon: <IconHistory className="size-4" stroke={1.75} /> },
];

export type ShellNotice = { id: string; title: string; note: string; to: string };

/** Uses the Operations shell and responsive navigation styles, with server identity. */
export function ConnectedOperationsShell({
  name,
  management,
  administrator,
  field = false,
  alerts = [],
  notices = [],
  flush = false,
  children,
}: {
  name?: string;
  management: boolean;
  administrator?: boolean;
  /** Someone who does the work on site: their own frame, without this menu and header. */
  field?: boolean;
  alerts?: {id: string; title: string; location_json: {towerCode?: string}}[];
  /** Sessions waiting for management: the bell, the menu badge and the tab title count them. */
  notices?: ShellNotice[];
  /** The page fills the pane and scrolls inside itself, as a conversation does. */
  flush?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const path = useLocation().pathname.split("/")[2] || (management ? "team" : "");
  const roleLabel = administrator ? "Quản trị hệ thống" : management ? "Ban quản lý" : "Nhân viên hiện trường";
  useEffect(() => {
    document.title = `${notices.length ? `(${notices.length}) ` : ""}Vinhomes · ${field ? "Việc của tôi" : "Quản lý vận hành"}`;
  }, [notices.length, field]);
  if (field) return <FieldShell name={name} notices={notices}>{children}</FieldShell>;
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
        account={{name: name || 'Đang tải tài khoản…', identifier: '', scope: '', roleLabel}}
        workspaceItems={[]}
        operationItems={management
          ? managementNav.map(({page, icon}) => ({id: page as MenuId, label: connectedPages[page], to: `/operations/${page}`, icon, section: 'OPERATIONS' as const,
              badgeCount: page === 'team' && notices.length ? notices.length : undefined}))
          // A technician has one list: what is open and, on its second tab, what is done.
          : [{id: 'my-tasks' as MenuId, label: connectedPages['my-tasks'], to: '/operations/my-tasks', section: 'OPERATIONS' as const,
              icon: <IconChecklist className="size-4" stroke={1.75} />, badgeCount: notices.length || undefined}]}
        managementItems={administrator ? adminNav.map(({page, icon}) => ({id: page as MenuId, label: connectedPages[page], to: `/operations/${page}`, icon, section: 'MANAGEMENT' as const})) : []} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <OperationsHeaderView menuOpen={open} onToggleMenu={() => setOpen(!open)}
          personalAccountsUrl="/settings/connected-accounts"
          breadcrumb={{section: 'Vận hành đô thị', page: connectedPages[path] || 'Không gian làm việc'}}
          name={name || 'Đang tải tài khoản…'} roleTitle={roleLabel} p1Incidents={alerts} pendingApprovals={[]} notices={notices} />
        {flush ? <main className="min-h-0 flex-1 overflow-hidden">{children}</main> : (
          <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 xl:p-8">
            <div className="operations-content w-full min-w-0 max-w-full">
              {children}
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
