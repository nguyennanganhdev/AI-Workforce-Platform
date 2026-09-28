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
import { PERSONA_PROFILES } from '../types/persona';

interface BreadcrumbConfig {
  section: string;
  page: string;
}

function getBreadcrumb(pathname: string): BreadcrumbConfig {
  if (pathname.includes('/triage')) {
    return { section: 'Vận hành đô thị', page: 'Tiếp nhận phản ánh' };
  }
  if (pathname.includes('/work-orders')) {
    return { section: 'Vận hành đô thị', page: 'Phiếu thi công' };
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
    return { section: 'Hiện trường', page: 'Vệ sinh môi trường A5' };
  }
  return { section: 'Vận hành đô thị', page: 'Tổng quan' };
}

export function OperationsHeader() {
  const location = useLocation();
  const breadcrumb = getBreadcrumb(location.pathname);

  const { currentPersona, incidents, approvals, resetToDefaultMock } = useOperationsData();
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
    <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between shrink-0 font-sans z-20">
      {/* Left: BistroPulse Breadcrumb with vertical Royal Blue indicator */}
      <div className="flex items-center gap-2">
        <div className="w-1 h-5 bg-blue-600 rounded-full shrink-0" />
        <nav className="flex items-center gap-1.5 text-sm">
          <span className="text-slate-500 font-medium hover:text-slate-700 transition-colors">
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
        {/* Reset Mock Data button for testing convenience */}
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

        {/* AI Action button */}
        <button
          type="button"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold transition-colors"
        >
          <IconSparkles className="w-4 h-4 text-blue-600" />
          <span>Trợ lý AI Đô thị</span>
        </button>

        {/* Chat / Messages Button */}
        <div className="relative">
          <button
            type="button"
            className="w-9 h-9 rounded-xl border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-50 transition-colors relative"
            title="Thảo luận nội bộ sự cố"
          >
            <IconMessageDots className="w-5 h-5 text-slate-600" />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-blue-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              3
            </span>
          </button>
        </div>

        {/* Notification Bell — with red badge for P1 emergencies */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setNotificationOpen(!notificationOpen)}
            className="w-9 h-9 rounded-xl border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-50 transition-colors relative"
            title="Thông báo khẩn cấp"
          >
            <IconBell className="w-5 h-5 text-slate-600" />
            {p1Incidents.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-bounce shadow-xs">
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
                        {inc.location_json.towerCode} • Hạn xử lý SLA: 45 phút
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
                        Đề xuất AI chờ BQL duyệt: {(app.estimated_cost_vnd || 0).toLocaleString()} đ
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
          <div className="hidden md:block text-left">
            <p className="text-xs font-bold text-slate-800 leading-tight">{profile.name}</p>
            <p className="text-[11px] text-slate-400 font-medium">{profile.roleTitle}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
