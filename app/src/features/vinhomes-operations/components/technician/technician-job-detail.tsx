import { useMemo, useState } from 'react';
import {
  IconArrowLeft,
  IconCheck,
  IconDeviceMobileShare,
  IconMapPin,
  IconPlayerPause,
  IconPlayerPlay,
  IconRotateClockwise,
  IconSend,
  IconSparkles,
} from '@tabler/icons-react';
import { useOperationsData } from '../../hooks/use-operations-data';
import { getFieldFlow, getTechnicianStep, formatVnd, splitQuote } from '../../lib/field-flow';
import {
  CLEANING_PAUSE_REASON_LABELS,
  SECURITY_OUTCOME_LABELS,
  SECURITY_PAUSE_REASON_LABELS,
  DECLINE_REASON_LABELS,
  PAUSE_REASON_LABELS,
  quoteTotal,
  type CleaningPauseReason,
  type DeclineReason,
  type FieldFlow,
  type PauseReason,
} from '../../types/field-flow';
import type { VhEvidenceRef } from '../../types/evidence';
import { CleaningSteps } from './cleaning-steps';
import { SecuritySteps } from './security-steps';
import { PhotoCapture } from './photo-capture';
import { QuoteEditor } from './quote-editor';
import { ResidentHandover } from './resident-handover';
import {
  ActionButton,
  AutoCompleteCountdown,
  Banner,
  BottomActionBar,
  ChecklistGate,
  ReasonSheet,
  Section,
  SeverityBadge,
  SlaCountdown,
  StatusPill,
  StepProgress,
  useNow,
} from './ui';

type Sheet = 'decline' | 'pause' | 'rework' | null;

const ALL_PAUSE_LABELS: Record<PauseReason | CleaningPauseReason, string> = { ...PAUSE_REASON_LABELS, ...CLEANING_PAUSE_REASON_LABELS };

function ReportSummary({ flow, before, after }: { flow: FieldFlow; before: VhEvidenceRef[]; after: VhEvidenceRef[] }) {
  const { agreed, additional } = splitQuote(flow.quote.lines);
  const total = quoteTotal(flow.quote.lines, flow.quote.labor_cost);
  return (
    <div className="space-y-4">
      <Section title="Ảnh hiện trường">
        <div className="grid grid-cols-2 gap-3">
          {[{ label: `Trước (${before.length})`, photos: before }, { label: `Sau (${after.length})`, photos: after }].map((g) => (
            <div key={g.label} className="space-y-1">
              <p className="text-sm text-slate-600">{g.label}</p>
              <div className="flex gap-1.5 overflow-x-auto">
                {g.photos.map((p) => (
                  <img key={p.id} src={p.file_url} alt={g.label} className="w-20 h-20 rounded-lg object-cover border border-slate-200 shrink-0" />
                ))}
                {g.photos.length === 0 && <p className="text-sm text-slate-400">Không có ảnh</p>}
              </div>
            </div>
          ))}
        </div>
      </Section>
      {flow.kind === 'REPAIR' && <Section title="Chi phí">
        {flow.no_charge ? (
          <p className="text-base text-slate-600">Không phát sinh chi phí</p>
        ) : (
          <div className="space-y-1.5 text-base">
            {agreed.map((l) => (
              <p key={l.id} className="flex justify-between gap-2"><span className="text-slate-700">{l.name} × {l.quantity}</span><span>{formatVnd(l.amount)}</span></p>
            ))}
            {flow.quote.labor_cost > 0 && <p className="flex justify-between"><span className="text-slate-700">Tiền công</span><span>{formatVnd(flow.quote.labor_cost)}</span></p>}
            {additional.map((l) => (
              <p key={l.id} className="flex justify-between gap-2 text-orange-700"><span>+ {l.name} × {l.quantity} (phát sinh)</span><span>{formatVnd(l.amount)}</span></p>
            ))}
            <p className="flex justify-between font-semibold border-t border-slate-200 pt-2"><span>Tổng</span><span>{formatVnd(total)}</span></p>
            {flow.quote.warranty_months > 0 && <p className="text-sm text-slate-500">Bảo hành {flow.quote.warranty_months} tháng</p>}
          </div>
        )}
      </Section>}
      {flow.signature && (
        <Section title="Chữ ký cư dân" right={<span className="text-sm text-slate-500">{new Date(flow.signature.signed_at).toLocaleString('vi-VN')}</span>}>
          <img src={flow.signature.signature_image_url} alt="Chữ ký cư dân" className="w-full max-h-32 object-contain bg-slate-50 rounded-lg border border-slate-200" />
        </Section>
      )}
    </div>
  );
}

