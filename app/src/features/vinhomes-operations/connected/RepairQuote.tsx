import { useEffect, useState } from "react";
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
    <div className="ws-stack">
      <div className="ws-row">
        <select
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
      </div>
      {lines.map((line, index) => (
        <div className="ws-row" key={index}>
          <input
            aria-label="Tên vật tư"
            placeholder="Tên vật tư"
            value={line.name}
            onChange={(e) => update(index, { name: e.target.value })}
          />
          <input
            aria-label="Số lượng"
            type="number"
            min="0.001"
            step="any"
            value={line.quantity}
            onChange={(e) => update(index, { quantity: e.target.value })}
          />
          <input
            aria-label="Đơn vị"
            value={line.unit}
            onChange={(e) => update(index, { unit: e.target.value })}
          />
          <input
            aria-label="Đơn giá"
            type="number"
            min="0"
            value={line.unit_price}
            onChange={(e) => update(index, { unit_price: Number(e.target.value) })}
          />
          <button type="button" onClick={() => setLines((all) => all.filter((_, i) => i !== index))}>
            Xóa
          </button>
        </div>
      ))}
      <div className="ws-row">
        <label>
          Tiền công (đ)
          <input type="number" min="0" value={labor} onChange={(e) => setLabor(e.target.value)} />
        </label>
        <label>
          Bảo hành (tháng)
          <input
            type="number"
            min="0"
            max="120"
            value={warranty}
            onChange={(e) => setWarranty(e.target.value)}
          />
        </label>
        <strong>Tổng tạm tính: {formatVnd(total)}</strong>
      </div>
      <button
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
      </button>
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
    <div className="ws-stack">
      <strong>Phương án đang chờ cư dân đồng ý</strong>
      {quote?.note && <p>{quote.note}</p>}
      {quote?.lines?.map((line, index) => (
        <div className="ws-row between" key={index}>
          <span>
            {line.name} × {line.quantity} {line.unit}
          </span>
          <span>{formatVnd(line.amount)}</span>
        </div>
      ))}
      {quote?.total !== undefined && (
        <>
          <div className="ws-row between">
            <span>Tiền công</span>
            <span>{formatVnd(quote.labor_cost ?? 0)}</span>
          </div>
          <div className="ws-row between">
            <strong>Tổng cộng</strong>
            <strong>{formatVnd(quote.total)}</strong>
          </div>
          {!!quote.warranty_months && <span>Bảo hành: {quote.warranty_months} tháng</span>}
        </>
      )}
      <small>
        Cư dân có thể đồng ý trên ứng dụng cư dân, hoặc đọc và trả lời ngay trên máy này.
      </small>
      <div className="live-actions">
        <button disabled={disabled} onClick={() => onDecide(true)}>
          Cư dân đồng ý tại chỗ
        </button>
        <button disabled={disabled} onClick={() => onDecide(false)}>
          Cư dân chưa đồng ý, lập lại phương án
        </button>
      </div>
    </div>
  );
}
