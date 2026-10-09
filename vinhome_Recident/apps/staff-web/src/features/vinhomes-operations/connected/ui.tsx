import type { ReactNode } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export type StatusTone = 'ok' | 'wait' | 'danger' | 'neutral' | 'agent';
export function StatusBadge({ tone = 'neutral', children, dot = true }: { tone?: StatusTone; children: ReactNode; dot?: boolean }) {
  return <span className="ops-status" data-tone={tone}>{dot && <span aria-hidden="true" className="ops-status-dot" />}{children}</span>;
}
export function OpsSelect({ value, onValueChange, options, label, disabled = false, placeholder, className = '' }: {
  value: string; onValueChange: (value: string) => void; options: { value: string; label: string }[]; label: string; disabled?: boolean; placeholder?: string; className?: string;
}) {
  const emptyValue = '__ops_empty__';
  const items = options.map(option => ({ ...option, value: option.value || emptyValue }));
  const selectedValue = value || (options.some(option => option.value === '') ? emptyValue : null);
  return <Select value={selectedValue} onValueChange={v => onValueChange(v === emptyValue ? '' : v || '')} disabled={disabled} items={items}>
    <SelectTrigger aria-label={label} className={`ops-select ${className}`}><SelectValue placeholder={placeholder || label} /></SelectTrigger>
    <SelectContent className="ops-ui ops-select-popup">{items.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
  </Select>;
}
