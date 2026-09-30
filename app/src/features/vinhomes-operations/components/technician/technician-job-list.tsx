import { useMemo, useState } from 'react';
import { IconChevronRight, IconMapPin, IconRotateClockwise } from '@tabler/icons-react';
import { useOperationsData } from '../../hooks/use-operations-data';
import { getFieldFlow, getTechnicianStep, type TechnicianTab } from '../../lib/field-flow';
import type { VhWorkOrder } from '../../types/work-order';
import { ActionButton, AutoCompleteCountdown, Banner, SeverityBadge, SlaCountdown, StatusPill, useNow } from './ui';

const TABS: Array<{ id: TechnicianTab; label: string }> = [
  { id: 'NEW', label: 'Mới giao' },
  { id: 'ACTIVE', label: 'Đang làm' },
  { id: 'WAITING', label: 'Chờ xác nhận' },
  { id: 'HISTORY', label: 'Lịch sử' },
];

const SEVERITY_RANK: Record<string, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };
const SHIFT_KEY = 'vhm_technician_on_shift';

export function TechnicianJobList({ onOpen }: { onOpen: (woId: string) => void }) {
  const { myWorkOrders, incidents, tasks, evidence, acceptJob, currentProfile, currentPersona } = useOperationsData();
  // Vệ sinh / an ninh hoàn thành ngay khi gửi, không có bước chờ cư dân xác nhận
  const tabs = currentPersona === 'STAFF_TECHNICAL' ? TABS : TABS.filter((t) => t.id !== 'WAITING');
  const now = useNow();
  const [tab, setTab] = useState<TechnicianTab>('NEW');
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
      return { wo, incident, task, step, flow: getFieldFlow(wo, incident?.category, task) };
    });
  }, [myWorkOrders, incidents, tasks, evidence]);

  const counts = useMemo(() => {
    const c: Record<TechnicianTab, number> = { NEW: 0, ACTIVE: 0, WAITING: 0, HISTORY: 0 };
    for (const j of jobs) c[j.step.tab] += 1;
    return c;
  }, [jobs]);

  const visible = useMemo(() => {
    return jobs
      .filter((j) => j.step.tab === tab)
      .sort((a, b) => {
        if (tab === 'HISTORY') return (b.wo.updated_at || '').localeCompare(a.wo.updated_at || '');
        const rework = Number(!!b.flow.rework_note) - Number(!!a.flow.rework_note);
        if (rework !== 0) return rework;
        const sev = (SEVERITY_RANK[a.incident?.severity || 'P3'] ?? 2) - (SEVERITY_RANK[b.incident?.severity || 'P3'] ?? 2);
        if (sev !== 0) return sev;
        return (a.incident?.sla_due_at || '').localeCompare(b.incident?.sla_due_at || '');
      });
  }, [jobs, tab]);

  const handleAccept = (wo: VhWorkOrder) => {
    try {
      acceptJob(wo.id);
      onOpen(wo.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không nhận được việc.');
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Greeting + shift */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-slate-500">Xin chào,</p>
          <p className="text-lg font-semibold text-slate-800 truncate">{currentProfile.name}</p>
        </div>
        <button
          type="button"
          onClick={toggleShift}
          aria-pressed={onShift}
          className={`min-h-11 px-4 rounded-full border text-sm font-semibold inline-flex items-center gap-2 ${
            onShift ? 'bg-emerald-50 border-emerald-300 text-emerald-700' : 'bg-slate-100 border-slate-300 text-slate-500'
          }`}
        >
          <span className={`w-2.5 h-2.5 rounded-full ${onShift ? 'bg-emerald-500' : 'bg-slate-400'}`} />
          {onShift ? 'Sẵn sàng nhận việc' : 'Đang nghỉ'}
        </button>
      </div>

      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}

      {/* Tabs */}
      <div role="tablist" className={`grid ${tabs.length === 4 ? 'grid-cols-4' : 'grid-cols-3'} gap-1 bg-slate-100 p-1 rounded-xl`}>
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`min-h-11 rounded-lg text-sm font-semibold px-1 ${tab === t.id ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'}`}
          >
            {t.label}
            {t.id !== 'HISTORY' && counts[t.id] > 0 && (
              <span className={`ml-1 inline-flex min-w-5 h-5 px-1 items-center justify-center rounded-full text-xs ${t.id === 'NEW' ? 'bg-rose-600 text-white' : 'bg-slate-200 text-slate-700'}`}>
                {counts[t.id]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Cards */}
      {visible.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-1">
          <p className="text-base font-medium text-slate-700">
            {tab === 'NEW' ? 'Chưa có việc mới' : tab === 'ACTIVE' ? 'Không có việc đang làm' : tab === 'WAITING' ? 'Không có việc chờ xác nhận' : 'Chưa có lịch sử'}
          </p>
          {tab === 'NEW' && <p className="text-sm text-slate-500">{onShift ? 'Việc mới do AI giao sẽ hiện ở đây.' : 'Bật “Sẵn sàng nhận việc” để AI giao việc cho bạn.'}</p>}
        </div>
      ) : (
        <ul className="space-y-3">
          {visible.map(({ wo, incident, task, step, flow }) => {
            const loc = incident?.location_json;
            return (
              <li
                key={wo.id}
                className={`bg-white rounded-xl border p-4 space-y-3 ${flow.rework_note && step.tab !== 'HISTORY' ? 'border-rose-300 border-l-4' : 'border-slate-200'}`}
              >
                <button type="button" onClick={() => onOpen(wo.id)} className="w-full text-left space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <SeverityBadge severity={incident?.severity} />
                      {flow.rework_note && step.tab !== 'HISTORY' && (
                        <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded inline-flex items-center gap-1">
                          <IconRotateClockwise className="w-3.5 h-3.5" /> Làm lại
                        </span>
                      )}
                    </div>
                    <StatusPill tone={step.tone}>{step.label}</StatusPill>
                  </div>
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-base font-semibold text-slate-800 leading-snug">{task?.title || incident?.title || 'Công việc hiện trường'}</p>
                    <IconChevronRight className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
                  </div>
                  <p className="text-sm text-slate-600 inline-flex items-center gap-1">
                    <IconMapPin className="w-4 h-4 text-slate-400" />
                    Tòa {loc?.towerCode || '—'}
                    {loc?.apartmentCode ? ` · Căn ${loc.apartmentCode}` : loc?.floor != null ? ` · Tầng ${loc.floor}` : ''}
                  </p>
                  {flow.rework_note && step.tab !== 'HISTORY' && <p className="text-sm text-rose-700">Cư dân phản ánh: {flow.rework_note}</p>}
                  {step.tab === 'WAITING' ? (
                    step.stage === 'DISPUTED' ? <p className="text-sm text-rose-700">BQL đang xử lý ý kiến của cư dân</p> : <AutoCompleteCountdown autoCompleteAt={flow.auto_complete_at} now={now} />
                  ) : step.tab !== 'HISTORY' ? (
                    <SlaCountdown dueAt={incident?.sla_due_at} now={now} />
                  ) : null}
                </button>
                {step.stage === 'ASSIGNED' && (
                  <div className="flex gap-2">
                    <ActionButton variant="secondary" onClick={() => onOpen(wo.id)}>Xem chi tiết</ActionButton>
                    <ActionButton onClick={() => handleAccept(wo)}>Nhận việc</ActionButton>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
