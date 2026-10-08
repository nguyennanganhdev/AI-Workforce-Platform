import type { ReactNode } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import { useOperationsData } from '../hooks/use-operations-data';
import { type MenuId } from '../types/persona';
import { previewAccount } from '../auth/demo-access';
import { canViewPath, roleLabels } from '../workspace/model';
import { useWorkspace } from '../workspace/use-workspace';
import { workItems } from '../workspace/work-items';

interface NavItemDef {
  id: MenuId;
  label: string;
  to: string;
  badgeCount?: number;
  icon?: ReactNode;
  section: 'OPERATIONS' | 'MANAGEMENT';
}

export function OperationsSidebar({ open = false, onNavigate }: { open?: boolean; onNavigate?: () => void }) {

  const {
    currentPersona,
    currentProfile,
    canAccessMenu,
    approvals,
    incidents,
    workOrders,
    tasks,
    evidence,
  } = useOperationsData();

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;
  const p1IncidentsCount = incidents.filter((i) => i.severity === 'P0' && i.status === 'OPEN').length;
  const workspace = useWorkspace();
  const myPendingTasksCount = workspace.account ? workItems(workspace.account, workspace.state, {tasks,incidents,workOrders,evidence}).filter(w=>w.phase!=='history').length : 0;
  const pendingQcCount = workOrders.filter((w) => w.status === 'COMPLETED').length;

  const account = previewAccount();
  const workspaceItems = account?.role === 'admin' ? [['accounts', 'Quản lý tài khoản']] : account?.role === 'manager' ? [['team', 'Nhóm ban quản lý'], ['reports', 'Báo cáo vận hành']] : [];

  const allNavItems: NavItemDef[] = [
    {
      id: 'dashboard',
      label: 'Tổng quan vận hành',
      to: '/operations',
      section: 'OPERATIONS',
    },
    {
      id: 'my-tasks',
      label: 'Việc của tôi',
      to: '/operations/my-tasks',
      badgeCount: myPendingTasksCount > 0 ? myPendingTasksCount : undefined,
      section: 'OPERATIONS',
    },
    {
      id: 'completed-tasks',
      label: 'Công việc đã hoàn thành',
      to: '/operations/completed-tasks',
      section: 'OPERATIONS',
    },
    {
      id: 'triage',
      label: 'Tiếp nhận phản ánh',
      to: '/operations/triage',
      section: 'OPERATIONS',
    },
    {
      id: 'incidents',
      label: 'Phản ánh & Sự cố',
      to: '/operations/incidents',
      badgeCount: p1IncidentsCount > 0 ? p1IncidentsCount : undefined,
      section: 'OPERATIONS',
    },
    {
      id: 'kanban',
      label: 'Phân công công việc',
      to: '/operations/kanban',
      section: 'OPERATIONS',
    },
    {
      id: 'work-orders',
      label: currentProfile.canAssignWork
        ? 'Quản lý phiếu thi công'
        : currentPersona === 'QC_INSPECTOR'
          ? 'Hồ sơ chờ nghiệm thu'
          : 'Hồ sơ công việc',
      to: '/operations/work-orders',
      section: 'OPERATIONS',
    },
    {
      id: 'sanitation',
      label: currentPersona === 'STAFF_SANITATION_A5'
        ? 'Thực hiện vệ sinh A5'
        : 'Giám sát vệ sinh A5',
      to: '/operations/sanitation',
      section: 'OPERATIONS',
    },
    {
      id: 'security',
      label: 'An ninh hiện trường',
      to: '/operations/security',
      section: 'OPERATIONS',
    },
    {
      id: 'contractor',
      label: 'Công việc nhà thầu',
      to: '/operations/contractor',
      section: 'OPERATIONS',
    },
    {
      id: 'qc',
      label: 'Nghiệm thu chất lượng',
      to: '/operations/qc',
      badgeCount: pendingQcCount > 0 ? pendingQcCount : undefined,
      section: 'MANAGEMENT',
    },
    {
      id: 'approvals',
      label: 'Phê duyệt chi phí',
      to: '/operations/approvals',
      badgeCount: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
      section: 'MANAGEMENT',
    },
  ];

  // RBAC Filtering: Only render menu items allowed for current persona
  const allowedNavItems = allNavItems.filter((item) => account && canViewPath(account.role, item.to) && canAccessMenu(item.id));
  const operationItems = allowedNavItems.filter((item) => item.section === 'OPERATIONS');
  const managementItems = allowedNavItems.filter((item) => item.section === 'MANAGEMENT');

  return <OperationsSidebarView open={open} onNavigate={onNavigate}
    account={{ name: account?.name || currentProfile.name, identifier: account?.identifier || '', scope: account?.scope || '', roleLabel: account ? roleLabels[account.role] : currentProfile.department }}
    workspaceItems={workspaceItems} operationItems={operationItems} managementItems={managementItems} />;
}

