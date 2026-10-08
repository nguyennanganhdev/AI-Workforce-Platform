import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

/**
 * The signed-in person changes their own password. The server ends every sign-in of theirs,
 * so on success they sign in again with the new one.
 */
export function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ current: "", next: "", again: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mismatch = !!form.again && form.next !== form.again;
  const ready = !!form.current && form.next.length >= 12 && form.next === form.again && form.next !== form.current;
  async function submit() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/business/auth/change-password", {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: form.current, new_password: form.next }),
      });
      if (response.ok) { location.assign("/operations/login"); return; }
      const detail = (await response.json().catch(() => ({}))).detail;
      setError(typeof detail === "string" ? detail : "Không đổi được mật khẩu. Thử lại sau.");
    } catch {
      setError("Không kết nối được máy chủ. Thử lại sau.");
    }
    setBusy(false);
  }
  const field = (key: keyof typeof form, label: string, autoComplete: string) =>
    <label className="flex flex-col gap-1 text-sm">{label}
      <Input type="password" aria-label={label} autoComplete={autoComplete} maxLength={128} value={form[key]} disabled={busy}
        onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>;
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent className="ops-ui">
    <DialogHeader><DialogTitle>Đổi mật khẩu</DialogTitle><DialogDescription>Sau khi đổi, bạn đăng nhập lại bằng mật khẩu mới trên mọi thiết bị.</DialogDescription></DialogHeader>
    <DialogBody><form className="flex flex-col gap-3" onSubmit={e => { e.preventDefault(); if (ready) void submit(); }}>
      {field("current", "Mật khẩu hiện tại", "current-password")}
      {field("next", "Mật khẩu mới", "new-password")}
      {field("again", "Nhập lại mật khẩu mới", "new-password")}
      <small className="text-xs text-slate-500">Ít nhất 12 ký tự, khác mật khẩu hiện tại.</small>
      {mismatch && <p role="alert" className="text-sm text-red-700">Hai lần nhập mật khẩu mới chưa khớp.</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button type="submit" hidden />
    </form></DialogBody>
    <DialogFooter><Button variant="outline" disabled={busy} onClick={onClose}>Hủy</Button><Button disabled={!ready || busy} onClick={() => void submit()}>{busy ? "Đang đổi…" : "Đổi mật khẩu"}</Button></DialogFooter>
  </DialogContent></Dialog>;
}
