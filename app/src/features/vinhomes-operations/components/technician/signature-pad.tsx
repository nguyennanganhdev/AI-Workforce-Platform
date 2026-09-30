import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { IconEraser } from '@tabler/icons-react';

export interface SignaturePadHandle {
  /** PNG data URL, or null when nothing has been drawn. */
  toDataUrl: () => string | null;
  clear: () => void;
}

export const SignaturePad = forwardRef<SignaturePadHandle, { onChange?: (hasInk: boolean) => void }>(function SignaturePad(
  { onChange },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const last = useRef<{ x: number; y: number } | null>(null);
  const [hasInk, setHasInk] = useState(false);

  const setInk = useCallback(
    (v: boolean) => {
      setHasInk(v);
      onChange?.(v);
    },
    [onChange],
  );

  const setupCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0f172a';
  }, []);

  useEffect(() => {
    setupCanvas();
  }, [setupCanvas]);

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drawing.current = true;
    last.current = point(e);
  };

  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current || !last.current) return;
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;
    const p = point(e);
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last.current = p;
    if (!hasInk) setInk(true);
  };

  const onUp = () => {
    drawing.current = false;
    last.current = null;
  };

  const clear = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
    setInk(false);
  }, [setInk]);

  useImperativeHandle(ref, () => ({
    toDataUrl: () => (hasInk && canvasRef.current ? canvasRef.current.toDataURL('image/png') : null),
    clear,
  }), [hasInk, clear]);

  return (
    <div className="space-y-2">
      <div className="relative rounded-xl border-2 border-slate-300 bg-white">
        <canvas
          ref={canvasRef}
          className="block w-full h-[38vh] min-h-48 touch-none cursor-crosshair"
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          aria-label="Khung ký tên"
        />
        {!hasInk && (
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-lg text-slate-300">
            Ký tên tại đây
          </span>
        )}
        <div className="pointer-events-none absolute left-6 right-6 bottom-10 border-b border-dashed border-slate-300" />
      </div>
      <button
        type="button"
        onClick={clear}
        disabled={!hasInk}
        className="min-h-11 px-4 rounded-lg border border-slate-300 text-slate-600 inline-flex items-center gap-2 text-base disabled:opacity-40"
      >
        <IconEraser className="w-5 h-5" /> Ký lại
      </button>
    </div>
  );
});
