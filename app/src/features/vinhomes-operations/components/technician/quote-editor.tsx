import { useMemo, useState } from 'react';
import { IconMinus, IconPlus, IconSearch, IconTrash } from '@tabler/icons-react';
import { MATERIAL_CATALOG, formatVnd } from '../../lib/field-flow';
import { quoteTotal, type FieldQuote, type QuoteLine } from '../../types/field-flow';

let lineSeq = 0;
const newLineId = () => `ql-${Date.now().toString(36)}-${(lineSeq++).toString(36)}`;

/**
 * mode 'draft'      – full edit before the resident agrees
 * mode 'additional' – agreed lines are frozen; new lines are "phát sinh" and need a reason
 */
export function QuoteEditor({
  quote,
  mode,
  agreedLineIds,
  onChange,
}: {
  quote: FieldQuote;
  mode: 'draft' | 'additional';
  agreedLineIds?: Set<string>;
  onChange: (next: FieldQuote) => void;
}) {
  const [search, setSearch] = useState('');
  const [pickerOpen, setPickerOpen] = useState(mode === 'draft' && quote.lines.length === 0);
  const [customName, setCustomName] = useState('');
  const [customPrice, setCustomPrice] = useState('');
  const [customUnit, setCustomUnit] = useState('cái');

  const isFrozen = (l: QuoteLine) => mode === 'additional' && !!agreedLineIds?.has(l.id);

  const results = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? MATERIAL_CATALOG.filter((m) => m.name.toLowerCase().includes(q) || m.code.toLowerCase().includes(q)) : MATERIAL_CATALOG;
  }, [search]);

  const update = (lines: QuoteLine[], patch?: Partial<FieldQuote>) => onChange({ ...quote, ...patch, lines });

  const addLine = (line: Omit<QuoteLine, 'id' | 'amount' | 'is_additional' | 'additional_reason'>) => {
    const existing = quote.lines.find((l) => l.material_code && l.material_code === line.material_code && !isFrozen(l));
    if (existing) {
      setQty(existing.id, existing.quantity + 1);
      return;
    }
    update([
      ...quote.lines,
      { ...line, id: newLineId(), amount: line.quantity * line.unit_price, is_additional: mode === 'additional', additional_reason: null },
    ]);
  };

  const setQty = (id: string, qty: number) => {
    if (qty <= 0) {
      update(quote.lines.filter((l) => l.id !== id));
      return;
    }
    update(quote.lines.map((l) => (l.id === id ? { ...l, quantity: qty, amount: qty * l.unit_price } : l)));
  };

  const setReason = (id: string, reason: string) =>
    update(quote.lines.map((l) => (l.id === id ? { ...l, additional_reason: reason } : l)));

  const addCustom = () => {
    const price = Number(customPrice.replace(/\D/g, ''));
    if (!customName.trim() || !price) return;
    addLine({ material_code: null, name: customName.trim(), quantity: 1, unit: customUnit || 'cái', unit_price: price });
    setCustomName('');
    setCustomPrice('');
  };

  const total = quoteTotal(quote.lines, quote.labor_cost);

  return (
    <div className="space-y-4">
      {/* Lines */}
      {quote.lines.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có vật tư nào. Bấm “Thêm vật tư” để chọn.</p>
      ) : (
        <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg">
          {quote.lines.map((l) => (
            <li key={l.id} className="p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-base font-medium text-slate-800">
                    {l.name}
                    {l.is_additional && <span className="ml-2 text-xs font-semibold text-orange-700 bg-orange-50 px-1.5 py-0.5 rounded">Phát sinh</span>}
                  </p>
                  <p className="text-sm text-slate-500">{formatVnd(l.unit_price)} / {l.unit}</p>
                </div>
                <p className="text-base font-semibold text-slate-800 shrink-0">{formatVnd(l.amount)}</p>
              </div>
              {isFrozen(l) ? (
                <p className="text-xs text-slate-400">Đã được cư dân đồng ý · {l.quantity} {l.unit}</p>
              ) : (
                <div className="flex items-center gap-2">
                  <button type="button" aria-label="Giảm" onClick={() => setQty(l.id, l.quantity - 1)} className="w-11 h-11 rounded-lg border border-slate-300 flex items-center justify-center">
                    {l.quantity === 1 ? <IconTrash className="w-5 h-5 text-rose-500" /> : <IconMinus className="w-5 h-5" />}
                  </button>
                  <span className="w-12 text-center text-base font-semibold">{l.quantity}</span>
                  <button type="button" aria-label="Tăng" onClick={() => setQty(l.id, l.quantity + 1)} className="w-11 h-11 rounded-lg border border-slate-300 flex items-center justify-center">
                    <IconPlus className="w-5 h-5" />
                  </button>
                  <span className="text-sm text-slate-500">{l.unit}</span>
                </div>
              )}
              {l.is_additional && !isFrozen(l) && (
                <input
                  value={l.additional_reason || ''}
                  onChange={(e) => setReason(l.id, e.target.value)}
                  placeholder="Lý do phát sinh (bắt buộc)"
                  className={`w-full min-h-11 rounded-lg border px-3 text-base ${l.additional_reason?.trim() ? 'border-slate-300' : 'border-orange-300 bg-orange-50/40'}`}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Picker */}
      {pickerOpen ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-3 space-y-3">
          <div className="relative">
            <IconSearch className="w-5 h-5 absolute left-3 top-3 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm vật tư (van, ống, aptomat…)"
              className="w-full min-h-11 rounded-lg border border-slate-300 bg-white pl-10 pr-3 text-base"
            />
          </div>
          <ul className="max-h-64 overflow-y-auto divide-y divide-slate-100 bg-white rounded-lg border border-slate-200">
            {results.map((m) => (
              <li key={m.code}>
                <button
                  type="button"
                  onClick={() => addLine({ material_code: m.code, name: m.name, quantity: 1, unit: m.unit, unit_price: m.unit_price })}
                  className="w-full min-h-12 px-3 py-2 flex items-center justify-between gap-2 text-left hover:bg-blue-50"
                >
                  <span className="text-base text-slate-800">{m.name}</span>
                  <span className="text-sm text-slate-500 shrink-0">{formatVnd(m.unit_price)}/{m.unit}</span>
                </button>
              </li>
            ))}
            {results.length === 0 && <li className="p-3 text-sm text-slate-500">Không có trong danh mục. Nhập tay bên dưới.</li>}
          </ul>
          <div className="grid grid-cols-[1fr_7rem_4rem] gap-2">
            <input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="Vật tư khác" className="min-h-11 rounded-lg border border-slate-300 px-3 text-base min-w-0" />
            <input value={customPrice} onChange={(e) => setCustomPrice(e.target.value)} inputMode="numeric" placeholder="Đơn giá" className="min-h-11 rounded-lg border border-slate-300 px-3 text-base min-w-0" />
            <input value={customUnit} onChange={(e) => setCustomUnit(e.target.value)} placeholder="ĐVT" className="min-h-11 rounded-lg border border-slate-300 px-2 text-base min-w-0" />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={addCustom} className="flex-1 min-h-11 rounded-lg border border-slate-300 bg-white text-base font-medium">Thêm vật tư nhập tay</button>
            <button type="button" onClick={() => setPickerOpen(false)} className="min-h-11 px-4 rounded-lg text-base text-blue-700 font-medium">Xong</button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="w-full min-h-12 rounded-lg border-2 border-dashed border-blue-300 text-blue-700 text-base font-semibold inline-flex items-center justify-center gap-2"
        >
          <IconPlus className="w-5 h-5" /> {mode === 'additional' ? 'Thêm vật tư phát sinh' : 'Thêm vật tư'}
        </button>
      )}

      {/* Labor, warranty, total */}
      {mode === 'draft' && (
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-sm text-slate-600">Tiền công (đ)</span>
            <input
              value={quote.labor_cost ? quote.labor_cost.toLocaleString('vi-VN') : ''}
              onChange={(e) => update(quote.lines, { labor_cost: Number(e.target.value.replace(/\D/g, '')) || 0 })}
              inputMode="numeric"
              placeholder="0"
              className="w-full min-h-11 rounded-lg border border-slate-300 px-3 text-base"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-slate-600">Bảo hành</span>
            <select
              value={quote.warranty_months}
              onChange={(e) => update(quote.lines, { warranty_months: Number(e.target.value) })}
              className="w-full min-h-11 rounded-lg border border-slate-300 px-3 text-base bg-white"
            >
              {[0, 1, 3, 6, 12].map((m) => (
                <option key={m} value={m}>{m === 0 ? 'Không bảo hành' : `${m} tháng`}</option>
              ))}
            </select>
          </label>
        </div>
      )}
      <div className="flex items-center justify-between rounded-lg bg-slate-900 text-white px-4 py-3">
        <span className="text-base">Tổng cộng{quote.labor_cost > 0 ? ' (gồm công)' : ''}</span>
        <span className="text-xl font-bold">{formatVnd(total)}</span>
      </div>
    </div>
  );
}
