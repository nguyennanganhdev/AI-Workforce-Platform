import { useEffect, useRef, useState } from 'react';
import { IncidentList } from './incident-list';
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
  IconSparkles,
  IconReceipt2,
  IconTool,
  IconHeadset,
  IconUsersGroup,
  IconChecklist,
  IconArrowRight,
  IconCircleCheck,
  IconX,
} from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { IncidentStage } from '../types/incident';
import type { VhSessionMessage } from '../types/session';
import { MOCK_MESSAGES } from '../mock/messages';
import { MOCK_BUSINESS_EVENTS } from '../mock/business-events';
import { MOCK_INCIDENT_RELATIONS } from '../mock/incidents';
import type { VhMessage } from '../types/message';

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

const CHAT_ACTOR_META: Record<
  VhMessage['author_type'],
  { label: string; avatarClass: string; bubbleClass: string }
> = {
  RESIDENT: {
    label: 'Cư dân',
    avatarClass: 'bg-amber-100 text-amber-700',
    bubbleClass: 'border-amber-200 bg-amber-50/70',
  },
  STAFF: {
    label: 'Nhân viên vận hành',
    avatarClass: 'bg-blue-100 text-blue-700',
    bubbleClass: 'border-slate-200 bg-white',
  },
  MANAGER: {
    label: 'Ban quản lý',
    avatarClass: 'bg-slate-800 text-white',
    bubbleClass: 'border-slate-300 bg-slate-50',
  },
  AGENT: {
    label: 'Agent nghiệp vụ',
    avatarClass: 'bg-indigo-100 text-indigo-700',
    bubbleClass: 'border-indigo-200 bg-indigo-50/70',
  },
  SYSTEM: {
    label: 'Hệ thống',
    avatarClass: 'bg-emerald-100 text-emerald-700',
    bubbleClass: 'border-emerald-200 bg-emerald-50/70',
  },
};

function getChatActorCode(message: VhMessage) {
  if (message.author_id.includes('customer-care') || message.author_id.includes('hotline')) return 'A1';
  if (message.author_id.includes('dispatcher')) return 'A0';
  if (message.author_id.includes('technical')) return 'A2';
  if (message.author_type === 'SYSTEM') return 'SYS';
  return message.author_name
    .split(' ')
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
}

