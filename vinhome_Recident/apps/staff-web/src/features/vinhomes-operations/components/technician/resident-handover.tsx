import { useEffect, useRef, useState } from 'react';
import { IconHandFinger, IconShieldCheck } from '@tabler/icons-react';
import type { VhEvidenceRef } from '../../types/evidence';
import { quoteTotal, type FieldFlow, type QuoteLine } from '../../types/field-flow';
import { formatVnd, splitQuote } from '../../lib/field-flow';
import { SignaturePad, type SignaturePadHandle } from './signature-pad';

function LineTable({ lines }: { lines: QuoteLine[] }) {
  return (
    <ul className="divide-y divide-slate-100">
      {lines.map((l) => (
        <li key={l.id} className="py-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-lg text-slate-900">{l.name}</p>
            <p className="text-base md:text-base text-slate-500">{l.quantity} {l.unit} × {formatVnd(l.unit_price)}</p>
            {l.is_additional && l.additional_reason && <p className="text-base md:text-base text-orange-700">Lý do: {l.additional_reason}</p>}
          </div>
          <p className="text-lg font-semibold text-slate-900 shrink-0">{formatVnd(l.amount)}</p>
        </li>
      ))}
    </ul>
  );
}

/** Staff must press-and-hold to leave the resident screen, so a resident cannot exit by accident. */
function HoldToExit({ onExit }: { onExit: () => void }) {
  const [progress, setProgress] = useState(0);
  const timer = useRef<number | null>(null);
  const start = () => {
    const t0 = Date.now();
    timer.current = window.setInterval(() => {
      const p = Math.min(1, (Date.now() - t0) / 1000);
      setProgress(p);
      if (p >= 1) {
        stop();
        onExit();
      }
    }, 30);
  };
  const stop = () => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    setProgress(0);
  };
  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current);
    },
    [],
  );
  return (
    <button
      type="button"
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      className="relative overflow-hidden w-full min-h-14 rounded-xl border border-slate-300 bg-white text-slate-700 text-base md:text-base font-semibold select-none touch-none"
    >
      <span className="absolute inset-y-0 left-0 bg-blue-100" style={{ width: `${progress * 100}%` }} />
      <span className="relative inline-flex items-center gap-2">
        <IconHandFinger className="w-5 h-5" /> Nhân viên: nhấn giữ để quay lại
      </span>
    </button>
  );
}

