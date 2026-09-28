import { useState } from 'react';
import {
  IconTrash,
  IconCheck,
  IconAlertTriangle,
  IconPhoto,
  IconBuilding,
  IconShieldCheck,
  IconMapPin,
  IconClock,
  IconDeviceMobile,
  IconAlertCircle,
  IconSend,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { CleaningPlan, CleaningActionItem } from '../types/cleaning-plan';
import { EvidenceModal } from './evidence-modal';

export function SanitationWorkspace() {
  const {
    tasks,
    workOrders,
    currentProfile,
    currentPersona,
    toggleCleaningAction,
    confirmSiteArrival,
    toggleWarningSigns,
    saveCleaningRootCause,
  } = useOperationsData();

  // Filter tasks: STAFF_SANITATION_A5 only sees their assigned tasks or tasks with work orders assigned to them
  const sanitationTasks = tasks.filter((t) => {
    if ((t.domain_type !== 'SANITATION' && t.domain_type !== 'LANDSCAPE') || !t.domain_data) return false;
    if (currentPersona === 'STAFF_SANITATION_A5') {
      const isDirectAssignee = t.assignee_id === currentProfile.id;
      const hasMyWo = workOrders.some((w) => w.task_id === t.id && w.executor_id === currentProfile.id);
      return isDirectAssignee || hasMyWo;
    }
    return true; // Supervisors and Managers oversee all sanitation tasks
  });

  const [selectedTaskId, setSelectedTaskId] = useState<string>(
    sanitationTasks[0]?.id || tasks.find((t) => t.domain_type === 'SANITATION')?.id || '',
  );

  const [issueModalActionIdx, setIssueModalActionIdx] = useState<number | null>(null);
  const [issueType, setIssueType] = useState('MISSING_CHEMICALS');
  const [issueNote, setIssueNote] = useState('');
  const [selectedWoForPhoto, setSelectedWoForPhoto] = useState<any | null>(null);
  const [wasteWeight, setWasteWeight] = useState<number>(15);

  const [rootCause, setRootCause] = useState<string>('RESIDENT_PEAK_OVERFLOW');
  const [rootCauseNote, setRootCauseNote] = useState<string>(
    'Khung giờ 18h-20h lượng rác sinh hoạt dồn ứ gấp 3 lần bình thường, thùng 240L bị quá tải.',
  );
  const [rootCauseSaved, setRootCauseSaved] = useState(false);

  const selectedTask = sanitationTasks.find((t) => t.id === selectedTaskId) || sanitationTasks[0];
  const plan = selectedTask?.domain_data as CleaningPlan | null;
  const taskWorkOrders = selectedTask ? workOrders.filter((w) => w.task_id === selectedTask.id) : [];
  const activeWorkOrder = selectedTask
    ? [...taskWorkOrders]
        .sort((a, b) => (b.attempt_no || 1) - (a.attempt_no || 1))
        .find((w) => w.status === 'IN_PROGRESS' || w.status === 'ASSIGNED') || taskWorkOrders[0]
    : null;

  const handleToggleStep = (idx: number, currentCompleted: boolean) => {
    if (!selectedTask) return;
    if (!plan?.arrived_at_site) {
      alert('Vui lòng bấm nút "Xác nhận có mặt tại điểm làm việc" trước khi thực hiện các bước vệ sinh!');
      return;
    }
    toggleCleaningAction(selectedTask.id, idx, !currentCompleted);
  };

  const handleReportIssue = (e: React.FormEvent) => {
    e.preventDefault();
    if (issueModalActionIdx === null || !selectedTask) return;
    toggleCleaningAction(
      selectedTask.id,
      issueModalActionIdx,
      false,
      `[SỰ CỐ PHÁT SINH]: ${issueType === 'MISSING_CHEMICALS' ? 'Thiếu hóa chất tẩy rửa' : issueType === 'LOCKED_AREA' ? 'Khu vực bị khóa' : 'Phát hiện rác nguy hại'} - ${issueNote}`,
    );
    setIssueModalActionIdx(null);
    setIssueNote('');
  };

  const handleSaveRootCause = () => {
    if (!selectedTask) return;
    saveCleaningRootCause(selectedTask.id, `${rootCause}: ${rootCauseNote}`, wasteWeight);
    setRootCauseSaved(true);
    setTimeout(() => setRootCauseSaved(false), 3000);
  };

  const getActionName = (type: string) => {
    switch (type) {
      case 'REMOVE_WASTE':
        return 'Thu gom và vận chuyển rác thải';
      case 'PRESSURE_WASH':
        return 'Xịt rửa áp lực cao loại bỏ bùn đất';
      case 'DISINFECT':
        return 'Phun khử khuẩn & chế phẩm khử mùi';
      case 'MOP_FLOOR':
        return 'Lau khô sàn và đặt biển cảnh báo';
      case 'LANDSCAPE_TRIM':
        return 'Cắt tỉa cây cảnh & thu dọn cành lá gãy';
      default:
        return type;
    }
  };

  return (
    <div className="space-y-5 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-emerald-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Thao Tác Vệ Sinh Môi Trường A5 & Cảnh Quan
            </h1>
            <p className="text-xs text-slate-500">
              Màn hình thao tác trực tiếp của nhân viên vệ sinh A5: Tick từng bước, chụp ảnh và báo sự cố
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3.5 py-1 bg-emerald-50 text-emerald-800 font-bold text-xs rounded-full border border-emerald-200 flex items-center gap-1.5">
            <IconTrash className="w-3.5 h-3.5 text-emerald-600" />
            Nhân viên: {currentProfile.name}
          </span>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Tasks List (4 cols) */}
        <div className="lg:col-span-4 space-y-2.5">
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs font-bold text-slate-700">Kế hoạch phụ trách ({sanitationTasks.length})</span>
            <span className="text-[11px] text-slate-400">Chọn để thao tác</span>
          </div>

          <div className="space-y-2">
            {sanitationTasks.map((t) => {
              const isSelected = selectedTask?.id === t.id;
              const tPlan = t.domain_data as CleaningPlan | null;
              const completedCount = tPlan?.actions?.filter((a) => a.completed).length || 0;
              const totalActions = tPlan?.actions?.length || 0;

              return (
                <div
                  key={t.id}
                  onClick={() => setSelectedTaskId(t.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                    isSelected
                      ? 'bg-emerald-50/80 border-emerald-500 shadow-2xs ring-1 ring-emerald-500/20'
                      : 'bg-white border-slate-200/80 hover:border-slate-300 shadow-2xs'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-emerald-700">{t.id}</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        t.status === 'DONE' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {t.status === 'DONE' ? 'Đã hoàn thành' : 'Đang xử lý'}
                    </span>
                  </div>

                  <p className="font-bold text-xs text-slate-900 leading-snug">{t.title}</p>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-100">
                    <span className="flex items-center gap-1">
                      <IconBuilding className="w-3.5 h-3.5 text-slate-400" />
                      Tòa {tPlan?.area.towerCode || 'S2.01'} • Tầng {tPlan?.area.floor || 'G'}
                    </span>
                    <span className="font-bold text-emerald-700">
                      Tiến độ: {completedCount}/{totalActions} bước
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Interactive Step-by-Step Execution Pane (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {selectedTask && plan ? (
            <>
              {/* Site Arrival & Safety Controls */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                  <div>
                    <span className="font-mono text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                      {selectedTask.id}
                    </span>
                    <h2 className="text-base font-bold text-slate-900 mt-1">{selectedTask.title}</h2>
                    <p className="text-xs text-slate-500">
                      Vị trí: Tòa <strong>{plan.area.towerCode}</strong> • Tầng {plan.area.floor} • {plan.area.areaDetail || 'Khu vực phòng rác'}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {!plan.arrived_at_site ? (
                      <button
                        type="button"
                        onClick={() => confirmSiteArrival(selectedTask.id)}
                        className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-2xs transition-colors"
                      >
                        📍 Xác nhận có mặt tại điểm làm việc
                      </button>
                    ) : (
                      <span className="text-xs font-bold text-blue-700 bg-blue-50 px-3 py-1.5 rounded-xl border border-blue-200">
                        ✓ Đã có mặt lúc {new Date(plan.arrived_at_site).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                </div>

                {/* Safety Warning Signs Toggle */}
                <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-amber-900 font-semibold">
                    <IconAlertTriangle className="w-4 h-4 text-amber-600" />
                    <span>Quy chuẩn an toàn: Đặt biển cảnh báo "Sàn ướt / Đang làm vệ sinh"</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleWarningSigns(selectedTask.id, !plan.warning_signs_placed)}
                    className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                      plan.warning_signs_placed
                        ? 'bg-emerald-600 text-white'
                        : 'bg-white border border-amber-300 text-amber-800'
                    }`}
                  >
                    {plan.warning_signs_placed ? '✓ Đã đặt biển an toàn' : 'Chưa đặt biển'}
                  </button>
                </div>
              </div>

              {/* Step-by-Step Action Items Checklist */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3.5">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <h3 className="font-bold text-xs text-slate-900 uppercase tracking-wider">
                    Các bước công việc cần thực hiện trực tiếp:
                  </h3>
                  <span className="text-[11px] text-slate-500">Tick chọn để xác nhận thời điểm hoàn thành</span>
                </div>

                <div className="space-y-3">
                  {plan.actions.map((act: CleaningActionItem, idx: number) => {
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border transition-all space-y-2 ${
                          act.completed
                            ? 'bg-emerald-50/40 border-emerald-300'
                            : act.issue_reported
                              ? 'bg-rose-50/40 border-rose-300'
                              : 'bg-slate-50 border-slate-200'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={Boolean(act.completed)}
                              onChange={() => handleToggleStep(idx, Boolean(act.completed))}
                              className="w-5 h-5 rounded text-emerald-600 mt-0.5 cursor-pointer"
                            />
                            <div>
                              <div className="font-bold text-xs text-slate-900">
                                Bước {idx + 1}: {getActionName(act.type)}
                              </div>
                              <p className="text-[11px] text-slate-500 mt-0.5">
                                {act.instruction || 'Thực hiện kỹ lưỡng theo đúng tiêu chuẩn vệ sinh A5'}
                              </p>
                              {act.completed_at && (
                                <p className="text-[10px] text-emerald-700 font-medium mt-1">
                                  ✓ Xong lúc: {new Date(act.completed_at).toLocaleTimeString('vi-VN')}
                                </p>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            {activeWorkOrder && (
                              <button
                                type="button"
                                onClick={() => setSelectedWoForPhoto(activeWorkOrder)}
                                className="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 rounded-lg text-[11px] font-bold border border-slate-200 flex items-center gap-1 shadow-2xs"
                              >
                                <IconPhoto className="w-3.5 h-3.5 text-blue-600" />
                                <span>Chụp ảnh bước này</span>
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => setIssueModalActionIdx(idx)}
                              className="px-2.5 py-1 bg-white hover:bg-rose-50 text-rose-700 rounded-lg text-[11px] font-bold border border-slate-200 flex items-center gap-1 shadow-2xs"
                            >
                              <IconAlertCircle className="w-3.5 h-3.5 text-rose-600" />
                              <span>Báo sự cố</span>
                            </button>
                          </div>
                        </div>

                        {act.issue_reported && (
                          <div className="p-2.5 bg-rose-100 border border-rose-200 rounded-lg text-rose-800 text-[11px] font-medium">
                            {act.issue_reported}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Root Cause Analysis (A5 Special Requirement) */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <h3 className="font-bold text-xs text-slate-900 uppercase tracking-wider">
                    Phân tích nguyên nhân gốc rễ (Root Cause Analysis - A5)
                  </h3>
                  {rootCauseSaved && (
                    <span className="text-xs font-bold text-emerald-600 flex items-center gap-1">
                      <IconCheck className="w-4 h-4" />
                      <span>Đã lưu vào hồ sơ</span>
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label htmlFor="waste-weight-input" className="text-xs font-bold text-slate-700">Khối lượng rác phát sinh (kg):</label>
                    <input
                      id="waste-weight-input"
                      type="number"
                      min="0"
                      value={wasteWeight}
                      onChange={(e) => setWasteWeight(Number(e.target.value))}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="root-cause-select" className="text-xs font-bold text-slate-700">Nguyên nhân chính:</label>
                    <select
                      id="root-cause-select"
                      value={rootCause}
                      onChange={(e) => setRootCause(e.target.value)}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                    >
                      <option value="RESIDENT_PEAK_OVERFLOW">Quá tải rác sinh hoạt giờ cao điểm (18h-20h)</option>
                      <option value="UNPACKED_BULK_CARDBOARD">Thùng carton cồng kềnh chưa gấp gọn gây kẹt miệng họng rác</option>
                      <option value="LEAKING_LIQUID_CONTAINER">Nước thải sinh hoạt rò rỉ từ túi rác không bọc kín</option>
                      <option value="SCHEDULE_IRREGULARITY">Xe thu gom đô thị đến chậm so với lịch định kỳ</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-1">
                  <label htmlFor="root-cause-note" className="text-xs font-bold text-slate-700">Kiến nghị biện pháp ngăn tái diễn:</label>
                  <textarea
                    id="root-cause-note"
                    rows={2}
                    value={rootCauseNote}
                    onChange={(e) => setRootCauseNote(e.target.value)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                  />
                </div>

                <div className="pt-1 flex justify-end">
                  <button
                    type="button"
                    onClick={handleSaveRootCause}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs"
                  >
                    Lưu phân tích nguyên nhân
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-2xl border border-slate-200">
              Chọn kế hoạch vệ sinh bên trái để thao tác.
            </div>
          )}
        </div>
      </div>

      {/* Modal Report Issue */}
      {issueModalActionIdx !== null && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleReportIssue}
            className="bg-white rounded-2xl max-w-md w-full p-5 space-y-3.5 shadow-xl"
          >
            <h3 className="font-bold text-sm text-slate-900">Báo cáo vấn đề phát sinh tại bước {issueModalActionIdx + 1}</h3>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Loại vấn đề:</label>
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs"
              >
                <option value="MISSING_CHEMICALS">Thiếu dụng cụ hoặc hóa chất chuyên dụng</option>
                <option value="LOCKED_AREA">Khu vực bị khóa / Không thể tiếp cận</option>
                <option value="HAZARDOUS_WASTE">Phát hiện rác thải nguy hại (thủy tinh vỡ, pin/ắc quy)</option>
                <option value="OTHER">Lý do khác</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Mô tả cụ thể:</label>
              <textarea
                required
                rows={2}
                value={issueNote}
                onChange={(e) => setIssueNote(e.target.value)}
                placeholder="VD: Cửa phòng rác bị kẹt chốt, cần bảo vệ mở khóa..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIssueModalActionIdx(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Hủy
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow-2xs"
              >
                Gửi báo cáo sự cố
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Photo Modal */}
      {selectedWoForPhoto && (
        <EvidenceModal
          workOrder={selectedWoForPhoto}
          onClose={() => setSelectedWoForPhoto(null)}
        />
      )}
    </div>
  );
}
