import { useState } from 'react';
import { useLocation } from '@tanstack/react-router';
import {
  IconBell,
  IconMessageDots,
  IconSparkles,
  IconAlertTriangle,
  IconCheck,
  IconRefresh,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import { PERSONA_PROFILES, type OperationsPersona } from '../types/persona';

interface BreadcrumbConfig {
  section: string;
  page: string;
}

function getBreadcrumb(pathname: string, persona: OperationsPersona): BreadcrumbConfig {
  if (pathname.includes('/triage')) {
    return { section: 'Vận hành đô thị', page: 'Tiếp nhận phản ánh' };
  }
  if (pathname.includes('/work-orders')) {
    const page = persona === 'SUPERVISOR' || persona === 'MANAGER'
      ? 'Quản lý phiếu thi công'
      : persona === 'QC_INSPECTOR'
        ? 'Hồ sơ chờ nghiệm thu'
        : 'Hồ sơ công việc';
    return { section: 'Vận hành đô thị', page };
  }
  if (pathname.includes('/kanban')) {
    return { section: 'Vận hành đô thị', page: 'Phân công nhiệm vụ' };
  }
  if (pathname.includes('/evidence')) {
    return { section: 'Vận hành đô thị', page: 'Hình ảnh bằng chứng' };
  }
  if (pathname.includes('/qc')) {
    return { section: 'Vận hành đô thị', page: 'Nghiệm thu chất lượng' };
  }
  if (pathname.includes('/approvals')) {
    return { section: 'Ban Quản Lý', page: 'Phê duyệt chi phí' };
  }
  if (pathname.includes('/incidents')) {
    return { section: 'Vận hành đô thị', page: 'Quản lý sự cố' };
  }
  if (pathname.includes('/completed-tasks')) {
    return { section: 'Hiện trường', page: 'Công việc đã hoàn thành' };
  }
  if (pathname.includes('/my-tasks')) {
    return { section: 'Hiện trường', page: 'Việc của tôi' };
  }
  if (pathname.includes('/security')) {
    return { section: 'Hiện trường', page: 'An ninh & Trật tự' };
  }
  if (pathname.includes('/contractor')) {
    return { section: 'Đối tác', page: 'Cổng nhà thầu kỹ thuật' };
  }
  if (pathname.includes('/sanitation')) {
    return {
      section: 'Hiện trường',
      page: persona === 'STAFF_SANITATION_A5' ? 'Thực hiện vệ sinh A5' : 'Giám sát vệ sinh A5',
    };
  }
  return { section: 'Vận hành đô thị', page: 'Tổng quan' };
}

export function OperationsHeader({ menuOpen, onToggleMenu }: { menuOpen?: boolean; onToggleMenu?: () => void }) {
  const location = useLocation();
  const { currentPersona, incidents, approvals, resetToDefaultMock } = useOperationsData();
  const breadcrumb = getBreadcrumb(location.pathname, currentPersona);
  const profile = PERSONA_PROFILES[currentPersona as keyof typeof PERSONA_PROFILES];

  const p1Incidents = incidents.filter((i) => i.severity === 'P1' && i.status === 'OPEN');
  const pendingApprovals = approvals.filter((a) => a.status === 'PENDING');

  const [notificationOpen, setNotificationOpen] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);

  const handleResetData = () => {
    resetToDefaultMock();
    setResetSuccess(true);
    setTimeout(() => setResetSuccess(false), 2000);
  };

  return (
    <header className="min-h-14 bg-white border-b border-slate-200/80 px-4 py-2 gap-3 flex items-center justify-between shrink-0 font-sans z-20">
      <button type="button" className="operations-menu-toggle rounded border border-slate-200 px-3 py-2 text-sm" aria-expanded={menuOpen} onClick={onToggleMenu}>Danh mục</button>
      <div className="flex items-center gap-2">
        <div className="w-1 h-5 bg-blue-600 rounded-full shrink-0" />
        <nav aria-label="Vị trí hiện tại" className="flex items-center gap-1.5 text-sm">
          <span className="hidden xl:inline text-slate-500">
            {breadcrumb.section}
          </span>
          <span className="text-slate-300 font-normal">›</span>
          <span className="text-slate-900 font-semibold tracking-tight">
            {breadcrumb.page}
          </span>
        </nav>
      </div>

      {/* Right: Quick actions, notifications, user profile — BistroPulse Style */}
      <div className="flex items-center gap-3">
        <details className="relative hidden lg:block text-xs text-slate-500"><summary className="cursor-pointer">Dữ liệu mẫu</summary><div className="absolute right-0 top-7 z-30 w-44 rounded border border-slate-200 bg-white p-2">        {/* Reset Mock Data button for testing convenience */}
        <button
          type="button"
          onClick={handleResetData}
          title="Khôi phục dữ liệu mẫu ban đầu"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs font-medium text-slate-600 transition-colors"
        >
          {resetSuccess ? (
            <>
              <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-emerald-600 font-semibold">Đã đặt lại</span>
            </>
          ) : (
            <>
              <IconRefresh className="w-3.5 h-3.5 text-slate-500" />
              <span>Đặt lại dữ liệu</span>
            </>
          )}
        </button>

</div></details>
        {/* Notification Bell — with red badge for P1 emergencies */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setNotificationOpen(!notificationOpen)}
            aria-expanded={notificationOpen}
            className="rounded border border-slate-200 px-3 py-2 flex items-center gap-2 text-sm text-slate-600 hover:bg-slate-50"
            title="Thông báo khẩn cấp"
          >
            <span>Thông báo</span>
            {p1Incidents.length > 0 && (
              <span className="text-xs font-medium text-red-700">
                {p1Incidents.length}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {notificationOpen && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-200 py-3 z-50">
              <div className="px-4 pb-2 border-b border-slate-100 flex items-center justify-between">
                <span className="font-bold text-xs text-slate-900">Thông báo vận hành</span>
                <span className="text-[11px] font-semibold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full">
                  {p1Incidents.length} Khẩn cấp
                </span>
              </div>
              <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto">
                {p1Incidents.map((inc) => (
                  <div key={inc.id} className="p-3 hover:bg-slate-50 transition-colors flex gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                      <IconAlertTriangle className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-900 leading-snug">{inc.title}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {inc.location_json.towerCode} • Hạn xử lý: 45 phút
                      </p>
                    </div>
                  </div>
                ))}
                {pendingApprovals.map((app) => (
                  <div key={app.id} className="p-3 hover:bg-slate-50 transition-colors flex gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                      <IconSparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-900 leading-snug">
                        Đề xuất chờ phê duyệt: {(app.estimated_cost_vnd || 0).toLocaleString()} đ
                      </p>
                      <p className="text-[11px] text-slate-500 mt-0.5">Thay van DN50 khẩn cấp</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* User Profile Avatar with Name & Role — BistroPulse Style */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
          <img
            src={profile.avatarUrl}
            alt={profile.name}
            className="w-9 h-9 rounded-full object-cover border border-slate-200 shadow-2xs"
          />
          <div className="hidden xl:block text-left">
            <p className="text-xs font-bold text-slate-800 leading-tight">{profile.name}</p>
            <p className="text-[11px] text-slate-400 font-medium">{profile.roleTitle}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
