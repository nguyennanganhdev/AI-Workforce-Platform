import { useState } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import {
  IconLayoutDashboard,
  IconChecklist,
  IconAlertTriangle,
  IconColumns,
  IconPhoto,
  IconShieldCheck,
  IconCash,
  IconSettings,
  IconBuildingCommunity,
  IconChevronRight,
  IconBriefcase,
  IconInbox,
  IconTrash,
  IconShield,
  IconTool,
  IconUser,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import { PERSONA_PROFILES, type OperationsPersona, type MenuId } from '../types/persona';

interface NavItemDef {
  id: MenuId;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  badgeCount?: number;
  badgeColor?: string;
  section: 'OPERATIONS' | 'MANAGEMENT';
}

export function OperationsSidebar() {
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
    qcResults,
  } = useOperationsData();

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;
  const p1IncidentsCount = incidents.filter((i) => i.severity === 'P1' && i.status === 'OPEN').length;
  const myPendingTasksCount = myWorkOrders.filter((w) => w.status === 'ASSIGNED' || w.status === 'IN_PROGRESS').length;
  const pendingQcCount = workOrders.filter((w) => w.status === 'COMPLETED').length;

  const personas: Array<{ id: OperationsPersona; label: string; roleDesc: string }> = [
    { id: 'STAFF_TECHNICAL', label: '👷 1. Kỹ thuật viên (MEP)', roleDesc: 'Thi công, đo đạc, báo hoàn thành' },
    { id: 'STAFF_SANITATION_A5', label: '🧹 2. Nhân viên Vệ sinh A5', roleDesc: 'Làm sạch, chụp Before/After, tick bước' },
    { id: 'STAFF_SECURITY', label: '🛡️ 3. Nhân viên An ninh', roleDesc: 'Tuần tra check-in, biên bản sự việc, bàn giao ca' },
    { id: 'CONTRACTOR', label: '🔧 4. Nhà thầu & Đối tác', roleDesc: 'Nhận việc, phân thợ, ghi vật tư thay' },
    { id: 'SUPERVISOR', label: '📋 5. Trưởng nhóm & Giám sát', roleDesc: 'Điều phối ca, kiểm tra tiến độ, nhắc việc' },
    { id: 'QC_INSPECTOR', label: '🔍 6. Chuyên viên QC', roleDesc: 'Chấm checklist, ký biên bản PASS/FAIL' },
    { id: 'MANAGER', label: '🏢 7. Ban Quản Lý (BQL)', roleDesc: 'Toàn cảnh đô thị, duyệt chi phí, đóng sự cố' },
  ];

  const allNavItems: NavItemDef[] = [
    {
      id: 'dashboard',
      label: 'Tổng quan vận hành',
      to: '/operations',
      icon: IconLayoutDashboard,
      section: 'OPERATIONS',
    },
    {
      id: 'my-tasks',
      label: 'Việc của tôi',
      to: '/operations/my-tasks',
      icon: IconBriefcase,
      badgeCount: myPendingTasksCount > 0 ? myPendingTasksCount : undefined,
      badgeColor: 'bg-blue-600 text-white',
      section: 'OPERATIONS',
    },
    {
      id: 'triage',
      label: 'Tiếp nhận phản ánh',
      to: '/operations/triage',
      icon: IconInbox,
      section: 'OPERATIONS',
    },
    {
      id: 'incidents',
      label: 'Quản lý sự cố',
      to: '/operations/incidents',
      icon: IconAlertTriangle,
      badgeCount: p1IncidentsCount > 0 ? p1IncidentsCount : undefined,
      badgeColor: 'bg-rose-600 text-white',
      section: 'OPERATIONS',
    },
    {
      id: 'kanban',
      label: 'Bảng phân bổ việc',
      to: '/operations/kanban',
      icon: IconColumns,
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
      icon: IconChecklist,
      section: 'OPERATIONS',
    },
    {
      id: 'sanitation',
      label: currentPersona === 'STAFF_SANITATION_A5'
        ? 'Thực hiện vệ sinh A5'
        : 'Giám sát vệ sinh A5',
      to: '/operations/sanitation',
      icon: IconTrash,
      section: 'OPERATIONS',
    },
    {
      id: 'security',
      label: 'An ninh hiện trường',
      to: '/operations/security',
      icon: IconShield,
      section: 'OPERATIONS',
    },
    {
      id: 'contractor',
      label: 'Cổng nhà thầu đối tác',
      to: '/operations/contractor',
      icon: IconTool,
      section: 'OPERATIONS',
    },
    {
      id: 'evidence',
      label: 'Kho ảnh hiện trường',
      to: '/operations/evidence',
      icon: IconPhoto,
      section: 'OPERATIONS',
    },
    {
      id: 'qc',
      label: 'Nghiệm thu chất lượng',
      to: '/operations/qc',
      icon: IconShieldCheck,
      badgeCount: pendingQcCount > 0 ? pendingQcCount : undefined,
      badgeColor: 'bg-purple-600 text-white',
      section: 'MANAGEMENT',
    },
    {
      id: 'approvals',
      label: 'Phê duyệt chi phí',
      to: '/operations/approvals',
      icon: IconCash,
      badgeCount: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
      badgeColor: 'bg-emerald-600 text-white',
      section: 'MANAGEMENT',
    },
  ];

  // RBAC Filtering: Only render menu items allowed for current persona
  const allowedNavItems = allNavItems.filter((item) => canAccessMenu(item.id));
  const operationItems = allowedNavItems.filter((item) => item.section === 'OPERATIONS');
  const managementItems = allowedNavItems.filter((item) => item.section === 'MANAGEMENT');

  return (
    <aside className="w-68 bg-white border-r border-slate-200/80 flex flex-col h-screen select-none font-sans shrink-0">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <Link to="/operations" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 group-hover:scale-105 transition-transform">
            <IconBuildingCommunity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-900 tracking-tight text-sm">BQL Vinhomes</span>
              <span className="px-1.5 py-0.2 text-[10px] font-semibold bg-blue-50 text-blue-600 rounded">Vận hành</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Smart City Operations</p>
          </div>
        </Link>
      </div>

      {/* Role Switcher Box (7 Roles) */}
      <div className="px-3.5 py-2.5 border-b border-slate-100 bg-slate-50/70">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Phân quyền vai trò (RBAC)</span>
          <span className="text-[9px] font-semibold px-1.5 py-0.2 bg-blue-100 text-blue-700 rounded font-mono">
            {currentProfile.role}
          </span>
        </div>
        <select
          value={currentPersona}
          onChange={(e) => setCurrentPersona(e.target.value as OperationsPersona)}
          className="w-full text-xs font-semibold text-slate-800 bg-white border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500 cursor-pointer shadow-2xs"
        >
          {personas.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        <div className="mt-1.5 text-[11px] text-slate-600 flex items-center gap-1.5 truncate">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          <span className="truncate font-medium">{currentProfile.name} • {currentProfile.roleTitle}</span>
        </div>
      </div>

      {/* Main Navigation Menu (RBAC Filtered) */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {/* Operations Section */}
        {operationItems.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 pb-1 block">
              Thực thi hiện trường
            </span>
            {operationItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.to === '/operations'
                  ? currentPath === '/operations' || currentPath === '/operations/'
                  : currentPath.startsWith(item.to);

              return (
                <Link
                  key={item.id}
                  to={item.to}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all group ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-xs font-bold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 transition-transform group-hover:scale-110 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-600'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badgeCount !== undefined && (
                    <span
                      className={`text-[10px] font-extrabold px-1.5 py-0.2 rounded-full ${
                        isActive ? 'bg-white text-blue-600' : item.badgeColor || 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {item.badgeCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        )}

        {/* Management & Quality Section */}
        {managementItems.length > 0 && (
          <div className="space-y-1 pt-1 border-t border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 pb-1 block">
              Quản lý & Kiểm định
            </span>
            {managementItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath.startsWith(item.to);

              return (
                <Link
                  key={item.id}
                  to={item.to}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all group ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-xs font-bold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 transition-transform group-hover:scale-110 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-600'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badgeCount !== undefined && (
                    <span
                      className={`text-[10px] font-extrabold px-1.5 py-0.2 rounded-full ${
                        isActive ? 'bg-white text-blue-600' : item.badgeColor || 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {item.badgeCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* Footer Profile */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/60">
        <div className="flex items-center gap-2.5 p-2 rounded-xl bg-white border border-slate-200/80 shadow-2xs">
          <img
            src={currentProfile.avatarUrl}
            alt={currentProfile.name}
            className="w-8 h-8 rounded-lg object-cover ring-1 ring-slate-200"
          />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-slate-800 truncate leading-tight">{currentProfile.name}</p>
            <p className="text-[10px] text-slate-400 truncate mt-0.5">{currentProfile.department}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
