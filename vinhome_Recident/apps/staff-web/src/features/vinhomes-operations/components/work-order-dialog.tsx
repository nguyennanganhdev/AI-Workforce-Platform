import { useState } from 'react';
import {
  IconX,
  IconClock,
  IconUser,
  IconBuilding,
  IconClipboardList,
  IconArrowBackUp,
  IconSparkles,
  } from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import { useOperationsData } from '../hooks/use-operations-data';

interface WorkOrderDialogProps {
  workOrder: VhWorkOrder;
  onClose: () => void;
  canEdit?: boolean;
}

export function WorkOrderDialog({ workOrder, onClose, canEdit = true }: WorkOrderDialogProps) {
  const {
    transitionWorkOrderStatus,
    tasks,
    incidents,
  } = useOperationsData();

  const task = tasks.find((t) => t.id === workOrder.task_id);
  const incident = incidents.find((i) => i.id === workOrder.incident_id);
  const [note, setNote] = useState((workOrder.result?.note as string) || '');
  const [currentStatus, setCurrentStatus] = useState(workOrder.status);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const handleUpdate = (status: VhWorkOrder['status']) => {
    try {
      setErrorMsg(null);
      transitionWorkOrderStatus(workOrder.id, status, { note });
      setCurrentStatus(status);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi kiểm soát trạng thái');
    }
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="work-order-title" onKeyDown={(event) => { if (event.key === 'Escape') onClose(); }} className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 z-50 font-sans">
      <div className="bg-white rounded-2xl sm:max-w-4xl w-full max-h-[95vh] sm:max-h-[90vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="p-3 sm:p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-6 bg-blue-600 rounded-full" />
            <div>
              <div className="flex items-center gap-2">
                <h3 id="work-order-title" className="font-bold text-slate-900 text-base">Chi tiết phiếu thi công</h3>
                <span className="font-mono text-xs px-2 py-0.5 bg-blue-50 text-blue-700 font-bold rounded">
                  {workOrder.id}
                </span>
                {workOrder.redo_of_work_order_id && (
                  <span className="text-[10px] px-2 py-0.5 bg-rose-100 text-rose-700 font-bold rounded flex items-center gap-1">
                    <IconArrowBackUp className="w-3 h-3" /> Làm lại của {workOrder.redo_of_work_order_id}
                  </span>
                )}
                {!canEdit && (
                  <span className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-600 font-bold rounded">
                    Chỉ xem
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Lần thực hiện: <span className="font-bold">#Lần {workOrder.attempt_no}</span> • Cập nhật:{' '}
                {new Date(workOrder.updated_at).toLocaleTimeString('vi-VN')}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="operations-back shrink-0" aria-label="Đóng chi tiết phiếu"
          >
            Đóng
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 text-xs text-slate-600">
          {/* Incident Context */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <IconBuilding className="w-3.5 h-3.5" /> Sự cố gốc liên quan
              </span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  incident?.severity === 'P0'
                    ? 'bg-rose-100 text-rose-700'
                    : 'bg-amber-100 text-amber-700'
                }`}
              >
                Mức {incident?.severity || 'P1'}
              </span>
            </div>
            <p className="font-bold text-slate-900 text-sm">{incident?.title || 'Sự cố hiện trường'}</p>
            <p className="text-slate-500">
              Vị trí: Tòa <span className="font-semibold text-slate-700">{incident?.location_json.towerCode}</span> •{' '}
              {incident?.location_json.areaCode || incident?.location_json.description}
            </p>
          </div>

          {/* Task Info */}
          <div className="space-y-1.5">
            <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
              <IconClipboardList className="w-4 h-4 text-blue-600" />
              Nhiệm vụ: {task?.title || 'Nhiệm vụ kỹ thuật'}
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <div className="p-3 bg-white border border-slate-200 rounded-xl">
                <span className="text-[11px] text-slate-400 block font-medium">Bộ phận phụ trách</span>
                <span className="font-bold text-slate-800 mt-0.5 block truncate">
                  {task?.domain_type === 'MEP'
                    ? 'Điện Nước'
                    : task?.domain_type === 'SANITATION'
                      ? 'Vệ sinh'
                      : task?.domain_type === 'LANDSCAPE'
                        ? 'Cảnh quan'
                        : task?.domain_type === 'ELEVATOR'
                          ? 'Thang máy'
                          : task?.domain_type || 'Kỹ thuật'}
                </span>
              </div>
              <div className="p-3 bg-white border border-slate-200 rounded-xl">
                <span className="text-[11px] text-slate-400 block font-medium">Người thực hiện</span>
                <span className="font-bold text-slate-800 mt-0.5 block truncate">
                  {workOrder.executor_name || 'Chưa phân công'}
                </span>
              </div>
              <div className="p-3 bg-white border border-slate-200 rounded-xl">
                <span className="text-[11px] text-slate-400 block font-medium">Tiêu chuẩn kiểm tra</span>
                <span className="font-mono font-bold text-blue-700 mt-0.5 block text-xs truncate">
                  {workOrder.checklist_version_id || 'CKL-VER-MEP-01'}
                </span>
              </div>
              <div className="p-3 bg-white border border-slate-200 rounded-xl">
                <span className="text-[11px] text-slate-400 block font-medium">Trạng thái hiện tại</span>
                <span className="font-bold text-blue-600 mt-0.5 block truncate">
                  {currentStatus === 'COMPLETED'
                    ? 'Đã hoàn thành'
                    : currentStatus === 'IN_PROGRESS'
                      ? 'Đang thực hiện'
                      : currentStatus === 'BLOCKED'
                        ? 'Tạm dừng / Bị chặn'
                        : currentStatus === 'FAILED'
                          ? 'Chưa đạt'
                          : 'Mới giao việc'}
                </span>
              </div>
            </div>
          </div>

          {/* Progress Notes */}
          <div className="space-y-2">
            <label className="font-bold text-slate-800 block text-xs">
              Ghi chú nhật ký hiện trường & Kết quả xử lý
            </label>
            <textarea
              rows={3}
              value={note}
              onChange={(e) => canEdit && setNote(e.target.value)}
              readOnly={!canEdit}
              placeholder="Nhập ghi chú kỹ thuật, thông số đo đạc, hoặc nguyên nhân phát sinh..."
              className={`w-full p-3 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none ${
                canEdit
                  ? 'focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500'
                  : 'bg-slate-50 cursor-default'
              }`}
            />
          </div>

          {/* Error Message if Guard Fails */}
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-xs text-rose-800">
              <span className="font-bold text-rose-600 text-sm">⚠️</span>
              <div>
                <p className="font-bold">Kiểm soát quy trình thất bại:</p>
                <p>{errorMsg}</p>
              </div>
            </div>
          )}

          {/* Status Quick Actions */}
          {canEdit && (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
              <span className="font-bold text-slate-800 block text-xs">Chuyển trạng thái phiếu:</span>
              <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => handleUpdate('IN_PROGRESS')}
                className={`px-3 py-2 rounded-xl text-xs font-bold transition-all ${
                  currentStatus === 'IN_PROGRESS'
                    ? 'bg-amber-600 text-white shadow-2xs'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                }`}
              >
                Đang thực hiện
              </button>
              <button
                type="button"
                onClick={() => handleUpdate('BLOCKED')}
                className={`px-3 py-2 rounded-xl text-xs font-bold transition-all ${
                  currentStatus === 'BLOCKED'
                    ? 'bg-orange-600 text-white shadow-2xs'
                    : 'bg-white border border-slate-200 text-orange-700 hover:bg-orange-50'
                }`}
              >
                Bị chặn (Tạm dừng)
              </button>
              <button
                type="button"
                onClick={() => handleUpdate('COMPLETED')}
                className={`px-3 py-2 rounded-xl text-xs font-bold transition-all ${
                  currentStatus === 'COMPLETED'
                    ? 'bg-emerald-600 text-white shadow-2xs'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                }`}
              >
                Đã hoàn thành (Chờ nghiệm thu)
              </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-end gap-2.5 bg-slate-50/50">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-semibold transition-colors"
          >
            Đóng
          </button>
          {canEdit && (
            <button
              type="button"
              onClick={() => {
                handleUpdate(currentStatus);
                onClose();
              }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm"
            >
              Lưu thay đổi
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
