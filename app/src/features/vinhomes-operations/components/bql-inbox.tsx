import { useMemo, useState } from 'react';
import { IconChevronRight, IconShieldCheck, IconSparkles, IconTool, IconUsersGroup, IconScale } from '@tabler/icons-react';
import { useOperationsData } from '../hooks/use-operations-data';
import { SECURITY_OUTCOME_LABELS } from '../types/field-flow';
import type { ContractorHandoff, VhIncident } from '../types/incident';
import type { VhIssueCandidate } from '../types/intake';
import type { VhWorkOrder } from '../types/work-order';
import { Banner, SeverityBadge } from './technician/ui';

type InboxItem =
  | { kind: 'CANDIDATE'; key: string; at: string; severity: string; candidate: VhIssueCandidate }
  | { kind: 'CONTRACTOR'; key: string; at: string; severity: string; incident: VhIncident }
  | { kind: 'DISPUTED' | 'UNCOOPERATIVE'; key: string; at: string; severity: string; incident: VhIncident; wo: VhWorkOrder };

const KIND_META: Record<InboxItem['kind'], { label: string; cls: string; Icon: typeof IconTool }> = {
  CANDIDATE: { label: 'AI cần BQL xác nhận', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200', Icon: IconSparkles },
  CONTRACTOR: { label: 'Cần nhà thầu', cls: 'bg-orange-50 text-orange-700 border-orange-200', Icon: IconTool },
  DISPUTED: { label: 'Cư dân tranh chấp chi phí', cls: 'bg-rose-50 text-rose-700 border-rose-200', Icon: IconScale },
  UNCOOPERATIVE: { label: 'Hộ không hợp tác', cls: 'bg-rose-50 text-rose-700 border-rose-200', Icon: IconUsersGroup },
};

const SEVERITY_RANK: Record<string, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };
const inputCls = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
const btnPrimary = 'px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold disabled:bg-slate-300';
const btnSecondary = 'px-4 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-sm font-medium';

/** Items AI escalates to BQL. Everything else is handled by AI + field staff. */
export function useBqlInboxItems(): InboxItem[] {
  const { issueCandidates, incidents, workOrders } = useOperationsData();
  return useMemo(() => {
    const items: InboxItem[] = [];
    for (const c of issueCandidates) {
      const open = c.status === 'DETECTED' || c.status === 'NEEDS_CLARIFICATION' || c.status === 'READY';
      if (open && !c.materialized_incident_id) items.push({ kind: 'CANDIDATE', key: c.id, at: c.created_at, severity: c.severity, candidate: c });
    }
    for (const inc of incidents) {
      if (inc.status === 'CLOSED') continue;
      if (inc.contractor_handoff && inc.contractor_handoff.status !== 'RESOLVED') {
        items.push({ kind: 'CONTRACTOR', key: inc.id, at: inc.created_at, severity: inc.severity, incident: inc });
      }
      for (const wo of workOrders.filter((w) => w.incident_id === inc.id)) {
        const f = wo.field_flow;
        if (f?.stage === 'DISPUTED') items.push({ kind: 'DISPUTED', key: wo.id, at: wo.updated_at, severity: inc.severity, incident: inc, wo });
        if (f?.stage === 'DONE' && f.security_outcome === 'UNCOOPERATIVE') {
          items.push({ kind: 'UNCOOPERATIVE', key: wo.id, at: wo.updated_at, severity: inc.severity, incident: inc, wo });
        }
      }
    }
    return items.sort(
      (a, b) => (SEVERITY_RANK[a.severity] ?? 2) - (SEVERITY_RANK[b.severity] ?? 2) || a.at.localeCompare(b.at),
    );
  }, [issueCandidates, incidents, workOrders]);
}

