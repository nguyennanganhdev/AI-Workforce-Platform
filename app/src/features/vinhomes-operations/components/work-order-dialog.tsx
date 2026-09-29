import { useState } from 'react';
import {
  IconX,
  IconClock,
  IconCheck,
  IconUser,
  IconBuilding,
  IconClipboardList,
  IconArrowBackUp,
  IconSparkles,
  IconReceipt2,
  IconTool,
  IconSend,
  IconShieldCheck,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import type { VhWorkOrder } from '../types/work-order';
import type { MaterialItem } from '../types/session';
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
    coordinationSessions,
    submitMaterialQuotation,
  } = useOperationsData();

  const task = tasks.find((t) => t.id === workOrder.task_id);
  const incident = incidents.find((i) => i.id === workOrder.incident_id);
  const session = coordinationSessions.find(
    (s) => s.work_order_id === workOrder.id || s.incident_id === workOrder.incident_id,
  );

  const [note, setNote] = useState((workOrder.result?.note as string) || '');
  const [currentStatus, setCurrentStatus] = useState(workOrder.status);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [quoteSuccessMsg, setQuoteSuccessMsg] = useState<string | null>(null);

  // Material Quotation State
  const [materialItems, setMaterialItems] = useState<MaterialItem[]>(
    session?.quotation?.items || [
      { id: 'mat-1', part_name: 'Ống hàn nhiệt PPR Tiền Phong D25', quantity: 2, unit: 'mét', unit_price: 45000, amount: 90000 },
      { id: 'mat-2', part_name: 'Măng sông ren đồng phi 25x1/2', quantity: 2, unit: 'cái', unit_price: 65000, amount: 130000 },
      { id: 'mat-3', part_name: 'Băng tan chống thấm & keo dán nhiệt', quantity: 1, unit: 'cuộn', unit_price: 30000, amount: 30000 },
    ],
  );
  const [laborCost, setLaborCost] = useState<number>(session?.quotation?.labor_cost ?? 150000);
  const [warrantyMonths, setWarrantyMonths] = useState<number>(session?.quotation?.warranty_months ?? 6);

  const totalMaterials = materialItems.reduce((acc, it) => acc + it.amount, 0);
  const grandTotal = totalMaterials + laborCost;

  const handleUpdateItem = (idx: number, field: keyof MaterialItem, val: any) => {
    setMaterialItems((prev) => {
      const next = [...prev];
      const cur = { ...next[idx], [field]: val };
      if (field === 'quantity' || field === 'unit_price') {
        cur.amount = Number(cur.quantity || 0) * Number(cur.unit_price || 0);
      }
      next[idx] = cur;
      return next;
    });
  };

  const handleAddItem = () => {
    setMaterialItems((prev) => [
      ...prev,
      {
        id: `mat-${Date.now()}`,
        part_name: '',
        quantity: 1,
        unit: 'cái',
        unit_price: 0,
        amount: 0,
      },
    ]);
  };

  const handleRemoveItem = (idx: number) => {
    setMaterialItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmitQuote = () => {
    if (!session) return;
    try {
      setErrorMsg(null);
      submitMaterialQuotation({
        sessionId: session.id,
        workOrderId: workOrder.id,
        items: materialItems,
        laborCost,
        warrantyMonths,
      });
      setQuoteSuccessMsg('Đã gửi báo giá cho Agent Kỹ Thuật lưu hồ sơ & Agent Báo Cáo xuất hóa đơn!');
      setTimeout(() => setQuoteSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi gửi báo giá');
    }
  };

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
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 font-sans">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-6 bg-blue-600 rounded-full" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-base">Chi Tiết Phiếu Thi Công</h3>
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
            className="w-8 h-8 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <IconX className="w-5 h-5" />
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
                  incident?.severity === 'P1'
                    ? 'bg-rose-100 text-rose-700'
                    : 'bg-amber-100 text-amber-700'
                }`}
              >
                Mức {incident?.severity || 'P2'}
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
                <span className="text-[11px] text-slate-400 block font-medium">Tiêu chuẩn Checklist</span>
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

          {/* Multi-Agent Coordination & Material Quotation */}
          {session && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-blue-50/60 via-indigo-50/30 to-purple-50/40 border border-blue-200/80 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-blue-200/50">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 bg-blue-600 text-white rounded-lg">
                    <IconReceipt2 className="w-4 h-4" />
                  </span>
                  <div>
                    <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                      Điều Phối Đa Tác Nhân (Multi-Agent Dispatch)
                      <span className="font-mono text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-bold">
                        {session.id}
                      </span>
                    </h4>
                    <p className="text-[11px] text-slate-500">
                      Quy trình: KTV khảo sát ➔ Báo giá Agent KT ➔ Agent Báo cáo xuất hóa đơn ➔ Agent CSKH gửi cư dân duyệt ➔ Thi công & Nghiệm thu
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      session.status === 'CLOSED'
                        ? 'bg-slate-200 text-slate-700'
                        : session.resident_ticket_status === 'DONE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : session.quotation?.resident_approved
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {session.status === 'CLOSED'
                      ? 'Đã đóng Session'
                      : session.resident_ticket_status === 'DONE'
                        ? 'Cư dân xác nhận DONE'
                        : session.quotation?.resident_approved
                          ? 'Cư dân đã duyệt giá'
                          : 'Chờ báo giá vật tư'}
                  </span>
                </div>
              </div>

              {/* Success Notification */}
              {quoteSuccessMsg && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2 text-xs text-emerald-800 animate-in fade-in">
                  <IconCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{quoteSuccessMsg}</span>
                </div>
              )}

              {/* Status Badges Row */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="p-2.5 bg-white/90 rounded-lg border border-slate-200 space-y-0.5">
                  <span className="text-[10px] text-slate-400 font-semibold block">Hóa đơn vật tư & nhân công</span>
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1">
                    {session.quotation ? (
                      <>
                        <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
                        {session.quotation.invoice_code} ({session.quotation.total_amount.toLocaleString('vi-VN')}đ)
                      </>
                    ) : (
                      'Chưa gửi báo giá'
                    )}
                  </span>
                </div>

                <div className="p-2.5 bg-white/90 rounded-lg border border-slate-200 space-y-0.5">
                  <span className="text-[10px] text-slate-400 font-semibold block">Ticket phía Cư Dân</span>
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1">
                    {session.resident_ticket_status === 'DONE' ? (
                      <>
                        <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
                        DONE (Đã đóng chat cư dân)
                      </>
                    ) : (
                      'Đang xử lý tại chỗ'
                    )}
                  </span>
                </div>

                <div className="p-2.5 bg-white/90 rounded-lg border border-slate-200 space-y-0.5">
                  <span className="text-[10px] text-slate-400 font-semibold block">Phê duyệt Ban Quản Lý (BQL)</span>
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1">
                    {session.status === 'CLOSED' ? (
                      <>
                        <IconShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                        {session.bql_approved_by || 'BQL'} đã duyệt đóng
                      </>
                    ) : (
                      'Chờ BQL duyệt đóng session'
                    )}
                  </span>
                </div>
              </div>

              {/* Material Items Table */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
                <div className="p-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <IconTool className="w-4 h-4 text-blue-600" />
                    Bảng Kê Chi Phí Vật Tư & Nhân Công (Gửi Agent Kỹ Thuật)
                  </span>
                  {canEdit && (
                    <button
                      type="button"
                      onClick={handleAddItem}
                      className="px-2 py-1 bg-white border border-slate-200 hover:bg-slate-50 text-blue-600 rounded-lg text-[11px] font-bold flex items-center gap-1"
                    >
                      <IconPlus className="w-3.5 h-3.5" /> Thêm vật tư
                    </button>
                  )}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50/50 text-slate-500 font-semibold border-b border-slate-100 text-[11px]">
                      <tr>
                        <th className="p-2.5 pl-3">Tên vật tư thay thế</th>
                        <th className="p-2.5 w-20 text-center">Số lượng</th>
                        <th className="p-2.5 w-16 text-center">ĐVT</th>
                        <th className="p-2.5 w-28 text-right">Đơn giá (đ)</th>
                        <th className="p-2.5 w-28 text-right">Thành tiền (đ)</th>
                        {canEdit && <th className="p-2.5 w-10 text-center"></th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {materialItems.map((item, idx) => (
                        <tr key={item.id} className="hover:bg-slate-50/50">
                          <td className="p-2 pl-3">
                            {canEdit ? (
                              <input
                                type="text"
                                value={item.part_name}
                                onChange={(e) => handleUpdateItem(idx, 'part_name', e.target.value)}
                                placeholder="Tên phụ tùng, vật tư..."
                                className="w-full p-1 border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                              />
                            ) : (
                              <span className="font-semibold text-slate-800">{item.part_name}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {canEdit ? (
                              <input
                                type="number"
                                min={1}
                                value={item.quantity}
                                onChange={(e) => handleUpdateItem(idx, 'quantity', Number(e.target.value))}
                                className="w-full p-1 text-center border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                              />
                            ) : (
                              <span className="text-center block">{item.quantity}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {canEdit ? (
                              <input
                                type="text"
                                value={item.unit}
                                onChange={(e) => handleUpdateItem(idx, 'unit', e.target.value)}
                                className="w-full p-1 text-center border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                              />
                            ) : (
                              <span className="text-center block text-slate-500">{item.unit}</span>
                            )}
                          </td>
                          <td className="p-2 text-right">
                            {canEdit ? (
                              <input
                                type="number"
                                step={5000}
                                value={item.unit_price}
                                onChange={(e) => handleUpdateItem(idx, 'unit_price', Number(e.target.value))}
                                className="w-full p-1 text-right border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
                              />
                            ) : (
                              <span>{item.unit_price.toLocaleString('vi-VN')}</span>
                            )}
                          </td>
                          <td className="p-2 pr-3 text-right font-bold text-slate-900">
                            {item.amount.toLocaleString('vi-VN')}
                          </td>
                          {canEdit && (
                            <td className="p-2 text-center">
                              {materialItems.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => handleRemoveItem(idx)}
                                  className="text-slate-400 hover:text-rose-600 p-1 rounded"
                                >
                                  <IconTrash className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-slate-50 font-semibold border-t border-slate-200">
                      <tr>
                        <td colSpan={4} className="p-2 pl-3 text-right text-slate-600">
                          Tiền công kỹ thuật & kiểm tra:
                        </td>
                        <td className="p-2 pr-3 text-right font-bold text-slate-900">
                          {canEdit ? (
                            <input
                              type="number"
                              step={10000}
                              value={laborCost}
                              onChange={(e) => setLaborCost(Number(e.target.value))}
                              className="w-24 p-1 text-right border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none inline-block"
                            />
                          ) : (
                            `${laborCost.toLocaleString('vi-VN')}`
                          )}
                        </td>
                        {canEdit && <td></td>}
                      </tr>
                      <tr>
                        <td colSpan={4} className="p-2 pl-3 text-right text-slate-600">
                          Thời gian bảo hành (tháng):
                        </td>
                        <td className="p-2 pr-3 text-right font-bold text-slate-900">
                          {canEdit ? (
                            <input
                              type="number"
                              min={1}
                              max={36}
                              value={warrantyMonths}
                              onChange={(e) => setWarrantyMonths(Number(e.target.value))}
                              className="w-16 p-1 text-right border border-slate-200 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none inline-block"
                            />
                          ) : (
                            `${warrantyMonths} tháng`
                          )}
                        </td>
                        {canEdit && <td></td>}
                      </tr>
                      <tr className="bg-blue-50/50 text-blue-900">
                        <td colSpan={4} className="p-2.5 pl-3 text-right font-bold">
                          TỔNG DỰ TOÁN BÁO GIÁ CHO CƯ DÂN:
                        </td>
                        <td className="p-2.5 pr-3 text-right font-extrabold text-sm text-blue-700">
                          {grandTotal.toLocaleString('vi-VN')} đ
                        </td>
                        {canEdit && <td></td>}
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {canEdit && (
                  <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">
                      * Nhấn gửi để Agent Kỹ Thuật lưu và Agent Báo Cáo lập hóa đơn chuyển Cư dân duyệt
                    </span>
                    <button
                      type="button"
                      onClick={handleSubmitQuote}
                      className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
                    >
                      <IconSend className="w-3.5 h-3.5" />
                      <span>Gửi báo giá cho Agent Kỹ Thuật</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

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
                Đã hoàn thành (Chờ QC)
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
