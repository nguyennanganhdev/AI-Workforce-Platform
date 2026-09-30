import type { ReactNode } from 'react';
import { IconCheck } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldLabel } from '@/components/ui/field';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { VhEvidenceRef } from '../../types/evidence';
import type { FieldFlow } from '../../types/field-flow';
import { PhotoCapture } from './photo-capture';

export type CardState = 'done' | 'active' | 'locked';

export function StepCard({ n, title, state, children }: { n: number; title: string; state: CardState; children: ReactNode }) {
  return (
    <Card
      aria-disabled={state === 'locked'}
      className={cn(state === 'active' && 'ring-2 ring-primary', state === 'locked' && 'bg-muted/40')}
    >
      <CardHeader className="flex items-center gap-3 px-4 md:px-5">
        <span
          className={cn(
            'flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-medium tabular-nums',
            state === 'active' && 'bg-primary text-primary-foreground',
            state === 'done' && 'bg-foreground text-background',
            state === 'locked' && 'bg-muted text-muted-foreground',
          )}
        >
          {state === 'done' ? <IconCheck className="size-4" aria-label="Đã xong" /> : n}
        </span>
        <CardTitle className={cn('text-[15px] font-semibold', state === 'locked' && 'text-muted-foreground')}>{title}</CardTitle>
      </CardHeader>
      {state !== 'locked' && <CardContent className="flex flex-col gap-3 px-4 md:px-5">{children}</CardContent>}
    </Card>
  );
}

/** Big tap target, usable with wet gloves. */
function ConfirmTap({ done, doneLabel, label, onClick }: { done: boolean; doneLabel: string; label: string; onClick: () => void }) {
  if (done) return <p className="text-[15px] text-slate-700">{doneLabel}</p>;
  return (
    <Button size="lg" onClick={onClick} className="h-12 w-full text-base md:text-base">
      {label}
    </Button>
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
    <div className="flex flex-col gap-3">
      <StepCard n={++n} title="Chụp ảnh hiện trường TRƯỚC khi làm" state={state(hasBefore, true)}>
        <PhotoCapture phase="BEFORE" photos={before} onAdd={onAddPhoto('BEFORE')} />
      </StepCard>

      {flow.sign_required && (
        <StepCard n={++n} title="Đặt biển cảnh báo sàn ướt" state={state(!!flow.sign_placed_at, hasBefore)}>
          <p className="text-sm text-muted-foreground">Đặt biển trước khi lau để người qua lại không bị trượt ngã.</p>
          <ConfirmTap
            done={!!flow.sign_placed_at}
            doneLabel="Đã đặt biển cảnh báo"
            label="Đã đặt biển"
            onClick={onPlaceSign}
          />
        </StepCard>
      )}

      <StepCard n={++n} title="Lau / làm sạch khu vực" state={state(cleaned, hasBefore && signOk)}>
        <ConfirmTap done={cleaned} doneLabel="Đã làm sạch" label="Đã làm sạch xong" onClick={onCleaned} />
      </StepCard>

      <StepCard n={++n} title="Chụp ảnh SAU khi làm" state={state(hasAfter, cleaned)}>
        <PhotoCapture phase="AFTER" photos={after} onAdd={onAddPhoto('AFTER')} />
        <Field>
          <FieldLabel htmlFor="cleaning-note">Ghi chú thêm (không bắt buộc)</FieldLabel>
          <Textarea id="cleaning-note" value={note} onChange={(e) => onNoteChange(e.target.value)} rows={2} className="text-base md:text-base" />
        </Field>
      </StepCard>
    </div>
  );
}
