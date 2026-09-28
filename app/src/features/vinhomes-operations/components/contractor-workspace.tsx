import { useState } from 'react';
import {
  IconTool,
  IconCheck,
  IconX,
  IconBuilding,
  IconFileText,
  IconPackage,
  IconPlus,
  IconClock,
  IconAlertTriangle,
  IconUpload,
  IconArrowRight,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { EvidenceModal } from './evidence-modal';

export function ContractorWorkspace() {
  const {
    workOrders,
    incidents,
    evidence,
    currentProfile,
    respondToContractorJob,
    recordContractorMaterials,
    transitionWorkOrderStatus,
  } = useOperationsData();

  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Reject dialog
  const [rejectWoId, setRejectWoId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Assign worker dialog
  const [acceptWoId, setAcceptWoId] = useState<string | null>(null);
  const [assignedWorkerName, setAssignedWorkerName] = useState('Kỹ sư Đặng Văn Thái (Chứng chỉ bậc 4)');

  // Materials modal
  const [materialsWoId, setMaterialsWoId] = useState<string | null>(null);
  const [partName, setPartName] = useState('');
  const [partQty, setPartQty] = useState(1);
  const [partUnit, setPartUnit] = useState('Bộ');

  // Filter contractor work orders
  const contractorOrders = workOrders.filter(
    (w) => w.executor_type === 'CONTRACTOR' || w.executor_id === 'usr-contractor-01',
  );

  const pendingAcceptanceOrders = contractorOrders.filter((w) => w.contractor_status === 'PENDING_ACCEPTANCE');
  const inProgressOrders = contractorOrders.filter((w) => w.status === 'IN_PROGRESS');
  const completedOrders = contractorOrders.filter((w) => w.status === 'COMPLETED');

  const handleConfirmAccept = () => {
    if (!acceptWoId) return;
    respondToContractorJob(acceptWoId, 'ACCEPT', undefined, assignedWorkerName);
    setAcceptWoId(null);
    setSuccessMsg('Đã tiếp nhận công việc và phân công nhân viên kỹ thuật!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleConfirmReject = () => {
    if (!rejectWoId) return;
    respondToContractorJob(rejectWoId, 'REJECT', rejectReason);
    setRejectWoId(null);
    setRejectReason('');
    setSuccessMsg('Đã gửi phản hồi từ chối tiếp nhận việc đến BQL.');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleAddMaterial = (wo: VhWorkOrder) => {
    if (!partName.trim()) return;
    const existing = wo.materials_used || [];
    const updated = [...existing, { part_name: partName.trim(), quantity: partQty, unit: partUnit }];
    recordContractorMaterials(wo.id, updated);
    setPartName('');
    setPartQty(1);
    setMaterialsWoId(null);
    setSuccessMsg('Đã ghi nhận vật tư thay thế thành công!');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleCompleteContractorWork = (woId: string) => {
    try {
      transitionWorkOrderStatus(woId, 'COMPLETED', {
        note: 'Nhà thầu đã thi công và kiểm định vận hành thử 30 phút đạt tiêu chuẩn an toàn.',
      });
      setSuccessMsg('Đã báo cáo hoàn thành công việc cho BQL!');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      alert(err.message || 'Lỗi hoàn thành');
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconTool className="w-5 h-5 text-blue-600" />
              <span>Cổng Thông Tin Nhà Thầu & Đối Tác Kỹ Thuật</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Tiếp nhận phiếu công việc, cử nhân sự thi công, ghi nhận vật tư và nộp hồ sơ nghiệm thu
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3.5 py-1 bg-amber-50 text-amber-800 font-bold text-xs rounded-full border border-amber-200">
            {currentProfile.name} • {currentProfile.department}
          </span>
        </div>
      </div>

      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
          <button type="button" onClick={() => setSuccessMsg(null)} className="text-emerald-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <div className="p-4 bg-white rounded-2xl border border-slate-200/80 shadow-2xs">
          <div className="text-xs font-semibold text-slate-500">Chờ tiếp nhận</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{pendingAcceptanceOrders.length}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Yêu cầu xác nhận trong 30 phút</div>
        </div>

        <div className="p-4 bg-white rounded-2xl border border-slate-200/80 shadow-2xs">
          <div className="text-xs font-semibold text-blue-600">Đang thi công hiện trường</div>
          <div className="text-2xl font-bold text-blue-700 mt-1">{inProgressOrders.length}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Nhân sự nhà thầu đang có mặt</div>
        </div>

        <div className="p-4 bg-white rounded-2xl border border-slate-200/80 shadow-2xs">
          <div className="text-xs font-semibold text-emerald-600">Đã xong / Chờ BQL nghiệm thu</div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">{completedOrders.length}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Biên bản nghiệm thu QC</div>
        </div>
      </div>

      {/* Main List */}
      <div className="space-y-4">
        <h3 className="font-bold text-sm text-slate-900">Danh sách phiếu công việc giao cho nhà thầu ({contractorOrders.length})</h3>

        <div className="space-y-3.5">
          {contractorOrders.map((wo) => {
            const inc = incidents.find((i) => i.id === wo.incident_id);
            const woEvidence = evidence.filter((e) => e.work_order_id === wo.id);
            const beforeCount = woEvidence.filter((e) => e.capture_phase === 'BEFORE').length;
            const afterCount = woEvidence.filter((e) => e.capture_phase === 'AFTER').length;

            return (
              <div
                key={wo.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3.5 hover:border-slate-300 transition-colors"
              >
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {wo.id}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs font-bold text-slate-800">
                      {inc?.title || 'Sự cố thiết bị chuyên trách'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                        wo.contractor_status === 'PENDING_ACCEPTANCE'
                          ? 'bg-amber-100 text-amber-800'
                          : wo.status === 'COMPLETED'
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {wo.contractor_status === 'PENDING_ACCEPTANCE'
                        ? '⏳ Chờ nhà thầu nhận việc'
                        : wo.status === 'COMPLETED'
                          ? '✓ Đã hoàn thành (Chờ QC)'
                          : '⚡ Đang thi công'}
                    </span>
                  </div>
                </div>

                {/* Details */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Vị trí thiết bị:</span>
                    <strong className="text-slate-800">
                      Tòa {inc?.location_json.towerCode || 'S2.01'} • Tầng {inc?.location_json.floor || 'G'}
                    </strong>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Kỹ thuật viên nhà thầu:</span>
                    <strong className="text-slate-800">
                      {wo.contractor_assigned_worker || 'Chưa chỉ định nhân sự'}
                    </strong>
                  </div>

                  <div>
                    <span className="text-slate-400 block text-[11px]">Checklist kỹ thuật:</span>
                    <span className="font-mono text-slate-700">{wo.checklist_version_id || 'CKL-VER-ELEV-01'}</span>
                  </div>
                </div>

                {/* Replaced Materials Log */}
                {wo.materials_used && wo.materials_used.length > 0 && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1.5">
                    <div className="font-bold text-slate-700 flex items-center gap-1.5">
                      <IconPackage className="w-3.5 h-3.5 text-blue-600" />
                      <span>Vật tư & linh kiện thay thế đã sử dụng:</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {wo.materials_used.map((m, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-slate-800 font-medium"
                        >
                          {m.part_name}: <strong>{m.quantity} {m.unit}</strong>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Evidence count & Action Row */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500">Ảnh Before/After:</span>
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
                    <button
                      type="button"
                      onClick={() => setSelectedWoForEvidence(wo)}
                      className="text-blue-600 hover:underline font-bold text-xs"
                    >
                      Tải ảnh hiện trường
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    {wo.contractor_status === 'PENDING_ACCEPTANCE' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setAcceptWoId(wo.id)}
                          className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs flex items-center gap-1"
                        >
                          <IconCheck className="w-3.5 h-3.5" />
                          <span>Tiếp nhận việc</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setRejectWoId(wo.id)}
                          className="px-3.5 py-1.5 bg-slate-100 hover:bg-rose-50 text-rose-700 rounded-xl text-xs font-bold transition-colors flex items-center gap-1"
                        >
                          <IconX className="w-3.5 h-3.5" />
                          <span>Từ chối</span>
                        </button>
                      </>
                    )}

                    {wo.status === 'IN_PROGRESS' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setMaterialsWoId(wo.id)}
                          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors flex items-center gap-1"
                        >
                          <IconPlus className="w-3.5 h-3.5" />
                          <span>Ghi vật tư thay thế</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleCompleteContractorWork(wo.id)}
                          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs flex items-center gap-1"
                        >
                          <IconCheck className="w-4 h-4" />
                          <span>Báo hoàn thành thi công</span>
                        </button>
                      </>
                    )}

                    {wo.status === 'COMPLETED' && (
                      <span className="text-emerald-700 font-bold flex items-center gap-1 bg-emerald-50 px-3 py-1 rounded-lg">
                        <IconCheck className="w-4 h-4" />
                        <span>Đã nộp biên bản hoàn thành</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Modal Accept Worker */}
      {acceptWoId && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 className="font-bold text-sm text-slate-900">Tiếp nhận phiếu công việc {acceptWoId}</h3>
            <p className="text-xs text-slate-500">Chỉ định kỹ sư/nhân viên nhà thầu trực tiếp thi công:</p>
            <input
              value={assignedWorkerName}
              onChange={(e) => setAssignedWorkerName(e.target.value)}
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setAcceptWoId(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmAccept}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Xác nhận cử nhân sự
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Reject Reason */}
      {rejectWoId && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 className="font-bold text-sm text-slate-900">Từ chối tiếp nhận công việc {rejectWoId}</h3>
            <p className="text-xs text-slate-500">Vui lòng nêu rõ lý do (hết vật tư, ngoài phạm vi bảo trì...):</p>
            <textarea
              rows={3}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Nhập lý do chi tiết..."
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setRejectWoId(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Đóng
              </button>
              <button
                type="button"
                onClick={handleConfirmReject}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Xác nhận từ chối
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Add Material */}
      {materialsWoId && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 className="font-bold text-sm text-slate-900">Ghi nhận vật tư & linh kiện thay thế</h3>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Tên vật tư / linh kiện:</label>
              <input
                value={partName}
                onChange={(e) => setPartName(e.target.value)}
                placeholder="VD: Cảm biến quang Otis, Bo điều khiển..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Số lượng:</label>
                <input
                  type="number"
                  min="1"
                  value={partQty}
                  onChange={(e) => setPartQty(Number(e.target.value))}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Đơn vị tính:</label>
                <input
                  value={partUnit}
                  onChange={(e) => setPartUnit(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setMaterialsWoId(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={() => {
                  const targetWo = contractorOrders.find((w) => w.id === materialsWoId);
                  if (targetWo) handleAddMaterial(targetWo);
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Thêm vật tư
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
