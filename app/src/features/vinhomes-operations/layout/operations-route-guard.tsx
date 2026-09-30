import React from 'react';
import { Link } from '@tanstack/react-router';
import { IconLock, IconShieldX, IconArrowLeft, IconUserCheck } from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { MenuId } from '../types/persona';

interface OperationsRouteGuardProps {
  menuId: MenuId;
  children: React.ReactNode;
  title?: string;
  description?: string;
}

const MENU_LABELS: Record<MenuId, string> = {
  dashboard: 'Tổng quan vận hành',
  'my-tasks': 'Việc của tôi',
  'completed-tasks': 'Công việc đã hoàn thành',
  triage: 'Tiếp nhận phản ánh',
  incidents: 'Phản ánh & Sự cố',
  kanban: 'Bảng phân bổ việc',
  'work-orders': 'Phiếu thi công',
  sanitation: 'Vệ sinh A5 & Cảnh quan',
  security: 'An ninh hiện trường',
  contractor: 'Cổng nhà thầu đối tác',
  evidence: 'Kho ảnh hiện trường',
  qc: 'Nghiệm thu chất lượng (QC)',
  approvals: 'Phê duyệt chi phí',
};

export function OperationsRouteGuard({
  menuId,
  children,
  title,
  description,
}: OperationsRouteGuardProps) {
  const { canAccessMenu, currentProfile, currentPersona } = useOperationsData();

  const isAllowed = canAccessMenu(menuId);

  if (isAllowed) {
    return <>{children}</>;
  }

  const moduleName = title || MENU_LABELS[menuId] || menuId;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="p-8 max-w-2xl mx-auto my-12 bg-white rounded-2xl border border-rose-200 shadow-xl space-y-6 font-sans text-center"
    >
      <div className="w-16 h-16 mx-auto bg-rose-50 text-rose-600 rounded-2xl flex items-center justify-center border border-rose-100 shadow-xs">
        <IconShieldX className="w-9 h-9" />
      </div>

      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 text-rose-700 text-xs font-bold rounded-full border border-rose-200">
          <IconLock className="w-3.5 h-3.5" />
          <span>RBAC Route Protection • 403 Forbidden</span>
        </div>
        <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
          Truy Cập Phân Hệ Bị Từ Chối
        </h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          {description ||
            `Tài khoản hiện tại không có quyền truy cập vào phân hệ "${moduleName}". Quy chuẩn an toàn thông tin Vinhomes Smart City ngăn chặn truy cập trực tiếp qua URL.`}
        </p>
      </div>

      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-left text-xs space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Tài khoản thao tác:</span>
          <span className="font-bold text-slate-900">{currentProfile.name}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Vai trò / Persona:</span>
          <span className="font-semibold text-rose-600 px-2 py-0.5 bg-rose-50 rounded border border-rose-200 font-mono">
            {currentProfile.role} ({currentProfile.roleTitle})
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Bộ phận:</span>
          <span className="text-slate-700 font-medium">{currentProfile.department}</span>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
        <Link
          to="/operations/my-tasks"
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm shadow-blue-500/20"
        >
          <IconArrowLeft className="w-4 h-4" />
          <span>Về "Việc của tôi"</span>
        </Link>
        <Link
          to="/operations"
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all"
        >
          <IconUserCheck className="w-4 h-4" />
          <span>Về trang chủ Vận hành</span>
        </Link>
      </div>
    </div>
  );
}
