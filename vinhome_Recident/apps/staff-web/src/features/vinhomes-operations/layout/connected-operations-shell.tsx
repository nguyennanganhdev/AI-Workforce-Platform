import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "@tanstack/react-router";
import { IconBuildingCommunity, IconChartBar, IconChecklist, IconHistory, IconUsers } from "@tabler/icons-react";
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { ConnectedNavigation, type NavigationPage } from './connected-navigation';
import { FieldShell } from "./field-shell";
import { OperationsHeaderView } from './operations-header';

export const connectedPages: Record<string, string> = {
  "": "Tổng quan vận hành",
  triage: "Tiếp nhận phản ánh",
  incidents: "Phản ánh & sự cố",
  kanban: "Công việc",
  dispatch: "Ticket & hiện trường",
  "my-tasks": "Việc của tôi",
  "work-orders": "Hồ sơ công việc",
  "completed-tasks": "Công việc đã hoàn thành",
  qc: "Nghiệm thu chất lượng",
  reports: "Báo cáo",
  evidence: "Hình ảnh bằng chứng",
  approvals: "Phê duyệt",
  accounts: "Tài khoản",
  units: "Đơn vị quản lý",
  audit: "Nhật ký",
  security: "An ninh hiện trường",
  sanitation: "Vệ sinh",
  contractor: "Nhà thầu",
};

// Management works from two places. The other pages still answer their address, without a menu entry.
const managementNav: {page:NavigationPage; icon:ReactNode}[] = [
  { page: "kanban", icon: <IconChecklist className="size-4" stroke={1.75} /> },
  { page: "reports", icon: <IconChartBar className="size-4" stroke={1.75} /> },
];

// What an administrator sets up for management to work with.
const adminNav: {page:NavigationPage; icon:ReactNode}[] = [
  { page: "accounts", icon: <IconUsers className="size-4" stroke={1.75} /> },
  { page: "units", icon: <IconBuildingCommunity className="size-4" stroke={1.75} /> },
  { page: "audit", icon: <IconHistory className="size-4" stroke={1.75} /> },
];

export type ShellNotice = { id: string; title: string; note: string; to: string; count?: number };

/** Uses the Operations shell and responsive navigation styles, with server identity. */
export function ConnectedOperationsShell({
  name,
  management,
  administrator,
  field = false,
  alerts = [],
  notices = [],
  flush = false,
  banner,
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
  /** What the field frame announces above the page, when that is not every notice. */
  banner?: ShellNotice[];
  children: ReactNode;
}) {
  const [open, setOpen] = useState(() => { try { return localStorage.getItem('operations.navigation') !== 'closed'; } catch { return true; } });
  const toggle = (value: boolean) => { setOpen(value); try { localStorage.setItem('operations.navigation', value ? 'open' : 'closed'); } catch { /* Navigation still works without storage. */ } };
  const path = useLocation().pathname.split("/")[2] || (management ? "kanban" : "");
  const roleLabel = administrator ? "Quản trị hệ thống" : management ? "Ban quản lý" : "Nhân viên hiện trường";
  useEffect(() => {
    document.title = `${notices.length ? `(${notices.length}) ` : ""}Vinhomes · ${field ? "Việc của tôi" : "Quản lý vận hành"}`;
  }, [notices.length, field]);
  if (field) return <FieldShell name={name} notices={banner ?? notices}>{children}</FieldShell>;
  return (
    <SidebarProvider open={open} onOpenChange={toggle}
      lang="vi"
      translate="no"
      className="operations-app connected-shell notranslate flex h-[100dvh] min-h-0 w-full overflow-hidden font-sans"
    >
      <ConnectedNavigation name={name || 'Đang tải tài khoản…'} role={roleLabel} page={path}
        work={(management ? managementNav : []).map(({page,icon}) => ({page,icon,label:connectedPages[page],count:page === 'kanban' ? notices.length : undefined}))}
        setup={administrator ? adminNav.map(({page,icon}) => ({page,icon,label:connectedPages[page]})) : []} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="connected-header"><SidebarTrigger aria-label={open ? 'Ẩn thanh điều hướng' : 'Hiện thanh điều hướng'} />
          <OperationsHeaderView menuOpen={open} onToggleMenu={() => toggle(!open)} personalAccountsUrl="/settings/connected-accounts"
            breadcrumb={{section:'Vận hành đô thị',page:connectedPages[path] || 'Không gian làm việc'}}
            name={name || 'Đang tải tài khoản…'} roleTitle={roleLabel} p1Incidents={alerts} pendingApprovals={[]} notices={notices} />
        </div>
        {flush ? <main className="min-h-0 flex-1 overflow-hidden">{children}</main> : (
          <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 xl:p-8">
            <div className="operations-content w-full min-w-0 max-w-full">
              {children}
            </div>
          </main>
        )}
      </div>
    </SidebarProvider>
  );
}
