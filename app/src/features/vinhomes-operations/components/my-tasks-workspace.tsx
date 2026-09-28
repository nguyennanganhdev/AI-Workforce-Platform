import { useState, useMemo, useEffect, useRef } from 'react';
import {
  IconBriefcase,
  IconClock,
  IconBuilding,
  IconPlayerPlay,
  IconPlayerPause,
  IconCheck,
  IconRotateClockwise,
  IconPhoto,
  IconAlertTriangle,
  IconInfoCircle,
  IconX,
  IconSearch,
  IconFilter,
  IconDotsVertical,
  IconEye,
  IconArrowsSort,
  IconChevronLeft,
  IconChevronRight,
  IconCamera,
  IconRefresh,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { EvidenceModal } from './evidence-modal';
import { WorkOrderDialog } from './work-order-dialog';

type FilterTab = 'ALL' | 'ASSIGNED' | 'IN_PROGRESS' | 'BLOCKED' | 'REDO' | 'COMPLETED';

export function MyTasksWorkspace() {
  const {
    myWorkOrders,
    incidents,
    evidence,
    currentProfile,
    transitionWorkOrderStatus,
  } = useOperationsData();

  const [activeTab, setActiveTab] = useState<FilterTab>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  // Modals & Popovers
  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);
  const [selectedWoForDetail, setSelectedWoForDetail] = useState<VhWorkOrder | null>(null);
  const [openActionId, setOpenActionId] = useState<string | null>(null);
  const actionMenuRef = useRef<HTMLDivElement | null>(null);

  // Block modal state
  const [blockingWoId, setBlockingWoId] = useState<string | null>(null);
  const [blockedReasonInput, setBlockedReasonInput] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Close 3-dots action menu when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (actionMenuRef.current && !actionMenuRef.current.contains(e.target as Node)) {
        setOpenActionId(null);
      }
    };
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  // Reset pagination & selection when persona/profile changes
  useEffect(() => {
    setCurrentPage(1);
    setSelectedIds([]);
  }, [currentProfile.id]);

  // Grouped counts for stats & tabs
  const assignedCount = myWorkOrders.filter((w) => w.status === 'ASSIGNED' && !w.redo_of_work_order_id).length;
  const inProgressCount = myWorkOrders.filter((w) => w.status === 'IN_PROGRESS').length;
  const blockedCount = myWorkOrders.filter((w) => w.status === 'BLOCKED').length;
  const redoCount = myWorkOrders.filter((w) => w.redo_of_work_order_id !== null && w.status !== 'COMPLETED').length;
  const completedCount = myWorkOrders.filter((w) => w.status === 'COMPLETED').length;

  // Filter tab list
  const tabFilteredOrders = useMemo(() => {
    switch (activeTab) {
      case 'ASSIGNED':
        return myWorkOrders.filter((w) => w.status === 'ASSIGNED' && !w.redo_of_work_order_id);
      case 'IN_PROGRESS':
        return myWorkOrders.filter((w) => w.status === 'IN_PROGRESS');
      case 'BLOCKED':
        return myWorkOrders.filter((w) => w.status === 'BLOCKED');
      case 'REDO':
        return myWorkOrders.filter((w) => w.redo_of_work_order_id !== null && w.status !== 'COMPLETED');
      case 'COMPLETED':
        return myWorkOrders.filter((w) => w.status === 'COMPLETED');
      default:
        return myWorkOrders;
    }
  }, [myWorkOrders, activeTab]);

  // Search filtering
  const searchedOrders = useMemo(() => {
    if (!searchTerm.trim()) return tabFilteredOrders;
    const term = searchTerm.toLowerCase().trim();
    return tabFilteredOrders.filter((wo) => {
      const inc = incidents.find((i) => i.id === wo.incident_id);
      const matchesId = wo.id.toLowerCase().includes(term);
      const matchesTitle = inc?.title?.toLowerCase().includes(term) ?? false;
      const matchesTower = inc?.location_json?.towerCode?.toLowerCase().includes(term) ?? false;
      const matchesChecklist = wo.checklist_version_id?.toLowerCase().includes(term) ?? false;
      return matchesId || matchesTitle || matchesTower || matchesChecklist;
    });
  }, [tabFilteredOrders, searchTerm, incidents]);

  // Sorting
  const sortedOrders = useMemo(() => {
    return [...searchedOrders].sort((a, b) => {
      const cmp = a.id.localeCompare(b.id);
      return sortAsc ? cmp : -cmp;
    });
  }, [searchedOrders, sortAsc]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sortedOrders.length / pageSize));
  const paginatedOrders = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedOrders.slice(start, start + pageSize);
  }, [sortedOrders, currentPage, pageSize]);

  // Handle select all checkbox
  const isPageAllSelected =
    paginatedOrders.length > 0 && paginatedOrders.every((wo) => selectedIds.includes(wo.id));

  const handleSelectAll = () => {
    const pageIds = paginatedOrders.map((wo) => wo.id);
    if (isPageAllSelected) {
      setSelectedIds((prev) => prev.filter((id) => !pageIds.includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Actions
  const handleStartWork = (woId: string) => {
    try {
      setErrorMessage(null);
      transitionWorkOrderStatus(woId, 'IN_PROGRESS');
      setSuccessMessage(`Đã bắt đầu thực hiện phiếu ${woId}!`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Lỗi thao tác');
    }
  };

  const handleResumeWork = (woId: string) => {
    try {
      setErrorMessage(null);
      transitionWorkOrderStatus(woId, 'IN_PROGRESS');
      setSuccessMessage(`Đã tiếp tục thực hiện phiếu ${woId}!`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Lỗi thao tác');
    }
  };

  const handleConfirmBlock = () => {
    if (!blockingWoId) return;
    try {
      setErrorMessage(null);
      transitionWorkOrderStatus(blockingWoId, 'BLOCKED', { blockedReason: blockedReasonInput });
      setBlockingWoId(null);
      setBlockedReasonInput('');
      setSuccessMessage(`Đã chuyển trạng thái phiếu sang Tạm dừng / Bị chặn.`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Lỗi thao tác');
    }
  };

  const handleCompleteWork = (woId: string) => {
    try {
      setErrorMessage(null);
      transitionWorkOrderStatus(woId, 'COMPLETED', {
        note: 'Đã hoàn thành thi công theo đúng tiêu chuẩn kỹ thuật.',
      });
      setSuccessMessage(`Đã báo cáo hoàn thành phiếu ${woId}! Chuyển sang chờ QC nghiệm thu.`);
      setTimeout(() => setSuccessMessage(null), 3500);
    } catch (err: any) {
      setErrorMessage(err.message || 'Chưa đủ điều kiện hoàn thành');
    }
  };

  return (
    <div className="space-y-4 font-sans">
      {/* Title Header with Blue Bar & User Identity */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-2.5">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconBriefcase className="w-5 h-5 text-blue-600" />
              <span>Việc Của Tôi</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Không gian thao tác dành riêng cho <strong>{currentProfile.name}</strong> • {currentProfile.roleTitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-bold text-xs rounded-full border border-blue-200">
            {myWorkOrders.length} Nhiệm vụ được phân công
          </span>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div
          role="status"
          aria-live="polite"
          className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs"
        >
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            aria-label="Đóng thông báo thành công"
            className="text-emerald-500 hover:text-emerald-700 text-xs p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {errorMessage && (
        <div
          role="alert"
          aria-live="assertive"
          className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center justify-between shadow-2xs"
        >
          <div className="flex items-start gap-2">
            <IconAlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            aria-label="Đóng thông báo lỗi"
            className="text-rose-500 hover:text-rose-700 text-xs p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Redesigned Compact Stats & Status Filter Toolbar (Replacing redundant 5 large cards & separate tab bar) */}
      <div className="bg-white p-1.5 rounded-2xl border border-slate-200/80 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-2">
        {/* Interactive Segmented Pill Tabs with live counts & color status dots */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          {[
            { id: 'ALL', label: 'Tất cả', count: myWorkOrders.length, dot: 'bg-slate-400' },
            { id: 'ASSIGNED', label: 'Mới giao', count: assignedCount, dot: 'bg-slate-400' },
            { id: 'IN_PROGRESS', label: 'Đang làm', count: inProgressCount, dot: 'bg-blue-500' },
            { id: 'BLOCKED', label: 'Bị chặn', count: blockedCount, dot: 'bg-amber-500' },
            { id: 'REDO', label: 'Cần làm lại', count: redoCount, dot: 'bg-rose-500' },
            { id: 'COMPLETED', label: 'Chờ QC', count: completedCount, dot: 'bg-emerald-500' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setActiveTab(tab.id as FilterTab);
                  setCurrentPage(1);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-2xs font-bold'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-white' : tab.dot}`} />
                <span>{tab.label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[11px] font-bold ${
                    isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-700'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Quick Search inside the toolbar */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="relative w-full md:w-64">
            <IconSearch className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Tìm mã WO, lỗi, tòa nhà..."
              className="w-full pl-8 pr-7 py-1.5 bg-slate-50 hover:bg-slate-100/70 focus:bg-white border border-slate-200 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs cursor-pointer p-0.5"
                title="Xóa tìm kiếm"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Table Card (BistroPulse Style - matching Ảnh 2) */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Table Top Header matching Ảnh 2 */}
        <div className="px-5 py-3.5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-5 bg-blue-600 rounded-full" />
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                Danh sách công việc
              </h2>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                {sortedOrders.length} nhiệm vụ
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            {selectedIds.length > 0 && (
              <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-200">
                Đã chọn {selectedIds.length}
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setActiveTab('ALL');
              }}
              className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl text-xs font-semibold border border-slate-200 transition-colors flex items-center gap-1.5 cursor-pointer"
              title="Xóa bộ lọc"
            >
              <IconFilter className="w-3.5 h-3.5 text-slate-500" />
              <span>Lọc</span>
            </button>
          </div>
        </div>

        {/* Table Container */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={isPageAllSelected}
                    onChange={handleSelectAll}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    aria-label="Chọn tất cả hàng"
                  />
                </th>
                <th
                  className="py-3 px-4 cursor-pointer select-none hover:text-slate-800 transition-colors"
                  onClick={() => setSortAsc(!sortAsc)}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Mã & Tên công việc</span>
                    <IconArrowsSort className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                </th>
                <th className="py-3 px-4">Vị trí / Tòa</th>
                <th className="py-3 px-4">Checklist</th>
                <th className="py-3 px-4">Bằng chứng (Trước / Sau)</th>
                <th className="py-3 px-4">Trạng thái</th>
                <th className="py-3 px-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {paginatedOrders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <IconBriefcase className="w-8 h-8 text-slate-300" />
                      <p className="font-semibold text-slate-600 text-xs">
                        Không tìm thấy công việc nào phù hợp
                      </p>
                      <p className="text-[11px] text-slate-400">
                        Thử thay đổi từ khóa tìm kiếm hoặc chuyển sang tab trạng thái khác.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedOrders.map((wo) => {
                  const inc = incidents.find((i) => i.id === wo.incident_id);
                  const woEvidence = evidence.filter((e) => e.work_order_id === wo.id);
                  const beforeCount = woEvidence.filter((e) => e.capture_phase === 'BEFORE').length;
                  const afterCount = woEvidence.filter((e) => e.capture_phase === 'AFTER').length;
                  const hasRequiredPhotos = beforeCount > 0 && afterCount > 0;
                  const isSelected = selectedIds.includes(wo.id);

                  return (
                    <tr
                      key={wo.id}
                      className={`hover:bg-slate-50/80 transition-colors group ${
                        isSelected ? 'bg-blue-50/30' : ''
                      } ${wo.redo_of_work_order_id ? 'bg-rose-50/15' : ''}`}
                    >
                      {/* Checkbox */}
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelect(wo.id)}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                          aria-label={`Chọn phiếu ${wo.id}`}
                        />
                      </td>

                      {/* Code & Title */}
                      <td className="py-3.5 px-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-mono text-[11px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200/60">
                              {wo.id}
                            </span>
                            <span className="text-[11px] font-semibold text-slate-600">
                              #{wo.attempt_no}
                            </span>
                            {wo.redo_of_work_order_id && (
                              <span className="px-1.5 py-0.5 bg-rose-100 text-rose-700 font-bold text-[10px] rounded flex items-center gap-0.5">
                                <IconRotateClockwise className="w-2.5 h-2.5" />
                                <span>Làm lại</span>
                              </span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedWoForDetail(wo)}
                            className="font-bold text-slate-900 hover:text-blue-600 text-left line-clamp-1 block cursor-pointer transition-colors max-w-xs sm:max-w-md"
                            title={inc?.title || 'Xem chi tiết'}
                          >
                            {inc?.title || `Công việc hiện trường #${wo.id}`}
                          </button>
                          {wo.status === 'BLOCKED' && wo.blocked_reason && (
                            <p className="text-[10px] text-amber-700 italic flex items-center gap-1">
                              <IconInfoCircle className="w-3 h-3 text-amber-600 shrink-0" />
                              <span className="line-clamp-1">{wo.blocked_reason}</span>
                            </p>
                          )}
                        </div>
                      </td>

                      {/* Location */}
                      <td className="py-3.5 px-4 text-slate-700 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 font-medium">
                          <IconBuilding className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>
                            Tòa <strong>{inc?.location_json.towerCode || 'S2.01'}</strong>
                          </span>
                          <span className="text-slate-300">•</span>
                          <span>Tầng {inc?.location_json.floor || '12'}</span>
                        </div>
                      </td>

                      {/* Checklist */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className="px-2 py-0.5 bg-slate-100 text-slate-700 font-mono text-[11px] font-semibold rounded">
                          {wo.checklist_version_id || 'CKL-VER-MEP-01'}
                        </span>
                      </td>

                      {/* Evidence (Before/After) */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedWoForEvidence(wo)}
                            className={`px-2 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                              hasRequiredPhotos
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                                : 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
                            }`}
                            title="Bấm để chụp / tải ảnh hiện trường"
                          >
                            <IconCamera className="w-3.5 h-3.5" />
                            <span>
                              {hasRequiredPhotos
                                ? `✓ Đủ (${beforeCount}T • ${afterCount}S)`
                                : `✕ Thiếu (${beforeCount}T • ${afterCount}S)`}
                            </span>
                          </button>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold ${
                            wo.status === 'COMPLETED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : wo.status === 'IN_PROGRESS'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : wo.status === 'BLOCKED'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              wo.status === 'COMPLETED'
                                ? 'bg-emerald-500'
                                : wo.status === 'IN_PROGRESS'
                                  ? 'bg-blue-500'
                                  : wo.status === 'BLOCKED'
                                    ? 'bg-amber-500'
                                    : 'bg-slate-400'
                            }`}
                          />
                          {wo.status === 'COMPLETED' && 'Chờ QC'}
                          {wo.status === 'IN_PROGRESS' && 'Đang làm'}
                          {wo.status === 'BLOCKED' && 'Bị chặn'}
                          {wo.status === 'ASSIGNED' && 'Mới giao'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5 relative">
                          {/* Quick inline button */}
                          {wo.status === 'ASSIGNED' && (
                            <button
                              type="button"
                              onClick={() => handleStartWork(wo.id)}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold flex items-center gap-1 transition-colors shadow-2xs cursor-pointer"
                              title="Bắt đầu thi công"
                            >
                              <IconPlayerPlay className="w-3 h-3" />
                              <span>Bắt đầu</span>
                            </button>
                          )}

                          {wo.status === 'IN_PROGRESS' && (
                            <button
                              type="button"
                              onClick={() => handleCompleteWork(wo.id)}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[11px] font-bold flex items-center gap-1 transition-colors shadow-2xs cursor-pointer"
                              title="Báo cáo hoàn thành"
                            >
                              <IconCheck className="w-3 h-3" />
                              <span>Hoàn thành</span>
                            </button>
                          )}

                          {wo.status === 'BLOCKED' && (
                            <button
                              type="button"
                              onClick={() => handleResumeWork(wo.id)}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-[11px] font-bold flex items-center gap-1 transition-colors shadow-2xs cursor-pointer"
                              title="Tiếp tục làm việc"
                            >
                              <IconPlayerPlay className="w-3 h-3" />
                              <span>Tiếp tục</span>
                            </button>
                          )}

                          {wo.status === 'COMPLETED' && (
                            <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              ✓ Đã nộp QC
                            </span>
                          )}

                          {/* 3-Dots Action Popover Menu (Matching Ảnh 2) */}
                          <div className="relative">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenActionId(openActionId === wo.id ? null : wo.id);
                              }}
                              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                              aria-label="Thao tác"
                              aria-expanded={openActionId === wo.id}
                            >
                              <IconDotsVertical className="w-4 h-4" />
                            </button>

                            {openActionId === wo.id && (
                              <div
                                ref={actionMenuRef}
                                className="absolute right-0 top-full mt-1 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1.5 z-40 text-left font-sans animate-in fade-in zoom-in-95 duration-100"
                              >
                                <button
                                  type="button"
                                  onClick={() => {
                                    setOpenActionId(null);
                                    setSelectedWoForDetail(wo);
                                  }}
                                  className="w-full px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer font-medium"
                                >
                                  <IconEye className="w-3.5 h-3.5 text-slate-500" />
                                  <span>Xem chi tiết</span>
                                </button>

                                <button
                                  type="button"
                                  onClick={() => {
                                    setOpenActionId(null);
                                    setSelectedWoForEvidence(wo);
                                  }}
                                  className="w-full px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer font-medium"
                                >
                                  <IconPhoto className="w-3.5 h-3.5 text-blue-600" />
                                  <span>Chụp / Tải ảnh</span>
                                </button>

                                <div className="my-1 border-t border-slate-100" />

                                {wo.status === 'ASSIGNED' && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setOpenActionId(null);
                                      handleStartWork(wo.id);
                                    }}
                                    className="w-full px-3 py-1.5 text-xs text-blue-700 hover:bg-blue-50 flex items-center gap-2 cursor-pointer font-bold"
                                  >
                                    <IconPlayerPlay className="w-3.5 h-3.5 text-blue-600" />
                                    <span>Bắt đầu thi công</span>
                                  </button>
                                )}

                                {wo.status === 'IN_PROGRESS' && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setOpenActionId(null);
                                        setBlockingWoId(wo.id);
                                        setBlockedReasonInput('');
                                      }}
                                      className="w-full px-3 py-1.5 text-xs text-amber-700 hover:bg-amber-50 flex items-center gap-2 cursor-pointer font-medium"
                                    >
                                      <IconPlayerPause className="w-3.5 h-3.5 text-amber-600" />
                                      <span>Tạm dừng / Bị chặn</span>
                                    </button>

                                    <button
                                      type="button"
                                      onClick={() => {
                                        setOpenActionId(null);
                                        handleCompleteWork(wo.id);
                                      }}
                                      className="w-full px-3 py-1.5 text-xs text-emerald-700 hover:bg-emerald-50 flex items-center gap-2 cursor-pointer font-bold"
                                    >
                                      <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
                                      <span>Báo cáo hoàn thành</span>
                                    </button>
                                  </>
                                )}

                                {wo.status === 'BLOCKED' && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setOpenActionId(null);
                                      handleResumeWork(wo.id);
                                    }}
                                    className="w-full px-3 py-1.5 text-xs text-blue-700 hover:bg-blue-50 flex items-center gap-2 cursor-pointer font-bold"
                                  >
                                    <IconPlayerPlay className="w-3.5 h-3.5 text-blue-600" />
                                    <span>Tiếp tục làm việc</span>
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Pagination Footer (Matching Ảnh 2: 1 of 2, 1 2 3 >) */}
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 bg-white">
          <div className="font-medium">
            <span className="px-2.5 py-1 bg-slate-100 text-slate-700 rounded-lg font-bold text-[11px]">
              {sortedOrders.length === 0
                ? '0 of 0'
                : `${currentPage} of ${totalPages}`}
            </span>
            <span className="ml-2 text-slate-400 hidden sm:inline">
              ({sortedOrders.length} công việc)
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              aria-label="Trang trước"
            >
              <IconChevronLeft className="w-3.5 h-3.5 text-slate-600" />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
              <button
                key={pageNum}
                type="button"
                onClick={() => setCurrentPage(pageNum)}
                className={`w-7 h-7 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  currentPage === pageNum
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {pageNum}
              </button>
            ))}

            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              aria-label="Trang sau"
            >
              <IconChevronRight className="w-3.5 h-3.5 text-slate-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Modal Block Reason */}
      {blockingWoId && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="block-modal-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 font-sans"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 id="block-modal-title" className="font-bold text-sm text-slate-900">
                Lý do Tạm dừng / Bị chặn công việc
              </h3>
              <button
                type="button"
                onClick={() => setBlockingWoId(null)}
                aria-label="Đóng cửa sổ"
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Vui lòng nêu rõ lý do (ví dụ: thiếu vật tư, căn hộ đóng cửa, cần hỗ trợ an ninh...) để Trưởng ca và BQL nắm thông tin xử lý:
            </p>

            <textarea
              rows={3}
              value={blockedReasonInput}
              onChange={(e) => setBlockedReasonInput(e.target.value)}
              placeholder="Nhập lý do chi tiết..."
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
            />

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setBlockingWoId(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleConfirmBlock}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl shadow-2xs cursor-pointer"
              >
                Xác nhận tạm dừng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Modal */}
      {selectedWoForEvidence && (
        <EvidenceModal
          workOrder={selectedWoForEvidence}
          onClose={() => setSelectedWoForEvidence(null)}
        />
      )}

      {/* Detail Dialog */}
      {selectedWoForDetail && (
        <WorkOrderDialog
          workOrder={selectedWoForDetail}
          onClose={() => setSelectedWoForDetail(null)}
        />
      )}
    </div>
  );
}
