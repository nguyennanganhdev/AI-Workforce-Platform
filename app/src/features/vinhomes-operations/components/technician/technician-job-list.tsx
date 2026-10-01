import { Fragment, useMemo, useState } from 'react';
import { IconChevronRight, IconClipboardList, IconClock, IconHistory, IconMapPin } from '@tabler/icons-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { useOperationsData } from '../../hooks/use-operations-data';
import { getFieldFlow, getTechnicianStep, type TechnicianTab } from '../../lib/field-flow';
import type { VhWorkOrder } from '../../types/work-order';
import { EmptyState, Pagination, Panel, SearchField, Segmented, normalizeSearch, paginate } from '../ops-ui';
import { Banner, SeverityBadge, autoCompleteText, severityLabel, slaText, useNow } from './ui';

/** Two top-level views: jobs still on my plate, and jobs I've finished. */
export type JobListView = 'CURRENT' | 'HISTORY';

const VIEWS: Array<{ id: JobListView; label: string; title: string; icon: typeof IconHistory }> = [
  { id: 'CURRENT', label: 'Việc của tôi', title: 'Việc của tôi', icon: IconClipboardList },
  { id: 'HISTORY', label: 'Lịch sử', title: 'Lịch sử công việc', icon: IconHistory },
];

/** Current jobs are grouped in the order a field worker handles them. */
const GROUPS: Array<{ id: Exclude<TechnicianTab, 'HISTORY'>; label: string }> = [
  { id: 'NEW', label: 'Việc mới giao' },
  { id: 'ACTIVE', label: 'Đang làm' },
  { id: 'WAITING', label: 'Chờ cư dân xác nhận' },
];

const SEVERITY_RANK: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };
const SHIFT_KEY = 'vhm_technician_on_shift';

