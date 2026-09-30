import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { IconArrowUp, IconPhoto, IconX } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { readPhotos } from '../lib/photos';
import { MAX_MESSAGE_LENGTH, MAX_PHOTOS } from '../lib/reception-agent';
import type { Photo } from '../types';

export function Composer({
  onSend,
  suggestions = [],
  placeholder = 'Nhắn cho trợ lý…',
}: {
  /** Throws when the message was not accepted, so the input is kept. */
  onSend: (text: string, photos: Photo[]) => void;
  suggestions?: string[];
  placeholder?: string;
}) {
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const send = (value: string, attached: Photo[]) => {
    if (!value.trim() && attached.length === 0) return;
    setError(null);
    try {
      onSend(value, attached);
      setText('');
      setPhotos([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chưa gửi được, bạn thử lại nhé.');
    }
  };

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    send(text, photos);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const pick = async (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    setReading(true);
    try {
      const list = Array.from(files).slice(0, MAX_PHOTOS - photos.length);
      if (list.length === 0) throw new Error('Mỗi lần gửi tối đa 3 ảnh.');
      const read = await readPhotos(list);
      setPhotos((prev) => [...prev, ...read].slice(0, MAX_PHOTOS));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không đọc được ảnh.');
    } finally {
      setReading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {suggestions.length > 0 && (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-0.5">
          {suggestions.map((s) => (
            <Button key={s} variant="outline" size="sm" className="rounded-full" onClick={() => send(s, [])}>
              {s}
            </Button>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <form onSubmit={submit} className="flex flex-col gap-2 rounded-2xl border bg-card p-2 shadow-xs focus-within:ring-3 focus-within:ring-ring/30">
        {photos.length > 0 && (
          <div className="flex gap-2 px-1 pt-1">
            {photos.map((p) => (
              <span key={p.id} className="relative">
                <img src={p.url} alt={p.name} className="size-14 rounded-lg border object-cover" />
                <button
                  type="button"
                  aria-label={`Bỏ ảnh ${p.name}`}
                  onClick={() => setPhotos((prev) => prev.filter((x) => x.id !== p.id))}
                  className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-foreground text-background"
                >
                  <IconX className="size-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          maxLength={MAX_MESSAGE_LENGTH}
          rows={1}
          aria-label="Tin nhắn"
          placeholder={placeholder}
          className="max-h-40 min-h-10 resize-none border-0 bg-transparent px-2 py-2 text-[15px] shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
        <div className="flex items-center justify-between">
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="sr-only"
            tabIndex={-1}
            onChange={(e) => pick(e.target.files)}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-lg"
            aria-label="Đính kèm ảnh"
            disabled={reading || photos.length >= MAX_PHOTOS}
            onClick={() => fileInput.current?.click()}
          >
            <IconPhoto />
          </Button>
          <Button type="submit" size="icon-lg" aria-label="Gửi" disabled={reading || (!text.trim() && photos.length === 0)} className="rounded-full">
            <IconArrowUp />
          </Button>
        </div>
      </form>
    </div>
  );
}