export function OperationsSidebarView({ open = false, onNavigate, account, workspaceItems, operationItems, managementItems }: {
  open?: boolean; onNavigate?: () => void;
  account: { name: string; identifier: string; scope: string; roleLabel: string };
  workspaceItems: string[][]; operationItems: NavItemDef[]; managementItems: NavItemDef[];
}) {
  const currentPath = useRouterState().location.pathname;
  return (
    <aside className="operations-sidebar" data-open={open} aria-label="Điều hướng vận hành">
      <Link to="/operations" onClick={onNavigate} className="hidden min-[901px]:flex h-16 flex-col justify-center border-b border-slate-200 px-5">
        <span className="block text-[15px] font-semibold text-slate-900 leading-tight">Vinhomes</span>
        <span className="block text-xs text-slate-500">Quản lý vận hành</span>
      </Link>
      {/* Without an identifier or a scope this block would only repeat the footer. */}
      {(account.identifier || account.scope) && <div className="border-b border-slate-200 p-4">
        <p className="mb-2 block text-xs text-slate-500">Vai trò được cấp</p>
        <strong className="text-sm">{account.roleLabel}</strong>
        <p className="text-xs text-slate-500 mt-1">{[account.identifier, account.scope].filter(Boolean).join(' · ')}</p>
      </div>}
      <nav aria-label="Chức năng vận hành" className="flex-1 space-y-5 overflow-y-auto p-3">
        {workspaceItems.length > 0 && <div><p className="px-3 pb-1.5 text-xs text-slate-500">Không gian làm việc</p>{workspaceItems.map(([path, label]) => <a key={path} href={`/operations/${path}`} onClick={onNavigate} aria-current={currentPath === `/operations/${path}` ? 'page' : undefined}>{label}</a>)}</div>}
        {[{title: 'Công việc', items: operationItems}, {title: 'Quản lý', items: managementItems}].map((section) => section.items.length > 0 && (
          <div key={section.title}>
            {/* One short list needs no heading; the headings sort a long one. */}
            {operationItems.length > 0 && managementItems.length > 0 && <p className="px-3 pb-1.5 text-xs text-slate-500">{section.title}</p>}
            {section.items.map((item) => {
              const active = item.to === '/operations' ? currentPath === '/operations' || currentPath === '/operations/' : currentPath.startsWith(item.to);
              return <Link key={item.id} to={item.to} activeOptions={{ exact: item.to === '/operations' }} onClick={onNavigate} aria-current={active ? 'page' : undefined}>
                <span className="flex items-center gap-2.5">{item.icon}{item.label}</span>
                {item.badgeCount !== undefined && <span aria-label={`${item.badgeCount} mục cần xử lý`}>{item.badgeCount}</span>}
              </Link>;
            })}
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-200 p-4">
        <p className="text-sm font-medium text-slate-900">{account.name}</p>
        <p className="mt-1 text-xs text-slate-500">{account.roleLabel}</p>
      </div>
    </aside>
  );
}
