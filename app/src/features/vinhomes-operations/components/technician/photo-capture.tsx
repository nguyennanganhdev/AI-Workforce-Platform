import { useRef, useState } from 'react';
import { IconCamera } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import type { VhEvidenceRef } from '../../types/evidence';

type Phase = 'BEFORE' | 'AFTER' | 'OTHER';

const SAMPLE_PHOTOS: Record<Phase, string> = {
  BEFORE: 'https://images.unsplash.com/photo-1584992236310-6edddc08acff?w=720&auto=format&fit=crop&q=60',
  AFTER: 'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=720&auto=format&fit=crop&q=60',
  OTHER: 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=720&auto=format&fit=crop&q=60',
};

const PHASE_LABELS: Record<Phase, string> = {
  BEFORE: 'TRƯỚC khi làm',
  AFTER: 'SAU khi làm',
  OTHER: 'hiện trường',
};

/** Downscale to stay under the mock store's 50k-char data URL limit (see use-operations-data persist). */
function compressImage(file: File, maxSize = 560, quality = 0.5): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Không đọc được ảnh.'));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('Ảnh không hợp lệ.'));
      img.onload = () => {
        const scale = Math.min(1, maxSize / Math.max(img.width, img.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext('2d')?.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

export function PhotoCapture({
  phase,
  photos,
  disabled,
  disabledHint,
  onAdd,
}: {
  phase: Phase;
  photos: VhEvidenceRef[];
  disabled?: boolean;
  disabledHint?: string;
  onAdd: (fileUrl: string, fileName: string, sizeBytes: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const label = PHASE_LABELS[phase];

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      const url = await compressImage(file);
      onAdd(url, file.name, Math.round((url.length * 3) / 4));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">
          Ảnh {label} <span className="font-normal tabular-nums text-muted-foreground">({photos.length})</span>
        </p>
        {!disabled && (
          <Button
            variant="link"
            size="sm"
            className="h-9 px-0 text-muted-foreground"
            onClick={() => onAdd(SAMPLE_PHOTOS[phase], `sample_${phase.toLowerCase()}.jpg`, 60_000)}
          >
            Dùng ảnh mẫu (demo)
          </Button>
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {photos.map((p) => (
          <img key={p.id} src={p.file_url} alt={`Ảnh ${label}`} className="size-24 shrink-0 rounded-md border object-cover" />
        ))}
        <Button
          variant="outline"
          disabled={disabled || busy}
          onClick={() => inputRef.current?.click()}
          className="size-24 shrink-0 flex-col gap-1 border-dashed text-[13px] font-normal"
        >
          <IconCamera className="size-6" />
          {busy ? 'Đang xử lý…' : 'Chụp ảnh'}
        </Button>
      </div>
      {disabled && disabledHint && <p className="text-xs text-muted-foreground">{disabledHint}</p>}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
    </div>
  );
}
