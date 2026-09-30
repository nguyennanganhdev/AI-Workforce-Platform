import { Field, FieldDescription, FieldLabel } from '@/components/ui/field';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { VhEvidenceRef } from '../../types/evidence';
import { SECURITY_OUTCOME_LABELS, type FieldFlow, type SecurityOutcome } from '../../types/field-flow';
import { StepCard } from './cleaning-steps';
import { PhotoCapture } from './photo-capture';

const OUTCOME_HINT: Record<SecurityOutcome, string> = {
  COOPERATED: 'AI sẽ báo người phản ánh là an ninh đã nhắc nhở.',
  NO_ANSWER: 'Nếu căn này bị phản ánh tiếp, AI sẽ chuyển Ban Quản Lý.',
  UNCOOPERATIVE: 'AI sẽ chuyển Ban Quản Lý xử lý. Ghi rõ diễn biến bên dưới.',
};

export function SecuritySteps({
  flow,
  photos,
  note,
  onNoteChange,
  onAddPhoto,
  onOutcome,
}: {
  flow: FieldFlow;
  photos: VhEvidenceRef[];
  note: string;
  onNoteChange: (v: string) => void;
  onAddPhoto: (fileUrl: string, fileName: string, sizeBytes: number) => void;
  onOutcome: (o: SecurityOutcome) => void;
}) {
  const hasPhoto = photos.length > 0;
  const outcome = flow.security_outcome;
  const noteRequired = outcome === 'UNCOOPERATIVE';

  return (
    <div className="flex flex-col gap-3">
      <StepCard n={1} title="Chụp ảnh hiện trường" state={hasPhoto ? 'done' : 'active'}>
        <p className="text-sm text-muted-foreground">
          Chụp cửa căn hộ hoặc hành lang. Không chụp mặt người, không chụp vào trong căn hộ.
        </p>
        <PhotoCapture phase="OTHER" photos={photos} onAdd={onAddPhoto} />
      </StepCard>

      <StepCard n={2} title="Gõ cửa nhắc nhở và ghi kết quả" state={outcome ? 'done' : hasPhoto ? 'active' : 'locked'}>
        <ToggleGroup
          aria-label="Kết quả nhắc nhở"
          orientation="vertical"
          variant="outline"
          spacing={2}
          value={outcome ? [outcome] : []}
          onValueChange={(next) => next[0] && onOutcome(next[0] as SecurityOutcome)}
          className="w-full"
        >
          {(Object.keys(SECURITY_OUTCOME_LABELS) as SecurityOutcome[]).map((o) => (
            <ToggleGroupItem
              key={o}
              value={o}
              size="lg"
              className="h-12 justify-start px-4 text-base md:text-base font-normal data-pressed:border-primary data-pressed:bg-primary/10 data-pressed:font-medium data-pressed:text-foreground"
            >
              {SECURITY_OUTCOME_LABELS[o]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {outcome && (
          <Field data-invalid={noteRequired && !note.trim() ? true : undefined}>
            <FieldLabel htmlFor="security-note">{noteRequired ? 'Diễn biến sự việc (bắt buộc)' : 'Ghi chú thêm (không bắt buộc)'}</FieldLabel>
            <Textarea
              id="security-note"
              value={note}
              onChange={(e) => onNoteChange(e.target.value)}
              rows={3}
              aria-invalid={noteRequired && !note.trim()}
              className="text-base md:text-base"
            />
            <FieldDescription>{OUTCOME_HINT[outcome]}</FieldDescription>
          </Field>
        )}
      </StepCard>
    </div>
  );
}