export function TechnicianJobDetail({ woId, onBack }: { woId: string; onBack: () => void }) {
  const ops = useOperationsData();
  const { myWorkOrders, incidents, tasks, evidence, addEvidence } = ops;
  const now = useNow();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [handover, setHandover] = useState<'agree' | 'sign' | null>(null);
  const [finalNote, setFinalNote] = useState('');

  const wo = myWorkOrders.find((w) => w.id === woId);
  const incident = incidents.find((i) => i.id === wo?.incident_id);
  const task = tasks.find((t) => t.id === wo?.task_id);
  const woEvidence = useMemo(() => evidence.filter((e) => e.work_order_id === woId), [evidence, woId]);
  const before = woEvidence.filter((e) => e.capture_phase === 'BEFORE');
  const after = woEvidence.filter((e) => e.capture_phase === 'AFTER');

  if (!wo) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <button type="button" onClick={onBack} className="min-h-11 inline-flex items-center gap-2 text-blue-700 font-medium">
          <IconArrowLeft className="w-5 h-5" /> Việc của tôi
        </button>
        <Banner kind="error">Không tìm thấy công việc này hoặc việc không còn được giao cho bạn.</Banner>
      </div>
    );
  }

  const flow = getFieldFlow(wo, incident?.category, task);
  const step = getTechnicianStep(wo, woEvidence, incident?.category, task);
  const loc = incident?.location_json;
  const title = task?.title || incident?.title || 'Công việc hiện trường';
  const address = `Tòa ${loc?.towerCode || '—'}${loc?.floor != null ? ` · Tầng ${loc.floor}` : ''}${loc?.apartmentCode ? ` · Căn ${loc.apartmentCode}` : ''}`;

  const act = (fn: () => void, success?: string) => {
    setError(null);
    try {
      fn();
      if (success) setNotice(success);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.');
      document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' });
      return false;
    }
  };

  const addPhoto = (phase: 'BEFORE' | 'AFTER' | 'OTHER') => (fileUrl: string, fileName: string, sizeBytes: number) =>
    act(() =>
      addEvidence({
        incident_id: wo.incident_id,
        task_id: wo.task_id,
        work_order_id: wo.id,
        capture_phase: phase,
        file_url: fileUrl,
        caption: phase === 'BEFORE' ? 'Hiện trạng trước khi làm' : phase === 'AFTER' ? 'Hiện trường sau khi làm' : 'Ảnh hiện trường an ninh',
        fileMetadata: { fileName, sizeBytes },
      }),
    );

  const isCleaning = flow.kind === 'CLEANING';
  const isSecurity = flow.kind === 'SECURITY';
  const scenePhotos = woEvidence.filter((e) => e.capture_phase === 'OTHER');
  const repeatCount =
    isSecurity && loc?.apartmentCode
      ? incidents.filter(
          (i) =>
            i.id !== incident?.id &&
            i.category === incident?.category &&
            i.location_json.apartmentCode === loc.apartmentCode &&
            Date.now() - new Date(i.created_at).getTime() < 7 * 24 * 3600 * 1000,
        ).length
      : 0;
  const agreedIds = new Set(flow.agreement?.quote_snapshot.map((l) => l.id) || []);

  // ---------------- Body per stage ----------------
  const body = (() => {
    if (isSecurity && step.stage === 'IN_PROGRESS') {
      return (
        <SecuritySteps
          flow={flow}
          photos={scenePhotos}
          note={flow.report_final_note}
          onNoteChange={(v) => act(() => ops.setReportNote(wo.id, v))}
          onAddPhoto={addPhoto('OTHER')}
          onOutcome={(o) => act(() => ops.setSecurityOutcome(wo.id, o))}
        />
      );
    }
    if (isCleaning && step.stage === 'IN_PROGRESS') {
      return (
        <CleaningSteps
          flow={flow}
          before={before}
          after={after}
          note={finalNote}
          onNoteChange={setFinalNote}
          onAddPhoto={addPhoto}
          onPlaceSign={() => act(() => ops.placeWarningSign(wo.id))}
          onCleaned={() => act(() => ops.markCleaned(wo.id))}
        />
      );
    }
    switch (step.stage) {
      case 'ASSIGNED':
      case 'ACCEPTED':
        return null;
      case 'ON_SITE':
        return (
          <Section title="Tình trạng thực tế">
            <textarea
              defaultValue={flow.diagnosis_note}
              onBlur={(e) => e.target.value !== flow.diagnosis_note && act(() => ops.setDiagnosisNote(wo.id, e.target.value))}
              rows={3}
              placeholder="Ghi nhanh tình trạng sau khi kiểm tra (không bắt buộc)"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
            />
            <p className="text-sm text-slate-500">Trao đổi với cư dân cần sửa gì. Nếu cần thay vật tư hoặc tính tiền công, bấm “Lập danh mục vật tư”.</p>
          </Section>
        );
      case 'QUOTE_DRAFT':
        return (
          <Section title="Danh mục vật tư & chi phí">
            <QuoteEditor quote={flow.quote} mode="draft" onChange={(q) => act(() => ops.saveQuote(wo.id, q))} />
          </Section>
        );
      case 'AWAITING_RESIDENT_AGREEMENT':
        return (
          <Section title="Đang chờ cư dân đồng ý">
            <p className="text-base text-slate-600">Danh mục {formatVnd(quoteTotal(flow.quote.lines, flow.quote.labor_cost))} đang chờ cư dân đọc và bấm đồng ý.</p>
          </Section>
        );
      case 'IN_PROGRESS':
        return (
          <>
            <Section title="1. Ảnh trước khi sửa">
              <PhotoCapture phase="BEFORE" photos={before} onAdd={addPhoto('BEFORE')} />
            </Section>
            <Section title="2. Các bước thực hiện" right={<span className="text-sm text-slate-500">{flow.checklist.filter((c) => c.done).length}/{flow.checklist.length}</span>}>
              <ul className="space-y-2">
                {flow.checklist.map((c) => (
                  <li key={c.id}>
                    <label className="flex items-center gap-3 min-h-12 px-3 rounded-lg border border-slate-200 cursor-pointer has-[:checked]:bg-emerald-50 has-[:checked]:border-emerald-200">
                      <input type="checkbox" checked={c.done} onChange={() => act(() => ops.toggleChecklistItem(wo.id, c.id))} className="w-6 h-6 accent-emerald-600 shrink-0" />
                      <span className={`text-base ${c.done ? 'text-slate-500 line-through' : 'text-slate-800'}`}>{c.label}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </Section>
            {!flow.no_charge && (
              <Section title="Vật tư" right={<span className="text-sm text-slate-500">Đã thống nhất {formatVnd(flow.agreement?.total || 0)}</span>}>
                <QuoteEditor quote={flow.quote} mode="additional" agreedLineIds={agreedIds} onChange={(q) => act(() => ops.saveQuote(wo.id, q))} />
              </Section>
            )}
            <Section title="3. Ảnh sau khi sửa">
              <PhotoCapture
                phase="AFTER"
                photos={after}
                disabled={before.length === 0}
                disabledHint="Chụp ảnh TRƯỚC khi sửa trước đã."
                onAdd={addPhoto('AFTER')}
              />
            </Section>
          </>
        );
      case 'PAUSED':
        return (
          <Section title="Đang tạm dừng">
            <p className="text-base text-slate-700">Lý do: {flow.pause_reason ? ALL_PAUSE_LABELS[flow.pause_reason] : '—'}</p>
            {flow.pause_note && <p className="text-base text-slate-600">{flow.pause_note}</p>}
          </Section>
        );
      case 'AWAITING_RESIDENT_SIGNATURE':
        return (
          <Section title="Đang chờ cư dân ký xác nhận">
            <p className="text-base text-slate-600">Đưa máy cho cư dân xem lại danh mục cuối và ký tên.</p>
          </Section>
        );
      case 'REPORT_READY':
        return (
          <>
            <ReportSummary flow={flow} before={before} after={after} />
            <Section title="Ghi chú gửi kèm báo cáo">
              <textarea
                value={finalNote}
                onChange={(e) => setFinalNote(e.target.value)}
                rows={3}
                placeholder="VD: Đã thay van, chạy thử 5 phút không rò rỉ"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
              />
            </Section>
          </>
        );
      default:
        return (
          <>
            {step.stage === 'DISPUTED' && flow.dispute_note && <Banner kind="error">Cư dân chưa đồng ý: {flow.dispute_note}. BQL sẽ liên hệ xử lý.</Banner>}
            {step.stage === 'DECLINED' && <Banner kind="error">Bạn đã từ chối việc này{flow.decline_reason ? `: ${DECLINE_REASON_LABELS[flow.decline_reason]}` : ''}.</Banner>}
            {isSecurity && flow.security_outcome && (
              <Section title="Kết quả nhắc nhở">
                <p className="text-base font-semibold text-slate-800">{SECURITY_OUTCOME_LABELS[flow.security_outcome]}</p>
              </Section>
            )}
            {flow.report_final_note && <Section title="Ghi chú báo cáo"><p className="text-base text-slate-700">{flow.report_final_note}</p></Section>}
            {step.stage !== 'DECLINED' && !isSecurity && <ReportSummary flow={flow} before={before} after={after} />}
            {step.stage !== 'DECLINED' && isSecurity && (
              <Section title="Ảnh hiện trường">
                <div className="flex gap-1.5 overflow-x-auto">
                  {scenePhotos.map((p) => (
                    <img key={p.id} src={p.file_url} alt="Ảnh hiện trường" className="w-20 h-20 rounded-lg object-cover border border-slate-200 shrink-0" />
                  ))}
                  {scenePhotos.length === 0 && <p className="text-sm text-slate-400">Không có ảnh</p>}
                </div>
              </Section>
            )}
          </>
        );
    }
  })();

  // ---------------- Bottom bar per stage ----------------
  const bar = (() => {
    switch (step.stage) {
      case 'ASSIGNED':
        return (
          <BottomActionBar>
            <ActionButton variant="danger" grow={false} onClick={() => setSheet('decline')}>Từ chối</ActionButton>
            <ActionButton onClick={() => act(() => ops.acceptJob(wo.id))}><IconCheck className="w-5 h-5" /> Nhận việc</ActionButton>
          </BottomActionBar>
        );
      case 'ACCEPTED':
        return (
          <BottomActionBar>
            <ActionButton variant="secondary" grow={false} onClick={() => setSheet('pause')}><IconPlayerPause className="w-5 h-5" /></ActionButton>
            <ActionButton onClick={() => act(() => ops.checkIn(wo.id))}><IconMapPin className="w-5 h-5" /> Tôi đã đến</ActionButton>
          </BottomActionBar>
        );
      case 'ON_SITE':
        return (
          <BottomActionBar>
            <ActionButton variant="secondary" onClick={() => act(() => ops.startNoCharge(wo.id))}>Không tính phí</ActionButton>
            <ActionButton onClick={() => act(() => ops.startQuote(wo.id))}>Lập danh mục vật tư</ActionButton>
          </BottomActionBar>
        );
      case 'QUOTE_DRAFT':
        return (
          <BottomActionBar hint={<ChecklistGate blockers={step.blockers} />}>
            <ActionButton disabled={step.blockers.length > 0} onClick={() => act(() => ops.handToResidentForAgreement(wo.id)) && setHandover('agree')}>
              <IconDeviceMobileShare className="w-5 h-5" /> Đưa máy cho cư dân xem
            </ActionButton>
          </BottomActionBar>
        );
      case 'AWAITING_RESIDENT_AGREEMENT':
        return (
          <BottomActionBar>
            <ActionButton variant="secondary" onClick={() => act(() => ops.residentRequestChanges(wo.id))}>Sửa danh mục</ActionButton>
            <ActionButton onClick={() => setHandover('agree')}><IconDeviceMobileShare className="w-5 h-5" /> Mở màn hình cư dân</ActionButton>
          </BottomActionBar>
        );
      case 'IN_PROGRESS':
        if (isSecurity) {
          return (
            <BottomActionBar hint={<ChecklistGate blockers={step.blockers} />}>
              <ActionButton variant="secondary" grow={false} onClick={() => setSheet('pause')}><IconPlayerPause className="w-5 h-5" /> Tạm dừng</ActionButton>
              <ActionButton
                variant="success"
                disabled={step.blockers.length > 0}
                onClick={() => act(() => ops.completeSecurity(wo.id), 'Đã hoàn thành. AI sẽ báo lại cho người phản ánh.')}
              >
                <IconCheck className="w-5 h-5" /> Hoàn thành
              </ActionButton>
            </BottomActionBar>
          );
        }
        if (isCleaning) {
          return (
            <BottomActionBar hint={<ChecklistGate blockers={step.blockers} />}>
              <ActionButton variant="secondary" grow={false} onClick={() => setSheet('pause')}><IconPlayerPause className="w-5 h-5" /> Tạm dừng</ActionButton>
              <ActionButton
                variant="success"
                disabled={step.blockers.length > 0}
                onClick={() => act(() => ops.completeCleaning(wo.id, finalNote), 'Đã hoàn thành. AI sẽ thông báo cho cư dân khu vực đã được làm sạch.')}
              >
                <IconCheck className="w-5 h-5" /> Hoàn thành
              </ActionButton>
            </BottomActionBar>
          );
        }
        return (
          <BottomActionBar hint={<ChecklistGate blockers={step.blockers} />}>
            <ActionButton variant="secondary" grow={false} onClick={() => setSheet('pause')}><IconPlayerPause className="w-5 h-5" /> Tạm dừng</ActionButton>
            <ActionButton variant="success" disabled={step.blockers.length > 0} onClick={() => act(() => ops.requestSignature(wo.id)) && setHandover('sign')}>
              <IconDeviceMobileShare className="w-5 h-5" /> Cho cư dân ký
            </ActionButton>
          </BottomActionBar>
        );
      case 'PAUSED':
        return (
          <BottomActionBar>
            <ActionButton onClick={() => act(() => ops.resumeJob(wo.id))}><IconPlayerPlay className="w-5 h-5" /> Tiếp tục</ActionButton>
          </BottomActionBar>
        );
      case 'AWAITING_RESIDENT_SIGNATURE':
        return (
          <BottomActionBar>
            <ActionButton variant="secondary" onClick={() => act(() => ops.backToWork(wo.id))}>Quay lại sửa</ActionButton>
            <ActionButton variant="success" onClick={() => setHandover('sign')}><IconDeviceMobileShare className="w-5 h-5" /> Mở màn hình ký</ActionButton>
          </BottomActionBar>
        );
      case 'REPORT_READY':
        return (
          <BottomActionBar>
            <ActionButton onClick={() => act(() => ops.submitReport(wo.id, finalNote), 'Đã gửi báo cáo cho AI. Việc sẽ hoàn thành khi cư dân xác nhận hoặc sau 72 giờ.')}>
              <IconSend className="w-5 h-5" /> Gửi báo cáo
            </ActionButton>
          </BottomActionBar>
        );
      default:
        return null;
    }
  })();

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <button type="button" onClick={onBack} className="min-h-11 -ml-1 inline-flex items-center gap-2 text-blue-700 font-medium">
        <IconArrowLeft className="w-5 h-5" /> Việc của tôi
      </button>

      {step.stepIndex <= 3 && <StepProgress current={step.stepIndex} kind={flow.kind} />}

      {error && <Banner kind="error" onClose={() => setError(null)}>{error}</Banner>}
      {notice && <Banner kind="success" onClose={() => setNotice(null)}>{notice}</Banner>}

      {/* Job header */}
      <section className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <SeverityBadge severity={incident?.severity} />
          <StatusPill tone={step.tone}>{step.label}</StatusPill>
        </div>
        <h1 className="!text-xl font-semibold text-slate-900 leading-snug">{title}</h1>
        <p className="text-base text-slate-700 inline-flex items-start gap-1.5">
          <IconMapPin className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" /> {address}
        </p>
        {step.tab === 'WAITING' ? (
          step.stage === 'AWAITING_COMPLETION' && <AutoCompleteCountdown autoCompleteAt={flow.auto_complete_at} now={now} />
        ) : step.tab !== 'HISTORY' ? (
          <SlaCountdown dueAt={incident?.sla_due_at} now={now} />
        ) : null}
        {flow.rework_note && step.tab !== 'HISTORY' && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-base text-rose-800 flex gap-2">
            <IconRotateClockwise className="w-5 h-5 shrink-0" />
            <span><b>Làm lại (lần {wo.attempt_no}).</b> Cư dân phản ánh: {flow.rework_note}</span>
          </div>
        )}
        {isSecurity && step.tab !== 'HISTORY' && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-1.5 text-sm text-slate-700">
            {repeatCount > 0 && (
              <p className="font-semibold text-rose-700">Căn này đã bị phản ánh {repeatCount} lần trong 7 ngày qua (đây là lần thứ {repeatCount + 1}).</p>
            )}
            <p>Giờ yên tĩnh theo nội quy: 22:00 – 06:00.</p>
            <p className="text-slate-500">Không tiết lộ danh tính người phản ánh khi nhắc nhở.</p>
          </div>
        )}
        {step.stepIndex <= 2 && (
          <>
            {loc?.description && (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-slate-500">{isSecurity ? 'Nội dung phản ánh' : 'Cư dân mô tả'}</p>
                <p className="text-base text-slate-700">{loc.description}</p>
              </div>
            )}
            <div className="rounded-lg bg-indigo-50/70 border border-indigo-100 p-3 space-y-1">
              <p className="text-sm font-semibold text-indigo-700 inline-flex items-center gap-1.5"><IconSparkles className="w-4 h-4" /> AI đánh giá</p>
              <p className="text-base text-slate-700">{incident?.title || title}</p>
              {incident?.category && <p className="text-sm text-slate-500">Loại sự cố: {incident.category}</p>}
            </div>
          </>
        )}
      </section>

      {body}

      {step.stage === 'AWAITING_COMPLETION' && (
        <Section title="Giả lập phía cư dân (demo)">
          <p className="text-sm text-slate-500">Dùng để demo khi chưa có app cư dân.</p>
          <div className="flex flex-wrap gap-2">
            <ActionButton variant="success" onClick={() => act(() => ops.simulateResidentConfirm(wo.id), 'Cư dân đã xác nhận hoàn thành.')}>Cư dân xác nhận</ActionButton>
            <ActionButton variant="danger" onClick={() => setSheet('rework')}>Cư dân báo lỗi</ActionButton>
            <ActionButton variant="secondary" onClick={() => act(() => ops.simulateFastForward72h(wo.id), 'Đã qua 72 giờ: tự động hoàn thành.')}>Tua nhanh 72 giờ</ActionButton>
          </div>
        </Section>
      )}

      {bar}

      {sheet === 'decline' && (
        <ReasonSheet<DeclineReason>
          title="Lý do từ chối việc"
          reasons={DECLINE_REASON_LABELS}
          requireNoteFor="OTHER"
          confirmLabel="Từ chối"
          onClose={() => setSheet(null)}
          onConfirm={(reason, note) => {
            if (reason && act(() => ops.declineJob(wo.id, reason, note))) {
              setSheet(null);
              onBack();
            }
          }}
        />
      )}
      {sheet === 'pause' && (
        <ReasonSheet<PauseReason | CleaningPauseReason>
          title="Tạm dừng công việc"
          reasons={isSecurity ? SECURITY_PAUSE_REASON_LABELS : isCleaning ? CLEANING_PAUSE_REASON_LABELS : PAUSE_REASON_LABELS}
          requireNoteFor="OTHER"
          confirmLabel="Tạm dừng"
          onClose={() => setSheet(null)}
          onConfirm={(reason, note) => reason && act(() => ops.pauseJob(wo.id, reason, note)) && setSheet(null)}
        />
      )}
      {sheet === 'rework' && (
        <ReasonSheet<never>
          title="Cư dân phản ánh lỗi"
          reasons={null}
          noteRequired
          confirmLabel="Tạo lượt làm lại"
          onClose={() => setSheet(null)}
          onConfirm={(_, note) => {
            if (act(() => ops.simulateResidentIssue(wo.id, note))) {
              setSheet(null);
              onBack();
            }
          }}
        />
      )}

      {handover && (
        <ResidentHandover
          mode={handover}
          flow={flow}
          title={title}
          address={address}
          beforePhotos={before}
          afterPhotos={after}
          onAgree={() => ops.residentAgree(wo.id)}
          onRequestChanges={() => ops.residentRequestChanges(wo.id)}
          onCancelJob={() => ops.residentCancel(wo.id)}
          onSign={(url) => ops.residentSign(wo.id, url)}
          onDispute={(note) => ops.residentDispute(wo.id, note)}
          onExit={() => setHandover(null)}
        />
      )}
    </div>
  );
}
