import { useMemo, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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

const KIND_LABEL: Record<InboxItem['kind'], string> = {
  CANDIDATE: 'AI cần BQL xác nhận',
  CONTRACTOR: 'Cần nhà thầu',
  DISPUTED: 'Cư dân tranh chấp chi phí',
  UNCOOPERATIVE: 'Hộ không hợp tác',
};

const SEVERITY_RANK: Record<string, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };

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

/** Nội dung cư dân gửi qua app: mô tả, vị trí và ảnh (ảnh đầu vào, không phải evidence thi công). */
function ResidentSubmission({ candidate }: { candidate: VhIssueCandidate }) {
  const photos = candidate.resident_photo_urls ?? [];
  return (
    <div className="flex flex-col gap-2">
      {candidate.location_json.description && (
        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">{candidate.location_json.description}</p>
      )}
      {photos.length > 0 && (
        <div className="flex gap-1.5 overflow-x-auto">
          {photos.map((url, i) => (
            <img key={url} src={url} alt={`Ảnh cư dân gửi ${i + 1}`} className="size-20 shrink-0 rounded-md border object-cover" />
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateActions({ candidate, others, run }: { candidate: VhIssueCandidate; others: VhIssueCandidate[]; run: (fn: () => void, ok: string) => void }) {
  const { materializeCandidate, mergeIssueCandidates } = useOperationsData();
  const [target, setTarget] = useState<string | null>(null);
  const [tried, setTried] = useState(false);
  const mergeItems = Object.fromEntries(others.map((o) => [o.id, o.normalized_summary]));
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Độ tin cậy AI: <span className="font-medium text-foreground tabular-nums">{Math.round(candidate.confidence * 100)}%</span>
        {candidate.missing_fields_json.length > 0 && <> · Thiếu thông tin: {candidate.missing_fields_json.join(', ')}</>}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <Button size="lg" onClick={() => run(() => { materializeCandidate(candidate.id); }, 'Đã tạo sự cố. AI sẽ giao việc cho nhân viên phù hợp.')}>
          Xác nhận, tạo sự cố
        </Button>
        {others.length > 0 && (
          <div className="flex gap-2">
            <Select items={mergeItems} value={target} onValueChange={(v) => { setTarget(v as string | null); setTried(false); }}>
              <SelectTrigger aria-label="Gộp vào phản ánh" aria-invalid={tried && !target} className="min-w-0 flex-1 data-[size=default]:h-10 sm:w-72">
                <SelectValue placeholder="Gộp vào phản ánh trùng…" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {others.map((o) => <SelectItem key={o.id} value={o.id}>{o.normalized_summary}</SelectItem>)}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="lg"
              onClick={() => (target ? run(() => mergeIssueCandidates(candidate.id, target), 'Đã gộp phản ánh trùng.') : setTried(true))}
            >
              Gộp
            </Button>
          </div>
        )}
      </div>
      {tried && !target && <FieldError>Chọn phản ánh trùng cần gộp vào.</FieldError>}
    </div>
  );
}

function ContractorActions({ incident, handoff: h, run }: { incident: VhIncident; handoff: ContractorHandoff; run: (fn: () => void, ok: string) => void }) {
  const { markContractorContacted, markContractorResolved } = useOperationsData();
  const [name, setName] = useState(h.warranty?.under_warranty ? h.warranty.contractor_name || '' : '');
  const [eta, setEta] = useState('');
  const [note, setNote] = useState('');
  const [tried, setTried] = useState(false);
  const idp = `ct-${incident.id}`;
  const missing = [!name.trim() && 'tên nhà thầu', !eta && 'ngày hẹn'].filter(Boolean);

  return (
    <div className="flex flex-col gap-3">
      {h.warranty && (
        <Alert className="bg-muted/40">
          <AlertTitle>{h.warranty.under_warranty ? 'AI gợi ý: còn bảo hành' : 'Đã hết bảo hành'}</AlertTitle>
          <AlertDescription>
            {h.warranty.under_warranty
              ? <>Bảo hành đến {h.warranty.expires_at}. Liên hệ <span className="font-medium text-foreground">{h.warranty.contractor_name}</span>, không phát sinh chi phí.</>
              : <>{h.warranty.contractor_name}, hết hạn {h.warranty.expires_at}. BQL chọn nhà thầu và duyệt chi phí.</>}
          </AlertDescription>
        </Alert>
      )}
      {h.status === 'PENDING' ? (
        <FieldGroup className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end">
          <Field>
            <FieldLabel htmlFor={`${idp}-name`}>Nhà thầu đã liên hệ</FieldLabel>
            <Input id={`${idp}-name`} aria-invalid={tried && !name.trim()} value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên nhà thầu" className="h-10" />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${idp}-eta`}>Ngày hẹn dự kiến</FieldLabel>
            <Input id={`${idp}-eta`} aria-invalid={tried && !eta} type="date" value={eta} onChange={(e) => setEta(e.target.value)} className="h-10" />
          </Field>
          <Button
            size="lg"
            onClick={() =>
              missing.length
                ? setTried(true)
                : run(() => markContractorContacted(incident.id, name, eta), 'Đã ghi nhận. AI sẽ báo cư dân đã có đơn vị xử lý.')
            }
          >
            Đã liên hệ nhà thầu
          </Button>
          {tried && missing.length > 0 && <FieldError className="sm:col-span-3">Vui lòng nhập {missing.join(' và ')}.</FieldError>}
        </FieldGroup>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Đã liên hệ <span className="font-medium text-foreground">{h.contractor_name}</span> · hẹn ngày <span className="font-medium text-foreground">{h.eta}</span>
          </p>
          <FieldGroup className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <Field>
              <FieldLabel htmlFor={`${idp}-note`}>Ghi chú kết quả (không bắt buộc)</FieldLabel>
              <Input id={`${idp}-note`} value={note} onChange={(e) => setNote(e.target.value)} className="h-10" />
            </Field>
            <Button size="lg" onClick={() => run(() => markContractorResolved(incident.id, note), 'Đã đóng sự cố. AI sẽ báo cư dân đã khắc phục.')}>
              Đã khắc phục xong
            </Button>
          </FieldGroup>
        </div>
      )}
    </div>
  );
}

function EscalationActions({ item, run }: { item: Extract<InboxItem, { kind: 'DISPUTED' | 'UNCOOPERATIVE' }>; run: (fn: () => void, ok: string) => void }) {
  const { closeWithBqlResolution } = useOperationsData();
  const [note, setNote] = useState('');
  const [tried, setTried] = useState(false);
  const f = item.wo.field_flow;
  if (!f) return null;
  const id = `esc-${item.key}`;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-slate-700">
        {item.kind === 'DISPUTED'
          ? <>Nhân viên {item.wo.executor_name} ghi nhận: “{f.dispute_note}”</>
          : <>Kết quả: {f.security_outcome ? SECURITY_OUTCOME_LABELS[f.security_outcome] : '-'} · {item.wo.executor_name}: “{f.report_final_note}”</>}
      </p>
      <FieldGroup className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <Field>
          <FieldLabel htmlFor={id}>BQL đã xử lý thế nào? (bắt buộc)</FieldLabel>
          <Input id={id} aria-invalid={tried && !note.trim()} value={note} onChange={(e) => setNote(e.target.value)} className="h-10" />
        </Field>
        <Button
          size="lg"
          onClick={() => (note.trim() ? run(() => closeWithBqlResolution(item.incident.id, note), 'Đã xử lý và đóng sự cố.') : setTried(true))}
        >
          Đã xử lý, đóng sự cố
        </Button>
        {tried && !note.trim() && <FieldError className="sm:col-span-2">Vui lòng ghi lại cách BQL đã xử lý.</FieldError>}
      </FieldGroup>
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
    <div className="flex flex-col gap-3">
      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}
      {notice && <Banner kind="success" onClose={() => setNotice(null)}>{notice}</Banner>}
      {items.length === 0 ? (
        <Card>
          <Empty className="py-10">
            <EmptyHeader>
              <EmptyTitle>Không có việc cần BQL xử lý</EmptyTitle>
              <EmptyDescription>AI và nhân viên hiện trường đang xử lý các sự cố còn lại.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </Card>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => {
            const incident = item.kind === 'CANDIDATE' ? null : item.incident;
            const title = item.kind === 'CANDIDATE' ? item.candidate.normalized_summary : item.incident.title;
            const loc = item.kind === 'CANDIDATE' ? item.candidate.location_json : item.incident.location_json;
            return (
              <li key={`${item.kind}-${item.key}`}>
                <Card>
                  <CardHeader className="gap-2 px-4 md:px-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{KIND_LABEL[item.kind]}</Badge>
                      {item.kind === 'CANDIDATE' && item.candidate.source_channel === 'APP' && <Badge variant="secondary">Từ app cư dân</Badge>}
                      <SeverityBadge severity={item.severity} />
                      <span className="ml-auto text-xs tabular-nums text-muted-foreground">{new Date(item.at).toLocaleString('vi-VN')}</span>
                    </div>
                    <CardTitle className="text-base font-semibold leading-snug">
                      {incident ? (
                        <button
                          type="button"
                          onClick={() => onOpenIncident(incident.id)}
                          className="text-left underline-offset-2 hover:text-primary hover:underline focus-visible:text-primary focus-visible:underline focus-visible:outline-none"
                        >
                          {title}
                        </button>
                      ) : title}
                    </CardTitle>
                    <CardDescription>
                      Tòa {loc.towerCode || '-'}{loc.floor != null ? ` · Tầng ${loc.floor}` : ''}{loc.areaCode ? ` · ${loc.areaCode}` : ''}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3 px-4 md:px-5">
                    {item.kind === 'CANDIDATE' && item.candidate.source_channel === 'APP' && (
                      <ResidentSubmission candidate={item.candidate} />
                    )}
                    {item.kind === 'CANDIDATE' && (
                      <CandidateActions candidate={item.candidate} others={openCandidates.filter((c) => c.id !== item.candidate.id)} run={run} />
                    )}
                    {item.kind === 'CONTRACTOR' && item.incident.contractor_handoff && (
                      <ContractorActions incident={item.incident} handoff={item.incident.contractor_handoff} run={run} />
                    )}
                    {(item.kind === 'DISPUTED' || item.kind === 'UNCOOPERATIVE') && <EscalationActions item={item} run={run} />}
                    {incident && (
                      <Button variant="link" className="h-auto self-start px-0" onClick={() => onOpenIncident(incident.id)}>
                        Xem chi tiết sự cố
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
