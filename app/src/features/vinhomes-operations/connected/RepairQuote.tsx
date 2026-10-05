import { useEffect, useState } from "react";
import { IconTrash } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MATERIAL_CATALOG, formatVnd } from "../lib/field-flow";

export type QuoteInput = {
  lines: { name: string; quantity: string; unit: string; unit_price: number }[];
  labor_cost: number;
  warranty_months: number;
};
type QuoteDetail = {
  note?: string;
  lines?: { name: string; quantity: string; unit: string; amount: number }[];
  labor_cost?: number;
  warranty_months?: number;
  total?: number;
};
type Line = QuoteInput["lines"][number];
const caption = "text-xs font-medium text-muted-foreground";

/** Danh mục vật tư + tiền công nhân viên lập tại hiện trường; tổng tiền do backend tính lại. */
export function QuoteForm({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (quote: QuoteInput) => void;
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [labor, setLabor] = useState("0");
  const [warranty, setWarranty] = useState("0");
  const update = (index: number, patch: Partial<Line>) =>
    setLines((all) => all.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  const valid = lines.every(
    (l) => l.name.trim() && l.unit.trim() && Number(l.quantity) > 0 && l.unit_price >= 0,
  );
  const total =
    lines.reduce((sum, l) => sum + Math.round(Number(l.quantity) * l.unit_price), 0) +
    Number(labor);
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-semibold text-foreground">Vật tư và chi phí</p>
      {lines.map((line, index) => (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3" key={index}>
          <div className="flex items-center gap-2">
            <Input aria-label="Tên vật tư" placeholder="Tên vật tư" className="h-11 flex-1" value={line.name}
              onChange={(e) => update(index, { name: e.target.value })} />
            <Button type="button" size="icon" variant="ghost" aria-label={`Xóa ${line.name || "vật tư"}`} className="size-11 shrink-0"
              onClick={() => setLines((all) => all.filter((_, i) => i !== index))}><IconTrash /></Button>
          </div>
          <div className="grid grid-cols-[1fr_1fr_1.5fr] gap-2">
            <label className={caption}>Số lượng
              <Input aria-label="Số lượng" type="number" inputMode="decimal" min="0.001" step="any" className="mt-1 h-11" value={line.quantity}
                onChange={(e) => update(index, { quantity: e.target.value })} /></label>
            <label className={caption}>Đơn vị
              <Input aria-label="Đơn vị" className="mt-1 h-11" value={line.unit} onChange={(e) => update(index, { unit: e.target.value })} /></label>
            <label className={caption}>Đơn giá (đ)
              <Input aria-label="Đơn giá" type="number" inputMode="numeric" min="0" className="mt-1 h-11" value={line.unit_price}
                onChange={(e) => update(index, { unit_price: Number(e.target.value) })} /></label>
          </div>
        </div>
      ))}
      <select
        aria-label="Thêm vật tư"
        className="h-11 w-full rounded-lg border border-dashed border-input bg-background px-3 text-sm text-foreground"
        value=""
        onChange={(e) => {
          const item = MATERIAL_CATALOG.find((m) => m.code === e.target.value);
          setLines((all) => [
            ...all,
            item
              ? { name: item.name, quantity: "1", unit: item.unit, unit_price: item.unit_price }
              : { name: "", quantity: "1", unit: "cái", unit_price: 0 },
          ]);
        }}
      >
        <option value="" disabled>
          Thêm vật tư…
        </option>
        {MATERIAL_CATALOG.map((m) => (
          <option key={m.code} value={m.code}>
            {m.name} ({formatVnd(m.unit_price)}/{m.unit})
          </option>
        ))}
        <option value="manual">Vật tư khác (nhập tay)</option>
      </select>
      <div className="grid grid-cols-2 gap-3">
        <label className={caption}>
          Tiền công (đ)
          <Input type="number" inputMode="numeric" min="0" className="mt-1 h-11" value={labor} onChange={(e) => setLabor(e.target.value)} />
        </label>
        <label className={caption}>
          Bảo hành (tháng)
          <Input type="number" inputMode="numeric" min="0" max="120" className="mt-1 h-11" value={warranty} onChange={(e) => setWarranty(e.target.value)} />
        </label>
      </div>
      <p className="flex items-baseline justify-between border-t border-border pt-3 text-sm text-muted-foreground">
        Tổng tạm tính<strong className="text-lg font-semibold tabular-nums text-foreground">{formatVnd(total)}</strong>
      </p>
      <Button
        className="h-12 w-full text-base"
        disabled={disabled || !valid}
        onClick={() =>
          onSubmit({
            lines: lines.map((l) => ({ ...l, name: l.name.trim(), unit: l.unit.trim() })),
            labor_cost: Number(labor),
            warranty_months: Number(warranty),
          })
        }
      >
        Gửi phương án cho cư dân
      </Button>
    </div>
  );
}

/** Cư dân đọc phương án ngay trên máy nhân viên và trả lời; app cư dân vẫn trả lời được song song. */
export function OnsiteConsent({
  orderId,
  disabled,
  request,
  onDecide,
}: {
  orderId: string;
  disabled: boolean;
  request: <T>(path: string) => Promise<T>;
  onDecide: (approved: boolean) => void;
}) {
  const [quote, setQuote] = useState<QuoteDetail>();
  useEffect(() => {
    let current = true;
    request<{ approvals: { kind: string; status: string; request_detail: QuoteDetail }[] }>(
      `/work-orders/${orderId}`,
    )
      .then((d) => {
        const pending = d.approvals.find(
          (a) => a.kind === "customer_repair" && a.status === "pending",
        );
        if (current) setQuote(pending?.request_detail);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [orderId, request]);
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border p-4">
        <p className="text-sm font-semibold text-foreground">Phương án gửi cư dân</p>
        {quote?.note && <p className="mt-1.5 whitespace-pre-line text-sm text-muted-foreground">{quote.note}</p>}
        {!!quote?.lines?.length && (
          <ul className="mt-3 flex flex-col gap-1.5 text-sm text-foreground">
            {quote.lines.map((line, index) => (
              <li className="flex justify-between gap-3" key={index}>
                <span>
                  {line.name} × {line.quantity} {line.unit}
                </span>
                <span className="shrink-0 tabular-nums">{formatVnd(line.amount)}</span>
              </li>
            ))}
          </ul>
        )}
        {quote?.total !== undefined && (
          <dl className="mt-3 flex flex-col gap-1.5 border-t border-border pt-3 text-sm">
            <div className="flex justify-between gap-3 text-muted-foreground">
              <dt>Tiền công</dt>
              <dd className="tabular-nums">{formatVnd(quote.labor_cost ?? 0)}</dd>
            </div>
            <div className="flex justify-between gap-3 text-base font-semibold text-foreground">
              <dt>Tổng cộng</dt>
              <dd className="tabular-nums">{formatVnd(quote.total)}</dd>
            </div>
            {!!quote.warranty_months && <div className="flex justify-between gap-3 text-muted-foreground"><dt>Bảo hành</dt><dd>{quote.warranty_months} tháng</dd></div>}
          </dl>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        Cư dân có thể đồng ý trên ứng dụng cư dân, hoặc đọc và trả lời ngay trên máy này.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <Button variant="outline" className="h-12 text-base" disabled={disabled} onClick={() => onDecide(true)}>
          Cư dân đồng ý tại chỗ
        </Button>
        <Button variant="ghost" className="h-12 text-base" disabled={disabled} onClick={() => onDecide(false)}>
          Chưa đồng ý, lập lại
        </Button>
      </div>
    </div>
  );
}