function CandidateActions({ candidate, others, run }: { candidate: VhIssueCandidate; others: VhIssueCandidate[]; run: (fn: () => void, ok: string) => void }) {
  const { materializeCandidate, mergeIssueCandidates } = useOperationsData();
  const [target, setTarget] = useState('');
  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600">
        Độ tin cậy AI: <b>{Math.round(candidate.confidence * 100)}%</b>
        {candidate.missing_fields_json.length > 0 && <> · Thiếu thông tin: {candidate.missing_fields_json.join(', ')}</>}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={btnPrimary} onClick={() => run(() => { materializeCandidate(candidate.id); }, 'Đã tạo sự cố. AI sẽ giao việc cho nhân viên phù hợp.')}>
          Xác nhận, tạo sự cố
        </button>
        {others.length > 0 && (
          <>
            <select className={`${inputCls} w-auto`} value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Gộp vào phản ánh">
              <option value="">Gộp vào phản ánh trùng…</option>
              {others.map((o) => <option key={o.id} value={o.id}>{o.normalized_summary}</option>)}
            </select>
            <button type="button" className={btnSecondary} disabled={!target} onClick={() => run(() => mergeIssueCandidates(candidate.id, target), 'Đã gộp phản ánh trùng.')}>
              Gộp
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function ContractorActions({ incident, handoff: h, run }: { incident: VhIncident; handoff: ContractorHandoff; run: (fn: () => void, ok: string) => void }) {
  const { markContractorContacted, markContractorResolved } = useOperationsData();
  const [name, setName] = useState(h.warranty?.under_warranty ? h.warranty.contractor_name || '' : '');
  const [eta, setEta] = useState('');
  const [note, setNote] = useState('');

  return (
    <div className="space-y-2">
      {h.warranty && (
        <p className={`text-sm rounded-lg px-3 py-2 ${h.warranty.under_warranty ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-50 text-slate-700'}`}>
          <IconSparkles className="w-4 h-4 inline -mt-0.5 mr-1" />
          {h.warranty.under_warranty
            ? <>AI gợi ý: <b>còn bảo hành</b> đến {h.warranty.expires_at} · liên hệ <b>{h.warranty.contractor_name}</b> (không phát sinh chi phí)</>
            : <>Đã hết bảo hành ({h.warranty.contractor_name}, hết hạn {h.warranty.expires_at}). BQL chọn nhà thầu và duyệt chi phí.</>}
        </p>
      )}
      {h.status === 'PENDING' ? (
        <div className="grid sm:grid-cols-[1fr_11rem_auto] gap-2 items-end">
          <label className="text-sm text-slate-600 space-y-1">Nhà thầu đã liên hệ
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên nhà thầu" />
          </label>
          <label className="text-sm text-slate-600 space-y-1">Ngày hẹn dự kiến
            <input className={inputCls} type="date" value={eta} onChange={(e) => setEta(e.target.value)} />
          </label>
          <button type="button" className={btnPrimary} disabled={!name.trim() || !eta} onClick={() => run(() => markContractorContacted(incident.id, name, eta), 'Đã ghi nhận. AI sẽ báo cư dân đã có đơn vị xử lý.')}>
            Đã liên hệ nhà thầu
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-slate-700">Đã liên hệ <b>{h.contractor_name}</b> · hẹn ngày <b>{h.eta}</b></p>
          <div className="flex flex-col sm:flex-row gap-2">
            <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú kết quả (không bắt buộc)" />
            <button type="button" className={`${btnPrimary} shrink-0`} onClick={() => run(() => markContractorResolved(incident.id, note), 'Đã đóng sự cố. AI sẽ báo cư dân đã khắc phục.')}>
              Đã khắc phục xong
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EscalationActions({ item, run }: { item: Extract<InboxItem, { kind: 'DISPUTED' | 'UNCOOPERATIVE' }>; run: (fn: () => void, ok: string) => void }) {
  const { closeWithBqlResolution } = useOperationsData();
  const [note, setNote] = useState('');
  const f = item.wo.field_flow;
  if (!f) return null;
  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-700">
        {item.kind === 'DISPUTED'
          ? <>Nhân viên {item.wo.executor_name} ghi nhận: “{f.dispute_note}”</>
          : <>Kết quả: {f.security_outcome ? SECURITY_OUTCOME_LABELS[f.security_outcome] : '—'} · {item.wo.executor_name}: “{f.report_final_note}”</>}
      </p>
      <div className="flex flex-col sm:flex-row gap-2">
        <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} placeholder="BQL đã xử lý thế nào? (bắt buộc)" />
        <button type="button" className={`${btnPrimary} shrink-0`} disabled={!note.trim()} onClick={() => run(() => closeWithBqlResolution(item.incident.id, note), 'Đã xử lý và đóng sự cố.')}>
          Đã xử lý, đóng sự cố
        </button>
      </div>
    </div>
  );
}

export function BqlInbox({ onOpenIncident }: { onOpenIncident: (id: string) => void }) {
  const items = useBqlInboxItems();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const run = (fn: () => void, ok: string) => {
    setError(null);
    try {
      fn();
      setNotice(ok);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.');
    }
  };

  const openCandidates = items.flatMap((i) => (i.kind === 'CANDIDATE' ? [i.candidate] : []));

  return (
    <div className="space-y-3">
      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}
      {notice && <Banner kind="success" onClose={() => setNotice(null)}>{notice}</Banner>}
      {items.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-10 text-center">
          <IconShieldCheck className="w-10 h-10 mx-auto text-emerald-500" />
          <p className="mt-2 text-base font-medium text-slate-700">Không có việc cần BQL xử lý</p>
          <p className="text-sm text-slate-500">AI và nhân viên hiện trường đang xử lý các sự cố còn lại.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => {
            const meta = KIND_META[item.kind];
            const incident = item.kind === 'CANDIDATE' ? null : item.incident;
            const title = item.kind === 'CANDIDATE' ? item.candidate.normalized_summary : item.incident.title;
            const loc = item.kind === 'CANDIDATE' ? item.candidate.location_json : item.incident.location_json;
            return (
              <li key={`${item.kind}-${item.key}`} className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full border ${meta.cls}`}>
                    <meta.Icon className="w-3.5 h-3.5" /> {meta.label}
                  </span>
                  <SeverityBadge severity={item.severity} />
                  <span className="text-xs text-slate-400 ml-auto">{new Date(item.at).toLocaleString('vi-VN')}</span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-slate-900">{title}</p>
                    <p className="text-sm text-slate-500">Tòa {loc.towerCode || '—'}{loc.floor != null ? ` · Tầng ${loc.floor}` : ''}{loc.areaCode ? ` · ${loc.areaCode}` : ''}</p>
                  </div>
                  {incident && (
                    <button type="button" onClick={() => onOpenIncident(incident.id)} className="shrink-0 text-sm text-blue-700 font-medium inline-flex items-center">
                      Chi tiết <IconChevronRight className="w-4 h-4" />
                    </button>
                  )}
                </div>
                {item.kind === 'CANDIDATE' && (
                  <CandidateActions candidate={item.candidate} others={openCandidates.filter((c) => c.id !== item.candidate.id)} run={run} />
                )}
                {item.kind === 'CONTRACTOR' && item.incident.contractor_handoff && (
                  <ContractorActions incident={item.incident} handoff={item.incident.contractor_handoff} run={run} />
                )}
                {(item.kind === 'DISPUTED' || item.kind === 'UNCOOPERATIVE') && <EscalationActions item={item} run={run} />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