export function IncidentsWorkspace() {
  const {
    incidents,
    tasks,
    workOrders,
    assignIncidentOwner,
    transitionIncidentStage,
    resolveIncident,
    residentConfirmIncident,
    coordinationSessions,
    sessionMessages,
    residentConfirmTicket,
    managerApproveAndCloseSession,
    sendSessionMessage,
    createCoordinationSession,
    currentProfile,
    currentPersona,
  } = useOperationsData();

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'COORDINATION' | 'TASKS' | 'MESSAGES' | 'TIMELINE' | 'RELATIONS'>('COORDINATION');
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [newMessageText, setNewMessageText] = useState('');
  const [localMessages, setLocalMessages] = useState(MOCK_MESSAGES);
  const [sessionChatInput, setSessionChatInput] = useState('');
  const [bqlNoteInput, setBqlNoteInput] = useState('');
  const [showBqlModal, setShowBqlModal] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId);

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

  useEffect(() => {
    if (activeTab === 'MESSAGES') {
      chatEndRef.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [activeTab, incidentMessages.length]);

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
      author_type: currentPersona === 'MANAGER' ? 'MANAGER' as const : 'STAFF' as const,
      author_id: currentProfile.id,
      author_name: `${currentProfile.name} (${currentProfile.roleTitle})`,
      author_avatar: currentProfile.avatarUrl,
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
              {selectedIncident ? 'Chi tiết sự cố' : 'Quản lý sự cố'}
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

      <div hidden={Boolean(selectedIncidentId)}>
        <IncidentList incidents={incidents} onSelect={(id) => {
          setSelectedIncidentId(id);
          setActiveTab('TASKS');
          setResolveError(null);
          setActionSuccess(null);
          setSessionChatInput('');
          setNewMessageText('');
          setBqlNoteInput('');
          setShowBqlModal(false);
        }} />
      </div>
      {selectedIncidentId && <div className="space-y-4">
        <button type="button" className="rounded border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" onClick={() => {
          setSelectedIncidentId('');
          setResolveError(null);
          setActionSuccess(null);
        }}>Quay lại danh sách</button>
        <div className="space-y-4">
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
                <div className="flex items-center gap-2 border-b border-slate-200 overflow-x-auto">
                  <button
                    type="button"
                    onClick={() => setActiveTab('COORDINATION')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors shrink-0 ${
                      activeTab === 'COORDINATION'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <IconSparkles className="w-4 h-4 text-indigo-600" />
                    <span>Điều phối</span>
                    {coordinationSessions.some((s) => s.incident_id === selectedIncident?.id) && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded">
                        Có phiên điều phối
                      </span>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab('TASKS')}
                    className={`pb-2.5 text-xs font-bold border-b-2 flex items-center gap-1.5 transition-colors shrink-0 ${
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
                    <span>Lịch sử xử lý</span>
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

                {/* Tab 0: Multi-Agent Coordination Session */}
                {activeTab === 'COORDINATION' && (() => {
                  const currentSession = coordinationSessions.find(
                    (s) => s.incident_id === selectedIncident?.id || s.work_order_id === relatedWorkOrders[0]?.id,
                  );
                  const sessionMsgs = currentSession
                    ? sessionMessages.filter((m) => m.session_id === currentSession.id)
                    : [];

                  if (!currentSession) {
                    return (
                      <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200/80 space-y-3">
                        <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
                          <IconSparkles className="w-6 h-6" />
                        </div>
                        <div>
                          <h4 className="font-bold text-slate-800 text-sm">Chưa có phiên điều phối</h4>
                          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                            Sự cố này chưa có phiên phối hợp giữa các trợ lý tự động và nhân viên kỹ thuật.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            if (selectedIncident) {
                              const newSes = createCoordinationSession({
                                incidentId: selectedIncident.id,
                                title: selectedIncident.title,
                              });
                              setActionSuccess(`Đã khởi tạo phiên điều phối ${newSes.id}!`);
                              setTimeout(() => setActionSuccess(null), 3000);
                            }
                          }}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-2xs inline-flex items-center gap-2"
                        >
                          <IconSparkles className="w-4 h-4" />
                          <span>Mở phiên điều phối</span>
                        </button>
                      </div>
                    );
                  }

                  const quotation = currentSession.quotation;

                  return (
                    <div className="space-y-5">
                      {/* Session Info Bar */}
                      <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-50/80 via-blue-50/40 to-slate-50 border border-indigo-200/70 flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-2xs">
                            <IconUsersGroup className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-xs text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                                {currentSession.id}
                              </span>
                              <span className="text-xs font-bold text-slate-800">
                                Phòng: {selectedIncident?.location_json.areaCode || 'P.1206'} (Tòa {selectedIncident?.location_json.towerCode || 'S2.01'})
                              </span>
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                  currentSession.status === 'CLOSED'
                                    ? 'bg-slate-200 text-slate-700'
                                    : currentSession.status === 'RESIDENT_CONFIRMED'
                                      ? 'bg-purple-100 text-purple-700'
                                      : currentSession.status === 'EXECUTING'
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'bg-emerald-100 text-emerald-700'
                                }`}
                              >
                                {currentSession.status === 'CLOSED'
                                  ? 'Đã đóng phiên điều phối'
                                  : currentSession.status === 'RESIDENT_CONFIRMED'
                                    ? 'Chờ BQL duyệt đóng'
                                    : currentSession.status === 'EXECUTING'
                                      ? 'Đang thi công sửa chữa'
                                      : 'Đang điều phối'}
                              </span>
                            </div>
                            <p className="text-xs text-slate-500 mt-1">
                              Cư dân: <strong>Nguyễn Thu Trang (0912.345.678)</strong> • KTV phụ trách: <strong>Nguyễn Văn Hùng (Kỹ sư MEP)</strong>
                            </p>
                          </div>
                        </div>

                        {/* Quick action simulation */}
                        <div className="flex flex-wrap items-center gap-2">
                          {currentSession.resident_ticket_status !== 'DONE' && currentSession.status !== 'CLOSED' && (
                            <button
                              type="button"
                              onClick={() => {
                                residentConfirmTicket(currentSession.id);
                                setActionSuccess('Cư dân đã xác nhận hoàn thành yêu cầu! Cuộc trò chuyện với cư dân đã đóng.');
                                setTimeout(() => setActionSuccess(null), 3500);
                              }}
                              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
                            >
                              <IconCheck className="w-3.5 h-3.5" />
                              <span>[Mô phỏng] Cư dân xác nhận hoàn thành</span>
                            </button>
                          )}

                          {currentSession.status !== 'CLOSED' && (
                            <button
                              type="button"
                              onClick={() => setShowBqlModal(true)}
                              className="px-3 py-1.5 bg-slate-900 hover:bg-black text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
                            >
                              <IconShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                              <span>Ban quản lý phê duyệt và đóng phiên</span>
                            </button>
                          )}

                          {currentSession.status === 'CLOSED' && (
                            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 bg-white/80 px-3 py-1.5 rounded-lg border border-slate-200">
                              <IconCheck className="w-4 h-4 text-emerald-600" />
                              <span>Đã lưu trữ hồ sơ ({currentSession.bql_approved_by})</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* 6-Step Visual Workflow */}
                      <div className="bg-slate-50/70 p-3.5 rounded-xl border border-slate-200">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
                          Tiến trình phối hợp xử lý
                        </span>
                        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-center text-xs">
                          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800">
                            <span className="text-[10px] font-bold block text-emerald-600">Bước 1</span>
                            <span className="font-bold text-[11px] block mt-0.5">CSKH xác nhận</span>
                            <span className="text-[10px] text-emerald-600">Đã chốt P.1206</span>
                          </div>

                          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800">
                            <span className="text-[10px] font-bold block text-emerald-600">Bước 2</span>
                            <span className="font-bold text-[11px] block mt-0.5">Giám sát mở phiên</span>
                            <span className="text-[10px] text-emerald-600">Đã mở phiên</span>
                          </div>

                          <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800">
                            <span className="text-[10px] font-bold block text-emerald-600">Bước 3</span>
                            <span className="font-bold text-[11px] block mt-0.5">Phối hợp kỹ thuật và báo cáo</span>
                            <span className="text-[10px] text-emerald-600">Đã giao KTV Hùng</span>
                          </div>

                          <div
                            className={`p-2 rounded-lg border ${
                              quotation?.resident_approved
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                : 'bg-amber-50 border-amber-200 text-amber-800'
                            }`}
                          >
                            <span className="text-[10px] font-bold block text-slate-400">Bước 4</span>
                            <span className="font-bold text-[11px] block mt-0.5">Báo giá & Duyệt giá</span>
                            <span className="text-[10px] font-semibold">
                              {quotation ? `Đã duyệt ${quotation.total_amount.toLocaleString('vi-VN')}đ` : 'Chờ KTV gửi'}
                            </span>
                          </div>

                          <div
                            className={`p-2 rounded-lg border ${
                              currentSession.resident_ticket_status === 'DONE'
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                : 'bg-slate-100 border-slate-200 text-slate-600'
                            }`}
                          >
                            <span className="text-[10px] font-bold block text-slate-400">Bước 5</span>
                            <span className="font-bold text-[11px] block mt-0.5">Cư dân xác nhận hoàn thành</span>
                            <span className="text-[10px] font-semibold">
                              {currentSession.resident_ticket_status === 'DONE' ? 'Đã đóng trao đổi' : 'Đang xử lý'}
                            </span>
                          </div>

                          <div
                            className={`p-2 rounded-lg border ${
                              currentSession.status === 'CLOSED'
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                : 'bg-slate-100 border-slate-200 text-slate-600'
                            }`}
                          >
                            <span className="text-[10px] font-bold block text-slate-400">Bước 6</span>
                            <span className="font-bold text-[11px] block mt-0.5">Ban quản lý đóng phiên</span>
                            <span className="text-[10px] font-semibold">
                              {currentSession.status === 'CLOSED' ? 'Đã đóng' : 'Chờ duyệt'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Embedded Quotation Invoice Widget if available */}
                      {quotation && (
                        <div className="p-4 bg-white rounded-xl border border-blue-200 shadow-2xs space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="p-1.5 bg-blue-100 text-blue-700 rounded-lg">
                                <IconReceipt2 className="w-4 h-4" />
                              </span>
                              <div>
                                <span className="font-bold text-slate-900 text-xs">
                                  Hóa Đơn Báo Giá Vật Tư (#{quotation.invoice_code})
                                </span>
                                <span className="text-[11px] text-slate-500 block">
                                  Lập bởi: {quotation.created_by_agent} • Bảo hành: {quotation.warranty_months} tháng
                                </span>
                              </div>
                            </div>
                            <span className="text-xs font-bold px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full flex items-center gap-1">
                              <IconCheck className="w-3.5 h-3.5" /> Cư dân đã xem và đồng ý báo giá
                            </span>
                          </div>

                          <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs">
                              <thead className="bg-slate-50 text-slate-500 text-[11px]">
                                <tr>
                                  <th className="p-2">Hạng mục vật tư</th>
                                  <th className="p-2 text-center">Số lượng</th>
                                  <th className="p-2 text-center">ĐVT</th>
                                  <th className="p-2 text-right">Đơn giá</th>
                                  <th className="p-2 text-right">Thành tiền</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {quotation.items.map((it) => (
                                  <tr key={it.id}>
                                    <td className="p-2 font-medium text-slate-800">{it.part_name}</td>
                                    <td className="p-2 text-center">{it.quantity}</td>
                                    <td className="p-2 text-center text-slate-500">{it.unit}</td>
                                    <td className="p-2 text-right">{it.unit_price.toLocaleString('vi-VN')} đ</td>
                                    <td className="p-2 text-right font-semibold">{it.amount.toLocaleString('vi-VN')} đ</td>
                                  </tr>
                                ))}
                                <tr>
                                  <td colSpan={4} className="p-2 text-right text-slate-500 font-medium">
                                    Tiền công kỹ thuật & kiểm tra áp lực:
                                  </td>
                                  <td className="p-2 text-right font-semibold">
                                    {quotation.labor_cost.toLocaleString('vi-VN')} đ
                                  </td>
                                </tr>
                                <tr className="bg-blue-50/60 font-bold text-blue-900">
                                  <td colSpan={4} className="p-2 text-right">
                                    TỔNG CHI PHÍ HÓA ĐƠN:
                                  </td>
                                  <td className="p-2 text-right text-sm text-blue-700">
                                    {quotation.total_amount.toLocaleString('vi-VN')} đ
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Groupchat Multi-Agent Messages Stream */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                            <IconMessageDots className="w-4 h-4 text-indigo-600" />
                            Hội Thoại Group Chat Điều Phối Đa Tác Nhân ({sessionMsgs.length} tin nhắn)
                          </span>
                          <span className="text-[10px] text-slate-400">
                            Tự động đồng bộ các kênh CSKH, Kỹ thuật, Kế toán & Ban Quản Lý
                          </span>
                        </div>

                        <div className="space-y-2.5 max-h-[460px] overflow-y-auto p-3.5 bg-slate-50/60 rounded-xl border border-slate-200">
                          {sessionMsgs.map((msg) => {
                            const isAgent = msg.sender_type.startsWith('AGENT');
                            const isCSKH = msg.sender_type === 'AGENT_CSKH';
                            const isDispatcher = msg.sender_type === 'AGENT_DISPATCHER';
                            const isTech = msg.sender_type === 'AGENT_TECHNICAL';
                            const isBilling = msg.sender_type === 'AGENT_BILLING';
                            const isManager = msg.sender_type === 'HUMAN_MANAGER';

                            const badgeColor = isCSKH
                              ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                              : isDispatcher
                                ? 'bg-purple-100 text-purple-800 border-purple-200'
                                : isTech
                                  ? 'bg-blue-100 text-blue-800 border-blue-200'
                                  : isBilling
                                    ? 'bg-amber-100 text-amber-800 border-amber-200'
                                    : isManager
                                      ? 'bg-slate-800 text-white border-slate-700'
                                      : 'bg-orange-100 text-orange-800 border-orange-200';

                            return (
                              <div
                                key={msg.id}
                                className={`p-3 rounded-xl border text-xs space-y-1.5 transition-all ${
                                  isAgent ? 'bg-white border-slate-200/90 shadow-2xs' : 'bg-white border-orange-200/80 shadow-2xs'
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md border flex items-center gap-1 ${badgeColor}`}
                                    >
                                      {isCSKH && <IconHeadset className="w-3 h-3" />}
                                      {isDispatcher && <IconSparkles className="w-3 h-3" />}
                                      {isTech && <IconTool className="w-3 h-3" />}
                                      {isBilling && <IconReceipt2 className="w-3 h-3" />}
                                      {isManager && <IconBuilding className="w-3 h-3" />}
                                      {!isAgent && !isManager && <IconUser className="w-3 h-3" />}
                                      {msg.sender_name}
                                    </span>

                                    {msg.action_type && (
                                      <span className="font-mono text-[9px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-semibold">
                                        {msg.action_type}
                                      </span>
                                    )}
                                  </div>

                                  <span className="text-[10px] text-slate-400">
                                    {new Date(msg.created_at).toLocaleTimeString('vi-VN', {
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })}
                                  </span>
                                </div>

                                <p className="text-slate-800 text-xs leading-relaxed whitespace-pre-wrap pl-1">
                                  {msg.content}
                                </p>
                              </div>
                            );
                          })}
                        </div>

                        {/* Send Message Input */}
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            if (!sessionChatInput.trim()) return;
                            sendSessionMessage(currentSession.id, sessionChatInput.trim());
                            setSessionChatInput('');
                          }}
                          className="flex items-center gap-2 pt-1"
                        >
                          <input
                            type="text"
                            value={sessionChatInput}
                            onChange={(e) => setSessionChatInput(e.target.value)}
                            placeholder={`Gửi phản hồi vào phiên điều phối (với tư cách ${currentProfile.name})...`}
                            className="flex-1 p-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:outline-none"
                          />
                          <button
                            type="submit"
                            disabled={!sessionChatInput.trim()}
                            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors shrink-0"
                          >
                            <IconSend className="w-3.5 h-3.5" />
                            <span>Gửi</span>
                          </button>
                        </form>
                      </div>

                      {/* Modal Ban quản lý phê duyệt đóng phiên */}
                      {showBqlModal && (
                        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
                          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-slate-200">
                            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                              <div className="flex items-center gap-2">
                                <span className="p-1.5 bg-slate-900 text-white rounded-lg">
                                  <IconShieldCheck className="w-4 h-4" />
                                </span>
                                <h4 className="font-bold text-slate-900 text-sm">Ban quản lý phê duyệt đóng phiên</h4>
                              </div>
                              <button
                                type="button"
                                onClick={() => setShowBqlModal(false)}
                                className="text-slate-400 hover:text-slate-600 p-1"
                              >
                                <IconX className="w-4 h-4" />
                              </button>
                            </div>

                            <p className="text-xs text-slate-600 leading-relaxed">
                              Ban Quản Lý xác nhận: KTV đã hoàn thành thi công, ảnh nghiệm thu đã đạt chuẩn, cư dân đã bấm <strong>Hoàn thành</strong> trên yêu cầu và cuộc trò chuyện cư dân đã đóng.
                            </p>

                            <div className="space-y-1.5">
                              <label className="text-xs font-bold text-slate-700 block">
                                Ghi chú phê duyệt của Ban Quản Lý:
                              </label>
                              <textarea
                                rows={3}
                                value={bqlNoteInput}
                                onChange={(e) => setBqlNoteInput(e.target.value)}
                                placeholder="VD: Đã nghiệm thu hiện trường đạt tiêu chuẩn. Chi phí vật tư đúng định mức..."
                                className="w-full p-2.5 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                              />
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2">
                              <button
                                type="button"
                                onClick={() => setShowBqlModal(false)}
                                className="px-3.5 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                              >
                                Hủy bỏ
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  managerApproveAndCloseSession(currentSession.id, bqlNoteInput);
                                  setShowBqlModal(false);
                                  setActionSuccess(`Đã phê duyệt và đóng phiên điều phối ${currentSession.id} thành công!`);
                                  setTimeout(() => setActionSuccess(null), 3500);
                                }}
                                className="px-4 py-2 bg-slate-900 hover:bg-black text-white rounded-xl text-xs font-bold shadow-2xs"
                              >
                                Xác nhận duyệt và đóng phiên
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

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
                  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50/80 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white">
                            <IconMessageDots className="h-4 w-4" />
                          </span>
                          <div>
                            <h3 className="text-sm font-bold text-slate-900">Phòng trao đổi xử lý sự cố</h3>
                            <p className="text-[11px] text-slate-500">Trao đổi nội bộ giữa agent, điều phối và nhân viên hiện trường</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-bold">
                        <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-slate-600">A1 · CSKH</span>
                        <IconArrowRight className="h-3 w-3 text-slate-300" />
                        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-1 text-indigo-700">A0 · Điều phối</span>
                        <IconArrowRight className="h-3 w-3 text-slate-300" />
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 text-blue-700">A2 · Kỹ thuật</span>
                        <IconArrowRight className="h-3 w-3 text-slate-300" />
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-700">Nhân viên</span>
                      </div>
                    </div>

                    <div className="max-h-[470px] space-y-4 overflow-y-auto bg-slate-50/30 px-3 py-4 sm:px-5">
                      <div className="flex items-center gap-3 text-[10px] font-medium text-slate-400">
                        <span className="h-px flex-1 bg-slate-200" />
                        <span>{selectedIncident?.id} · Luồng xử lý nội bộ</span>
                        <span className="h-px flex-1 bg-slate-200" />
                      </div>

                      {incidentMessages.map((msg) => {
                        const isCurrentUser = msg.author_id === currentProfile.id;
                        const meta = CHAT_ACTOR_META[msg.author_type];
                        const actorCode = getChatActorCode(msg);

                        return (
                          <div key={msg.id} className={`flex items-start gap-2.5 ${isCurrentUser ? 'flex-row-reverse' : ''}`}>
                            {msg.author_avatar ? (
                              <img
                                src={msg.author_avatar}
                                alt=""
                                className="h-9 w-9 shrink-0 rounded-xl border border-white object-cover shadow-sm"
                              />
                            ) : (
                              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-extrabold ${meta.avatarClass}`}>
                                {actorCode}
                              </span>
                            )}

                            <div className={`min-w-0 max-w-[88%] sm:max-w-[76%] ${isCurrentUser ? 'text-right' : ''}`}>
                              <div className={`mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 ${isCurrentUser ? 'justify-end' : ''}`}>
                                <span className="text-xs font-bold text-slate-900">{msg.author_name}</span>
                                <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${meta.avatarClass}`}>
                                  {actorCode} · {meta.label}
                                </span>
                                <time className="text-[10px] text-slate-400">
                                  {new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                                </time>
                              </div>
                              <div className={`rounded-2xl border px-3.5 py-2.5 text-left text-xs leading-relaxed text-slate-700 shadow-xs ${
                                isCurrentUser
                                  ? 'rounded-tr-sm border-blue-600 bg-blue-600 text-white'
                                  : `rounded-tl-sm ${meta.bubbleClass}`
                              }`}>
                                {msg.body}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                      <div ref={chatEndRef} />
                    </div>

                    {/* Send Message Form */}
                    <form onSubmit={handleSendMessage} className="flex items-end gap-2 border-t border-slate-200 bg-white p-3 sm:p-4">
                      <span className="hidden h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-blue-50 sm:flex">
                        {currentProfile.avatarUrl ? (
                          <img src={currentProfile.avatarUrl} alt="" className="h-full w-full object-cover" />
                        ) : (
                          <IconUser className="h-4 w-4 text-blue-600" />
                        )}
                      </span>
                      <div className="flex-1">
                        <label htmlFor="incident-internal-message" className="mb-1 block text-[10px] font-semibold text-slate-500">
                          Gửi với tư cách {currentProfile.name}
                        </label>
                        <input
                          id="incident-internal-message"
                          value={newMessageText}
                          onChange={(e) => setNewMessageText(e.target.value)}
                          placeholder="Nhập nội dung trao đổi hoặc @ tên người cần phối hợp..."
                          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/10"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={!newMessageText.trim()}
                        className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-4 text-xs font-bold text-white shadow-2xs transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <IconSend className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Gửi</span>
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
              Không tìm thấy sự cố. Vui lòng quay lại danh sách.
            </div>
          )}
        </div>
      </div>}
    </div>
  );
}
