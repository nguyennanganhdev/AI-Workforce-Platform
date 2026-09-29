import { useState, useMemo, useEffect, useRef } from 'react';
import {
  IconBriefcase,
  IconClock,
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
  IconRefresh,
  IconTrash,
  IconSparkles,
  IconReceipt2,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { EvidenceModal } from './evidence-modal';
import { WorkOrderDialog } from './work-order-dialog';
import { SanitationWorkspace } from './sanitation-workspace';

type FilterTab = 'ALL' | 'ASSIGNED' | 'IN_PROGRESS' | 'BLOCKED' | 'REDO' | 'COMPLETED';

export function MyTasksWorkspace() {
  const {
    myWorkOrders,
    tasks,
    incidents,
    evidence,
    coordinationSessions,
    currentProfile,
    currentPersona,
    transitionWorkOrderStatus,
  } = useOperationsData();

  const usesDedicatedSanitationWorkspace = currentPersona === 'STAFF_SANITATION_A5';

  const [activeTab, setActiveTab] = useState<FilterTab>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  // Modals & Popovers
  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);
  const [selectedWoForDetail, setSelectedWoForDetail] = useState<VhWorkOrder | null>(null);
  const [selectedSanitationTaskId, setSelectedSanitationTaskId] = useState<string | null>(null);
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
    setSelectedSanitationTaskId(null);
    setSelectedWoForDetail(null);
    setSelectedWoForEvidence(null);
    setOpenActionId(null);
    setBlockingWoId(null);
    setActiveTab('ALL');
    setSearchTerm('');
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
      const matchesTitle = `${tasks.find((task) => task.id === wo.task_id)?.title || ''} ${inc?.title || ''}`.toLowerCase().includes(term);
      const matchesTower = inc?.location_json?.towerCode?.toLowerCase().includes(term) ?? false;
      const matchesChecklist = wo.checklist_version_id?.toLowerCase().includes(term) ?? false;
      return matchesId || matchesTitle || matchesTower || matchesChecklist;
    });
  }, [tabFilteredOrders, searchTerm, incidents, tasks]);

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
    const targetWo = myWorkOrders.find((w) => w.id === woId);
    if (usesDedicatedSanitationWorkspace && targetWo) {
      setSelectedSanitationTaskId(targetWo.task_id);
      return;
    }
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

  const openWorkOrderDetail = (workOrder: VhWorkOrder) => {
    if (usesDedicatedSanitationWorkspace) {
      setSelectedSanitationTaskId(workOrder.task_id);
      setOpenActionId(null);
      return;
    }
    setSelectedWoForDetail(workOrder);
  };

  if (usesDedicatedSanitationWorkspace && selectedSanitationTaskId) {
    return (
      <SanitationWorkspace
        embedded
        initialTaskId={selectedSanitationTaskId}
        onBack={() => setSelectedSanitationTaskId(null)}
      />
    );
  }

  return (
    <div className="operations-worker-view operations-plain-list operations-work-orders space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>Công việc của tôi</h1><span className="text-sm text-slate-500">{currentProfile.name} · {myWorkOrders.length} công việc</span>
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

      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-100 pb-4">
        <label className="flex flex-col gap-1 text-xs text-slate-500">Trạng thái
          <select aria-label="Trạng thái công việc" value={activeTab} onChange={(event) => { setActiveTab(event.target.value as FilterTab); setCurrentPage(1); }} className="border border-slate-200 bg-white rounded px-3 py-2 text-sm">
            <option value="ALL">Tất cả công việc</option><option value="ASSIGNED">Mới giao</option>
            <option value="IN_PROGRESS">Đang thực hiện</option><option value="BLOCKED">Tạm dừng</option>
            <option value="REDO">Cần làm lại</option><option value="COMPLETED">Chờ nghiệm thu</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">Tìm kiếm
          <input value={searchTerm} onChange={(event) => { setSearchTerm(event.target.value); setCurrentPage(1); }} placeholder="Tìm mã phiếu, công việc, tòa nhà" className="border border-slate-200 rounded px-3 py-2 text-sm w-72 max-w-full" />
        </label>
      </div>
      <div>
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
                    <span>Tên công việc</span>
                    <IconArrowsSort className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                </th>
                <th className="py-3 px-4">Vị trí / Tòa</th>
                <th className="py-3 px-4">Bằng chứng (Trước / Sau)</th>
                <th className="py-3 px-4">Trạng thái</th>
                <th className="py-3 px-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {paginatedOrders.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
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
                      className={`hover:bg-slate-50/80 transition-colors group ${isSelected ? 'bg-blue-50/30' : ''
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

                      <td>
                        <button type="button" className="text-left text-slate-700 hover:text-blue-600" onClick={() => openWorkOrderDetail(wo)}>{tasks.find((task) => task.id === wo.task_id)?.title || inc?.title || 'Công việc hiện trường'}</button>
                        <p className="mt-1 text-xs text-slate-400">{wo.id}{wo.redo_of_work_order_id ? ' · Làm lại' : ''}</p>
                      </td>
                      <td className="whitespace-nowrap">Tòa {inc?.location_json.towerCode || '—'} · Tầng {inc?.location_json.floor ?? '—'}</td>
                      <td><button type="button" className="text-left text-slate-600 hover:text-blue-600" onClick={() => setSelectedWoForEvidence(wo)}>
                        Trước xử lý: {beforeCount} ảnh<br />Sau xử lý: {afterCount} ảnh
                      </button></td>
                      <td className="whitespace-nowrap">{({OPEN: 'Mới tạo', ASSIGNED: 'Mới giao', IN_PROGRESS: 'Đang thực hiện', BLOCKED: 'Tạm dừng', COMPLETED: 'Chờ nghiệm thu', FAILED: 'Cần làm lại', CANCELLED: 'Đã hủy'})[wo.status]}</td>
                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5 relative">
                          {/* Quick inline button */}
                          {!usesDedicatedSanitationWorkspace && wo.status === 'ASSIGNED' && (
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

                          {!usesDedicatedSanitationWorkspace && wo.status === 'IN_PROGRESS' && (
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

                          {!usesDedicatedSanitationWorkspace && wo.status === 'BLOCKED' && (
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
                              Đã gửi nghiệm thu
                            </span>
                          )}

                          <button type="button" className="operations-text-action" onClick={() => openWorkOrderDetail(wo)}>Xem chi tiết</button>
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
                              Thao tác
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
                                    openWorkOrderDetail(wo);
                                  }}
                                  className="w-full px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center gap-2 cursor-pointer font-medium"
                                >
                                  <IconEye className="w-3.5 h-3.5 text-slate-500" />
                                  <span>Xem chi tiết</span>
                                </button>

                                {!usesDedicatedSanitationWorkspace && (
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
                                )}

                                {usesDedicatedSanitationWorkspace && wo.status !== 'COMPLETED' && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setOpenActionId(null);
                                      setSelectedSanitationTaskId(wo.task_id);
                                    }}
                                    className="w-full px-3 py-1.5 text-xs text-emerald-700 hover:bg-emerald-50 flex items-center gap-2 font-bold"
                                  >
                                    <IconTrash className="w-3.5 h-3.5" />
                                    <span>Mở quy trình thực hiện A5</span>
                                  </button>
                                )}

                                <div className="my-1 border-t border-slate-100" />

                                {!usesDedicatedSanitationWorkspace && wo.status === 'ASSIGNED' && (
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

                                {!usesDedicatedSanitationWorkspace && wo.status === 'IN_PROGRESS' && (
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

                                {!usesDedicatedSanitationWorkspace && wo.status === 'BLOCKED' && (
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
                ? 'Không có kết quả'
                : `Trang ${currentPage} trên ${totalPages}`}
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
                className={`w-7 h-7 rounded-lg text-xs font-bold transition-colors cursor-pointer ${currentPage === pageNum
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
          readOnly={usesDedicatedSanitationWorkspace}
          onClose={() => setSelectedWoForEvidence(null)}
        />
      )}

      {/* Detail Dialog */}
      {selectedWoForDetail && (
        <WorkOrderDialog
          workOrder={selectedWoForDetail}
          canEdit={!usesDedicatedSanitationWorkspace}
          onClose={() => setSelectedWoForDetail(null)}
        />
      )}
    </div>
  );
}
