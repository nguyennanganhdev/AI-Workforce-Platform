import { useEffect, useState, type FormEvent } from "react";
import "./auth.css";

export function ResetPasswordPage() {
  const [token] = useState(() => new URLSearchParams(location.hash.split("?")[1] || "").get("token") || "");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    document.title = "Đặt lại mật khẩu — Vinhomes";
    // Keep the token in memory only; no browser history entry retains the email link after loading.
    history.replaceState(null, "", "/login#reset-password");
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    if (password.length < 12 || password.length > 128 || password !== confirmation) {
      setError("Mật khẩu cần 12–128 ký tự và hai lần nhập phải khớp."); return;
    }
    setPending(true); setError("");
    try {
      const response = await fetch("/api/business/auth/password-reset/confirm", {method: "POST", credentials: "include",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({token, new_password: password})});
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Không đổi được mật khẩu. Hãy yêu cầu link mới.");
      setPassword(""); setConfirmation(""); setDone(true);
    } catch (failure) {setError(failure instanceof Error ? failure.message : "Không kết nối được. Vui lòng thử lại.");}
    finally {setPending(false);}
  }
  return <main className="resident-auth-status">
    <a className="resident-auth-status-brand" href="/"><img src="/images/vinhomes-logo.png" alt="Vinhomes" width={120} height={48} style={{objectFit: "contain"}} /></a>
    <section><h1>Đặt lại mật khẩu</h1>
      {done ? <><p role="status">Mật khẩu đã được đổi. Các phiên đăng nhập cũ đã kết thúc.</p><a className="resident-auth-status-action" href="/login">Đăng nhập</a></> : !token ?
        <><p role="alert">Link chưa đầy đủ hoặc đã được mở. Vui lòng yêu cầu email khôi phục mới.</p><a href="/forgot-password">Yêu cầu link mới</a></> :
        <form className="resident-recovery-form" onSubmit={submit}>
          <p>Chọn mật khẩu mới, tối thiểu 12 ký tự.</p>
          <label>Mật khẩu mới<input aria-label="Mật khẩu mới" type="password" autoComplete="new-password" minLength={12} maxLength={128} value={password} disabled={pending} onChange={e => setPassword(e.target.value)} required /></label>
          <label>Nhập lại mật khẩu<input aria-label="Nhập lại mật khẩu" type="password" autoComplete="new-password" maxLength={128} value={confirmation} disabled={pending} onChange={e => setConfirmation(e.target.value)} required /></label>
          {error && <p role="alert">{error}</p>}<button className="resident-auth-status-action" disabled={pending} type="submit">{pending ? "Đang đổi…" : "Lưu mật khẩu mới"}</button>
        </form>}
    </section>
  </main>;
}
