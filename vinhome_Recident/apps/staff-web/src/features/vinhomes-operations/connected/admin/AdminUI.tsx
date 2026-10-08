import { PageToolbar } from "../PageToolbar";
import type { ReactNode } from "react";
import {
  Download as IconDownload,
  Search as IconSearch,
  X as IconX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import "./admin.css";

export function AdminPage({
  title,
  meta,
  action,
  children,
}: {
  title: string;
  meta?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="ops-admin">
      <PageToolbar><header className="ops-admin-heading">
        <div>
          <h1>{title}</h1>
          {meta && <span>{meta}</span>}
        </div>
        {action}
      </header></PageToolbar>
      {children}
    </div>
  );
}
export function AdminSelect({
  label,
  value,
  options,
  onChange,
  disabled,
  id,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  id?: string;
}) {
  return (
    <Select
      value={value}
      onValueChange={(next) => onChange(next ?? "")}
      disabled={disabled}
      items={options}
    >
      <SelectTrigger id={id} aria-label={label} className="ops-admin-select">
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="ops-ui ops-admin-menu">
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
export function AdminSearch({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className="ops-admin-search">
      <IconSearch aria-hidden="true" size={16} />
      <Input
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
export function AdminBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "ok" | "wait" | "danger" | "neutral" | "agent";
}) {
  return (
    <span className={`ops-admin-badge ops-admin-badge-${tone}`}>
      <span aria-hidden="true" />
      {children}
    </span>
  );
}
export function AdminState({
  loading,
  error,
  empty,
  onRetry,
}: {
  loading?: boolean;
  error?: Error | null;
  empty?: string;
  onRetry?: () => void;
}) {
  if (loading)
    return (
      <div
        className="ops-admin-loading"
        aria-label="Đang tải dữ liệu"
        role="status"
      >
        {[1, 2, 3, 4].map((row) => (
          <Skeleton key={row} className="h-10 w-full" />
        ))}
      </div>
    );
  if (error)
    return (
      <div className="ops-admin-state" role="alert">
        <p>{error.message}</p>
        {onRetry && (
          <Button variant="outline" onClick={onRetry}>
            Thử lại
          </Button>
        )}
      </div>
    );
  return empty ? <p className="ops-admin-state">{empty}</p> : null;
}
export function AdminDrawer({
  title,
  description,
  children,
  footer,
  onClose,
  busy = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <SheetContent className="ops-ui ops-admin-drawer" showCloseButton={false}>
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          {description && <SheetDescription>{description}</SheetDescription>}
          <Button
            variant="ghost"
            size="icon-sm"
            className="ops-admin-drawer-close"
            aria-label="Đóng chi tiết"
            title="Đóng chi tiết"
            disabled={busy}
            onClick={onClose}
          >
            <IconX />
          </Button>
        </SheetHeader>
        <div className="ops-admin-drawer-body">{children}</div>
        {footer && <div className="ops-admin-drawer-footer">{footer}</div>}
      </SheetContent>
    </Sheet>
  );
}
export function AdminConfirm({
  title,
  consequence,
  confirm,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  consequence: string;
  confirm: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onCancel();
      }}
    >
      <DialogContent className="ops-ui ops-admin-confirm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{consequence}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onCancel}>
            Hủy
          </Button>
          <Button
            variant="outline"
            className="ops-admin-danger"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Đang thực hiện…" : confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
export function downloadCsv(name: string, rows: (string | number)[][]) {
  const escape = (value: string | number) => {
    const text = String(value);
    return `"${(/^[=+\-@\t\r]/.test(text) ? "'" : "") + text.replaceAll('"', '""')}"`;
  };
  const url = URL.createObjectURL(
    new Blob(
      ["\uFEFF", rows.map((row) => row.map(escape).join(",")).join("\r\n")],
      { type: "text/csv;charset=utf-8" },
    ),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export function ExportButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Button
      variant="ghost"
      className="ops-admin-export"
      disabled={disabled}
      onClick={onClick}
    >
      <IconDownload />
      Xuất CSV
    </Button>
  );
}
export function absoluteTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .format(date)
    .replace(",", "");
}
export function relativeTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - date.getTime()) / 60_000),
  );
  if (minutes < 1) return "Vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} giờ trước`;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}
