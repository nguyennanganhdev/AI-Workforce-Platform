import { useState } from 'react';
import { OperationsTable } from './operations-table';
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
    currentPersona,
    respondToContractorJob,
    recordContractorMaterials,
    transitionWorkOrderStatus,
  } = useOperationsData();

  const [selectedWoForEvidence, setSelectedWoForEvidence] = useState<VhWorkOrder | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState('');
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

  // Filter contractor work orders strictly by contractor organization or executor
  const contractorOrders = workOrders.filter((w) => {
    if (w.executor_type !== 'CONTRACTOR') return false;
    if (currentPersona === 'CONTRACTOR') {
      if (currentProfile.contractor_organization_id && w.contractor_organization_id) {
        return (
          w.contractor_organization_id === currentProfile.contractor_organization_id ||
          w.executor_id === currentProfile.id
        );
      }
      return w.executor_id === currentProfile.id;
    }
    return true;
  });

  const pendingAcceptanceOrders = contractorOrders.filter((w) => w.contractor_status === 'PENDING_ACCEPTANCE');
  const acceptedWaitingStartOrders = contractorOrders.filter(
    (w) => w.contractor_status === 'ACCEPTED' && w.status === 'ASSIGNED',
  );
  const inProgressOrders = contractorOrders.filter((w) => w.status === 'IN_PROGRESS');
  const completedOrders = contractorOrders.filter((w) => w.status === 'COMPLETED');

  const handleConfirmAccept = () => {
    if (!acceptWoId) return;
    respondToContractorJob(acceptWoId, 'ACCEPT', undefined, assignedWorkerName);
    setAcceptWoId(null);
    setSuccessMsg('Đã tiếp nhận công việc và cử kỹ sư phụ trách! Nhấn "Bắt đầu thi công" khi có mặt tại hiện trường.');
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleStartWork = (woId: string) => {
    try {
      transitionWorkOrderStatus(woId, 'IN_PROGRESS', {
        note: 'Nhà thầu đã có mặt tại hiện trường và bắt đầu quy trình thi công.',
      });
      setSuccessMsg('Đã chuyển sang trạng thái Đang thi công!');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      alert(err.message || 'Lỗi khi bắt đầu thi công');
    }
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
    <div className="operations-worker-view operations-plain-list operations-work-orders space-y-5">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">

          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <IconTool className="w-5 h-5 text-blue-600" />
              <span>Công việc nhà thầu</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Tiếp nhận phiếu công việc, cử nhân sự thi công, ghi nhận vật tư và nộp hồ sơ nghiệm thu
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">
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

      <p className="text-sm text-slate-500">{pendingAcceptanceOrders.length} chờ tiếp nhận · {inProgressOrders.length} đang thi công · {completedOrders.length} chờ nghiệm thu</p>
      <div className="operations-plain-list" hidden={Boolean(selectedOrderId)}>
        <OperationsTable title="Công việc nhà thầu" titleColumn={1} columns={['Mã phiếu', 'Nội dung', 'Người thực hiện', 'Trạng thái']}
          rows={contractorOrders.map((order) => {
            const title = incidents.find((incident) => incident.id === order.incident_id)?.title || 'Công việc nhà thầu';
            return {id: order.id, search: `${order.id} ${title} ${order.executor_name || ''}`, cells: [
              order.id, title, order.executor_name || 'Chưa phân công',
              order.contractor_status === 'PENDING_ACCEPTANCE' ? 'Chờ tiếp nhận' : order.contractor_status === 'REJECTED' ? 'Đã từ chối' :
              ({OPEN: 'Mới tạo', ASSIGNED: 'Đã giao', IN_PROGRESS: 'Đang thi công', BLOCKED: 'Tạm dừng', COMPLETED: 'Chờ nghiệm thu', FAILED: 'Không đạt', CANCELLED: 'Đã hủy'})[order.status],
            ]};
          })} onSelect={setSelectedOrderId} />
      </div>
      {selectedOrderId && <button type="button" className="operations-back" onClick={() => setSelectedOrderId('')}>Quay lại danh sách</button>}
      {/* Main List */}
      <div className="space-y-4">
        {selectedOrderId && <h2>Chi tiết công việc nhà thầu</h2>}

        <div className="space-y-3.5">
          {contractorOrders.filter((order) => order.id === selectedOrderId).map((wo) => {
            const inc = incidents.find((i) => i.id === wo.incident_id);
            const woEvidence = evidence.filter((e) => e.work_order_id === wo.id);
            const beforeCount = woEvidence.filter((e) => e.capture_phase === 'BEFORE').length;
            const afterCount = woEvidence.filter((e) => e.capture_phase === 'AFTER').length;

            return (
              <div
                key={wo.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3.5 hover:border-slate-300 transition-colors"
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
                          : wo.contractor_status === 'ACCEPTED' && wo.status === 'ASSIGNED'
                            ? 'bg-purple-100 text-purple-700'
                            : wo.status === 'COMPLETED'
                              ? 'bg-emerald-100 text-emerald-700'
                              : wo.contractor_status === 'REJECTED'
                                ? 'bg-rose-100 text-rose-700'
                                : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {wo.contractor_status === 'PENDING_ACCEPTANCE'
                        ? 'Chờ tiếp nhận'
                        : wo.contractor_status === 'ACCEPTED' && wo.status === 'ASSIGNED'
                          ? '📋 Đã nhận việc • Chờ bắt đầu thi công'
                          : wo.status === 'COMPLETED'
                            ? 'Chờ nghiệm thu'
                            : wo.contractor_status === 'REJECTED'
                              ? 'Đã từ chối'
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
                    <span className="text-slate-400 block text-[11px]">Tiêu chí kỹ thuật:</span>
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
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                    <span className="text-slate-500">Ảnh trước và sau xử lý:</span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        beforeCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {beforeCount > 0 ? `Ảnh trước xử lý (${beforeCount})` : 'Chưa có ảnh trước xử lý'}
                    </span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        afterCount > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {afterCount > 0 ? `Ảnh sau xử lý (${afterCount})` : 'Chưa có ảnh sau xử lý'}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedWoForEvidence(wo)}
                      className="text-blue-600 hover:underline font-bold text-xs"
                    >
                      Tải ảnh hiện trường
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 self-end sm:self-auto">
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

                    {wo.contractor_status === 'ACCEPTED' && wo.status === 'ASSIGNED' && (
                      <button
                        type="button"
                        onClick={() => handleStartWork(wo.id)}
                        className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs flex items-center gap-1.5"
                      >
                        <IconArrowRight className="w-3.5 h-3.5" />
                        <span>Bắt đầu thi công</span>
                      </button>
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="accept-wo-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="accept-wo-title" className="font-bold text-sm text-slate-900">Tiếp nhận phiếu công việc {acceptWoId}</h3>
            <div className="space-y-1">
              <label htmlFor="assigned-worker-name" className="text-xs text-slate-600 font-medium block">
                Chỉ định kỹ sư/nhân viên nhà thầu trực tiếp thi công:
              </label>
              <input
                id="assigned-worker-name"
                value={assignedWorkerName}
                onChange={(e) => setAssignedWorkerName(e.target.value)}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              />
            </div>
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="reject-wo-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="reject-wo-title" className="font-bold text-sm text-slate-900">Từ chối tiếp nhận công việc {rejectWoId}</h3>
            <div className="space-y-1">
              <label htmlFor="reject-reason-text" className="text-xs text-slate-600 font-medium block">
                Vui lòng nêu rõ lý do (hết vật tư, ngoài phạm vi bảo trì...):
              </label>
              <textarea
                id="reject-reason-text"
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Nhập lý do chi tiết..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
              />
            </div>
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="material-wo-title"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <h3 id="material-wo-title" className="font-bold text-sm text-slate-900">Ghi nhận vật tư & linh kiện thay thế</h3>
            <div className="space-y-1">
              <label htmlFor="part-name-input" className="text-xs font-bold text-slate-700">Tên vật tư / linh kiện:</label>
              <input
                id="part-name-input"
                value={partName}
                onChange={(e) => setPartName(e.target.value)}
                placeholder="VD: Cảm biến quang Otis, Bo điều khiển..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label htmlFor="part-qty-input" className="text-xs font-bold text-slate-700">Số lượng:</label>
                <input
                  id="part-qty-input"
                  type="number"
                  min="1"
                  value={partQty}
                  onChange={(e) => setPartQty(Number(e.target.value))}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="part-unit-input" className="text-xs font-bold text-slate-700">Đơn vị tính:</label>
                <input
                  id="part-unit-input"
                  value={partUnit}
                  onChange={(e) => setPartUnit(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                />
              </div>
            </div>

            {partQty > 10 && (
              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center gap-2">
                <IconAlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Số lượng vật tư lớn ({partQty}). Yêu cầu có phiếu phê duyệt ngân sách (Execution Grant) từ BQL.</span>
              </div>
            )}

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
