import type { ReactNode } from 'react';
import { IconAlertTriangle, IconCheck, IconSparkles } from '@tabler/icons-react';
import type { VhEvidenceRef } from '../../types/evidence';
import type { FieldFlow } from '../../types/field-flow';
import { PhotoCapture } from './photo-capture';

export type CardState = 'done' | 'active' | 'locked';

export function StepCard({ n, title, state, children }: { n: number; title: string; state: CardState; children: ReactNode }) {
  const ring = state === 'done' ? 'border-emerald-200 bg-emerald-50/40' : state === 'active' ? 'border-blue-300 bg-white' : 'border-slate-200 bg-slate-50 opacity-60';
  return (
    <section className={`rounded-xl border-2 p-4 space-y-3 ${ring}`} aria-disabled={state === 'locked'}>
      <div className="flex items-center gap-3">
        <span
          className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-sm font-bold ${
            state === 'done' ? 'bg-emerald-600 text-white' : state === 'active' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-500'
          }`}
        >
          {state === 'done' ? <IconCheck className="w-5 h-5" /> : n}
        </span>
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      </div>
      {state !== 'locked' && children}
    </section>
  );
}

/** Big tap target, usable with wet gloves. */
function ConfirmTap({ done, doneLabel, label, icon, onClick }: { done: boolean; doneLabel: string; label: string; icon: ReactNode; onClick: () => void }) {
  if (done) return <p className="text-base text-emerald-700 font-medium">✓ {doneLabel}</p>;
  return (
    <button type="button" onClick={onClick} className="w-full min-h-14 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-lg font-semibold inline-flex items-center justify-center gap-2">
      {icon} {label}
    </button>
  );
}

export function CleaningSteps({
  flow,
  before,
  after,
  note,
  onNoteChange,
  onAddPhoto,
  onPlaceSign,
  onCleaned,
}: {
  flow: FieldFlow;
  before: VhEvidenceRef[];
  after: VhEvidenceRef[];
  note: string;
  onNoteChange: (v: string) => void;
  onAddPhoto: (phase: 'BEFORE' | 'AFTER') => (fileUrl: string, fileName: string, sizeBytes: number) => void;
  onPlaceSign: () => void;
  onCleaned: () => void;
}) {
  const hasBefore = before.length > 0;
  const signOk = !flow.sign_required || !!flow.sign_placed_at;
  const cleaned = !!flow.cleaned_at;
  const hasAfter = after.length > 0;
  const state = (done: boolean, unlocked: boolean): CardState => (done ? 'done' : unlocked ? 'active' : 'locked');

  let n = 0;
  return (
    <div className="space-y-3">
      <StepCard n={++n} title="Chụp ảnh hiện trường TRƯỚC khi làm" state={state(hasBefore, true)}>
        <PhotoCapture phase="BEFORE" photos={before} onAdd={onAddPhoto('BEFORE')} />
      </StepCard>

      {flow.sign_required && (
        <StepCard n={++n} title="Đặt biển cảnh báo sàn ướt" state={state(!!flow.sign_placed_at, hasBefore)}>
          <p className="text-sm text-slate-600">Đặt biển trước khi lau để người qua lại không bị trượt ngã.</p>
          <ConfirmTap
            done={!!flow.sign_placed_at}
            doneLabel="Đã đặt biển cảnh báo"
            label="Đã đặt biển"
            icon={<IconAlertTriangle className="w-6 h-6" />}
            onClick={onPlaceSign}
          />
        </StepCard>
      )}

      <StepCard n={++n} title="Lau / làm sạch khu vực" state={state(cleaned, hasBefore && signOk)}>
        <ConfirmTap done={cleaned} doneLabel="Đã làm sạch" label="Đã làm sạch xong" icon={<IconSparkles className="w-6 h-6" />} onClick={onCleaned} />
      </StepCard>

      <StepCard n={++n} title="Chụp ảnh SAU khi làm" state={state(hasAfter, cleaned)}>
        <PhotoCapture phase="AFTER" photos={after} onAdd={onAddPhoto('AFTER')} />
        <textarea
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
          rows={2}
          placeholder="Ghi chú thêm (không bắt buộc)"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-base"
        />
      </StepCard>
    </div>
  );
}
