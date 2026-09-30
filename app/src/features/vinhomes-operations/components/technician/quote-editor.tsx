import { useMemo, useState } from 'react';
import { IconMinus, IconPlus, IconSearch, IconTrash } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { InputGroup, InputGroupAddon, InputGroupInput } from '@/components/ui/input-group';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MATERIAL_CATALOG, formatVnd } from '../../lib/field-flow';
import { quoteTotal, type FieldQuote, type QuoteLine } from '../../types/field-flow';

const WARRANTY_ITEMS: Record<string, string> = { '0': 'Không bảo hành', '1': '1 tháng', '3': '3 tháng', '6': '6 tháng', '12': '12 tháng' };

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
    <div className="flex flex-col gap-4">
      {/* Lines */}
      {quote.lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">Chưa có vật tư nào. Bấm “Thêm vật tư” để chọn.</p>
      ) : (
        <ul className="divide-y rounded-md border">
          {quote.lines.map((l) => (
            <li key={l.id} className="flex flex-col gap-2 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-base md:text-base font-medium text-foreground">
                    {l.name}
                    {l.is_additional && <span className="ml-2 text-[13px] font-normal text-muted-foreground">(phát sinh)</span>}
                  </p>
                  <p className="text-sm text-muted-foreground">{formatVnd(l.unit_price)} / {l.unit}</p>
                </div>
                <p className="shrink-0 text-base md:text-base font-semibold tabular-nums text-foreground">{formatVnd(l.amount)}</p>
              </div>
              {isFrozen(l) ? (
                <p className="text-[13px] text-muted-foreground">Cư dân đã đồng ý · {l.quantity} {l.unit}</p>
              ) : (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="icon-lg" className="size-11" aria-label={l.quantity === 1 ? 'Xóa vật tư' : 'Giảm'} onClick={() => setQty(l.id, l.quantity - 1)}>
                    {l.quantity === 1 ? <IconTrash /> : <IconMinus />}
                  </Button>
                  <span className="w-12 text-center text-base md:text-base font-semibold tabular-nums">{l.quantity}</span>
                  <Button variant="outline" size="icon-lg" className="size-11" aria-label="Tăng" onClick={() => setQty(l.id, l.quantity + 1)}>
                    <IconPlus />
                  </Button>
                  <span className="text-sm text-muted-foreground">{l.unit}</span>
                </div>
              )}
              {l.is_additional && !isFrozen(l) && (
                <Field data-invalid={!l.additional_reason?.trim() ? true : undefined}>
                  <FieldLabel htmlFor={`reason-${l.id}`}>Lý do phát sinh (bắt buộc)</FieldLabel>
                  <Input
                    id={`reason-${l.id}`}
                    value={l.additional_reason || ''}
                    onChange={(e) => setReason(l.id, e.target.value)}
                    aria-invalid={!l.additional_reason?.trim()}
                    className="h-11 text-base md:text-base"
                  />
                </Field>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Picker */}
      {pickerOpen ? (
        <div className="flex flex-col gap-3 rounded-md border bg-muted/40 p-3">
          <InputGroup className="h-11 bg-card">
            <InputGroupAddon>
              <IconSearch />
            </InputGroupAddon>
            <InputGroupInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm vật tư (van, ống, aptomat…)"
              aria-label="Tìm vật tư"
              className="text-base md:text-base"
            />
          </InputGroup>
          <ul className="max-h-64 divide-y overflow-y-auto rounded-md border bg-card">
            {results.map((m) => (
              <li key={m.code}>
                <button
                  type="button"
                  onClick={() => addLine({ material_code: m.code, name: m.name, quantity: 1, unit: m.unit, unit_price: m.unit_price })}
                  className="flex min-h-12 w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-muted/50"
                >
                  <span className="text-base md:text-base text-foreground">{m.name}</span>
                  <span className="shrink-0 text-sm tabular-nums text-muted-foreground">{formatVnd(m.unit_price)}/{m.unit}</span>
                </button>
              </li>
            ))}
            {results.length === 0 && <li className="p-3 text-sm text-muted-foreground">Không có trong danh mục. Nhập tay bên dưới.</li>}
          </ul>
          <FieldGroup className="grid grid-cols-[1fr_7rem_4.5rem] gap-2">
            <Field>
              <FieldLabel htmlFor="custom-name">Vật tư khác</FieldLabel>
              <Input id="custom-name" value={customName} onChange={(e) => setCustomName(e.target.value)} className="h-11 bg-card text-base md:text-base" />
            </Field>
            <Field>
              <FieldLabel htmlFor="custom-price">Đơn giá</FieldLabel>
              <Input id="custom-price" value={customPrice} onChange={(e) => setCustomPrice(e.target.value)} inputMode="numeric" className="h-11 bg-card text-base md:text-base" />
            </Field>
            <Field>
              <FieldLabel htmlFor="custom-unit">ĐVT</FieldLabel>
              <Input id="custom-unit" value={customUnit} onChange={(e) => setCustomUnit(e.target.value)} className="h-11 bg-card text-base md:text-base" />
            </Field>
          </FieldGroup>
          <div className="flex gap-2">
            <Button variant="outline" size="lg" className="h-11 flex-1 bg-card text-base md:text-base" onClick={addCustom}>Thêm vật tư nhập tay</Button>
            <Button size="lg" className="h-11 px-5 text-base md:text-base" onClick={() => setPickerOpen(false)}>Xong</Button>
          </div>
        </div>
      ) : (
        <Button variant="outline" size="lg" className="h-12 w-full border-dashed text-base md:text-base" onClick={() => setPickerOpen(true)}>
          <IconPlus data-icon="inline-start" /> {mode === 'additional' ? 'Thêm vật tư phát sinh' : 'Thêm vật tư'}
        </Button>
      )}

      {/* Labor, warranty, total */}
      {mode === 'draft' && (
        <FieldGroup className="grid grid-cols-2 gap-3">
          <Field>
            <FieldLabel htmlFor="labor-cost">Tiền công (đ)</FieldLabel>
            <Input
              id="labor-cost"
              value={quote.labor_cost ? quote.labor_cost.toLocaleString('vi-VN') : ''}
              onChange={(e) => update(quote.lines, { labor_cost: Number(e.target.value.replace(/\D/g, '')) || 0 })}
              inputMode="numeric"
              placeholder="0"
              className="h-11 text-base md:text-base"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="warranty">Bảo hành</FieldLabel>
            <Select
              items={WARRANTY_ITEMS}
              value={String(quote.warranty_months)}
              onValueChange={(v) => update(quote.lines, { warranty_months: Number(v) })}
            >
              <SelectTrigger id="warranty" className="w-full text-base md:text-base data-[size=default]:h-11">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {Object.entries(WARRANTY_ITEMS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>
      )}
      <div className="flex items-center justify-between border-t pt-3">
        <span className="text-base md:text-base text-slate-700">Tổng cộng{quote.labor_cost > 0 ? ' (gồm công)' : ''}</span>
        <span className="text-xl font-semibold tabular-nums text-foreground">{formatVnd(total)}</span>
      </div>
    </div>
  );
}