export function ResidentHandover({
  mode,
  flow,
  title,
  address,
  beforePhotos,
  afterPhotos,
  onAgree,
  onRequestChanges,
  onCancelJob,
  onSign,
  onDispute,
  onExit,
}: {
  mode: 'agree' | 'sign';
  flow: FieldFlow;
  title: string;
  address: string;
  beforePhotos: VhEvidenceRef[];
  afterPhotos: VhEvidenceRef[];
  onAgree: () => void;
  onRequestChanges: () => void;
  onCancelJob: () => void;
  onSign: (dataUrl: string) => void;
  onDispute: (note: string) => void;
  onExit: () => void;
}) {
  const [done, setDone] = useState<string | null>(null);
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeNote, setDisputeNote] = useState('');
  const [hasInk, setHasInk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const padRef = useRef<SignaturePadHandle>(null);

  const { agreed, additional } = splitQuote(flow.quote.lines);
  const agreedTotal = quoteTotal(agreed, flow.quote.labor_cost);
  const additionalTotal = quoteTotal(additional, 0);
  const total = agreedTotal + additionalTotal;
  const noCharge = flow.no_charge;

  const run = (fn: () => void, message: string) => {
    try {
      fn();
      setDone(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Có lỗi xảy ra, vui lòng thử lại.');
    }
  };

  return (
    <div className="fixed inset-0 z-[60] bg-slate-50 overflow-y-auto" role="dialog" aria-modal="true" aria-label="Màn hình dành cho cư dân">
      <div
        className="max-w-2xl mx-auto px-4 space-y-5"
        style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 20px)', paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 24px)' }}
      >
        {done ? (
          <div className="min-h-[80vh] flex flex-col items-center justify-center text-center gap-6">
            <IconShieldCheck className="w-20 h-20 text-emerald-600" />
            <div className="space-y-2">
              <p className="text-2xl font-semibold text-slate-900">{done}</p>
              <p className="text-lg text-slate-600">Vui lòng trả máy cho nhân viên kỹ thuật.</p>
            </div>
            <div className="w-full max-w-sm">
              <HoldToExit onExit={onExit} />
            </div>
          </div>
        ) : (
          <>
            <header className="space-y-1">
              <p className="text-base md:text-base text-blue-700 font-semibold">
                {mode === 'agree' ? 'Kính mời quý cư dân xem danh mục sửa chữa' : 'Kính mời quý cư dân xác nhận kết quả sửa chữa'}
              </p>
              <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
              <p className="text-lg text-slate-600">{address}</p>
              {flow.diagnosis_note && <p className="text-lg text-slate-700">Tình trạng: {flow.diagnosis_note}</p>}
            </header>

            {error && <p role="alert" className="text-lg text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</p>}

            {mode === 'sign' && (beforePhotos.length > 0 || afterPhotos.length > 0) && (
              <section className="grid grid-cols-2 gap-3">
                {[{ label: 'Trước khi sửa', photos: beforePhotos }, { label: 'Sau khi sửa', photos: afterPhotos }].map((g) => (
                  <figure key={g.label} className="space-y-1">
                    {g.photos[0] && <img src={g.photos[g.photos.length - 1].file_url} alt={g.label} className="w-full aspect-square object-cover rounded-xl border border-slate-200" />}
                    <figcaption className="text-base md:text-base text-slate-600 text-center">{g.label}</figcaption>
                  </figure>
                ))}
              </section>
            )}

            {noCharge ? (
              <section className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xl text-slate-900">Không phát sinh chi phí.</p>
              </section>
            ) : (
              <section className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                {mode === 'sign' && additional.length > 0 ? (
                  <>
                    <h2 className="text-lg font-semibold text-slate-700">Đã thống nhất trước khi sửa</h2>
                    <LineTable lines={agreed} />
                    {flow.quote.labor_cost > 0 && (
                      <p className="flex justify-between text-lg"><span>Tiền công</span><span className="font-semibold">{formatVnd(flow.quote.labor_cost)}</span></p>
                    )}
                    <p className="flex justify-between text-lg border-t border-slate-200 pt-2"><span>Cộng</span><span className="font-semibold">{formatVnd(agreedTotal)}</span></p>
                    <h2 className="text-lg font-semibold text-orange-700 pt-2">Phát sinh trong khi sửa</h2>
                    <LineTable lines={additional} />
                    <p className="flex justify-between text-lg text-orange-700"><span>Phát sinh</span><span className="font-semibold">+{formatVnd(additionalTotal)}</span></p>
                  </>
                ) : (
                  <>
                    <LineTable lines={flow.quote.lines} />
                    {flow.quote.labor_cost > 0 && (
                      <p className="flex justify-between text-lg"><span>Tiền công</span><span className="font-semibold">{formatVnd(flow.quote.labor_cost)}</span></p>
                    )}
                  </>
                )}
                <p className="flex justify-between items-center border-t-2 border-slate-900 pt-3">
                  <span className="text-xl font-semibold">TỔNG CỘNG</span>
                  <span className="text-3xl font-bold text-slate-900">{formatVnd(total)}</span>
                </p>
                {flow.quote.warranty_months > 0 && <p className="text-lg text-slate-600">Bảo hành: {flow.quote.warranty_months} tháng</p>}
              </section>
            )}

            {mode === 'agree' ? (
              <div className="space-y-3">
                <button type="button" onClick={() => run(onAgree, 'Cảm ơn quý cư dân đã đồng ý!')} className="w-full min-h-16 rounded-xl bg-emerald-600 text-white text-xl font-semibold">
                  Tôi đồng ý, bắt đầu sửa
                </button>
                <button type="button" onClick={() => run(onRequestChanges, 'Nhân viên sẽ điều chỉnh lại danh mục.')} className="w-full min-h-14 rounded-xl border border-slate-300 bg-white text-lg font-medium text-slate-700">
                  Chưa đồng ý, cần điều chỉnh
                </button>
                <button type="button" onClick={() => run(onCancelJob, 'Đã ghi nhận quý cư dân không sửa.')} className="w-full min-h-12 text-lg text-rose-600">
                  Tôi không muốn sửa nữa
                </button>
              </div>
            ) : disputeOpen ? (
              <div className="space-y-3">
                <label className="block space-y-2">
                  <span className="text-lg text-slate-800">Quý cư dân vui lòng cho biết điểm chưa đồng ý:</span>
                  <textarea value={disputeNote} onChange={(e) => setDisputeNote(e.target.value)} rows={4} className="w-full rounded-xl border border-slate-300 p-3 text-lg" />
                </label>
                <button
                  type="button"
                  disabled={!disputeNote.trim()}
                  onClick={() => run(() => onDispute(disputeNote), 'Ban Quản Lý sẽ liên hệ quý cư dân để giải quyết.')}
                  className="w-full min-h-14 rounded-xl bg-rose-600 text-white text-lg font-semibold disabled:bg-slate-300"
                >
                  Gửi ý kiến cho Ban Quản Lý
                </button>
                <button type="button" onClick={() => setDisputeOpen(false)} className="w-full min-h-12 text-lg text-slate-600">Quay lại ký xác nhận</button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-lg text-slate-800">Quý cư dân ký tên để xác nhận khối lượng công việc và chi phí:</p>
                <SignaturePad ref={padRef} onChange={setHasInk} />
                <button
                  type="button"
                  disabled={!hasInk}
                  onClick={() => {
                    const url = padRef.current?.toDataUrl();
                    if (url) run(() => onSign(url), 'Cảm ơn quý cư dân đã xác nhận!');
                  }}
                  className="w-full min-h-16 rounded-xl bg-emerald-600 text-white text-xl font-semibold disabled:bg-slate-300"
                >
                  Ký xác nhận
                </button>
                {additional.length > 0 && (
                  <button type="button" onClick={() => setDisputeOpen(true)} className="w-full min-h-12 text-lg text-rose-600">
                    Tôi không đồng ý phần phát sinh
                  </button>
                )}
              </div>
            )}

            <div className="pt-4 border-t border-slate-200">
              <HoldToExit onExit={onExit} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
