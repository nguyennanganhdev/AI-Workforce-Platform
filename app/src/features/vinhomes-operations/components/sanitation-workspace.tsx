import { OperationsTable } from './operations-table';
import { useEffect, useState } from 'react';
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
  IconSearch,
  IconArrowLeft,
  IconChevronRight,
  IconPhone,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { CleaningPlan, CleaningActionItem } from '../types/cleaning-plan';
import { EvidenceModal } from './evidence-modal';

interface SanitationWorkspaceProps {
  initialTaskId?: string;
  embedded?: boolean;
  onBack?: () => void;
}

export function SanitationWorkspace({
  initialTaskId = '',
  embedded = false,
  onBack,
}: SanitationWorkspaceProps = {}) {
  const {
    tasks,
    workOrders,
    evidence,
    currentProfile,
    currentPersona,
    toggleCleaningAction,
    confirmSiteArrival,
    toggleWarningSigns,
    saveCleaningRootCause,
    transitionWorkOrderStatus,
  } = useOperationsData();

  const isExecutionMode = currentPersona === 'STAFF_SANITATION_A5';

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

  const [selectedTaskId, setSelectedTaskId] = useState<string>(initialTaskId);
  const [listSearch, setListSearch] = useState('');
  const [listStatus, setListStatus] = useState<'ALL' | 'ASSIGNED' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED'>('ALL');

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
  const [workflowMessage, setWorkflowMessage] = useState<{ type: 'SUCCESS' | 'ERROR'; text: string } | null>(null);

  useEffect(() => {
    setSelectedTaskId(initialTaskId);
    setWorkflowMessage(null);
  }, [initialTaskId]);

  const selectedTask = sanitationTasks.find((t) => t.id === selectedTaskId);
  const plan = selectedTask?.domain_data as CleaningPlan | null;
  const taskWorkOrders = selectedTask ? workOrders.filter((w) => w.task_id === selectedTask.id) : [];
  const activeWorkOrder = selectedTask
    ? [...taskWorkOrders]
      .sort((a, b) => (b.attempt_no || 1) - (a.attempt_no || 1))
      .find((w) => w.status === 'IN_PROGRESS' || w.status === 'ASSIGNED' || w.status === 'BLOCKED') || taskWorkOrders[0]
    : null;
  const isWorkInProgress = activeWorkOrder?.status === 'IN_PROGRESS';
  const allStepsCompleted = Boolean(plan?.actions?.length) && plan!.actions.every((action) => action.completed);

  const activeTaskEvidence = activeWorkOrder
    ? evidence.filter((item) => item.work_order_id === activeWorkOrder.id)
    : [];
  const activeBeforeCount = activeTaskEvidence.filter((item) => item.capture_phase === 'BEFORE').length;
  const activeAfterCount = activeTaskEvidence.filter((item) => item.capture_phase === 'AFTER').length;

  const sanitationRows = sanitationTasks.map((task) => {
    const taskOrders = workOrders
      .filter((workOrder) => workOrder.task_id === task.id)
      .sort((a, b) => (b.attempt_no || 1) - (a.attempt_no || 1));
    const workOrder = taskOrders.find((item) => ['ASSIGNED', 'IN_PROGRESS', 'BLOCKED'].includes(item.status)) || taskOrders[0];
    const taskEvidence = workOrder ? evidence.filter((item) => item.work_order_id === workOrder.id) : [];
    const taskPlan = task.domain_data as CleaningPlan;
    return {
      task,
      workOrder,
      plan: taskPlan,
      beforeCount: taskEvidence.filter((item) => item.capture_phase === 'BEFORE').length,
      afterCount: taskEvidence.filter((item) => item.capture_phase === 'AFTER').length,
    };
  });

  const filteredSanitationRows = sanitationRows.filter((row) => {
    const query = listSearch.trim().toLowerCase();
    const matchesSearch = !query ||
      row.task.title.toLowerCase().includes(query) ||
      row.task.id.toLowerCase().includes(query) ||
      (row.workOrder?.id || '').toLowerCase().includes(query) ||
      (row.plan?.area?.towerCode || '').toLowerCase().includes(query);
    const matchesStatus = listStatus === 'ALL' || row.workOrder?.status === listStatus;
    return matchesSearch && matchesStatus;
  });

  const statusCounts = {
    ALL: sanitationRows.length,
    ASSIGNED: sanitationRows.filter((row) => row.workOrder?.status === 'ASSIGNED').length,
    IN_PROGRESS: sanitationRows.filter((row) => row.workOrder?.status === 'IN_PROGRESS').length,
    BLOCKED: sanitationRows.filter((row) => row.workOrder?.status === 'BLOCKED').length,
    COMPLETED: sanitationRows.filter((row) => row.workOrder?.status === 'COMPLETED').length,
  };

  const runWorkOrderTransition = (targetStatus: 'IN_PROGRESS' | 'COMPLETED') => {
    if (!activeWorkOrder) {
      setWorkflowMessage({ type: 'ERROR', text: 'Kế hoạch này chưa có phiếu công việc để thực hiện.' });
      return;
    }

    if (targetStatus === 'COMPLETED') {
      if (!wasteWeight || wasteWeight <= 0) {
        setWorkflowMessage({
          type: 'ERROR',
          text: 'Vui lòng nhập khối lượng rác thu gom (> 0 kg) trước khi báo hoàn thành!',
        });
        return;
      }
      if (selectedTask) {
        try {
          saveCleaningRootCause(selectedTask.id, `${rootCause}: ${rootCauseNote}`, wasteWeight);
        } catch (_) {}
      }
    }

    try {
      transitionWorkOrderStatus(activeWorkOrder.id, targetStatus, {
        note:
          targetStatus === 'IN_PROGRESS'
            ? 'Nhân viên vệ sinh A5 bắt đầu thực hiện kế hoạch tại hiện trường.'
            : 'Đã hoàn thành các bước kiểm tra vệ sinh A5 và gửi hồ sơ chờ nghiệm thu.',
      });
      if (targetStatus === 'IN_PROGRESS' && selectedTask && !plan?.arrived_at_site) {
        try {
          confirmSiteArrival(selectedTask.id);
        } catch (_) {}
      }
      setWorkflowMessage({
        type: 'SUCCESS',
        text:
          targetStatus === 'IN_PROGRESS'
            ? 'Đã bắt đầu làm việc và tự động ghi nhận có mặt hiện trường.'
            : 'Đã báo hoàn thành công việc và tự động lưu dữ liệu rác, hồ sơ đã chuyển sang chờ nghiệm thu.',
      });
    } catch (error: any) {
      setWorkflowMessage({ type: 'ERROR', text: error.message || 'Không thể cập nhật phiếu công việc.' });
    }
  };

  const handleToggleStep = (idx: number, currentCompleted: boolean) => {
    if (!selectedTask) return;
    if (!isExecutionMode || !isWorkInProgress) return;
    if (!plan?.arrived_at_site) {
      try {
        confirmSiteArrival(selectedTask.id);
      } catch (_) {}
    }
    toggleCleaningAction(selectedTask.id, idx, !currentCompleted);
  };

  const handleReportIssue = (e: React.FormEvent) => {
    e.preventDefault();
    if (issueModalActionIdx === null || !selectedTask || !activeWorkOrder) return;
    const issueDescription = `[SỰ CỐ PHÁT SINH]: ${issueType === 'MISSING_CHEMICALS'
        ? 'Thiếu hóa chất tẩy rửa'
        : issueType === 'LOCKED_AREA'
          ? 'Khu vực bị khóa'
          : issueType === 'HAZARDOUS_WASTE'
            ? 'Phát hiện rác nguy hại'
            : 'Vấn đề khác'
      } - ${issueNote}`;
    try {
      toggleCleaningAction(selectedTask.id, issueModalActionIdx, false, issueDescription);
      transitionWorkOrderStatus(activeWorkOrder.id, 'BLOCKED', { blockedReason: issueDescription });
      setIssueModalActionIdx(null);
      setIssueNote('');
      setWorkflowMessage({
        type: 'SUCCESS',
        text: 'Đã báo vấn đề và tạm dừng phiếu công việc để Giám sát/BQL hỗ trợ.',
      });
    } catch (error: any) {
      setWorkflowMessage({ type: 'ERROR', text: error.message || 'Không thể gửi báo cáo sự cố.' });
    }
  };

  const handleSaveRootCause = () => {
    if (!selectedTask) return;
    try {
      saveCleaningRootCause(selectedTask.id, `${rootCause}: ${rootCauseNote}`, wasteWeight);
      setRootCauseSaved(true);
      setTimeout(() => setRootCauseSaved(false), 3000);
    } catch (error: any) {
      setWorkflowMessage({ type: 'ERROR', text: error.message || 'Không thể lưu báo cáo thực địa.' });
    }
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
    <div className="operations-worker-view space-y-5">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">

          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              {embedded
                ? 'Chi tiết công việc vệ sinh A5'
                : isExecutionMode
                  ? 'Công việc vệ sinh'
                  : 'Giám sát vệ sinh'}
            </h1>
            <p className="text-xs text-slate-500">
              {embedded
                ? 'Thực hiện các bước kiểm tra, cập nhật bằng chứng và báo cáo kết quả cho công việc đã chọn.'
                : isExecutionMode
                  ? 'Thực hiện trọn quy trình: bắt đầu việc, xác nhận hiện trường, các bước kiểm tra, ảnh bằng chứng và báo hoàn thành.'
                  : 'Theo dõi tiến độ, an toàn, bằng chứng và kết quả thực hiện của đội vệ sinh; các thao tác hiện trường được khóa.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">

            {isExecutionMode ? `Nhân viên: ${currentProfile.name}` : 'Chế độ giám sát • Chỉ xem'}
          </span>
        </div>
      </div>

      {workflowMessage && (
        <div
          className={`p-3 rounded-xl border text-xs font-semibold flex items-center justify-between ${workflowMessage.type === 'SUCCESS'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
            }`}
        >
          <span>{workflowMessage.text}</span>
          <button type="button" onClick={() => setWorkflowMessage(null)} className="px-2">×</button>
        </div>
      )}

      {!selectedTask ? (
        <div className="operations-plain-list">
          <OperationsTable title="Danh sách công việc" columns={['Mã công việc', 'Nội dung', 'Vị trí', 'Ảnh trước xử lý', 'Ảnh sau xử lý', 'Trạng thái']}
            filters={<label className="flex flex-col gap-1 text-xs text-slate-600">Trạng thái
              <select className="rounded border border-slate-200 bg-white px-3 py-2 text-sm" value={listStatus} onChange={(event) => setListStatus(event.target.value as typeof listStatus)}>
                <option value="ALL">Tất cả trạng thái</option>
                <option value="ASSIGNED">Mới giao</option>
                <option value="IN_PROGRESS">Đang thực hiện</option>
                <option value="BLOCKED">Tạm dừng</option>
                <option value="COMPLETED">Chờ nghiệm thu</option>
              </select>
            </label>}
            rows={filteredSanitationRows.map(({task, workOrder, plan: rowPlan, beforeCount, afterCount}) => ({
              id: task.id,
              search: `${task.id} ${workOrder?.id || ''} ${task.title} ${rowPlan?.area?.towerCode || ''}`,
              cells: [
                task.id, task.title,
                `Tòa ${rowPlan?.area?.towerCode || '—'} · Tầng ${rowPlan?.area?.floor ?? '—'}`,
                beforeCount ? `${beforeCount} ảnh` : 'Chưa có ảnh',
                afterCount ? `${afterCount} ảnh` : 'Chưa có ảnh',
                workOrder?.status === 'COMPLETED' ? 'Chờ nghiệm thu' : workOrder?.status === 'IN_PROGRESS' ? 'Đang thực hiện' : workOrder?.status === 'BLOCKED' ? 'Tạm dừng' : 'Mới giao',
              ],
            }))} onSelect={setSelectedTaskId} />
        </div>
      ) : (
        <div className="space-y-4">
          <button
            type="button"
            onClick={() => {
              if (onBack) {
                onBack();
              } else {
                setSelectedTaskId('');
              }
              setWorkflowMessage(null);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-bold shadow-2xs"
          >
            <IconArrowLeft className="w-4 h-4" />
            {embedded ? 'Quay lại Việc của tôi' : 'Quay lại danh sách công việc'}
          </button>

          {selectedTask && plan ? (
            <>
              {/* Site Arrival & Safety Controls */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3.5">
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
                    {activeWorkOrder && (
                      <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${activeWorkOrder.status === 'IN_PROGRESS'
                          ? 'bg-blue-100 text-blue-700'
                          : activeWorkOrder.status === 'COMPLETED'
                            ? 'bg-emerald-100 text-emerald-700'
                            : activeWorkOrder.status === 'BLOCKED'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-100 text-slate-700'
                        }`}>
                        Phiếu {activeWorkOrder.id} • {({OPEN: 'Mới tạo', ASSIGNED: 'Mới giao', IN_PROGRESS: 'Đang thực hiện', BLOCKED: 'Tạm dừng', COMPLETED: 'Chờ nghiệm thu', FAILED: 'Không đạt', CANCELLED: 'Đã hủy'})[activeWorkOrder.status]}
                      </span>
                    )}
                    {isExecutionMode && activeWorkOrder?.status === 'ASSIGNED' && (
                      <button
                        type="button"
                        onClick={() => runWorkOrderTransition('IN_PROGRESS')}
                        className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-2xs transition-colors"
                      >
                        Bắt đầu công việc
                      </button>
                    )}
                    {isExecutionMode && activeWorkOrder?.status === 'BLOCKED' && (
                      <button
                        type="button"
                        onClick={() => runWorkOrderTransition('IN_PROGRESS')}
                        className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-2xs transition-colors"
                      >
                        Tiếp tục công việc
                      </button>
                    )}
                    {plan.arrived_at_site ? (
                      <span className="text-xs font-bold text-blue-700 bg-blue-50 px-3 py-1.5 rounded-xl border border-blue-200 flex items-center gap-1">
                        <IconCheck className="w-3.5 h-3.5 text-blue-600" />
                        <span>Đã có mặt lúc {new Date(plan.arrived_at_site).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
                      </span>
                    ) : isExecutionMode && isWorkInProgress ? (
                      <button
                        type="button"
                        onClick={() => {
                          try {
                            confirmSiteArrival(selectedTask.id);
                          } catch (error: any) {
                            setWorkflowMessage({ type: 'ERROR', text: error.message });
                          }
                        }}
                        className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-2xs transition-colors"
                      >
                        📍 Xác nhận có mặt tại điểm làm việc
                      </button>
                    ) : null}
                  </div>
                </div>

                {/* Safety Warning Signs Toggle */}
                <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-amber-900 font-semibold">
                    <IconAlertTriangle className="w-4 h-4 text-amber-600" />
                    <span>Quy chuẩn an toàn: Đặt biển cảnh báo "Sàn ướt / Đang làm vệ sinh"</span>
                  </div>
                  {isExecutionMode ? (
                    <button
                      type="button"
                      disabled={!isWorkInProgress || !plan.arrived_at_site}
                      onClick={() => {
                        try {
                          toggleWarningSigns(selectedTask.id, !plan.warning_signs_placed);
                        } catch (error: any) {
                          setWorkflowMessage({ type: 'ERROR', text: error.message });
                        }
                      }}
                      className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${plan.warning_signs_placed
                          ? 'bg-emerald-600 text-white'
                          : 'bg-white border border-amber-300 text-amber-800'
                        }`}
                    >
                      {plan.warning_signs_placed ? '✓ Đã đặt biển an toàn' : 'Xác nhận đã đặt biển'}
                    </button>
                  ) : (
                    <span className={`px-3 py-1 text-xs font-bold rounded-lg ${plan.warning_signs_placed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
                      }`}>
                      {plan.warning_signs_placed ? '✓ Đã đặt biển an toàn' : 'Chưa đặt biển'}
                    </span>
                  )}
                </div>
              </div>

              {/* Photo Status & Prompts */}
              {isExecutionMode && isWorkInProgress && (
                <div className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <IconPhoto className="w-4 h-4 text-blue-600" />
                      <span>Ảnh minh chứng hiện trường ({activeBeforeCount} ảnh Trước • {activeAfterCount} ảnh Sau)</span>
                    </span>
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                      activeBeforeCount > 0 && activeAfterCount > 0
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-amber-100 text-amber-800'
                    }`}>
                      {activeBeforeCount > 0 && activeAfterCount > 0 ? '✓ Đủ ảnh nghiệm thu' : 'Cần tối thiểu 1 ảnh Trước và 1 ảnh Sau'}
                    </span>
                  </div>

                  {activeBeforeCount === 0 ? (
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                      <div className="flex items-start gap-2">
                        <IconAlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-bold text-amber-900">
                            Chú ý: Chưa có ảnh Hiện trạng (Trước khi làm)
                          </p>
                          <p className="text-[11px] text-amber-700">
                            Vui lòng chụp ảnh hiện trạng phòng rác trước khi quét dọn để tránh phải làm lại.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedWoForPhoto({ ...activeWorkOrder, initialPhase: 'BEFORE' })}
                        className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold shrink-0 flex items-center justify-center gap-1.5 shadow-2xs"
                      >
                        <IconPhoto className="w-4 h-4" />
                        <span>Chụp ảnh trước xử lý</span>
                      </button>
                    </div>
                  ) : activeAfterCount === 0 ? (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                      <div className="flex items-start gap-2">
                        <IconCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-bold text-blue-900">
                            Đã có ảnh Trước khi làm. Sau khi dọn sạch, vui lòng chụp thêm ảnh Sau khi làm.
                          </p>
                          <p className="text-[11px] text-blue-700">
                            Ảnh sau khi làm sẽ chứng minh phòng rác đã sạch bong và đạt tiêu chuẩn A5.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedWoForPhoto({ ...activeWorkOrder, initialPhase: 'AFTER' })}
                        className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shrink-0 flex items-center justify-center gap-1.5 shadow-2xs"
                      >
                        <IconPhoto className="w-4 h-4" />
                        <span>Chụp ảnh sau xử lý</span>
                      </button>
                    </div>
                  ) : (
                    <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800 font-semibold">
                      <span className="flex items-center gap-1.5">
                        <IconCheck className="w-4 h-4 text-emerald-600" />
                        <span>Đã có đủ ảnh Trước & Sau khi làm. Đạt tiêu chuẩn nghiệm thu ảnh!</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedWoForPhoto(activeWorkOrder)}
                        className="text-[11px] text-blue-700 font-bold hover:underline"
                      >
                        Xem / chụp thêm ảnh
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Step-by-Step Action Items Checklist */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3.5">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <h3 className="font-bold text-xs text-slate-900 uppercase tracking-wider">
                    Các bước thực hiện
                  </h3>
                  <span className="text-[11px] text-slate-500">
                    {isExecutionMode ? 'Đánh dấu từng bước sau khi hoàn thành' : 'Dữ liệu do nhân viên thực địa cập nhật'}
                  </span>
                </div>

                <div className="space-y-3">
                  {plan.actions.map((act: CleaningActionItem, idx: number) => {
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border transition-all space-y-2 ${act.completed
                            ? 'bg-emerald-50/40 border-emerald-300'
                            : act.issue_reported
                              ? 'bg-rose-50/40 border-rose-300'
                              : 'bg-slate-50 border-slate-200'
                          }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={Boolean(act.completed)}
                              disabled={!isExecutionMode || !isWorkInProgress || !plan.arrived_at_site}
                              onChange={() => handleToggleStep(idx, Boolean(act.completed))}
                              className="w-5 h-5 rounded text-emerald-600 mt-0.5 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
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

                          <div className="flex items-center gap-1.5 self-end sm:self-auto shrink-0">
                            {activeWorkOrder && isExecutionMode && isWorkInProgress && (
                              <button
                                type="button"
                                onClick={() => setSelectedWoForPhoto(activeWorkOrder)}
                                className="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 rounded-lg text-[11px] font-bold border border-slate-200 flex items-center gap-1 shadow-2xs"
                              >
                                <IconPhoto className="w-3.5 h-3.5 text-blue-600" />
                                <span>Chụp ảnh bước này</span>
                              </button>
                            )}

                            {isExecutionMode && isWorkInProgress && (
                              <button
                                type="button"
                                onClick={() => setIssueModalActionIdx(idx)}
                                className="px-2.5 py-1 bg-white hover:bg-rose-50 text-rose-700 rounded-lg text-[11px] font-bold border border-slate-200 flex items-center gap-1 shadow-2xs"
                              >
                                <IconAlertCircle className="w-3.5 h-3.5 text-rose-600" />
                                <span>Báo sự cố</span>
                              </button>
                            )}
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
              <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <h3 className="font-bold text-xs text-slate-900 uppercase tracking-wider">
                    Nguyên nhân và biện pháp xử lý
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
                      disabled={!isExecutionMode || !isWorkInProgress}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-70"
                    />
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="root-cause-select" className="text-xs font-bold text-slate-700">Nguyên nhân chính:</label>
                    <select
                      id="root-cause-select"
                      value={rootCause}
                      onChange={(e) => setRootCause(e.target.value)}
                      disabled={!isExecutionMode || !isWorkInProgress}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-70"
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
                    readOnly={!isExecutionMode || !isWorkInProgress}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 read-only:opacity-70"
                  />
                </div>

                {isExecutionMode && isWorkInProgress && (
                  <div className="pt-1 flex justify-end">
                    <button
                      type="button"
                      onClick={handleSaveRootCause}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs"
                    >
                      Lưu phân tích nguyên nhân
                    </button>
                  </div>
                )}
              </div>

              {isExecutionMode && isWorkInProgress && (
                <div className="bg-white rounded-2xl border border-emerald-200 p-5 shadow-2xs space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <h3 className="font-bold text-sm text-slate-900">Hoàn tất và gửi nghiệm thu</h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Kiểm tra các điều kiện bắt buộc trước khi bàn giao hồ sơ cho QC nghiệm thu.
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={
                        !allStepsCompleted ||
                        !plan.warning_signs_placed ||
                        !plan.arrived_at_site ||
                        wasteWeight <= 0 ||
                        activeBeforeCount === 0 ||
                        activeAfterCount === 0
                      }
                      onClick={() => runWorkOrderTransition('COMPLETED')}
                      className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold shadow-2xs transition-colors shrink-0"
                    >
                      Báo hoàn thành • Chờ nghiệm thu
                    </button>
                  </div>

                  {/* Visual Condition Checklist */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100 text-[11px]">
                    <div className={`p-2 rounded-lg border font-medium ${
                      plan.arrived_at_site ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
                    }`}>
                      {plan.arrived_at_site ? '✓ Đã có mặt' : '⚠️ Chưa có mặt'}
                    </div>
                    <div className={`p-2 rounded-lg border font-medium ${
                      plan.warning_signs_placed ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
                    }`}>
                      {plan.warning_signs_placed ? '✓ Biển an toàn' : '⚠️ Chưa đặt biển'}
                    </div>
                    <div className={`p-2 rounded-lg border font-medium ${
                      allStepsCompleted ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
                    }`}>
                      {allStepsCompleted ? '✓ Đủ các bước kiểm tra' : `⚠️ Còn ${plan.actions.filter((a) => !a.completed).length} bước`}
                    </div>
                    <div className={`p-2 rounded-lg border font-medium ${
                      wasteWeight > 0 && activeBeforeCount > 0 && activeAfterCount > 0
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                        : 'bg-rose-50 text-rose-800 border-rose-200'
                    }`}>
                      {wasteWeight <= 0
                        ? '⚠️ Chưa nhập kg rác'
                        : activeBeforeCount === 0 || activeAfterCount === 0
                          ? `⚠️ Ảnh: ${activeBeforeCount}T • ${activeAfterCount}S`
                          : `✓ Rác: ${wasteWeight}kg & Đủ ảnh`}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-2xl border border-slate-200">
              Công việc này chưa có kế hoạch vệ sinh A5 hợp lệ.
            </div>
          )}
        </div>
      )}

      {/* Modal Report Issue */}
      {issueModalActionIdx !== null && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4">
          <form
            onSubmit={handleReportIssue}
            className="bg-white rounded-2xl max-w-md w-full p-4 sm:p-5 space-y-3.5 shadow-xl"
          >
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="font-bold text-sm text-slate-900">
                Báo cáo sự cố phát sinh tại bước {issueModalActionIdx + 1}
              </h3>
              <button
                type="button"
                onClick={() => setIssueModalActionIdx(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Quick 1-touch Presets */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700">Chọn nhanh lý do (chạm để điền):</label>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { type: 'LOCKED_AREA', label: '🔒 Cửa khóa / Kẹt chốt', note: 'Cửa phòng rác bị khóa kẹt chốt, không vào được.' },
                  { type: 'MISSING_CHEMICALS', label: '🧴 Hết hóa chất tẩy rửa', note: 'Hết hóa chất khử khuẩn chuyên dụng, cần cấp phát.' },
                  { type: 'HAZARDOUS_WASTE', label: '⚠️ Mảnh kính vỡ nguy hiểm', note: 'Có mảnh kính vỡ nguy hiểm trên sàn, cần hỗ trợ dọn.' },
                  { type: 'OTHER', label: '💧 Nước rò rỉ tràn sàn', note: 'Đường ống rò rỉ nước ngập sàn hành lang.' },
                ].map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => {
                      setIssueType(preset.type);
                      setIssueNote(preset.note);
                    }}
                    className="p-2 text-left bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl text-[11px] font-semibold text-slate-700 transition-colors cursor-pointer"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Loại vấn đề:</label>
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium"
              >
                <option value="MISSING_CHEMICALS">Thiếu dụng cụ hoặc hóa chất chuyên dụng</option>
                <option value="LOCKED_AREA">Khu vực bị khóa / Không thể tiếp cận</option>
                <option value="HAZARDOUS_WASTE">Phát hiện rác thải nguy hại (thủy tinh vỡ, pin/ắc quy)</option>
                <option value="OTHER">Lý do khác</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">Mô tả cụ thể (không bắt buộc nếu đã chọn ở trên):</label>
              <textarea
                rows={2}
                value={issueNote}
                onChange={(e) => setIssueNote(e.target.value)}
                placeholder="VD: Cửa phòng rác bị kẹt chốt, cần bảo vệ mở khóa..."
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none"
              />
            </div>

            {/* Direct hotline */}
            <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-blue-900 font-semibold">
                <IconPhone className="w-4 h-4 text-blue-600 shrink-0" />
                <span>Cần hỗ trợ gấp: Trưởng ca Mai</span>
              </div>
              <a
                href="tel:0988765432"
                className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-[11px]"
              >
                0988 765 432
              </a>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIssueModalActionIdx(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer"
              >
                Hủy
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl shadow-2xs cursor-pointer"
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
          readOnly={!isExecutionMode}
          onClose={() => setSelectedWoForPhoto(null)}
        />
      )}
    </div>
  );
}
