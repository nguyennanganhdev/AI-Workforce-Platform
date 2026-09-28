import { useState } from 'react';
import {
  IconAlertTriangle,
  IconBuilding,
  IconClock,
  IconCheck,
  IconMessageDots,
  IconListCheck,
  IconChevronRight,
  IconUser,
  IconShieldCheck,
  IconHistory,
  IconSend,
  IconRotateClockwise,
  IconAlertCircle,
  IconLink,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { IncidentStage } from '../types/incident';
import { MOCK_MESSAGES } from '../mock/messages';
import { MOCK_BUSINESS_EVENTS } from '../mock/business-events';
import { MOCK_INCIDENT_RELATIONS } from '../mock/incidents';

const STAGE_LABELS: Record<IncidentStage, string> = {
  INTAKE: '1. Tiếp nhận',
  TRIAGE: '2. Phân loại',
  PLANNING: '3. Lên phương án',
  EXECUTION: '4. Đang sửa chữa',
  QC: '5. Nghiệm thu',
  RESIDENT_CONFIRMATION: '6. Cư dân xác nhận',
};

const STAGES: IncidentStage[] = [
  'INTAKE',
  'TRIAGE',
  'PLANNING',
  'EXECUTION',
  'QC',
  'RESIDENT_CONFIRMATION',
];

export function IncidentsWorkspace() {
  const {
    incidents,
    tasks,
    workOrders,
    assignIncidentOwner,
    transitionIncidentStage,
    resolveIncident,
    residentConfirmIncident,
  } = useOperationsData();

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(incidents[0]?.id || '');
  const [activeTab, setActiveTab] = useState<'TASKS' | 'MESSAGES' | 'TIMELINE' | 'RELATIONS'>('TASKS');
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [newMessageText, setNewMessageText] = useState('');
  const [localMessages, setLocalMessages] = useState(MOCK_MESSAGES);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId) || incidents[0];

  const relatedTasks = selectedIncident
    ? tasks.filter((t) => t.incident_id === selectedIncident.id)
    : [];

  const relatedWorkOrders = selectedIncident
    ? workOrders.filter((w) => w.incident_id === selectedIncident.id)
    : [];

  const incidentMessages = localMessages.filter((m) => m.incident_id === selectedIncident?.id);
  const incidentEvents = MOCK_BUSINESS_EVENTS.filter((e) => e.incident_id === selectedIncident?.id);
  const incidentRelations = MOCK_INCIDENT_RELATIONS.filter(
    (r) => r.source_incident_id === selectedIncident?.id || r.target_incident_id === selectedIncident?.id,
  );

  const handleResolve = () => {
    if (!selectedIncident) return;
    setResolveError(null);
    try {
      resolveIncident(selectedIncident.id);
      setActionSuccess(`Đã hoàn tất xử lý sự cố ${selectedIncident.id}! Chuyển sang chờ cư dân xác nhận.`);
      setTimeout(() => setActionSuccess(null), 3500);
    } catch (err: any) {
      setResolveError(err.message || 'Chưa đủ điều kiện hoàn tất sự cố');
    }
  };

  const handleResidentConfirmation = (confirmed: boolean) => {
    if (!selectedIncident) return;
    residentConfirmIncident(selectedIncident.id, confirmed);
    if (confirmed) {
      setActionSuccess(`Cư dân đã đồng ý nghiệm thu! Sự cố ${selectedIncident.id} đã hoàn thành và đóng lại.`);
    } else {
      setActionSuccess(`Cư dân phản ánh chưa đạt yêu cầu! Sự cố được mở lại để kiểm tra bổ sung.`);
    }
    setTimeout(() => setActionSuccess(null), 3500);
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessageText.trim() || !selectedIncident) return;

    const newMsg = {
      id: `MSG-${Date.now().toString().slice(-4)}`,
      incident_id: selectedIncident.id,
      body: newMessageText.trim(),
      author_type: 'STAFF' as const,
      author_id: 'usr-tech-01',
      author_name: 'Nguyễn Văn Hùng (Kỹ sư Trưởng)',
      author_avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80',
      created_at: new Date().toISOString(),
    };

    setLocalMessages((prev) => [...prev, newMsg]);
    setNewMessageText('');
  };

  return (
    <div className="space-y-5 font-sans">
      {/* Title Header with Blue Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-blue-600 rounded-full shrink-0" />
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Quản Lý & Theo Dõi Sự Cố
            </h1>
            <p className="text-xs text-slate-500">
              Theo dõi tiến độ từ lúc tiếp nhận, phân công sửa chữa đến khi cư dân nghiệm thu hài lòng
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-blue-50 text-blue-700 font-semibold text-xs rounded-full border border-blue-200">
            {incidents.length} Sự cố ghi nhận
          </span>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconCheck className="w-4 h-4 text-emerald-600" />
            <span>{actionSuccess}</span>
          </div>
          <button type="button" onClick={() => setActionSuccess(null)} className="text-emerald-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {resolveError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <IconAlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{resolveError}</span>
          </div>
          <button type="button" onClick={() => setResolveError(null)} className="text-rose-500 text-xs">
            ✕
          </button>
        </div>
      )}

      {/* Two Column Layout: List & Detail Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Incidents List (4 cols) */}
        <div className="lg:col-span-4 space-y-2.5">
          <div className="flex items-center justify-between pb-1">
            <span className="text-xs font-bold text-slate-700">Danh sách sự cố</span>
            <span className="text-[11px] text-slate-400">Chọn sự cố để xem</span>
          </div>

          <div className="space-y-2 max-h-[720px] overflow-y-auto pr-1">
            {incidents.map((inc) => {
              const isSelected = selectedIncident?.id === inc.id;
              return (
                <div
                  key={inc.id}
                  onClick={() => {
                    setSelectedIncidentId(inc.id);
                    setResolveError(null);
                  }}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                    isSelected
                      ? 'bg-blue-50/70 border-blue-500 shadow-2xs ring-1 ring-blue-500/20'
                      : 'bg-white border-slate-200/80 hover:border-slate-300 shadow-2xs'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-bold text-blue-600">{inc.id}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          inc.severity === 'P1'
                            ? 'bg-rose-100 text-rose-700'
                            : inc.severity === 'P2'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {inc.severity === 'P1' ? 'Khẩn cấp (P1)' : inc.severity === 'P2' ? 'Mức cao (P2)' : 'Bình thường'}
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        inc.status === 'CLOSED'
                          ? 'bg-slate-100 text-slate-600'
                          : inc.status === 'RESOLVED'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {inc.status === 'CLOSED' ? 'Đã đóng' : inc.status === 'RESOLVED' ? 'Chờ cư dân duyệt' : 'Đang xử lý'}
                    </span>
                  </div>

                  <p className="font-bold text-xs text-slate-900 line-clamp-2 leading-snug">
                    {inc.title}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-100">
                    <span className="flex items-center gap-1 font-medium">
                      <IconBuilding className="w-3.5 h-3.5 text-slate-400" />
                      Tòa {inc.location_json.towerCode}
                    </span>
                    <span className="text-[10px] font-semibold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                      {STAGE_LABELS[inc.stage as IncidentStage] || inc.stage}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Incident Detail Pane (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {selectedIncident ? (
            <>
              {/* Header & Stepper */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                        {selectedIncident.id}
                      </span>
                      <span className="text-xs text-slate-400">•</span>
                      <span className="text-xs font-semibold text-slate-700">
                        {selectedIncident.category === 'MEP_PLUMBING'
                          ? 'Kỹ thuật Cấp Thoát Nước'
                          : selectedIncident.category === 'SANITATION_A5'
                            ? 'Vệ sinh Môi trường A5'
                            : selectedIncident.category === 'ELEVATOR'
                              ? 'Hệ thống Thang máy'
                              : selectedIncident.category === 'ELECTRICAL'
                                ? 'Kỹ thuật Điện chiếu sáng'
                                : selectedIncident.category === 'CIVIL'
                                  ? 'Xây dựng hoàn thiện'
                                  : selectedIncident.category}
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-slate-900 mt-1 leading-snug">
                      {selectedIncident.title}
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Vị trí: Tòa <strong>{selectedIncident.location_json.towerCode}</strong> • Tầng {selectedIncident.location_json.floor || '—'} • {selectedIncident.location_json.areaCode || selectedIncident.location_json.description}
                    </p>
                  </div>

                  {/* Owner & Stage Controls */}
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-slate-500 text-[11px] font-medium">Chủ trì:</span>
                      <select
                        value={selectedIncident.owner_user_id || ''}
                        onChange={(e) => assignIncidentOwner(selectedIncident.id, e.target.value)}
                        className="p-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 focus:outline-none"
                      >
                        <option value="">-- Chưa chỉ định --</option>
                        <option value="usr-tech-01">Nguyễn Văn Hùng (Kỹ sư MEP)</option>
                        <option value="usr-cleaner-01">Lê Thị Bích (Nhân viên Vệ sinh A5)</option>
                        <option value="usr-sec-01">Phạm Văn Đạt (Đội An ninh)</option>
                        <option value="usr-sup-01">Trần Thị Mai (Giám sát Vận hành)</option>
                        <option value="usr-mgr-01">Vũ Đức Thịnh (Trưởng BQL)</option>
                      </select>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-slate-500 text-[11px] font-medium">Chuyển bước:</span>
                      <select
                        value={selectedIncident.stage}
                        onChange={(e) => transitionIncidentStage(selectedIncident.id, e.target.value as IncidentStage)}
                        className="p-1.5 bg-blue-50 text-blue-700 font-bold border border-blue-200 rounded-lg text-xs focus:outline-none"
                      >
                        {STAGES.map((s) => (
                          <option key={s} value={s}>
                            {STAGE_LABELS[s]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Stepper */}
                <div className="overflow-x-auto pb-1">
                  <div className="flex items-center gap-1 text-[11px] font-semibold min-w-[580px]">
                    {STAGES.map((s, idx) => {
                      const currentIdx = STAGES.indexOf(selectedIncident.stage);
                      const isPast = idx < currentIdx;
                      const isCurrent = idx === currentIdx;

                      return (
                        <div key={s} className="flex items-center gap-1 flex-1">
                          <div
                            className={`flex-1 py-1.5 px-2 rounded-lg text-center transition-all truncate text-[10px] font-bold ${
                              isCurrent
                                ? 'bg-blue-600 text-white shadow-2xs'
                                : isPast
                                  ? 'bg-blue-50 text-blue-700 border border-blue-100'
                                  : 'bg-slate-100 text-slate-400'
                            }`}
                          >
                            {STAGE_LABELS[s]}
                          </div>
                          {idx < STAGES.length - 1 && (
                            <IconChevronRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Action Bar */}
                <div className="p-3 bg-slate-50/80 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs text-slate-600">
                    Trạng thái hiện tại: <strong className="text-slate-900">{selectedIncident.status === 'CLOSED' ? 'Đã hoàn tất đóng lại' : selectedIncident.status === 'RESOLVED' ? 'Đã xong việc kỹ thuật, chờ cư dân xác nhận' : 'Đang trong quá trình xử lý'}</strong>
                  </div>

                  <div className="flex items-center gap-2">
                    {selectedIncident.status === 'OPEN' && (
                      <button
                        type="button"
                        onClick={handleResolve}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs"
                      >
                        <IconShieldCheck className="w-4 h-4" />
                        <span>Báo cáo hoàn thành sự cố</span>
                      </button>
                    )}

                    {selectedIncident.stage === 'RESIDENT_CONFIRMATION' && (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleResidentConfirmation(true)}
                          className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow-2xs"
                        >
                          <IconCheck className="w-3.5 h-3.5" />
                          <span>Cư dân hài lòng (Đóng sự cố)</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResidentConfirmation(false)}
                          className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow-2xs"
                        >
                          <IconRotateClockwise className="w-3.5 h-3.5" />
                          <span>Cư dân chưa hài lòng (Làm lại)</span>
                        </button>
                      </div>
                    )}

                    {selectedIncident.status === 'CLOSED' && (
                      <span className="px-3 py-1.5 bg-slate-200 text-slate-700 rounded-lg text-xs font-bold flex items-center gap-1">
                        <IconCheck className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Sự cố đã được đóng</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Multi-Tab Detail Section */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-2xs space-y-4">
                {/* Tabs Header */}
                <div className="flex items-center gap-2 border-b border-slate-200">
                  <button
                    type="button"
                    onClick={() => setActiveTab('TASKS')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
                      activeTab === 'TASKS'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <IconListCheck className="w-4 h-4" />
                    <span>Công việc & Phiếu thi công ({relatedTasks.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('MESSAGES')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
                      activeTab === 'MESSAGES'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <IconMessageDots className="w-4 h-4" />
                    <span>Trao đổi nội bộ ({incidentMessages.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('TIMELINE')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
                      activeTab === 'TIMELINE'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <IconHistory className="w-4 h-4" />
                    <span>Nhật ký tiến trình</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('RELATIONS')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors ${
                      activeTab === 'RELATIONS'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <IconLink className="w-4 h-4" />
                    <span>Sự cố liên quan ({incidentRelations.length})</span>
                  </button>
                </div>

                {/* Tab 1: Tasks & WorkOrders */}
                {activeTab === 'TASKS' && (
                  <div className="space-y-4">
                    {/* Tasks */}
                    <div className="space-y-2">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                        Các nhiệm vụ cần làm
                      </span>
                      {relatedTasks.map((t) => (
                        <div
                          key={t.id}
                          className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between"
                        >
                          <div>
                            <div className="flex items-center gap-1.5 font-mono">
                              <span className="font-bold text-blue-600">{t.id}</span>
                              <span className="text-slate-400">•</span>
                              <span className="text-[10px] font-sans font-semibold text-slate-500">
                                {t.domain_type === 'MEP'
                                  ? 'Điện Nước (MEP)'
                                  : t.domain_type === 'SANITATION'
                                    ? 'Vệ sinh môi trường'
                                    : t.domain_type === 'LANDSCAPE'
                                      ? 'Cảnh quan'
                                      : t.domain_type === 'ELEVATOR'
                                        ? 'Thang máy'
                                        : t.domain_type}
                              </span>
                            </div>
                            <p className="font-bold text-slate-800 mt-0.5">{t.title}</p>
                            <p className="text-[11px] text-slate-500">Người phụ trách: {t.assignee_name || 'Chưa giao'}</p>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
                              t.status === 'DONE'
                                ? 'bg-emerald-100 text-emerald-800'
                                : t.status === 'BLOCKED'
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {t.status === 'DONE' ? 'Hoàn thành' : t.status === 'BLOCKED' ? 'Tạm dừng' : 'Đang làm'}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Work Orders */}
                    <div className="space-y-2 pt-2 border-t border-slate-100">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                        Lịch sử các lần thi công thực tế
                      </span>
                      {relatedWorkOrders.map((w) => (
                        <div
                          key={w.id}
                          className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between"
                        >
                          <div>
                            <div className="flex items-center gap-1.5 font-mono">
                              <span className="font-bold text-blue-600">{w.id}</span>
                              <span className="text-slate-400">•</span>
                              <span className="font-sans font-medium text-slate-600">Lần thi công #{w.attempt_no}</span>
                              {w.redo_of_work_order_id && (
                                <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded font-sans">
                                  Làm lại của {w.redo_of_work_order_id}
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-500 mt-0.5">
                              Người làm: {w.executor_name || 'Kỹ thuật'} ({w.executor_phone || '—'})
                            </p>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
                              w.status === 'COMPLETED'
                                ? 'bg-emerald-100 text-emerald-700'
                                : w.status === 'IN_PROGRESS'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-rose-100 text-rose-700'
                            }`}
                          >
                            {w.status === 'COMPLETED' ? 'Đã hoàn thành' : w.status === 'IN_PROGRESS' ? 'Đang thực hiện' : 'Thất bại'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tab 2: Internal Messages */}
                {activeTab === 'MESSAGES' && (
                  <div className="space-y-3">
                    <div className="space-y-2.5 max-h-[360px] overflow-y-auto pr-1">
                      {incidentMessages.map((msg) => (
                        <div key={msg.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-800">{msg.author_name}</span>
                            <span className="text-[10px] text-slate-400">
                              {new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p className="text-slate-700 leading-relaxed">{msg.body}</p>
                        </div>
                      ))}
                    </div>

                    {/* Send Message Form */}
                    <form onSubmit={handleSendMessage} className="flex items-center gap-2 pt-2 border-t border-slate-100">
                      <input
                        value={newMessageText}
                        onChange={(e) => setNewMessageText(e.target.value)}
                        placeholder="Nhập ghi chú hoặc trao đổi nội bộ..."
                        className="flex-1 p-2 bg-white border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-blue-500"
                      />
                      <button
                        type="submit"
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1 transition-colors shadow-2xs shrink-0"
                      >
                        <IconSend className="w-3.5 h-3.5" />
                        <span>Gửi</span>
                      </button>
                    </form>
                  </div>
                )}

                {/* Tab 3: Timeline */}
                {activeTab === 'TIMELINE' && (
                  <div className="space-y-2.5">
                    {incidentEvents.length === 0 ? (
                      <div className="p-8 text-center text-slate-400 text-xs">
                        Chưa có ghi nhận nhật ký nào.
                      </div>
                    ) : (
                      incidentEvents.map((evt) => (
                        <div key={evt.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-start gap-2.5">
                          <div className="w-2 h-2 rounded-full bg-blue-600 mt-1 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-800">
                                {evt.event_type === 'INCIDENT_CREATED'
                                  ? 'Tiếp nhận sự cố mới'
                                  : evt.event_type === 'TRIAGE_COMPLETED'
                                    ? 'Hoàn thành phân loại'
                                    : evt.event_type === 'TASK_ASSIGNED'
                                      ? 'Giao nhiệm vụ hiện trường'
                                      : evt.event_type === 'WORK_ORDER_STARTED'
                                        ? 'Bắt đầu thi công'
                                        : evt.event_type === 'EVIDENCE_UPLOADED'
                                          ? 'Tải lên hình ảnh hiện trường'
                                          : evt.event_type === 'WORK_ORDER_COMPLETED'
                                            ? 'Hoàn thành phiếu thi công'
                                            : evt.event_type === 'QC_INSPECTED'
                                              ? 'Nghiệm thu đạt chuẩn'
                                              : evt.event_type === 'QC_FAILED_REDO_TRIGGERED'
                                                ? 'Nghiệm thu chưa đạt — Tạo phiếu làm lại'
                                                : evt.event_type === 'ACTION_APPROVAL_REQUIRED'
                                                  ? 'Đề xuất phê duyệt chi phí'
                                                  : evt.event_type === 'ACTION_APPROVED'
                                                    ? 'BQL đã phê duyệt chi phí'
                                                    : evt.event_type === 'INCIDENT_RESOLVED'
                                                      ? 'Báo cáo hoàn thành sự cố'
                                                      : evt.event_type}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                {new Date(evt.occurred_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p className="text-slate-500 mt-0.5">
                              Người thực hiện: <strong>{evt.actor_name}</strong>
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Tab 4: Relations */}
                {activeTab === 'RELATIONS' && (
                  <div className="space-y-2">
                    {incidentRelations.length === 0 ? (
                      <div className="p-8 text-center text-slate-400 text-xs">
                        Sự cố này độc lập, không có liên quan đến sự cố nào khác.
                      </div>
                    ) : (
                      incidentRelations.map((rel, idx) => (
                        <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <IconLink className="w-4 h-4 text-blue-600" />
                            <span className="font-bold text-slate-800">
                              {rel.relation_type === 'CAUSED_BY' ? 'Gây ra bởi' : 'Có liên quan đến'}
                            </span>
                            <span className="font-semibold text-blue-600">{rel.target_incident_id}</span>
                          </div>
                          <span className="text-[11px] text-slate-500">{rel.reason}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-2xl border border-slate-200">
              Chọn sự cố bên trái để xem chi tiết.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
