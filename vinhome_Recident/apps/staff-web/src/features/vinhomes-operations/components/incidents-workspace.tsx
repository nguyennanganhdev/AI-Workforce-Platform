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
import { IconSend, IconChevronLeft } from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { IncidentStage } from '../types/incident';
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

type DetailTab = 'TASKS' | 'MESSAGES' | 'TIMELINE' | 'RELATIONS';

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
    currentProfile,
    currentPersona,
  } = useOperationsData();

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<DetailTab>('TASKS');
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [newMessageText, setNewMessageText] = useState('');
  const [localMessages, setLocalMessages] = useState(MOCK_MESSAGES);
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
    setNewMessageText('');
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
