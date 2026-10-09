import { useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { IncidentList } from './incident-list';
import { PanelTitle } from './ops-ui';
import { Banner } from './technician/ui';
import { BqlInbox, useBqlInboxItems } from './bql-inbox';
import { IconSend, IconX, IconChevronLeft } from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { IncidentStage } from '../types/incident';
import type { VhSessionMessage } from '../types/session';
import { MOCK_MESSAGES } from '../mock/messages';
import { MOCK_BUSINESS_EVENTS } from '../mock/business-events';
import { MOCK_INCIDENT_RELATIONS } from '../mock/incidents';
import type { VhMessage } from '../types/message';

type ListTab = 'INBOX' | 'OPEN' | 'CLOSED';
const LIST_TABS: Array<{ id: ListTab; label: string }> = [
  { id: 'INBOX', label: 'Cần BQL xử lý (minh họa)' },
  { id: 'OPEN', label: 'Đang xử lý (minh họa)' },
  { id: 'CLOSED', label: 'Đã đóng (minh họa)' },
];

const STAGE_LABELS: Record<IncidentStage, string> = {
  INTAKE: '1. Tiếp nhận',
  TRIAGE: '2. Phân loại',
  PLANNING: '3. Lên phương án',
  EXECUTION: '4. Đang sửa chữa',
  QC: '5. Nghiệm thu',
  RESIDENT_CONFIRMATION: '6. Cư dân xác nhận',
};

const CATEGORY_LABELS: Record<string, string> = {
  MEP_PLUMBING: 'Kỹ thuật cấp thoát nước',
  SANITATION_A5: 'Vệ sinh môi trường A5',
  ELEVATOR: 'Hệ thống thang máy',
  ELECTRICAL: 'Kỹ thuật điện chiếu sáng',
  CIVIL: 'Xây dựng hoàn thiện',
};

const NO_OWNER = 'NONE';
const OWNER_ITEMS: Record<string, string> = {
  [NO_OWNER]: 'Chưa chỉ định',
  'usr-tech-01': 'Nguyễn Văn Hùng (Kỹ sư MEP)',
  'usr-cleaner-01': 'Lê Thị Bích (Nhân viên vệ sinh A5)',
  'usr-sec-01': 'Phạm Văn Đạt (Đội an ninh)',
  'usr-sup-01': 'Trần Thị Mai (Giám sát vận hành)',
  'usr-mgr-01': 'Vũ Đức Thịnh (Trưởng BQL)',
};

type DetailTab = 'COORDINATION' | 'TASKS' | 'MESSAGES' | 'TIMELINE' | 'RELATIONS';

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
    avatarClass: 'bg-muted/60 text-slate-700',
    bubbleClass: 'border-border bg-muted/60',
  },
  STAFF: {
    label: 'Nhân viên vận hành',
    avatarClass: 'bg-muted/60 text-foreground',
    bubbleClass: 'border-slate-200 bg-white',
  },
  MANAGER: {
    label: 'Ban quản lý',
    avatarClass: 'bg-slate-100 text-white',
    bubbleClass: 'border-slate-300 bg-slate-50',
  },
  AGENT: {
    label: 'Agent nghiệp vụ',
    avatarClass: 'bg-muted/60 text-slate-700',
    bubbleClass: 'border-border bg-muted/60',
  },
  SYSTEM: {
    label: 'Hệ thống',
    avatarClass: 'bg-muted/60 text-slate-700',
    bubbleClass: 'border-border bg-muted/60',
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
  const [activeTab, setActiveTab] = useState<DetailTab>('COORDINATION');
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [newMessageText, setNewMessageText] = useState('');
  const [localMessages, setLocalMessages] = useState(MOCK_MESSAGES);
  const [sessionChatInput, setSessionChatInput] = useState('');
  const [bqlNoteInput, setBqlNoteInput] = useState('');
  const [showBqlModal, setShowBqlModal] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const selectedIncident = incidents.find((i) => i.id === selectedIncidentId);

  // Gộp "Tiếp nhận phản ánh" + "Quản lý sự cố": hộp việc BQL + danh sách theo trạng thái
  const [listTab, setListTab] = useState<ListTab>('INBOX');
  const inboxItems = useBqlInboxItems();
  const openIncidents = incidents.filter((i) => i.status !== 'CLOSED');
  const closedIncidents = incidents.filter((i) => i.status === 'CLOSED');

  const openIncident = (id: string) => {
    setSelectedIncidentId(id);
    setActiveTab('TASKS');
    setResolveError(null);
    setActionSuccess(null);
    setSessionChatInput('');
    setNewMessageText('');
    setBqlNoteInput('');
    setShowBqlModal(false);
  };

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
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="flex min-w-0 flex-col gap-1">
          <PanelTitle>{selectedIncident ? 'Chi tiết sự cố' : 'Phản ánh & Sự cố'}</PanelTitle>
          <p className="pl-3.5 text-sm text-muted-foreground">AI tiếp nhận và giao việc. BQL chỉ cần xử lý các mục AI chuyển lên.</p>
        </div>
        <p className="shrink-0 pl-3.5 text-sm text-muted-foreground tabular-nums sm:pl-0">{incidents.length} sự cố minh họa</p>
      </div>

      {actionSuccess && <Banner kind="success" onClose={() => setActionSuccess(null)}>{actionSuccess}</Banner>}
      {resolveError && <Banner kind="error" onClose={() => setResolveError(null)}>{resolveError}</Banner>}

      {!selectedIncidentId && (
        <Tabs value={listTab} onValueChange={(v) => setListTab(v as ListTab)} className="gap-4">
          <TabsList variant="line" aria-label="Nhóm sự cố" className="ops-scroll-tabs h-auto w-full justify-start border-b pb-1">
            {LIST_TABS.map((t) => {
              const count = t.id === 'INBOX' ? inboxItems.length : t.id === 'OPEN' ? openIncidents.length : closedIncidents.length;
              return (
                <TabsTrigger key={t.id} value={t.id} className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                  {t.label}
                  {count !== null && <span className="text-xs font-normal tabular-nums text-muted-foreground">{count}</span>}
                </TabsTrigger>
              );
            })}
          </TabsList>
          <TabsContent value="INBOX"><BqlInbox onOpenIncident={openIncident} /></TabsContent>
          <TabsContent value="OPEN"><IncidentList incidents={openIncidents} onSelect={openIncident} /></TabsContent>
          <TabsContent value="CLOSED"><IncidentList incidents={closedIncidents} onSelect={openIncident} /></TabsContent>
        </Tabs>
      )}
      {selectedIncidentId && <div className="flex flex-col gap-4">
        <Button
          variant="ghost"
          className="-ml-2 self-start text-muted-foreground"
          onClick={() => {
            setSelectedIncidentId('');
            setResolveError(null);
            setActionSuccess(null);
          }}
        >
          <IconChevronLeft data-icon="inline-start" /> Quay lại danh sách
        </Button>
        <div className="flex flex-col gap-4">
          {selectedIncident ? (
            <>
              {/* Header & Stepper */}
              <Card className="gap-4">
                <CardHeader className="gap-1 px-4 md:px-6">
                  <CardDescription className="tabular-nums">
                    {selectedIncident.id} · {CATEGORY_LABELS[selectedIncident.category] || selectedIncident.category}
                  </CardDescription>
                  <CardTitle className="text-base font-semibold leading-snug md:text-lg">{selectedIncident.title}</CardTitle>
                  <CardDescription>
                    Tòa {selectedIncident.location_json.towerCode} · Tầng {selectedIncident.location_json.floor || '-'} · {selectedIncident.location_json.areaCode || selectedIncident.location_json.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4 px-4 md:px-6">
                  <FieldGroup className="grid gap-3 sm:grid-cols-2 lg:max-w-2xl">
                    <Field>
                      <FieldLabel htmlFor="incident-owner">Chủ trì</FieldLabel>
                      <Select
                        items={OWNER_ITEMS}
                        value={selectedIncident.owner_user_id || NO_OWNER}
                        onValueChange={(v) => assignIncidentOwner(selectedIncident.id, v === NO_OWNER ? '' : String(v))}
                      >
                        <SelectTrigger id="incident-owner" className="w-full data-[size=default]:h-10"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {Object.entries(OWNER_ITEMS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="incident-stage">Chuyển bước</FieldLabel>
                      <Select
                        items={STAGE_LABELS}
                        value={selectedIncident.stage}
                        onValueChange={(v) => v && transitionIncidentStage(selectedIncident.id, v as IncidentStage)}
                      >
                        <SelectTrigger id="incident-stage" className="w-full data-[size=default]:h-10"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {STAGES.map((st) => <SelectItem key={st} value={st}>{STAGE_LABELS[st]}</SelectItem>)}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                  </FieldGroup>

                  {/* Stepper */}
                  <ol className="ops-scroll-tabs flex gap-1.5 pb-1" aria-label="Tiến trình sự cố">
                    {STAGES.map((st, idx) => {
                      const currentIdx = STAGES.indexOf(selectedIncident.stage);
                      return (
                        <li key={st} className="flex min-w-24 flex-1 flex-col gap-1.5" aria-current={idx === currentIdx ? 'step' : undefined}>
                          <div className={cn('h-1 rounded-full', idx <= currentIdx ? 'bg-primary' : 'bg-muted')} />
                          <span className={cn('truncate text-xs', idx === currentIdx ? 'font-medium text-foreground' : idx < currentIdx ? 'text-slate-600' : 'text-muted-foreground')}>
                            {STAGE_LABELS[st]}
                          </span>
                        </li>
                      );
                    })}
                  </ol>

                  {/* Action Bar */}
                  <div className="flex flex-col gap-3 rounded-lg border bg-muted/40 p-3 lg:flex-row lg:items-center lg:justify-between">
                    <p className="text-sm text-muted-foreground">
                      Trạng thái: <span className="font-medium text-foreground">{selectedIncident.status === 'CLOSED' ? 'Đã hoàn tất, đóng lại' : selectedIncident.status === 'RESOLVED' ? 'Xong việc kỹ thuật, chờ cư dân xác nhận' : 'Đang xử lý'}</span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {selectedIncident.status === 'OPEN' && (
                        <Button size="lg" onClick={handleResolve}>Báo cáo hoàn thành sự cố</Button>
                      )}
                      {selectedIncident.stage === 'RESIDENT_CONFIRMATION' && (
                        <>
                          <Button size="lg" onClick={() => handleResidentConfirmation(true)}>Cư dân hài lòng, đóng sự cố</Button>
                          <Button size="lg" variant="outline" onClick={() => handleResidentConfirmation(false)}>Cư dân chưa hài lòng, làm lại</Button>
                        </>
                      )}
                      {selectedIncident.status === 'CLOSED' && <Badge variant="secondary">Sự cố đã được đóng</Badge>}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Multi-Tab Detail Section */}
              <div className="bg-white rounded-2xl border border-slate-200/80 p-3.5 sm:p-5 shadow-2xs flex flex-col gap-4">
                <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as DetailTab)}>
                  <TabsList variant="line" aria-label="Thông tin sự cố" className="ops-scroll-tabs h-auto w-full justify-start border-b pb-1">
                    <TabsTrigger value="COORDINATION" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                      Điều phối
                      {coordinationSessions.some((cs) => cs.incident_id === selectedIncident?.id) && (
                        <span className="text-xs font-normal text-muted-foreground">(có phiên)</span>
                      )}
                    </TabsTrigger>
                    <TabsTrigger value="TASKS" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                      Công việc & phiếu thi công <span className="text-xs font-normal tabular-nums text-muted-foreground">{relatedTasks.length}</span>
                    </TabsTrigger>
                    <TabsTrigger value="MESSAGES" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                      Trao đổi nội bộ <span className="text-xs font-normal tabular-nums text-muted-foreground">{incidentMessages.length}</span>
                    </TabsTrigger>
                    <TabsTrigger value="TIMELINE" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                      Lịch sử xử lý
                    </TabsTrigger>
                    <TabsTrigger value="RELATIONS" className="h-9 flex-none px-3 data-active:text-primary after:bg-primary">
                      Sự cố liên quan <span className="text-xs font-normal tabular-nums text-muted-foreground">{incidentRelations.length}</span>
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

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
                      <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200/80 flex flex-col gap-3">
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
                          className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl text-xs font-bold shadow-2xs inline-flex items-center gap-2"
                        >
                          
                          <span>Mở phiên điều phối</span>
                        </button>
                      </div>
                    );
                  }

                  const quotation = currentSession.quotation;

                  return (
                    <div className="flex flex-col gap-5">
                      {/* Session Info Bar */}
                      <div className="p-4 rounded-xl border border-border flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-xs text-slate-700 bg-white px-2 py-0.5 rounded border border-border">
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
                                      ? 'bg-muted/60 text-slate-700'
                                      : currentSession.status === 'EXECUTING'
                                        ? 'bg-muted/60 text-foreground'
                                        : 'bg-muted/60 text-slate-700'
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
                              className="px-3 py-1.5 bg-primary hover:bg-primary/90 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
                            >
                              
                              <span>[Mô phỏng] Cư dân xác nhận hoàn thành</span>
                            </button>
                          )}

                          {currentSession.status !== 'CLOSED' && (
                            <button
                              type="button"
                              onClick={() => setShowBqlModal(true)}
                              className="px-3 py-1.5 bg-primary hover:bg-primary/90 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
                            >
                              
                              <span>Ban quản lý phê duyệt và đóng phiên</span>
                            </button>
                          )}

                          {currentSession.status === 'CLOSED' && (
                            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 bg-white/80 px-3 py-1.5 rounded-lg border border-slate-200">
                              
                              <span>Đã lưu trữ hồ sơ ({currentSession.bql_approved_by})</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* 6-Step Visual Workflow */}
                      <div className="bg-slate-50/70 p-3.5 rounded-xl border border-slate-200">
                        <span className="text-[10px] font-bold text-slate-400 block mb-2">
                          Tiến trình phối hợp xử lý
                        </span>
                        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-center text-xs">
                          <div className="p-2 rounded-lg bg-muted/60 border border-border text-slate-700">
                            <span className="text-[10px] font-bold block text-slate-700">Bước 1</span>
                            <span className="font-bold text-[11px] block mt-0.5">CSKH xác nhận</span>
                            <span className="text-[10px] text-slate-700">Đã chốt P.1206</span>
                          </div>

                          <div className="p-2 rounded-lg bg-muted/60 border border-border text-slate-700">
                            <span className="text-[10px] font-bold block text-slate-700">Bước 2</span>
                            <span className="font-bold text-[11px] block mt-0.5">Giám sát mở phiên</span>
                            <span className="text-[10px] text-slate-700">Đã mở phiên</span>
                          </div>

                          <div className="p-2 rounded-lg bg-muted/60 border border-border text-slate-700">
                            <span className="text-[10px] font-bold block text-slate-700">Bước 3</span>
                            <span className="font-bold text-[11px] block mt-0.5">Phối hợp kỹ thuật và báo cáo</span>
                            <span className="text-[10px] text-slate-700">Đã giao KTV Hùng</span>
                          </div>

                          <div
                            className={`p-2 rounded-lg border ${
                              quotation?.resident_approved
                                ? 'bg-muted/60 border-border text-slate-700'
                                : 'bg-muted/60 border-border text-slate-700'
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
                                ? 'bg-muted/60 border-border text-slate-700'
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
                                ? 'bg-muted/60 border-border text-slate-700'
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
                        <div className="p-4 bg-white rounded-xl border border-border shadow-2xs flex flex-col gap-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div>
                                <span className="font-bold text-slate-900 text-xs">
                                  Hóa Đơn Báo Giá Vật Tư (#{quotation.invoice_code})
                                </span>
                                <span className="text-[11px] text-slate-500 block">
                                  Lập bởi: {quotation.created_by_agent} • Bảo hành: {quotation.warranty_months} tháng
                                </span>
                              </div>
                            </div>
                            <span className="text-xs font-bold px-2.5 py-1 bg-muted/60 text-slate-700 rounded-full flex items-center gap-1">
                              Cư dân đã xem và đồng ý báo giá
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
                                <tr className="bg-muted/60 font-bold text-foreground">
                                  <td colSpan={4} className="p-2 text-right">
                                    TỔNG CHI PHÍ HÓA ĐƠN:
                                  </td>
                                  <td className="p-2 text-right text-sm text-foreground">
                                    {quotation.total_amount.toLocaleString('vi-VN')} đ
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Groupchat Multi-Agent Messages Stream */}
                      <div className="flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-slate-500 flex items-center gap-1.5">
                            
                            Hội Thoại Group Chat Điều Phối Đa Tác Nhân ({sessionMsgs.length} tin nhắn)
                          </span>
                          <span className="text-[10px] text-slate-400">
                            Tự động đồng bộ các kênh CSKH, Kỹ thuật, Kế toán & Ban Quản Lý
                          </span>
                        </div>

                        <div className="flex flex-col gap-2.5 max-h-[460px] overflow-y-auto p-3.5 bg-slate-50/60 rounded-xl border border-slate-200">
                          {sessionMsgs.map((msg) => {
                            const isAgent = msg.sender_type.startsWith('AGENT');
                            const isCSKH = msg.sender_type === 'AGENT_CSKH';
                            const isDispatcher = msg.sender_type === 'AGENT_DISPATCHER';
                            const isTech = msg.sender_type === 'AGENT_TECHNICAL';
                            const isBilling = msg.sender_type === 'AGENT_BILLING';
                            const isManager = msg.sender_type === 'HUMAN_MANAGER';

                            const badgeColor = isCSKH
                              ? 'bg-muted/60 text-slate-700 border-border'
                              : isDispatcher
                                ? 'bg-muted/60 text-slate-700 border-border'
                                : isTech
                                  ? 'bg-muted/60 text-foreground border-border'
                                  : isBilling
                                    ? 'bg-muted/60 text-slate-700 border-border'
                                    : isManager
                                      ? 'bg-slate-100 text-white border-slate-700'
                                      : 'bg-muted/60 text-slate-700 border-border';

                            return (
                              <div
                                key={msg.id}
                                className={`flex flex-col gap-1.5 p-3 rounded-xl border text-xs transition-all ${
                                  isAgent ? 'bg-white border-slate-200/90 shadow-2xs' : 'bg-white border-border shadow-2xs'
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md border flex items-center gap-1 ${badgeColor}`}
                                    >
                                      
                                      
                                      
                                      
                                      
                                      
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
                            className="flex-1 p-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-ring/40 focus:border-primary focus:outline-none"
                          />
                          <button
                            type="submit"
                            disabled={!sessionChatInput.trim()}
                            className="px-4 py-2.5 bg-primary hover:bg-primary/90 disabled:opacity-50 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors shrink-0"
                          >
                            <IconSend className="w-3.5 h-3.5" />
                            <span>Gửi</span>
                          </button>
                        </form>
                      </div>

                      {/* Modal Ban quản lý phê duyệt đóng phiên */}
                      {showBqlModal && (
                        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 z-50">
                          <div className="bg-white rounded-2xl max-w-md w-full p-4 sm:p-6 flex flex-col gap-4 shadow-2xl border border-slate-200">
                            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                              <div className="flex items-center gap-2">
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

                            <div className="flex flex-col gap-1.5">
                              <label className="text-xs font-bold text-slate-700 block">
                                Ghi chú phê duyệt của Ban Quản Lý:
                              </label>
                              <textarea
                                rows={3}
                                value={bqlNoteInput}
                                onChange={(e) => setBqlNoteInput(e.target.value)}
                                placeholder="VD: Đã nghiệm thu hiện trường đạt tiêu chuẩn. Chi phí vật tư đúng định mức..."
                                className="w-full p-2.5 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-ring/40"
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
                                  setShowBqlModal(false);
                                  try {
                                    managerApproveAndCloseSession(currentSession.id, bqlNoteInput);
                                    setResolveError(null);
                                    setActionSuccess(`Đã phê duyệt và đóng phiên điều phối ${currentSession.id} thành công!`);
                                    setTimeout(() => setActionSuccess(null), 3500);
                                  } catch (err) {
                                    setResolveError(err instanceof Error ? err.message : 'Chưa đủ điều kiện đóng hồ sơ.');
                                  }
                                }}
                                className="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl text-xs font-bold shadow-2xs"
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
                  <div className="flex flex-col gap-4">
                    {/* Tasks */}
                    <div className="flex flex-col gap-2">
                      <span className="text-[11px] font-bold text-slate-500">
                        Các nhiệm vụ cần làm
                      </span>
                      {relatedTasks.map((t) => (
                        <div
                          key={t.id}
                          className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                        >
                          <div>
                            <div className="flex items-center gap-1.5 font-mono">
                              <span className="font-bold text-foreground">{t.id}</span>
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
                                ? 'bg-muted/60 text-slate-700'
                                : t.status === 'BLOCKED'
                                  ? 'bg-muted/60 text-slate-700'
                                  : 'bg-muted/60 text-foreground'
                            }`}
                          >
                            {t.status === 'DONE' ? 'Hoàn thành' : t.status === 'BLOCKED' ? 'Tạm dừng' : 'Đang làm'}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Work Orders */}
                    <div className="flex flex-col gap-2 pt-2 border-t border-slate-100">
                      <span className="text-[11px] font-bold text-slate-500">
                        Lịch sử các lần thi công thực tế
                      </span>
                      {relatedWorkOrders.map((w) => (
                        <div
                          key={w.id}
                          className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                        >
                          <div>
                            <div className="flex items-center gap-1.5 font-mono">
                              <span className="font-bold text-foreground">{w.id}</span>
                              <span className="text-slate-400">•</span>
                              <span className="font-sans font-medium text-slate-600">Lần thi công #{w.attempt_no}</span>
                              {w.redo_of_work_order_id && (
                                <span className="text-[10px] font-bold text-slate-700 bg-muted/60 px-1.5 py-0.2 rounded font-sans">
                                  Làm lại của {w.redo_of_work_order_id}
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-500 mt-0.5">
                              Người làm: {w.executor_name || 'Kỹ thuật'} ({w.executor_phone || '-'})
                            </p>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
                              w.status === 'COMPLETED'
                                ? 'bg-muted/60 text-slate-700'
                                : w.status === 'IN_PROGRESS'
                                  ? 'bg-muted/60 text-slate-700'
                                  : 'bg-muted/60 text-slate-700'
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
                          <div>
                            <h3 className="text-sm font-bold text-slate-900">Phòng trao đổi xử lý sự cố</h3>
                            <p className="text-[11px] text-slate-500">Trao đổi nội bộ giữa agent, điều phối và nhân viên hiện trường</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-bold">
                        <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-slate-600">A1 · CSKH</span>
                        
                        <span className="rounded-full border border-border bg-muted/60 px-2 py-1 text-slate-700">A0 · Điều phối</span>
                        
                        <span className="rounded-full border border-border bg-muted/60 px-2 py-1 text-foreground">A2 · Kỹ thuật</span>
                        
                        <span className="rounded-full border border-border bg-muted/60 px-2 py-1 text-slate-700">Nhân viên</span>
                      </div>
                    </div>

                    <div className="max-h-[470px] flex flex-col gap-4 overflow-y-auto bg-slate-50/30 px-3 py-4 sm:px-5">
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
                                <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${meta.avatarClass}`}>
                                  {actorCode} · {meta.label}
                                </span>
                                <time className="text-[10px] text-slate-400">
                                  {new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                                </time>
                              </div>
                              <div className={`rounded-2xl border px-3.5 py-2.5 text-left text-xs leading-relaxed text-slate-700 shadow-xs ${
                                isCurrentUser
                                  ? 'rounded-tr-sm border-primary bg-primary text-primary-foreground'
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
                      <span className="hidden h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-muted/60 sm:flex">
                        {currentProfile.avatarUrl && <img src={currentProfile.avatarUrl} alt="" className="size-full object-cover" />}
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
                          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs focus:border-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-ring/40"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={!newMessageText.trim()}
                        className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-primary px-4 text-xs font-bold text-white shadow-2xs transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <IconSend className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Gửi</span>
                      </button>
                    </form>
                  </div>
                )}

                {/* Tab 3: Timeline */}
                {activeTab === 'TIMELINE' && (
                  <div className="flex flex-col gap-2.5">
                    {incidentEvents.length === 0 ? (
                      <div className="p-8 text-center text-slate-400 text-xs">
                        Chưa có ghi nhận nhật ký nào.
                      </div>
                    ) : (
                      incidentEvents.map((evt) => (
                        <div key={evt.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-start gap-2.5">
                          <div className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-300" />
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
                                                ? 'Nghiệm thu chưa đạt - Tạo phiếu làm lại'
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
                  <div className="flex flex-col gap-2">
                    {incidentRelations.length === 0 ? (
                      <div className="p-8 text-center text-slate-400 text-xs">
                        Sự cố này độc lập, không có liên quan đến sự cố nào khác.
                      </div>
                    ) : (
                      incidentRelations.map((rel, idx) => (
                        <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            
                            <span className="font-bold text-slate-800">
                              {rel.relation_type === 'CAUSED_BY' ? 'Gây ra bởi' : 'Có liên quan đến'}
                            </span>
                            <span className="font-semibold text-foreground">{rel.target_incident_id}</span>
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
