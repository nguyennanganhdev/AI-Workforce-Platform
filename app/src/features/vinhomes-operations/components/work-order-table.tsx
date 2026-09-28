import { useState, useMemo } from 'react';
import {
  IconSearch,
  IconFilter,
  IconPlus,
  IconDownload,
  IconDotsVertical,
  IconEye,
  IconEdit,
  IconPhoto,
  IconShieldCheck,
  IconGavel,
  IconArrowsSort,
  IconChevronLeft,
  IconChevronRight,
  IconCheck,
  IconClock,
  IconAlertTriangle,
  IconLayoutList,
  IconLayoutKanban,
  IconPhotoCheck,
  IconX,
  IconArrowBackUp,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { WorkOrderDialog } from './work-order-dialog';
import { EvidenceModal } from './evidence-modal';
import { QcInspectorModal } from './qc-inspector-modal';

const DOMAIN_LABELS: Record<string, string> = {
  MEP: 'Điện Nước',
  SANITATION: 'Vệ sinh',
  SECURITY: 'An ninh',
  CIVIL: 'Xây dựng',
  LANDSCAPE: 'Cảnh quan',
  ELEVATOR: 'Thang máy',
  GENERAL: 'Kỹ thuật',
};

export function WorkOrderTable() {
  const { workOrders, tasks, incidents, updateWorkOrderStatus, createWorkOrder } = useOperationsData();

  // Search & Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [filterDomain, setFilterDomain] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterTower, setFilterTower] = useState<string>('ALL');
  const [filterOpen, setFilterOpen] = useState(false);

  // Sorting
  const [sortField, setSortField] = useState<'id' | 'status' | 'created_at'>('created_at');
  const [sortAsc, setSortAsc] = useState(false);

  // Selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Active Action Menu Popover
  const [openActionId, setOpenActionId] = useState<string | null>(null);

  // Dialog states
  const [selectedWoForDetail, setSelectedWoForDetail] = useState<VhWorkOrder | null>(null);
  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);
  const [selectedWoForQc, setSelectedWoForQc] = useState<VhWorkOrder | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  // Enrich work order with task and incident metadata
  const enrichedOrders = useMemo(() => {
    return workOrders.map((wo) => {
      const task = tasks.find((t) => t.id === wo.task_id);
      const incident = incidents.find((i) => i.id === wo.incident_id);
      return {
        ...wo,
        taskTitle: task?.title || 'Công việc bảo trì hiện trường',
        domainType: task?.domain_type || 'GENERAL',
        priority: task?.priority || 'MEDIUM',
        towerCode: incident?.location_json.towerCode || 'Khu đô thị',
        areaDesc: incident?.location_json.areaCode || incident?.location_json.description || 'Khu vực chung',
        incidentSeverity: incident?.severity || 'P3',
        slaDueAt: incident?.sla_due_at,
      };
    });
  }, [workOrders, tasks, incidents]);

  // Filter & Search
  const filteredOrders = useMemo(() => {
    return enrichedOrders.filter((wo) => {
      const matchSearch =
        searchTerm === '' ||
        wo.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        wo.taskTitle.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (wo.executor_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        wo.towerCode.toLowerCase().includes(searchTerm.toLowerCase());

      const matchDomain = filterDomain === 'ALL' || wo.domainType === filterDomain;
      const matchStatus = filterStatus === 'ALL' || wo.status === filterStatus;
      const matchTower = filterTower === 'ALL' || wo.towerCode === filterTower;

      return matchSearch && matchDomain && matchStatus && matchTower;
    });
  }, [enrichedOrders, searchTerm, filterDomain, filterStatus, filterTower]);

  // Sort
  const sortedOrders = useMemo(() => {
    return [...filteredOrders].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'id') comparison = a.id.localeCompare(b.id);
      else if (sortField === 'status') comparison = a.status.localeCompare(b.status);
      else if (sortField === 'created_at') comparison = a.created_at.localeCompare(b.created_at);
      return sortAsc ? comparison : -comparison;
    });
  }, [filteredOrders, sortField, sortAsc]);

  // Paged
  const totalPages = Math.ceil(sortedOrders.length / pageSize) || 1;
  const pagedOrders = sortedOrders.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Selection handlers
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(pagedOrders.map((o) => o.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectRow = (id: string, checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => [...prev, id]);
    } else {
      setSelectedIds((prev) => prev.filter((item) => item !== id));
    }
  };

  const isAllSelected = pagedOrders.length > 0 && pagedOrders.every((o) => selectedIds.includes(o.id));

  // Toggle sort
  const toggleSort = (field: 'id' | 'status' | 'created_at') => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-4">
      {/* Title & Action Toolbar — Chuẩn 100% Template BistroPulse */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left: Blue Vertical Line + Title */}
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Quản Lý Phiếu Thi Công Hiện Trường
          </h1>
          <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full">
            {filteredOrders.length} phiếu
          </span>
        </div>

        {/* Right Toolbar: Search, Filter, Add, Export */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Search Bar */}
          <div className="relative">
            <IconSearch className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm theo mã phiếu, tên việc, nhân sự..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-48 sm:w-60 shadow-2xs font-medium"
            />
          </div>

          {/* Filter Button */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setFilterOpen(!filterOpen)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-semibold transition-colors shadow-2xs ${
                filterDomain !== 'ALL' || filterStatus !== 'ALL' || filterTower !== 'ALL'
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              <IconFilter className="w-4 h-4 text-slate-500" />
              <span>Bộ lọc</span>
            </button>

            {/* Filter Dropdown Popover */}
            {filterOpen && (
              <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-slate-200 p-4 z-40 space-y-3 font-sans">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <span className="text-xs font-bold text-slate-900">Bộ lọc nâng cao</span>
                  <button
                    type="button"
                    onClick={() => {
                      setFilterDomain('ALL');
                      setFilterStatus('ALL');
                      setFilterTower('ALL');
                    }}
                    className="text-[11px] text-blue-600 font-semibold hover:underline"
                  >
                    Đặt lại
                  </button>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-500 block mb-1">Bộ phận</label>
                  <select
                    value={filterDomain}
                    onChange={(e) => setFilterDomain(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white"
                  >
                    <option value="ALL">Tất cả bộ phận</option>
                    <option value="MEP">Kỹ thuật MEP (Điện nước)</option>
                    <option value="SANITATION">Vệ sinh & Cảnh quan A5</option>
                    <option value="ELEVATOR">Thang máy Schindler/Otis</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-500 block mb-1">Trạng thái phiếu</label>
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white"
                  >
                    <option value="ALL">Tất cả trạng thái</option>
                    <option value="OPEN">Chờ giao việc</option>
                    <option value="ASSIGNED">Đã giao việc</option>
                    <option value="IN_PROGRESS">Đang thực hiện</option>
                    <option value="COMPLETED">Đã hoàn thành</option>
                    <option value="FAILED">Chưa đạt (Cần làm lại)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-500 block mb-1">Tòa nhà</label>
                  <select
                    value={filterTower}
                    onChange={(e) => setFilterTower(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white"
                  >
                    <option value="ALL">Toàn phân khu</option>
                    <option value="S2.01">Tòa S2.01</option>
                    <option value="S1.05">Tòa S1.05</option>
                    <option value="S2.03">Tòa S2.03</option>
                    <option value="S1.01">Tòa S1.01</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Primary Action Button — BistroPulse Royal Blue "+ Add Restaurant" */}
          <button
            type="button"
            onClick={() => setIsCreatingNew(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm shadow-blue-500/20 active:scale-95"
          >
            <IconPlus className="w-4 h-4" />
            <span>+ Giao việc mới</span>
          </button>

          {/* Export Dropdown Button */}
          <button
            type="button"
            onClick={() => alert('Xuất danh sách phiếu thi công ra file CSV/Excel')}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-2xs"
          >
            <IconDownload className="w-4 h-4 text-slate-500" />
            <span>Xuất file ⌄</span>
          </button>
        </div>
      </div>

      {/* Main Table Card — BistroPulse Rounded White Container */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto min-h-[380px]">
          <table className="w-full text-left text-xs text-slate-600 font-sans">
            {/* Table Header */}
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 font-bold tracking-tight">
                {/* Checkbox Header */}
                <th className="py-3.5 pl-4 pr-2 w-10">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500 cursor-pointer"
                  />
                </th>

                {/* Name / Task Title with Sort */}
                <th
                  onClick={() => toggleSort('id')}
                  className="py-3.5 px-3 cursor-pointer hover:text-slate-900 select-none min-w-[220px]"
                >
                  <div className="flex items-center gap-1">
                    <span>Mã & Tên công việc</span>
                    <IconArrowsSort className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                </th>

                {/* Location */}
                <th className="py-3.5 px-3 min-w-[130px]">Vị trí / Tòa</th>

                {/* Domain / Department */}
                <th className="py-3.5 px-3 min-w-[110px]">Bộ phận</th>

                {/* Assignee / Representative */}
                <th className="py-3.5 px-3 min-w-[160px]">Người thực hiện</th>

                {/* SLA / Priority */}
                <th className="py-3.5 px-3 min-w-[110px]">SLA / Hạn</th>

                {/* Status */}
                <th
                  onClick={() => toggleSort('status')}
                  className="py-3.5 px-3 cursor-pointer hover:text-slate-900 select-none min-w-[120px]"
                >
                  <div className="flex items-center gap-1">
                    <span>Trạng thái</span>
                    <IconArrowsSort className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                </th>

                {/* Action Column */}
                <th className="py-3.5 pr-4 pl-2 text-right w-16">Thao tác</th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody className="divide-y divide-slate-100">
              {pagedOrders.map((wo) => {
                const isSelected = selectedIds.includes(wo.id);
                const isActionOpen = openActionId === wo.id;
                const isRedo = !!wo.redo_of_work_order_id;

                return (
                  <tr
                    key={wo.id}
                    className={`transition-colors relative ${
                      isSelected ? 'bg-blue-50/40' : 'hover:bg-slate-50/80'
                    }`}
                  >
                    {/* Row Checkbox */}
                    <td className="py-3.5 pl-4 pr-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => handleSelectRow(wo.id, e.target.checked)}
                        className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500 cursor-pointer"
                      />
                    </td>

                    {/* Name & ID */}
                    <td className="py-3.5 px-3">
                      <div className="flex items-center gap-2">
                        {isRedo && (
                          <span
                            title={`Làm lại của phiếu ${wo.redo_of_work_order_id}`}
                            className="p-1 rounded bg-rose-100 text-rose-700 shrink-0"
                          >
                            <IconArrowBackUp className="w-3.5 h-3.5" />
                          </span>
                        )}
                        <div>
                          <p className="font-bold text-slate-900 hover:text-blue-600 cursor-pointer">
                            {wo.taskTitle}
                          </p>
                          <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono mt-0.5">
                            <span className="font-semibold text-blue-600">{wo.id}</span>
                            <span>•</span>
                            <span>Lần {wo.attempt_no}</span>
                            {isRedo && (
                              <span className="text-rose-600 font-semibold">
                                (Làm lại của {wo.redo_of_work_order_id})
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Location */}
                    <td className="py-3.5 px-3">
                      <p className="font-bold text-slate-800">{wo.towerCode}</p>
                      <p className="text-[11px] text-slate-400 truncate max-w-[130px]">
                        {wo.areaDesc}
                      </p>
                    </td>

                    {/* Domain */}
                    <td className="py-3.5 px-3">
                      <span className="inline-block px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                        {DOMAIN_LABELS[wo.domainType] || wo.domainType}
                      </span>
                    </td>

                    {/* Assignee / Representative — BistroPulse Avatar Style */}
                    <td className="py-3.5 px-3">
                      {wo.executor_name ? (
                        <div className="flex items-center gap-2.5">
                          {wo.executor_avatar ? (
                            <img
                              src={wo.executor_avatar}
                              alt={wo.executor_name}
                              className="w-7 h-7 rounded-full object-cover border border-slate-200 shrink-0"
                            />
                          ) : (
                            <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-600 font-bold flex items-center justify-center text-[10px]">
                              {wo.executor_name.charAt(0)}
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="font-semibold text-slate-800 truncate">{wo.executor_name}</p>
                            <p className="text-[10px] text-slate-400">{wo.executor_phone || 'Hiện trường'}</p>
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Chưa chỉ định</span>
                      )}
                    </td>

                    {/* SLA / Priority */}
                    <td className="py-3.5 px-3">
                      <div className="flex items-center gap-1 font-medium">
                        {wo.priority === 'URGENT' ? (
                          <span className="text-rose-600 font-bold flex items-center gap-0.5">
                            ★ P1 (45p)
                          </span>
                        ) : wo.priority === 'HIGH' ? (
                          <span className="text-amber-600 font-semibold flex items-center gap-0.5">
                            ★ P2 (2h)
                          </span>
                        ) : (
                          <span className="text-slate-500">P3 (24h)</span>
                        )}
                      </div>
                    </td>

                    {/* Status — BistroPulse Clean Soft Badges */}
                    <td className="py-3.5 px-3">
                      {wo.status === 'COMPLETED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          Hoàn thành
                        </span>
                      ) : wo.status === 'IN_PROGRESS' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                          Đang làm
                        </span>
                      ) : wo.status === 'ASSIGNED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                          Đã giao
                        </span>
                      ) : wo.status === 'FAILED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                          Cần làm lại
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600">
                          Mới tạo
                        </span>
                      )}
                    </td>

                    {/* Action 3-dots with BistroPulse Popover Menu */}
                    <td className="py-3.5 pr-4 pl-2 text-right relative">
                      <button
                        type="button"
                        onClick={() => setOpenActionId(isActionOpen ? null : wo.id)}
                        className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                        title="Tùy chọn thao tác"
                      >
                        <IconDotsVertical className="w-4 h-4" />
                      </button>

                      {/* BistroPulse 3-dots Context Menu Popover */}
                      {isActionOpen && (
                        <div className="absolute right-6 top-10 w-52 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-40 text-left font-sans">
                          {/* 1. View Details */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedWoForDetail(wo);
                              setOpenActionId(null);
                            }}
                            className="w-full px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                          >
                            <IconEye className="w-4 h-4 text-slate-400" />
                            <span>Xem chi tiết phiếu</span>
                          </button>

                          {/* 2. Edit / Update Progress */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedWoForDetail(wo);
                              setOpenActionId(null);
                            }}
                            className="w-full px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                          >
                            <IconEdit className="w-4 h-4 text-slate-400" />
                            <span>Cập nhật tiến độ</span>
                          </button>

                          {/* 3. Evidence Gallery */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedWoForEvidence(wo);
                              setOpenActionId(null);
                            }}
                            className="w-full px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                          >
                            <IconPhoto className="w-4 h-4 text-blue-500" />
                            <span>Ảnh Trước / Sau thi công</span>
                          </button>

                          {/* 4. QC Inspection */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedWoForQc(wo);
                              setOpenActionId(null);
                            }}
                            className="w-full px-3 py-2 text-xs font-semibold text-purple-700 hover:bg-purple-50 flex items-center gap-2.5 transition-colors"
                          >
                            <IconShieldCheck className="w-4 h-4 text-purple-600" />
                            <span>Nghiệm thu chất lượng</span>
                          </button>

                          <div className="my-1 border-t border-slate-100" />

                          {/* Quick Status Toggles */}
                          {wo.status !== 'IN_PROGRESS' && wo.status !== 'COMPLETED' && (
                            <button
                              type="button"
                              onClick={() => {
                                updateWorkOrderStatus(wo.id, 'IN_PROGRESS');
                                setOpenActionId(null);
                              }}
                              className="w-full px-3 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50 flex items-center gap-2.5"
                            >
                              <IconCheck className="w-4 h-4" />
                              <span>Bắt đầu làm việc</span>
                            </button>
                          )}
                          {wo.status === 'IN_PROGRESS' && (
                            <button
                              type="button"
                              onClick={() => {
                                updateWorkOrderStatus(wo.id, 'COMPLETED');
                                setOpenActionId(null);
                              }}
                              className="w-full px-3 py-2 text-xs font-semibold text-emerald-600 hover:bg-emerald-50 flex items-center gap-2.5"
                            >
                              <IconCheck className="w-4 h-4" />
                              <span>Đánh dấu hoàn tất</span>
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer — Chuẩn 100% Template BistroPulse */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-medium">
          {/* Left: "1 of 2" */}
          <div>
            Trang <span className="font-bold text-slate-800">{currentPage}</span> trên{' '}
            <span className="font-bold text-slate-800">{totalPages}</span> ({filteredOrders.length} công việc)
          </div>

          {/* Right: <  1  2  3  > */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <IconChevronLeft className="w-4 h-4" />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                type="button"
                onClick={() => setCurrentPage(page)}
                className={`w-8 h-8 rounded-lg text-xs font-bold transition-colors ${
                  currentPage === page
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {page}
              </button>
            ))}

            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <IconChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Modals & Dialogs */}
      {selectedWoForDetail && (
        <WorkOrderDialog
          workOrder={selectedWoForDetail}
          onClose={() => setSelectedWoForDetail(null)}
        />
      )}

      {selectedWoForEvidence && (
        <EvidenceModal
          workOrder={selectedWoForEvidence}
          onClose={() => setSelectedWoForEvidence(null)}
        />
      )}

      {selectedWoForQc && (
        <QcInspectorModal
          workOrder={selectedWoForQc}
          onClose={() => setSelectedWoForQc(null)}
        />
      )}

      {/* Create New WorkOrder Dialog - Canonical ERD Flow */}
      {isCreatingNew && (
        <CreateWorkOrderModal
          incidents={incidents}
          tasks={tasks}
          onClose={() => setIsCreatingNew(false)}
          onCreate={(params) => {
            createWorkOrder(params);
            setIsCreatingNew(false);
          }}
        />
      )}
    </div>
  );
}

interface CreateWorkOrderModalProps {
  incidents: ReturnType<typeof useOperationsData>['incidents'];
  tasks: ReturnType<typeof useOperationsData>['tasks'];
  onClose: () => void;
  onCreate: (params: {
    incident_id: string;
    task_id: string;
    action_request_id?: string | null;
    execution_grant_id?: string | null;
    executor_type: 'STAFF' | 'CONTRACTOR' | 'ROBOT';
    executor_id: string | null;
    executor_name?: string;
    executor_phone?: string;
    checklist_version_id?: string | null;
  }) => void;
}

function CreateWorkOrderModal({ incidents, tasks, onClose, onCreate }: CreateWorkOrderModalProps) {
  const { executionGrants } = useOperationsData();
  const openIncidents = incidents.filter((i) => i.status === 'OPEN' || i.status === 'NEW');
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(openIncidents[0]?.id || incidents[0]?.id || '');

  const availableTasks = tasks.filter((t) => t.incident_id === selectedIncidentId && t.status !== 'DONE');
  const [selectedTaskId, setSelectedTaskId] = useState<string>(availableTasks[0]?.id || '');
  const [selectedGrantId, setSelectedGrantId] = useState<string>('');
  const [executorName, setExecutorName] = useState('Nguyễn Văn Hùng');
  const [executorType, setExecutorType] = useState<'STAFF' | 'CONTRACTOR' | 'ROBOT'>('STAFF');
  const [checklistVersion, setChecklistVersion] = useState('CKL-VER-MEP-01');

  const activeGrants = executionGrants.filter((g) => g.status === 'ACTIVE');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIncidentId || !selectedTaskId) return;

    onCreate({
      incident_id: selectedIncidentId,
      task_id: selectedTaskId,
      execution_grant_id: selectedGrantId || null,
      executor_type: executorType,
      executor_id: executorType === 'STAFF' ? 'usr-tech-01' : 'usr-contractor-01',
      executor_name: executorName,
      executor_phone: '0912 345 678',
      checklist_version_id: checklistVersion,
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-5 bg-blue-600 rounded-full" />
            <h3 className="font-bold text-slate-900 text-base">Giao Phiếu Thi Công Mới</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-xs font-bold"
          >
            ✕
          </button>
        </div>

        <p className="text-xs text-slate-500">
          Tạo phiếu giao việc cụ thể cho kỹ thuật viên hoặc đối tác thi công ngoài hiện trường.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3 text-xs">
          {/* 1. Select Incident */}
          <div>
            <label className="font-bold text-slate-700 block mb-1">Thuộc sự cố liên quan *</label>
            <select
              value={selectedIncidentId}
              onChange={(e) => {
                setSelectedIncidentId(e.target.value);
                const nextTasks = tasks.filter((t) => t.incident_id === e.target.value && t.status !== 'DONE');
                if (nextTasks.length > 0) {
                  setSelectedTaskId(nextTasks[0].id);
                }
              }}
              className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:border-blue-500 focus:outline-none font-medium text-slate-800"
            >
              {openIncidents.map((inc) => (
                <option key={inc.id} value={inc.id}>
                  {inc.id} — {inc.title.slice(0, 45)}... ({inc.location_json.towerCode})
                </option>
              ))}
            </select>
          </div>

          {/* 2. Select Task */}
          <div>
            <label className="font-bold text-slate-700 block mb-1">Nhiệm vụ cần thực hiện *</label>
            {availableTasks.length > 0 ? (
              <select
                value={selectedTaskId}
                onChange={(e) => setSelectedTaskId(e.target.value)}
                className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:border-blue-500 focus:outline-none font-medium text-slate-800"
              >
                {availableTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.id} [{t.domain_type === 'MEP' ? 'Điện Nước' : t.domain_type === 'SANITATION' ? 'Vệ sinh' : t.domain_type}] — {t.title}
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-2.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl text-xs">
                Sự cố này chưa có nhiệm vụ nào đang mở. Vui lòng tạo nhiệm vụ trên bảng phân công trước!
              </div>
            )}
          </div>

          {/* 3. Execution Grant (Optional) */}
          <div>
            <label className="font-bold text-slate-700 block mb-1">
              Khoản chi phí / Lệnh thi công đã duyệt (nếu có)
            </label>
            <select
              value={selectedGrantId}
              onChange={(e) => setSelectedGrantId(e.target.value)}
              className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:border-blue-500 focus:outline-none font-medium text-slate-800"
            >
              <option value="">-- Không yêu cầu lệnh đặc biệt (Công việc thông thường) --</option>
              {activeGrants.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.id} — {g.allowed_action_type === 'PURCHASE_MATERIAL' ? 'Mua sắm vật tư thay thế' : g.allowed_action_type} (Đã duyệt)
                </option>
              ))}
            </select>
          </div>

          {/* 4. Executor & Checklist */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-bold text-slate-700 block mb-1">Người thi công</label>
              <select
                value={executorType}
                onChange={(e) => setExecutorType(e.target.value as any)}
                className="w-full p-2.5 border border-slate-200 rounded-xl bg-white focus:border-blue-500 focus:outline-none"
              >
                <option value="STAFF">Kỹ thuật viên nội bộ</option>
                <option value="CONTRACTOR">Nhà thầu phụ (Đối tác)</option>
                <option value="ROBOT">Robot tự hành</option>
              </select>
            </div>
            <div>
              <label className="font-bold text-slate-700 block mb-1">Họ tên nhân viên / Đối tác</label>
              <input
                value={executorName}
                onChange={(e) => setExecutorName(e.target.value)}
                required
                className="w-full p-2.5 border border-slate-200 rounded-xl focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="font-bold text-slate-700 block mb-1">Quy chuẩn kiểm tra chất lượng</label>
            <select
              value={checklistVersion}
              onChange={(e) => setChecklistVersion(e.target.value)}
              className="w-full p-2.5 border border-slate-200 rounded-xl bg-white focus:border-blue-500 focus:outline-none"
            >
              <option value="CKL-VER-MEP-01">Quy chuẩn kỹ thuật cơ điện MEP</option>
              <option value="CKL-VER-A5-01">Tiêu chuẩn vệ sinh khu vực A5 & Khử mùi</option>
              <option value="CKL-VER-ELEV-01">Kiểm định an toàn thang máy</option>
            </select>
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-200 rounded-xl font-semibold text-slate-600 hover:bg-slate-50"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={availableTasks.length === 0}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-bold shadow-sm"
            >
              Giao Phiếu Thi Công
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

