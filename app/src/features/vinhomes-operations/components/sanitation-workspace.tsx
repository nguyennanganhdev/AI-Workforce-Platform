import { useState } from 'react';
import {
  IconTrash,
  IconCheck,
  IconAlertTriangle,
  IconPhoto,
  IconBuilding,
  IconShieldCheck,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { CleaningPlan, CleaningActionItem } from '../types/cleaning-plan';

export function SanitationWorkspace() {
  const { tasks, workOrders } = useOperationsData();

  const sanitationTasks = tasks.filter(
    (t) => (t.domain_type === 'SANITATION' || t.domain_type === 'LANDSCAPE') && t.domain_data,
  );

  const [selectedTaskId, setSelectedTaskId] = useState<string>(
    sanitationTasks[0]?.id || tasks.find((t) => t.domain_type === 'SANITATION')?.id || '',
  );

  const [rootCause, setRootCause] = useState<string>('RESIDENT_PEAK_OVERFLOW');
  const [rootCauseNote, setRootCauseNote] = useState<string>(
    'Khung giờ 18h-20h lượng rác sinh hoạt dồn ứ gấp 3 lần bình thường, thùng 240L bị quá tải.',
  );
  const [rootCauseSaved, setRootCauseSaved] = useState(false);

  const selectedTask = sanitationTasks.find((t) => t.id === selectedTaskId) || sanitationTasks[0];
  const plan = selectedTask?.domain_data as CleaningPlan | null;

  const taskWorkOrders = selectedTask ? workOrders.filter((w) => w.task_id === selectedTask.id) : [];

  const handleSaveRootCause = () => {
    setRootCauseSaved(true);
    setTimeout(() => setRootCauseSaved(false), 3000);
  };

  const getActionName = (type: string) => {
    switch (type) {
      case 'REMOVE_WASTE':
        return 'Thu gom và vận chuyển rác';
      case 'PRESSURE_WASH':
        return 'Xịt rửa áp lực cao';
      case 'DISINFECT':
        return 'Phun khử khuẩn & khử mùi';
      case 'MOP_FLOOR':
        return 'Lau khô và đặt biển cảnh báo';
      case 'LANDSCAPE_TRIM':
        return 'Cắt tỉa cây cảnh & gom cành lá';
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
              Kế Hoạch Vệ Sinh Môi Trường A5 & Cảnh Quan
            </h1>
            <p className="text-xs text-slate-500">
              Theo dõi kế hoạch làm sạch rác thải, kiểm soát mùi hôi và tìm giải pháp ngăn ngừa tái phát
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-emerald-50 text-emerald-700 font-semibold text-xs rounded-full border border-emerald-200 flex items-center gap-1.5">
            <IconTrash className="w-3.5 h-3.5 text-emerald-600" />
            {sanitationTasks.length} Kế hoạch đang thực hiện
          </span>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Tasks List (4 cols) */}
        <div className="lg:col-span-4 space-y-2.5">
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs font-bold text-slate-700">Danh sách kế hoạch vệ sinh</span>
            <span className="text-[11px] text-slate-400">Chọn để xem</span>
          </div>

          <div className="space-y-2">
            {sanitationTasks.map((t) => {
              const isSelected = selectedTask?.id === t.id;
              const tPlan = t.domain_data as CleaningPlan | null;

              return (
                <div
                  key={t.id}
                  onClick={() => setSelectedTaskId(t.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                    isSelected
                      ? 'bg-emerald-50/70 border-emerald-500 shadow-2xs ring-1 ring-emerald-500/20'
                      : 'bg-white border-slate-200/80 hover:border-slate-300 shadow-2xs'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-emerald-700">{t.id}</span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        t.status === 'DONE'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {t.status === 'DONE' ? 'Đã hoàn thành' : 'Đang thực hiện'}
                    </span>
                  </div>

                  <p className="font-bold text-xs text-slate-900 line-clamp-2 leading-snug">
                    {t.title}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-100">
                    <span className="flex items-center gap-1 font-medium">
                      <IconBuilding className="w-3.5 h-3.5 text-slate-400" />
                      Tòa {tPlan?.area?.towerCode || 'Khu A5'} (Tầng {tPlan?.area?.floor || '—'})
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">
                      {t.incident_id}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Details Pane (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {selectedTask && plan ? (
            <>
              {/* Summary Card */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                  <div>
                    <h2 className="text-base font-bold text-slate-900 leading-snug">
                      {selectedTask.title}
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Vị trí: Tòa <strong>{plan.area.towerCode}</strong> • Tầng {plan.area.floor} • Khu vực: <span className="font-mono">{plan.area.locationId}</span>
                    </p>
                  </div>

                  <div className="text-xs text-slate-600">
                    Người phụ trách: <strong className="text-emerald-700">{selectedTask.assignee_name || 'Trần Thị Mai'}</strong>
                  </div>
                </div>

                {/* Actions Grid */}
                <div className="space-y-2">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    Các bước thực hiện ({plan.actions.length} bước)
                  </span>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {plan.actions.map((act: CleaningActionItem, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800 flex items-center gap-1.5">
                            <span className="w-4 h-4 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">
                              {idx + 1}
                            </span>
                            <span>{getActionName(act.type)}</span>
                          </span>
                          <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-white border border-slate-200 text-slate-600">
                            {act.executorType === 'HUMAN' ? 'Nhân viên' : act.executorType === 'ROBOT' ? 'Robot' : 'Nhà thầu'}
                          </span>
                        </div>
                        <p className="text-slate-600 italic">
                          "{act.instruction || 'Thực hiện theo tiêu chuẩn sạch sẽ'}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidence & QC Criteria Requirements */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-2 border-t border-slate-100 text-xs">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                    <span className="font-bold text-slate-700 flex items-center gap-1.5">
                      <IconPhoto className="w-4 h-4 text-blue-600" />
                      Yêu cầu ảnh chụp hiện trường
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="px-2 py-0.5 bg-white border border-blue-200 text-blue-700 font-semibold rounded-lg text-[10px]">
                        ✓ Ảnh trước khi dọn dẹp
                      </span>
                      <span className="px-2 py-0.5 bg-white border border-blue-200 text-blue-700 font-semibold rounded-lg text-[10px]">
                        ✓ Ảnh sau khi làm sạch
                      </span>
                    </div>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                    <span className="font-bold text-slate-700 flex items-center gap-1.5">
                      <IconShieldCheck className="w-4 h-4 text-purple-600" />
                      Tiêu chuẩn nghiệm thu
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      <span className="px-2 py-0.5 bg-white border border-purple-200 text-purple-700 font-semibold rounded-lg text-[10px]">
                        ✓ Sạch rác tồn đọng
                      </span>
                      <span className="px-2 py-0.5 bg-white border border-purple-200 text-purple-700 font-semibold rounded-lg text-[10px]">
                        ✓ Hết mùi hôi chua nồng
                      </span>
                      <span className="px-2 py-0.5 bg-white border border-purple-200 text-purple-700 font-semibold rounded-lg text-[10px]">
                        ✓ Thùng rác đã vệ sinh
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Root Cause Analysis */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <IconAlertTriangle className="w-4 h-4 text-amber-600" />
                    <h3 className="font-bold text-slate-900 text-xs">
                      Tìm Hiểu Nguyên Nhân & Đề Xuất Giải Pháp Lâu Dài
                    </h3>
                  </div>
                  {rootCauseSaved && (
                    <span className="text-xs font-bold text-emerald-600 flex items-center gap-1">
                      <IconCheck className="w-3.5 h-3.5" /> Đã lưu
                    </span>
                  )}
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">
                      Nguyên nhân gây ra sự cố:
                    </label>
                    <select
                      value={rootCause}
                      onChange={(e) => setRootCause(e.target.value)}
                      className="w-full p-2 bg-white border border-slate-200 rounded-xl focus:border-emerald-500 focus:outline-none font-medium text-slate-800"
                    >
                      <option value="RESIDENT_PEAK_OVERFLOW">Cư dân xả rác tập trung giờ cao điểm (quá tải thùng chứa)</option>
                      <option value="IMPROPER_SORTING">Vứt rác cồng kềnh làm tắc đường ống gom rác</option>
                      <option value="HVAC_VENTILATION_FAIL">Hệ thống quạt hút mùi phòng rác bị yếu hoặc hỏng</option>
                      <option value="MISSED_SCHEDULE">Nhân viên ca trước chưa kịp gom theo lịch định kỳ</option>
                    </select>
                  </div>

                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">
                      Phương án khắc phục lâu dài:
                    </label>
                    <textarea
                      rows={2}
                      value={rootCauseNote}
                      onChange={(e) => setRootCauseNote(e.target.value)}
                      className="w-full p-2 bg-white border border-slate-200 rounded-xl focus:border-emerald-500 focus:outline-none text-xs text-slate-800"
                    />
                  </div>

                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleSaveRootCause}
                      className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors shadow-2xs"
                    >
                      Lưu giải pháp phòng ngừa
                    </button>
                  </div>
                </div>
              </div>

              {/* Lịch sử thi công */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-2.5">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                  Lịch sử thi công thực tế ({taskWorkOrders.length} lần thực hiện)
                </span>
                <div className="space-y-2">
                  {taskWorkOrders.map((wo) => (
                    <div
                      key={wo.id}
                      className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between"
                    >
                      <div>
                        <span className="font-mono font-bold text-blue-600">{wo.id}</span>
                        <span className="text-slate-400 mx-1">•</span>
                        <span className="text-slate-600">Lần làm #{wo.attempt_no}</span>
                        <p className="text-[11px] text-slate-500">
                          Nhân viên: {wo.executor_name} ({wo.executor_phone})
                        </p>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          wo.status === 'COMPLETED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {wo.status === 'COMPLETED' ? 'Hoàn thành' : 'Đang làm'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-2xl border border-slate-200">
              Chọn một kế hoạch vệ sinh bên trái để xem chi tiết.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
