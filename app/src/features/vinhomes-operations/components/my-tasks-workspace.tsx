import { useState, useMemo } from 'react';
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
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { EvidenceModal } from './evidence-modal';

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
  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);

  // Block modal state
  const [blockingWoId, setBlockingWoId] = useState<string | null>(null);
  const [blockedReasonInput, setBlockedReasonInput] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Grouped counts
  const assignedCount = myWorkOrders.filter((w) => w.status === 'ASSIGNED' && !w.redo_of_work_order_id).length;
  const inProgressCount = myWorkOrders.filter((w) => w.status === 'IN_PROGRESS').length;
  const blockedCount = myWorkOrders.filter((w) => w.status === 'BLOCKED').length;
  const redoCount = myWorkOrders.filter((w) => w.redo_of_work_order_id !== null && w.status !== 'COMPLETED').length;
  const completedCount = myWorkOrders.filter((w) => w.status === 'COMPLETED').length;

  const filteredOrders = useMemo(() => {
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
    <div className="space-y-6 font-sans">
      {/* Title Header with Blue Bar & User Identity */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconBriefcase className="w-5 h-5 text-blue-600" />
              <span>Việc Của Tôi (My Tasks)</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Không gian thao tác dành riêng cho <strong>{currentProfile.name}</strong> • {currentProfile.roleTitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-bold text-xs rounded-full border border-blue-200">
            {myWorkOrders.length} Phiếu được phân công
          </span>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button type="button" onClick={() => setSuccessMessage(null)} className="text-emerald-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-start gap-2">
            <IconAlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div
          onClick={() => setActiveTab('ASSIGNED')}
          className={`p-3.5 rounded-2xl border transition-all cursor-pointer ${
            activeTab === 'ASSIGNED' ? 'bg-blue-50/80 border-blue-500 shadow-2xs' : 'bg-white border-slate-200/80'
          }`}
        >
          <div className="text-[11px] font-semibold text-slate-500">Mới được giao</div>
          <div className="text-xl font-bold text-slate-800 mt-1">{assignedCount}</div>
        </div>

        <div
          onClick={() => setActiveTab('IN_PROGRESS')}
          className={`p-3.5 rounded-2xl border transition-all cursor-pointer ${
            activeTab === 'IN_PROGRESS' ? 'bg-blue-50/80 border-blue-500 shadow-2xs' : 'bg-white border-slate-200/80'
          }`}
        >
          <div className="text-[11px] font-semibold text-blue-600">Đang thực hiện</div>
          <div className="text-xl font-bold text-blue-700 mt-1">{inProgressCount}</div>
        </div>

        <div
          onClick={() => setActiveTab('BLOCKED')}
          className={`p-3.5 rounded-2xl border transition-all cursor-pointer ${
            activeTab === 'BLOCKED' ? 'bg-amber-50/80 border-amber-500 shadow-2xs' : 'bg-white border-slate-200/80'
          }`}
        >
          <div className="text-[11px] font-semibold text-amber-600">Bị chặn / Tạm dừng</div>
          <div className="text-xl font-bold text-amber-700 mt-1">{blockedCount}</div>
        </div>

        <div
          onClick={() => setActiveTab('REDO')}
          className={`p-3.5 rounded-2xl border transition-all cursor-pointer ${
            activeTab === 'REDO' ? 'bg-rose-50/80 border-rose-500 shadow-2xs' : 'bg-white border-slate-200/80'
          }`}
        >
          <div className="text-[11px] font-semibold text-rose-600">Làm lại (QC Fail)</div>
          <div className="text-xl font-bold text-rose-700 mt-1">{redoCount}</div>
        </div>

        <div
          onClick={() => setActiveTab('COMPLETED')}
          className={`p-3.5 rounded-2xl border transition-all cursor-pointer ${
            activeTab === 'COMPLETED' ? 'bg-emerald-50/80 border-emerald-500 shadow-2xs' : 'bg-white border-slate-200/80'
          }`}
        >
          <div className="text-[11px] font-semibold text-emerald-600">Đã xong / Chờ QC</div>
          <div className="text-xl font-bold text-emerald-700 mt-1">{completedCount}</div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
        {[
          { id: 'ALL', label: `Tất cả (${myWorkOrders.length})` },
          { id: 'ASSIGNED', label: `Mới giao (${assignedCount})` },
          { id: 'IN_PROGRESS', label: `Đang làm (${inProgressCount})` },
          { id: 'BLOCKED', label: `Bị chặn (${blockedCount})` },
          { id: 'REDO', label: `Làm lại (${redoCount})` },
          { id: 'COMPLETED', label: `Chờ QC (${completedCount})` },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as FilterTab)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors shrink-0 ${
              activeTab === tab.id ? 'bg-blue-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Work Orders List */}
      <div className="space-y-3.5">
        {filteredOrders.length === 0 ? (
          <div className="p-12 bg-white rounded-2xl border border-dashed border-slate-200 text-center text-slate-400 text-xs">
            Hiện không có công việc nào trong danh mục này.
          </div>
        ) : (
          filteredOrders.map((wo) => {
            const inc = incidents.find((i) => i.id === wo.incident_id);
            const woEvidence = evidence.filter((e) => e.work_order_id === wo.id);
            const beforeCount = woEvidence.filter((e) => e.capture_phase === 'BEFORE').length;
            const afterCount = woEvidence.filter((e) => e.capture_phase === 'AFTER').length;
            const hasRequiredPhotos = beforeCount > 0 && afterCount > 0;

            return (
              <div
                key={wo.id}
                className={`bg-white rounded-2xl border p-5 shadow-2xs space-y-3.5 transition-all ${
                  wo.redo_of_work_order_id
                    ? 'border-rose-300 ring-1 ring-rose-200 bg-rose-50/20'
                    : wo.status === 'BLOCKED'
                      ? 'border-amber-300 bg-amber-50/20'
                      : wo.status === 'IN_PROGRESS'
                        ? 'border-blue-300 bg-blue-50/10'
                        : 'border-slate-200/80'
                }`}
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {wo.id}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="font-semibold text-xs text-slate-700">Lần thi công #{wo.attempt_no}</span>
                    {wo.redo_of_work_order_id && (
                      <span className="px-2 py-0.5 bg-rose-100 text-rose-700 font-bold text-[10px] rounded-full flex items-center gap-1">
                        <IconRotateClockwise className="w-3 h-3" />
                        <span>Phiếu làm lại của {wo.redo_of_work_order_id}</span>
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                        wo.status === 'COMPLETED'
                          ? 'bg-emerald-100 text-emerald-700'
                          : wo.status === 'IN_PROGRESS'
                            ? 'bg-blue-100 text-blue-700'
                            : wo.status === 'BLOCKED'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {wo.status === 'COMPLETED' && '✓ Đã xong (Chờ QC)'}
                      {wo.status === 'IN_PROGRESS' && '⚡ Đang thực hiện'}
                      {wo.status === 'BLOCKED' && '⏸ Tạm dừng / Bị chặn'}
                      {wo.status === 'ASSIGNED' && '⏳ Mới được giao'}
                    </span>
                  </div>
                </div>

                {/* Content */}
                <div className="space-y-2">
                  <div className="text-sm font-bold text-slate-900 leading-snug">
                    {inc?.title || `Công việc hiện trường #${wo.id}`}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <IconBuilding className="w-3.5 h-3.5 text-slate-400" />
                      Tòa <strong>{inc?.location_json.towerCode || 'S2.01'}</strong> • Tầng{' '}
                      {inc?.location_json.floor || '12'}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span>Checklist: <strong>{wo.checklist_version_id || 'Tiêu chuẩn'}</strong></span>
                  </div>

                  {/* Redo Reason Banner */}
                  {wo.redo_of_work_order_id && wo.result && (
                    <div className="p-3 bg-rose-100/60 border border-rose-200 rounded-xl text-xs space-y-1 text-rose-900">
                      <p className="font-bold flex items-center gap-1">
                        <IconAlertTriangle className="w-4 h-4 text-rose-600" />
                        <span>Lý do nghiệm thu chưa đạt (Yêu cầu khắc phục):</span>
                      </p>
                      <p className="italic">"{String((wo.result as any).redoReason || 'Tiêu chí kỹ thuật chưa đạt')}"</p>
                    </div>
                  )}

                  {/* Blocked Reason Banner */}
                  {wo.status === 'BLOCKED' && wo.blocked_reason && (
                    <div className="p-3 bg-amber-100/60 border border-amber-200 rounded-xl text-xs space-y-1 text-amber-900">
                      <p className="font-bold flex items-center gap-1">
                        <IconInfoCircle className="w-4 h-4 text-amber-600" />
                        <span>Nguyên nhân bị chặn / Tạm dừng:</span>
                      </p>
                      <p className="italic">"{wo.blocked_reason}"</p>
                    </div>
                  )}
                </div>

                {/* Evidence Checklist Indicator */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-slate-600 flex items-center gap-1">
                      <IconPhoto className="w-4 h-4 text-slate-400" />
                      Bằng chứng hiện trường:
                    </span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        beforeCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {beforeCount > 0 ? `✓ Ảnh Trước (${beforeCount})` : '✕ Thiếu ảnh Trước'}
                    </span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        afterCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {afterCount > 0 ? `✓ Ảnh Sau (${afterCount})` : '✕ Thiếu ảnh Sau'}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => setSelectedWoForEvidence(wo)}
                    className="px-3 py-1 bg-white hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-bold border border-slate-200 transition-colors flex items-center gap-1 shrink-0 self-start sm:self-auto"
                  >
                    <IconPhoto className="w-3.5 h-3.5 text-blue-600" />
                    <span>Chụp / Tải ảnh hiện trường</span>
                  </button>
                </div>

                {/* Action Buttons Row */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
                  <div className="text-[11px] text-slate-400">
                    {wo.execution_started_at
                      ? `Bắt đầu lúc: ${new Date(wo.execution_started_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}`
                      : 'Chưa bấm bắt đầu thi công'}
                  </div>

                  <div className="flex items-center gap-2">
                    {wo.status === 'ASSIGNED' && (
                      <button
                        type="button"
                        onClick={() => handleStartWork(wo.id)}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                      >
                        <IconPlayerPlay className="w-4 h-4" />
                        <span>Bắt đầu thi công</span>
                      </button>
                    )}

                    {wo.status === 'IN_PROGRESS' && (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setBlockingWoId(wo.id);
                            setBlockedReasonInput('');
                          }}
                          className="px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-800 rounded-xl text-xs font-bold border border-amber-200 transition-colors flex items-center gap-1"
                        >
                          <IconPlayerPause className="w-3.5 h-3.5" />
                          <span>Tạm dừng / Báo bị chặn</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleCompleteWork(wo.id)}
                          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                        >
                          <IconCheck className="w-4 h-4" />
                          <span>Báo cáo hoàn thành</span>
                        </button>
                      </>
                    )}

                    {wo.status === 'BLOCKED' && (
                      <button
                        type="button"
                        onClick={() => handleResumeWork(wo.id)}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                      >
                        <IconPlayerPlay className="w-4 h-4" />
                        <span>Tiếp tục làm việc</span>
                      </button>
                    )}

                    {wo.status === 'COMPLETED' && (
                      <span className="text-xs font-bold text-emerald-700 flex items-center gap-1 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-200">
                        <IconCheck className="w-4 h-4 text-emerald-600" />
                        <span>Đã nộp báo cáo — Chờ nghiệm thu</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Modal Block Reason */}
      {blockingWoId && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="font-bold text-sm text-slate-900">Lý do Tạm dừng / Bị chặn công việc</h3>
              <button type="button" onClick={() => setBlockingWoId(null)} className="text-slate-400 hover:text-slate-600">
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
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleConfirmBlock}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl shadow-2xs"
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
    </div>
  );
}
