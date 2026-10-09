import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { X, Plus, ArrowUpRight, AlertCircle } from 'lucide-react';
import { labels } from './api';
import type { Row } from './api';

export function Badge({ value }: { value: string }) {
  return <span className={'badge ' + value}>{labels[value] || value}</span>;
}
export function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div role="alert" className="error">
      <AlertCircle size={18} />
      {error}
    </div>
  ) : null;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-mark">/</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function PageHead({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
export function NewButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button className="primary" onClick={onClick}>
      <Plus size={17} />
      {children}
    </button>
  );
}
export function Detail({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details>
      <summary>
        {title}
        <ArrowUpRight size={15} />
      </summary>
      <div className="detail-content">{children}</div>
    </details>
  );
}

export type FieldSpec = {
  key: string;
  label: string;
  type?: string;
  required?: boolean;
  help?: string;
  options?: { value: string; label: string }[];
  default?: unknown;
};
export function Form({
  fields,
  initial = {},
  submit,
  onCancel,
  label = 'Lưu',
}: {
  fields: FieldSpec[];
  initial?: Row;
  submit: (value: Row) => Promise<void>;
  onCancel?: () => void;
  label?: string;
}) {
  const [values, setValues] = useState<Row>(() =>
    Object.fromEntries(
      fields.map((f) => {
        let value =
          initial[f.key] ??
          f.default ??
          (f.type === 'checkbox' ? false : f.type === 'multi' ? [] : '');
        if (f.type === 'list' && Array.isArray(value)) value = value.join('\n');
        return [f.key, value];
      })
    )
  );
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const parsed: Row = {};
      for (const field of fields) {
        const v = values[field.key];
        parsed[field.key] =
          field.type === 'number'
            ? Number(v)
            : field.type === 'list'
              ? String(v)
                  .split('\n')
                  .map((s) => s.trim())
                  .filter(Boolean)
              : field.type === 'multi'
                ? v || []
                : v;
      }
      await submit(parsed);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="form-grid">
      <ErrorBox error={error} />
      {fields.map((f) => (
        <label key={f.key} className={f.type === 'textarea' || f.type === 'list' ? 'wide' : ''}>
          <span>
            {f.label}
            {f.required ? ' *' : ''}
          </span>
          {f.type === 'select' ? (
            <select
              aria-label={f.label}
              value={values[f.key]}
              required={f.required}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
            >
              <option value="">Chọn…</option>
              {f.options?.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : f.type === 'multi' ? (
            <select
              aria-label={f.label}
              multiple
              value={values[f.key]}
              onChange={(e) =>
                setValues({
                  ...values,
                  [f.key]: Array.from(e.target.selectedOptions, (o) => o.value),
                })
              }
            >
              {f.options?.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : f.type === 'textarea' || f.type === 'list' ? (
            <textarea
              aria-label={f.label}
              rows={4}
              value={Array.isArray(values[f.key]) ? values[f.key].join('\n') : values[f.key]}
              required={f.required}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
            />
          ) : f.type === 'checkbox' ? (
            <input
              aria-label={f.label}
              type="checkbox"
              checked={values[f.key]}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.checked })}
            />
          ) : (
            <input
              aria-label={f.label}
              type={f.type || 'text'}
              value={values[f.key]}
              required={f.required}
              min={f.type === 'number' ? 0 : undefined}
              autoComplete={f.type === 'password' ? 'new-password' : undefined}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
            />
          )}{' '}
          {f.help && <small>{f.help}</small>}
        </label>
      ))}
      <div className="form-actions wide">
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Hủy
          </button>
        )}
        <button className="primary" disabled={busy}>
          {busy ? 'Đang lưu…' : label}
        </button>
      </div>
    </form>
  );
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <dialog
        open
        aria-label={title}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
          if (e.key === 'Tab') {
            const list = Array.from(
              e.currentTarget.querySelectorAll<HTMLElement>(
                'button,input,textarea,select,[tabindex="0"]'
              )
            );
            const first = list[0],
              last = list.at(-1);
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button autoFocus onClick={onClose} aria-label="Đóng">
            <X size={20} />
          </button>
        </div>
        {children}
      </dialog>
    </div>
  );
}