export function TechnicianJobList({
  view,
  onViewChange,
  onOpen,
}: {
  view: JobListView;
  onViewChange: (view: JobListView) => void;
  onOpen: (woId: string) => void;
}) {
  const { myWorkOrders, incidents, tasks, evidence, acceptJob } = useOperationsData();
  const now = useNow();
  const isHistory = view === 'HISTORY';
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [onShift, setOnShift] = useState(() => {
    try {
      return localStorage.getItem(SHIFT_KEY) !== 'false';
    } catch {
      return true;
    }
  });

  const toggleShift = () => {
    setOnShift((v) => {
      try {
        localStorage.setItem(SHIFT_KEY, String(!v));
      } catch { /* per-device convenience only */ }
      return !v;
    });
  };

  const jobs = useMemo(() => {
    return myWorkOrders.map((wo) => {
      const incident = incidents.find((i) => i.id === wo.incident_id);
      const task = tasks.find((t) => t.id === wo.task_id);
      const step = getTechnicianStep(wo, evidence.filter((e) => e.work_order_id === wo.id), incident?.category, task);
      const loc = incident?.location_json;
      const title = task?.title || incident?.title || 'Công việc hiện trường';
      const place = `Tòa ${loc?.towerCode || '-'}${loc?.apartmentCode ? ` · Căn ${loc.apartmentCode}` : loc?.floor != null ? ` · Tầng ${loc.floor}` : ''}`;
      return {
        wo, incident, task, step, title, place,
        flow: getFieldFlow(wo, incident?.category, task),
        search: normalizeSearch(`${title} ${place}`),
      };
    });
  }, [myWorkOrders, incidents, tasks, evidence]);

  const counts = useMemo(() => {
    const c: Record<TechnicianTab, number> = { NEW: 0, ACTIVE: 0, WAITING: 0, HISTORY: 0 };
    for (const j of jobs) c[j.step.tab] += 1;
    return c;
  }, [jobs]);

  const visible = useMemo(() => {
    const q = normalizeSearch(query.trim());
    const groupRank = (t: TechnicianTab) => GROUPS.findIndex((g) => g.id === t);
    return jobs
      .filter((j) => (j.step.tab === 'HISTORY') === isHistory && (!q || j.search.includes(q)))
      .sort((a, b) => {
        if (isHistory) return (b.wo.updated_at || '').localeCompare(a.wo.updated_at || '');
        const group = groupRank(a.step.tab) - groupRank(b.step.tab);
        if (group !== 0) return group;
        const rework = Number(!!b.flow.rework_note) - Number(!!a.flow.rework_note);
        if (rework !== 0) return rework;
        const sev = (SEVERITY_RANK[a.incident?.severity || 'P2'] ?? 2) - (SEVERITY_RANK[b.incident?.severity || 'P2'] ?? 2);
        if (sev !== 0) return sev;
        return (a.incident?.sla_due_at || '').localeCompare(b.incident?.sla_due_at || '');
      });
  }, [jobs, isHistory, query]);

  // Current jobs are few and grouped, so they show in full; only history pages.
  const { pages, current, slice } = paginate(visible, page);
  const rows = isHistory ? slice : visible;
  const currentCount = counts.NEW + counts.ACTIVE + counts.WAITING;

  /** Group heading goes before the first row of each group (current view only). */
  const groupStart = (i: number) => {
    if (isHistory) return null;
    const t = rows[i].step.tab;
    if (i > 0 && rows[i - 1].step.tab === t) return null;
    const g = GROUPS.find((x) => x.id === t);
    return g ? { label: g.label, count: rows.filter((r) => r.step.tab === t).length } : null;
  };

  const handleAccept = (wo: VhWorkOrder) => {
    try {
      acceptJob(wo.id);
      onOpen(wo.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không nhận được việc.');
    }
  };

  /** Deadline column: SLA while working, auto-complete timer while waiting, finish time in history. */
  const deadline = (j: (typeof jobs)[number]) => {
    if (j.step.tab === 'HISTORY') {
      return { text: j.wo.updated_at ? new Date(j.wo.updated_at).toLocaleDateString('vi-VN') : '-', pressing: false };
    }
    if (j.step.tab === 'WAITING') {
      if (j.step.stage === 'DISPUTED') return { text: 'BQL đang xử lý', pressing: false };
      return { text: autoCompleteText(j.flow.auto_complete_at, now) || '-', pressing: false };
    }
    return slaText(j.incident?.sla_due_at, now) || { text: '-', pressing: false };
  };

  const isUrgent = (j: (typeof jobs)[number]) => j.incident?.severity === 'P0' || j.incident?.severity === 'P1';

  const isRework = (j: (typeof jobs)[number]) => !!j.flow.rework_note && j.step.tab !== 'HISTORY';

  const actions = (j: (typeof jobs)[number]) => (
    <div className="flex items-center justify-end gap-3">
      {j.step.stage === 'ASSIGNED' && (
        <Button size="lg" onClick={() => handleAccept(j.wo)}>Nhận việc</Button>
      )}
      <Button variant="link" className="h-9 px-0" onClick={() => onOpen(j.wo.id)}>Xem chi tiết</Button>
    </div>
  );

  const changeView = (v: JobListView) => {
    if (v === view) return;
    setQuery('');
    setPage(1);
    onViewChange(v);
  };

  const viewMeta = VIEWS.find((v) => v.id === view)!;

  return (
    <div className="flex flex-col gap-4 pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:pb-0">
      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}

      <Panel
        title={viewMeta.title}
        meta={
          !isHistory && (
            <div className="flex items-center gap-2.5">
              <Switch id="on-shift" checked={onShift} onCheckedChange={toggleShift} />
              <Label htmlFor="on-shift" className="font-normal text-foreground">{onShift ? 'Sẵn sàng nhận việc' : 'Đang nghỉ'}</Label>
            </div>
          )
        }
        toolbar={
          <>
            {/* Tablet & desktop switch; phones use the bottom bar */}
            <div className="hidden md:flex">
              <Segmented
                label="Chọn danh sách"
                value={view}
                onChange={changeView}
                options={VIEWS.map((v) => ({ id: v.id, label: v.label, count: v.id === 'CURRENT' ? currentCount : undefined }))}
              />
            </div>
            <SearchField
              value={query}
              onChange={(v) => { setQuery(v); setPage(1); }}
              placeholder="Tìm công việc, tòa nhà, căn hộ"
            />
          </>
        }
        footer={
          isHistory && visible.length > 0 && (
            <Pagination page={current} pages={pages} total={visible.length} unit="công việc" onChange={setPage} />
          )
        }
      >
        {rows.length === 0 ? (
          <EmptyState
            title={query ? 'Không tìm thấy công việc phù hợp' : isHistory ? 'Chưa có công việc đã làm' : 'Chưa có việc nào'}
            hint={
              query
                ? 'Thử từ khóa khác hoặc xóa ô tìm kiếm.'
                : isHistory
                  ? 'Việc bạn hoàn thành sẽ được lưu ở đây.'
                  : onShift ? 'Việc mới do AI giao sẽ hiện ở đây.' : 'Bật “Sẵn sàng nhận việc” để AI giao việc cho bạn.'
            }
          />
        ) : (
          <>
            {/* Tablet & desktop */}
            <div className="ops-list-table px-2 md:px-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Công việc</TableHead>
                    <TableHead>Vị trí</TableHead>
                    <TableHead className="hidden lg:table-cell">Mức độ</TableHead>
                    <TableHead>{isHistory ? 'Cập nhật' : 'Thời hạn'}</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((j, i) => {
                    const d = deadline(j);
                    const group = groupStart(i);
                    return (
                      <Fragment key={j.wo.id}>
                        {group && (
                          <TableRow className="bg-muted/50 hover:bg-muted/50">
                            <TableCell colSpan={6} className="py-2 text-[13px] font-medium text-foreground">
                              {group.label} <span className="font-normal tabular-nums text-muted-foreground">· {group.count}</span>
                            </TableCell>
                          </TableRow>
                        )}
                        <TableRow>
                          <TableCell className="min-w-64 whitespace-normal">
                            <button type="button" onClick={() => onOpen(j.wo.id)} className="ops-title text-left hover:text-primary hover:underline underline-offset-2">
                              {j.title}
                            </button>
                            {isRework(j) && <p className="ops-subtle font-medium text-foreground">Làm lại</p>}
                          </TableCell>
                          <TableCell className="whitespace-nowrap">{j.place}</TableCell>
                          <TableCell className="hidden whitespace-nowrap lg:table-cell"><SeverityBadge severity={j.incident?.severity} /></TableCell>
                          <TableCell className={cn('whitespace-nowrap tabular-nums', d.pressing && 'font-semibold text-foreground')}>{d.text}</TableCell>
                          <TableCell className="whitespace-nowrap">{j.step.label}</TableCell>
                          <TableCell className="text-right">{actions(j)}</TableCell>
                        </TableRow>
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Phone */}
            <ul className="ops-list-rows">
              {rows.map((j, i) => {
                const d = deadline(j);
                const group = groupStart(i);
                return (
                  <Fragment key={j.wo.id}>
                    {group && (
                      <li className="bg-muted/50 py-2! text-[13px] font-medium text-foreground">
                        {group.label} <span className="font-normal tabular-nums text-muted-foreground">· {group.count}</span>
                      </li>
                    )}
                    <li className="p-0!">
                      {/* The whole card opens the job; the accept button sits outside it */}
                      <button
                        type="button"
                        onClick={() => onOpen(j.wo.id)}
                        className="flex w-full items-center gap-3 px-4 py-3.5 text-left outline-none transition-colors active:bg-muted/60 focus-visible:bg-muted/60"
                      >
                        <div className="flex min-w-0 flex-1 flex-col gap-1">
                          {isRework(j) && <p className="text-xs font-medium text-foreground">Làm lại</p>}
                          <p className="line-clamp-2 text-[15px] font-medium leading-snug text-foreground">{j.title}</p>
                          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                            <IconMapPin className="size-3.5 shrink-0" aria-hidden />
                            <span className="truncate">{j.place}</span>
                          </p>
                          <div className="mt-1.5 flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <Badge
                                variant={isUrgent(j) ? 'secondary' : 'outline'}
                                className={cn('shrink-0', isUrgent(j) && 'font-semibold text-foreground')}
                              >
                                {severityLabel(j.incident?.severity)}
                              </Badge>
                              <span className="truncate text-[13px] text-slate-700">{j.step.label}</span>
                            </div>
                            <span
                              className={cn(
                                'flex shrink-0 items-center gap-1 text-[13px] tabular-nums',
                                d.pressing ? 'font-semibold text-foreground' : 'text-muted-foreground',
                              )}
                            >
                              <IconClock className="size-3.5" aria-hidden />
                              {d.text}
                            </span>
                          </div>
                          {isRework(j) && (
                            <p className="mt-1.5 rounded-md bg-muted/60 px-2.5 py-1.5 text-[13px] leading-snug text-slate-700">
                              {j.flow.rework_note}
                            </p>
                          )}
                        </div>
                        <IconChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                      </button>
                      {j.step.stage === 'ASSIGNED' && (
                        <div className="px-4 pb-3.5">
                          <Button size="lg" className="w-full" onClick={() => handleAccept(j.wo)}>Nhận việc</Button>
                        </div>
                      )}
                    </li>
                  </Fragment>
                );
              })}
            </ul>
          </>
        )}
      </Panel>

      <BottomNav view={view} onChange={changeView} currentCount={currentCount} />
    </div>
  );
}

/** Phone-only tab bar pinned to the bottom of the screen: "Việc của tôi" and "Lịch sử". */
function BottomNav({
  view,
  onChange,
  currentCount,
}: {
  view: JobListView;
  onChange: (view: JobListView) => void;
  currentCount: number;
}) {
  return (
    <nav
      aria-label="Danh sách công việc"
      className="fixed inset-x-0 bottom-0 z-30 border-t bg-card/95 backdrop-blur md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="grid h-16 grid-cols-2">
        {VIEWS.map(({ id, label, icon: Icon }) => {
          const active = id === view;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex flex-col items-center justify-center gap-1 text-xs font-medium outline-none transition-colors focus-visible:bg-muted',
                active ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {active && <span aria-hidden className="absolute inset-x-10 top-0 h-0.5 rounded-full bg-primary" />}
              <span className="relative">
                <Icon className="size-6" stroke={active ? 2 : 1.6} aria-hidden />
                {id === 'CURRENT' && currentCount > 0 && (
                  <span className="absolute -top-1.5 left-4 min-w-4.5 rounded-full bg-primary px-1 text-center text-[11px] leading-4.5 font-semibold tabular-nums text-primary-foreground">
                    {currentCount}
                  </span>
                )}
              </span>
              {label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
