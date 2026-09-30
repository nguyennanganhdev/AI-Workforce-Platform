import { Link, useRouterState } from '@tanstack/react-router';
import { useOperationsData } from '../hooks/use-operations-data';
import { type OperationsPersona, type MenuId } from '../types/persona';

interface NavItemDef {
  id: MenuId;
  label: string;
  to: string;
  badgeCount?: number;
  section: 'OPERATIONS' | 'MANAGEMENT';
}

export function OperationsSidebar({ open = false, onNavigate }: { open?: boolean; onNavigate?: () => void }) {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  const {
    currentPersona,
    setCurrentPersona,
    currentProfile,
    canAccessMenu,
    myWorkOrders,
    approvals,
    incidents,
    workOrders,
  } = useOperationsData();

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;
  const p1IncidentsCount = incidents.filter((i) => i.severity === 'P1' && i.status === 'OPEN').length;
  const myPendingTasksCount = myWorkOrders.filter((w) => w.status === 'ASSIGNED' || w.status === 'IN_PROGRESS').length;
  const pendingQcCount = workOrders.filter((w) => w.status === 'COMPLETED').length;

  const personas: Array<{ id: OperationsPersona; label: string; roleDesc: string }> = [
    { id: 'STAFF_TECHNICAL', label: 'Kỹ thuật viên', roleDesc: 'Thi công, đo đạc, báo hoàn thành' },
    { id: 'STAFF_SANITATION_A5', label: 'Nhân viên vệ sinh', roleDesc: 'Làm sạch, chụp Before/After, tick bước' },
    { id: 'STAFF_SECURITY', label: 'Nhân viên an ninh', roleDesc: 'Tuần tra check-in, biên bản sự việc, bàn giao ca' },
    { id: 'MANAGER', label: 'Ban quản lý', roleDesc: 'Giám sát, nghiệm thu, duyệt chi phí, liên hệ nhà thầu' },
  ];

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
  const allowedNavItems = allNavItems.filter((item) => canAccessMenu(item.id));
  const operationItems = allowedNavItems.filter((item) => item.section === 'OPERATIONS');
  const managementItems = allowedNavItems.filter((item) => item.section === 'MANAGEMENT');

  return (
    <aside className="operations-sidebar" data-open={open} aria-label="Điều hướng vận hành">
      <Link to="/operations" onClick={onNavigate} className="hidden min-[901px]:flex h-16 flex-col justify-center border-b border-slate-200 px-5">
        <span className="block text-[15px] font-semibold text-slate-900 leading-tight">Vinhomes</span>
        <span className="block text-xs text-slate-500">Quản lý vận hành</span>
      </Link>
      <div className="border-b border-slate-200 p-4">
        <label htmlFor="operations-persona" className="mb-2 block text-xs text-slate-500">Vai trò làm việc</label>
        <select id="operations-persona" value={currentPersona} onChange={(event) => setCurrentPersona(event.target.value as OperationsPersona)} className="w-full h-10 rounded-md border border-slate-200 bg-white px-2.5 text-sm text-slate-800">
          {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.label}</option>)}
        </select>
      </div>
      <nav aria-label="Chức năng vận hành" className="flex-1 space-y-5 overflow-y-auto p-3">
        {[{title: 'Công việc', items: operationItems}, {title: 'Quản lý', items: managementItems}].map((section) => section.items.length > 0 && (
          <div key={section.title}>
            <p className="px-3 pb-1.5 text-xs text-slate-500">{section.title}</p>
            {section.items.map((item) => {
              const active = item.to === '/operations' ? currentPath === '/operations' || currentPath === '/operations/' : currentPath.startsWith(item.to);
              return <Link key={item.id} to={item.to} activeOptions={{ exact: item.to === '/operations' }} onClick={onNavigate} aria-current={active ? 'page' : undefined}>
                <span>{item.label}</span>
                {item.badgeCount !== undefined && <span>{item.badgeCount}</span>}
              </Link>;
            })}
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-200 p-4">
        <p className="text-sm font-medium text-slate-900">{currentProfile.name}</p>
        <p className="mt-1 text-xs text-slate-500">{currentProfile.department}</p>
      </div>
    </aside>
  );
}
