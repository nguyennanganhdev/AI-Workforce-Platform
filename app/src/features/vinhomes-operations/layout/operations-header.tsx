import { useEffect, useRef, useState } from 'react';
import { useLocation } from '@tanstack/react-router';
import { IconBell, IconMenu2, IconX } from '@tabler/icons-react';
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
    return { section: 'Vận hành đô thị', page: 'Phân công công việc' };
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
    return { section: 'Vận hành đô thị', page: 'Phản ánh & Sự cố' };
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
  const notificationCount = p1Incidents.length + pendingApprovals.length;

  const [notificationOpen, setNotificationOpen] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);
  const notificationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!notificationOpen) return;
    const onPointer = (e: PointerEvent) => {
      if (!notificationRef.current?.contains(e.target as Node)) setNotificationOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setNotificationOpen(false);
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [notificationOpen]);

  useEffect(() => {
    if (!resetSuccess) return;
    const t = window.setTimeout(() => setResetSuccess(false), 2000);
    return () => window.clearTimeout(t);
  }, [resetSuccess]);

  const handleResetData = () => {
    resetToDefaultMock();
    setResetSuccess(true);
  };

  return (
    <header className="h-14 min-[901px]:h-16 bg-white border-b border-slate-200 px-3 md:px-6 flex items-center gap-3 shrink-0 z-20">
      <button
        type="button"
        className="operations-menu-toggle items-center justify-center -ml-1 w-10 h-10 rounded-md text-slate-700 hover:bg-slate-100"
        aria-expanded={menuOpen}
        aria-label={menuOpen ? 'Đóng danh mục' : 'Mở danh mục'}
        onClick={onToggleMenu}
      >
        {menuOpen ? <IconX className="w-5 h-5" stroke={1.75} /> : <IconMenu2 className="w-5 h-5" stroke={1.75} />}
      </button>

      <nav aria-label="Vị trí hiện tại" className="flex items-center gap-2 min-w-0 flex-1 text-sm">
        <span aria-hidden="true" className="w-1 h-5 rounded-sm bg-blue-600 shrink-0" />
        <span className="hidden md:inline text-slate-500 shrink-0">{breadcrumb.section}</span>
        <span aria-hidden="true" className="hidden md:inline text-slate-300 shrink-0">›</span>
        <span className="text-slate-900 font-medium truncate" aria-current="page">{breadcrumb.page}</span>
      </nav>

      <div className="flex items-center gap-1 md:gap-3 shrink-0">
        <details className="relative hidden lg:block">
          <summary className="cursor-pointer list-none text-[13px] text-slate-500 hover:text-slate-900">Dữ liệu mẫu</summary>
          <div className="absolute right-0 top-8 z-30 w-48 rounded-md border border-slate-200 bg-white p-2 shadow-[0_8px_24px_rgb(15_23_42/0.08)]">
            <button
              type="button"
              onClick={handleResetData}
              className="w-full min-h-9 px-3 rounded-md text-left text-[13px] text-slate-700 hover:bg-slate-50"
            >
              {resetSuccess ? 'Đã đặt lại dữ liệu' : 'Đặt lại dữ liệu mẫu'}
            </button>
          </div>
        </details>

        <div className="relative" ref={notificationRef}>
          <button
            type="button"
            onClick={() => setNotificationOpen((v) => !v)}
            aria-expanded={notificationOpen}
            aria-haspopup="true"
            aria-label={`Thông báo${notificationCount ? `, ${notificationCount} mục mới` : ''}`}
            className="relative w-10 h-10 rounded-md flex items-center justify-center text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            <IconBell className="w-5 h-5" stroke={1.75} />
            {notificationCount > 0 && (
              <span className="absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] leading-4 text-center tabular-nums">
                {notificationCount}
              </span>
            )}
          </button>

          {notificationOpen && (
            <div className="ops-notification-dropdown absolute right-0 mt-2 w-80 bg-white rounded-lg border border-slate-200 shadow-[0_12px_32px_rgb(15_23_42/0.10)] z-50">
              <p className="px-4 py-3 border-b border-slate-100 text-sm font-medium text-slate-900">Thông báo</p>
              {notificationCount === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-slate-500">Không có thông báo mới.</p>
              ) : (
                <ul className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                  {p1Incidents.map((inc) => (
                    <li key={inc.id} className="px-4 py-3">
                      <p className="text-sm text-slate-900 leading-snug">{inc.title}</p>
                      <p className="mt-0.5 text-[13px] text-slate-500">Khẩn cấp · Tòa {inc.location_json.towerCode || '-'}</p>
                    </li>
                  ))}
                  {pendingApprovals.map((app) => (
                    <li key={app.id} className="px-4 py-3">
                      <p className="text-sm text-slate-900 leading-snug">Đề xuất chờ phê duyệt</p>
                      <p className="mt-0.5 text-[13px] text-slate-500 tabular-nums">{(app.estimated_cost_vnd || 0).toLocaleString('vi-VN')} đ</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2.5 pl-2 md:pl-3 md:border-l border-slate-200">
          <img src={profile.avatarUrl} alt="" className="w-8 h-8 md:w-9 md:h-9 rounded-full object-cover border border-slate-200" />
          <div className="hidden md:block text-left max-w-[220px]">
            <p className="text-[13px] font-medium text-slate-900 leading-tight truncate">{profile.name}</p>
            <p className="text-xs text-slate-500 truncate">{profile.roleTitle}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
