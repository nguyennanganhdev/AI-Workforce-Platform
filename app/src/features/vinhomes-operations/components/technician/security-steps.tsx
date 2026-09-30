import { IconShieldLock } from '@tabler/icons-react';
import type { VhEvidenceRef } from '../../types/evidence';
import { SECURITY_OUTCOME_LABELS, type FieldFlow, type SecurityOutcome } from '../../types/field-flow';
import { StepCard } from './cleaning-steps';
import { PhotoCapture } from './photo-capture';

const OUTCOME_STYLE: Record<SecurityOutcome, string> = {
  COOPERATED: 'border-emerald-500 bg-emerald-50 text-emerald-800',
  NO_ANSWER: 'border-amber-500 bg-amber-50 text-amber-800',
  UNCOOPERATIVE: 'border-rose-500 bg-rose-50 text-rose-800',
};

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
    <div className="space-y-3">
      <StepCard n={1} title="Chụp ảnh hiện trường" state={hasPhoto ? 'done' : 'active'}>
        <p className="text-sm text-slate-600 inline-flex items-start gap-1.5">
          <IconShieldLock className="w-4 h-4 shrink-0 mt-0.5 text-slate-400" />
          Chụp cửa căn hộ hoặc hành lang. Không chụp mặt người, không chụp vào trong căn hộ.
        </p>
        <PhotoCapture phase="OTHER" photos={photos} onAdd={onAddPhoto} />
      </StepCard>

      <StepCard n={2} title="Gõ cửa nhắc nhở · Kết quả" state={outcome ? 'done' : hasPhoto ? 'active' : 'locked'}>
        <fieldset aria-label="Kết quả nhắc nhở" className="grid gap-2">
          {(Object.keys(SECURITY_OUTCOME_LABELS) as SecurityOutcome[]).map((o) => (
            <button
              key={o}
              type="button"
              aria-pressed={outcome === o}
              onClick={() => onOutcome(o)}
              className={`min-h-14 rounded-xl border-2 px-4 text-left text-lg font-semibold ${
                outcome === o ? OUTCOME_STYLE[o] : 'border-slate-200 bg-white text-slate-700'
              }`}
            >
              {SECURITY_OUTCOME_LABELS[o]}
            </button>
          ))}
        </fieldset>
        {outcome && <p className="text-sm text-slate-600">{OUTCOME_HINT[outcome]}</p>}
        {outcome && (
          <textarea
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
            rows={3}
            placeholder={noteRequired ? 'Diễn biến sự việc (bắt buộc)' : 'Ghi chú thêm (không bắt buộc)'}
            className={`w-full rounded-lg border px-3 py-2 text-base ${noteRequired && !note.trim() ? 'border-rose-300 bg-rose-50/40' : 'border-slate-300'}`}
          />
        )}
      </StepCard>
    </div>
  );
}
