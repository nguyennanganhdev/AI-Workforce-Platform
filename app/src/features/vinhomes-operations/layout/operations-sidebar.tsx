import { useState } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import {
  IconLayoutDashboard,
  IconClipboardList,
  IconLayoutKanban,
  IconPhoto,
  IconShieldCheck,
  IconCash,
  IconAlertTriangle,
  IconChevronDown,
  IconChevronRight,
  IconBuildingCommunity,
  IconUserCheck,
  IconSparkles,
  IconInbox,
  IconTrash,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import { PERSONA_PROFILES, type OperationsPersona } from '../types/persona';

export function OperationsSidebar() {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  const { currentPersona, setCurrentPersona, approvals, incidents, workOrders } = useOperationsData();
  const profile = PERSONA_PROFILES[currentPersona as keyof typeof PERSONA_PROFILES];

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;
  const p1IncidentsCount = incidents.filter((i) => i.severity === 'P1' && i.status === 'OPEN').length;

  const [workOrderMenuOpen, setWorkOrderMenuOpen] = useState(false);

  const personas: Array<{ id: OperationsPersona; label: string; roleDesc: string }> = [
    { id: 'STAFF_TECHNICAL', label: '👷 Kỹ sư Hiện trường', roleDesc: 'Kỹ thuật MEP, PCCC, Thang máy' },
    { id: 'STAFF_SANITATION', label: '🧹 Giám sát Vệ sinh', roleDesc: 'Vệ sinh môi trường A5 & Cảnh quan' },
    { id: 'MANAGER', label: '🏢 Ban Quản Lý (BQL)', roleDesc: 'Phê duyệt, Giám sát vận hành đô thị' },
  ];

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
            <p className="text-[11px] text-slate-400 font-medium">Khu đô thị thông minh</p>
          </div>
        </Link>
      </div>

      {/* Persona Switcher Box */}
      <div className="px-3.5 py-2.5 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Đang thao tác với vai trò</span>
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
        <div className="mt-1.5 text-[11px] text-slate-500 flex items-center gap-1.5 truncate">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          <span className="truncate">{profile.name} — {profile.roleTitle}</span>
        </div>
      </div>

      {/* Main Navigation Menu */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {/* 1. Dashboard */}
        <Link
          to="/operations"
          className={`flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath === '/operations' || currentPath === '/operations/'
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <IconLayoutDashboard className={`w-4 h-4 ${currentPath === '/operations' ? 'text-blue-600' : 'text-slate-400'}`} />
          <span>Tổng quan</span>
        </Link>

        {/* 2. Tiếp nhận phản ánh */}
        <Link
          to="/operations/triage"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/triage')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconInbox className={`w-4 h-4 ${currentPath.includes('/operations/triage') ? 'text-blue-600' : 'text-slate-400'}`} />
            <span>Tiếp nhận phản ánh</span>
          </div>
        </Link>

        {/* 3. Quản lý sự cố */}
        <Link
          to="/operations/incidents"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/incidents')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconAlertTriangle className={`w-4 h-4 ${p1IncidentsCount > 0 ? 'text-rose-500' : 'text-slate-400'}`} />
            <span>Quản lý sự cố</span>
          </div>
          {p1IncidentsCount > 0 && (
            <span className="px-1.5 py-0.2 text-[10px] font-bold bg-rose-100 text-rose-700 rounded-full">
              {p1IncidentsCount} khẩn
            </span>
          )}
        </Link>

        {/* 4. Phân công nhiệm vụ */}
        <Link
          to="/operations/kanban"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/kanban')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconLayoutKanban className={`w-4 h-4 ${currentPath.includes('/operations/kanban') ? 'text-blue-600' : 'text-slate-400'}`} />
            <span>Phân công nhiệm vụ</span>
          </div>
        </Link>

        {/* 5. Phiếu thi công */}
        <div>
          <button
            type="button"
            onClick={() => setWorkOrderMenuOpen(!workOrderMenuOpen)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <IconClipboardList className="w-4 h-4 text-slate-400" />
              <span>Phiếu thi công</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded">
                {workOrders.length}
              </span>
              {workOrderMenuOpen ? (
                <IconChevronDown className="w-3.5 h-3.5 text-slate-400" />
              ) : (
                <IconChevronRight className="w-3.5 h-3.5 text-slate-400" />
              )}
            </div>
          </button>

          {workOrderMenuOpen && (
            <div className="mt-1 ml-4 pl-3 border-l border-slate-200/80 space-y-1">
              <Link
                to="/operations/work-orders"
                className={`flex items-center px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  currentPath.includes('/operations/work-orders')
                    ? 'text-blue-600 font-bold bg-blue-50/60'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <span>Tất cả phiếu thi công</span>
              </Link>
              <Link
                to="/operations/work-orders"
                search={{ action: 'new' }}
                className="flex items-center px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-900 hover:bg-slate-50 transition-colors"
              >
                <span>+ Giao việc mới</span>
              </Link>
            </div>
          )}
        </div>

        {/* 6. Hình ảnh bằng chứng */}
        <Link
          to="/operations/evidence"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/evidence')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconPhoto className={`w-4 h-4 ${currentPath.includes('/operations/evidence') ? 'text-blue-600' : 'text-slate-400'}`} />
            <span>Hình ảnh bằng chứng</span>
          </div>
          <span className="text-[10px] text-slate-400">Trước / Sau</span>
        </Link>

        {/* 7. Nghiệm thu chất lượng */}
        <Link
          to="/operations/qc"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/qc')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconShieldCheck className={`w-4 h-4 ${currentPath.includes('/operations/qc') ? 'text-blue-600' : 'text-slate-400'}`} />
            <span>Nghiệm thu chất lượng</span>
          </div>
        </Link>

        {/* 8. Phê duyệt chi phí */}
        <Link
          to="/operations/approvals"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/approvals')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconCash className={`w-4 h-4 ${currentPath.includes('/operations/approvals') ? 'text-blue-600' : 'text-slate-400'}`} />
            <span>Phê duyệt chi phí</span>
          </div>
          {pendingApprovalsCount > 0 && (
            <span className="px-1.5 py-0.2 text-[10px] font-bold bg-rose-500 text-white rounded-full">
              {pendingApprovalsCount}
            </span>
          )}
        </Link>

        {/* 9. Kế hoạch vệ sinh */}
        <Link
          to="/operations/sanitation"
          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
            currentPath.includes('/operations/sanitation')
              ? 'bg-blue-50 text-blue-600 font-bold shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <div className="flex items-center gap-3">
            <IconTrash className={`w-4 h-4 ${currentPath.includes('/operations/sanitation') ? 'text-emerald-600' : 'text-slate-400'}`} />
            <span>Kế hoạch vệ sinh</span>
          </div>
        </Link>
      </div>

      {/* User Footer */}
      <div className="p-3 border-t border-slate-100 flex items-center gap-2.5">
        <img
          src={profile.avatarUrl}
          alt={profile.name}
          className="w-8 h-8 rounded-full object-cover border border-slate-200"
        />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-slate-800 truncate">{profile.name}</p>
          <p className="text-[11px] text-slate-400 truncate">{profile.assignedTower}</p>
        </div>
      </div>
    </aside>
  );
}
