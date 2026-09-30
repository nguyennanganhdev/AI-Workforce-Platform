import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { useOperationsData } from '../../hooks/use-operations-data';
import { getFieldFlow, getTechnicianStep, type TechnicianTab } from '../../lib/field-flow';
import type { VhWorkOrder } from '../../types/work-order';
import { EmptyState, Pagination, Panel, SearchField, Segmented, normalizeSearch, paginate } from '../ops-ui';
import { Banner, SeverityBadge, autoCompleteText, slaText, useNow } from './ui';

const TABS: Array<{ id: TechnicianTab; label: string }> = [
  { id: 'NEW', label: 'Mới giao' },
  { id: 'ACTIVE', label: 'Đang làm' },
  { id: 'WAITING', label: 'Chờ xác nhận' },
  { id: 'HISTORY', label: 'Lịch sử' },
];

const EMPTY_TEXT: Record<TechnicianTab, string> = {
  NEW: 'Chưa có việc mới',
  ACTIVE: 'Không có việc đang làm',
  WAITING: 'Không có việc chờ xác nhận',
  HISTORY: 'Chưa có lịch sử',
};

const SEVERITY_RANK: Record<string, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };
const SHIFT_KEY = 'vhm_technician_on_shift';

export function TechnicianJobList({ onOpen }: { onOpen: (woId: string) => void }) {
  const { myWorkOrders, incidents, tasks, evidence, acceptJob, currentPersona } = useOperationsData();
  // Vệ sinh / an ninh hoàn thành ngay khi gửi, không có bước chờ cư dân xác nhận
  const tabs = currentPersona === 'STAFF_TECHNICAL' ? TABS : TABS.filter((t) => t.id !== 'WAITING');
  const now = useNow();
  const [tab, setTab] = useState<TechnicianTab>('NEW');
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
        search: normalizeSearch(`${wo.id} ${title} ${place}`),
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
    return jobs
      .filter((j) => j.step.tab === tab && (!q || j.search.includes(q)))
      .sort((a, b) => {
        if (tab === 'HISTORY') return (b.wo.updated_at || '').localeCompare(a.wo.updated_at || '');
        const rework = Number(!!b.flow.rework_note) - Number(!!a.flow.rework_note);
        if (rework !== 0) return rework;
        const sev = (SEVERITY_RANK[a.incident?.severity || 'P3'] ?? 2) - (SEVERITY_RANK[b.incident?.severity || 'P3'] ?? 2);
        if (sev !== 0) return sev;
        return (a.incident?.sla_due_at || '').localeCompare(b.incident?.sla_due_at || '');
      });
  }, [jobs, tab, query]);

  const { pages, current, slice } = paginate(visible, page);

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

  const isRework = (j: (typeof jobs)[number]) => !!j.flow.rework_note && j.step.tab !== 'HISTORY';

  const actions = (j: (typeof jobs)[number]) => (
    <div className="flex items-center justify-end gap-3">
      {j.step.stage === 'ASSIGNED' && (
        <Button size="lg" onClick={() => handleAccept(j.wo)}>Nhận việc</Button>
      )}
      <Button variant="link" className="h-9 px-0" onClick={() => onOpen(j.wo.id)}>Xem chi tiết</Button>
    </div>
  );

  const changeTab = (t: TechnicianTab) => {
    setTab(t);
    setPage(1);
  };

  return (
    <div className="flex flex-col gap-4">
      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}

      <Panel
        title="Việc của tôi"
        meta={
          <div className="flex items-center gap-2.5">
            <Switch id="on-shift" checked={onShift} onCheckedChange={toggleShift} />
            <Label htmlFor="on-shift" className="font-normal text-foreground">{onShift ? 'Sẵn sàng nhận việc' : 'Đang nghỉ'}</Label>
          </div>
        }
        toolbar={
          <>
            <Segmented
              label="Lọc theo trạng thái"
              value={tab}
              onChange={changeTab}
              options={tabs.map((t) => ({ id: t.id, label: t.label, count: t.id === 'HISTORY' ? undefined : counts[t.id] }))}
            />
            <SearchField
              value={query}
              onChange={(v) => { setQuery(v); setPage(1); }}
              placeholder="Tìm mã phiếu, công việc, tòa nhà"
            />
          </>
        }
        footer={
          visible.length > 0 && (
            <Pagination page={current} pages={pages} total={visible.length} unit="công việc" onChange={setPage} />
          )
        }
      >
        {slice.length === 0 ? (
          <EmptyState
            title={query ? 'Không tìm thấy công việc phù hợp' : EMPTY_TEXT[tab]}
            hint={
              query
                ? 'Thử từ khóa khác hoặc xóa ô tìm kiếm.'
                : tab === 'NEW'
                  ? onShift ? 'Việc mới do AI giao sẽ hiện ở đây.' : 'Bật “Sẵn sàng nhận việc” để AI giao việc cho bạn.'
                  : undefined
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
                    <TableHead>{tab === 'HISTORY' ? 'Cập nhật' : 'Thời hạn'}</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead className="text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {slice.map((j) => {
                    const d = deadline(j);
                    return (
                      <TableRow key={j.wo.id}>
                        <TableCell className="min-w-64 whitespace-normal">
                          <button type="button" onClick={() => onOpen(j.wo.id)} className="ops-title text-left hover:text-primary hover:underline underline-offset-2">
                            {j.title}
                          </button>
                          <p className="ops-subtle tabular-nums">{j.wo.id}{isRework(j) ? ' · Làm lại' : ''}</p>
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{j.place}</TableCell>
                        <TableCell className="hidden whitespace-nowrap lg:table-cell"><SeverityBadge severity={j.incident?.severity} /></TableCell>
                        <TableCell className={cn('whitespace-nowrap tabular-nums', d.pressing && 'font-semibold text-foreground')}>{d.text}</TableCell>
                        <TableCell className="whitespace-nowrap">{j.step.label}</TableCell>
                        <TableCell className="text-right">{actions(j)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Phone */}
            <ul className="ops-list-rows">
              {slice.map((j) => {
                const d = deadline(j);
                return (
                  <li key={j.wo.id} className="flex flex-col gap-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <button type="button" onClick={() => onOpen(j.wo.id)} className="ops-title text-left font-medium hover:text-primary hover:underline underline-offset-2">
                        {j.title}
                      </button>
                      <span className="shrink-0 text-[13px] text-slate-600">{j.step.label}</span>
                    </div>
                    <p className="ops-subtle">
                      <span className="tabular-nums">{j.wo.id}</span> · {j.place}
                    </p>
                    <p className="flex items-center gap-2 text-[13px] text-slate-600">
                      <SeverityBadge severity={j.incident?.severity} />
                      <Separator orientation="vertical" className="h-3.5" />
                      <span className={cn(d.pressing && 'font-semibold text-foreground')}>{d.text}</span>
                    </p>
                    {isRework(j) && <p className="text-[13px] text-slate-700">Làm lại: {j.flow.rework_note}</p>}
                    <div className="pt-1">{actions(j)}</div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </Panel>
    </div>
  );
}
