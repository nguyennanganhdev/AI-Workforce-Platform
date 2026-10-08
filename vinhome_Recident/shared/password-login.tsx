import { useState, type FormEvent } from "react";
import "./password-login.css";

export function PasswordLogin({ audience }: {audience:"resident"|"operations"}) {
  const [mode,setMode] = useState<"login"|"register"|"change">("login");
  const [identifier,setIdentifier] = useState("");
  const [name,setName] = useState("");
  const [password,setPassword] = useState("");
  const [nextPassword,setNextPassword] = useState("");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const home = audience === "resident" ? "/" : "/operations";
  async function call(path:string, body:object) {
    const r = await fetch(`/api/business/auth/${path}`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const data = await r.json().catch(()=>null);
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Không hoàn thành được yêu cầu (${r.status}).`);
    return data;
  }
  async function submit(e:FormEvent) {
    e.preventDefault(); if (busy) return;
    setBusy(true);setError("");setNotice("");
    try {
      if (mode === "register") {
        await call("register",{email:identifier.trim(),name:name.trim(),password});
        setPassword("");setMode("login");setNotice("Đã tạo tài khoản. Ban quản lý cần duyệt và liên kết căn hộ trước khi bạn gửi phản ánh.");
      } else if (mode === "change") {
        await call("change-password",{current_password:password,new_password:nextPassword});
        setPassword("");setNextPassword("");setMode("login");setNotice("Đã đổi mật khẩu và thu hồi các phiên cũ. Đăng nhập lại bằng mật khẩu mới.");
      } else {
        await call("login",{identifier:identifier.trim(),password});
        if (audience === "operations") {
          const r=await fetch("/api/business/operations/me",{credentials:"include"});
          if (!r.ok) throw new Error("Đã đăng nhập, nhưng tài khoản chưa có quyền BQL/nhân viên. Liên hệ quản trị viên cấp quyền.");
        }
        location.assign(home);
      }
    } catch(e) { setError(e instanceof Error ? e.message : "Không kết nối được máy chủ."); }
    finally { setBusy(false); }
  }
  return <div className="password-login">
    <h1>{mode === "register" ? "Đăng ký cư dân" : mode === "change" ? "Đổi mật khẩu" : audience === "resident" ? "Đăng nhập cư dân" : "Đăng nhập nhân viên"}</h1>
    <p>{mode === "change" ? "Yêu cầu phiên đăng nhập hiện tại và mật khẩu cũ." : "Sử dụng tài khoản của bạn để kết nối với hệ thống."}</p>
    {error && <p role="alert" className="password-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form onSubmit={submit}><fieldset disabled={busy}>
      {mode === "register" && <label>Họ và tên<input autoComplete="name" required minLength={2} maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>}
      {mode !== "change" && <label>{mode === "register" ? "Email" : "Email hoặc số điện thoại"}<input type={mode === "register" ? "email" : "text"} autoComplete="username" required maxLength={254} value={identifier} onChange={e=>setIdentifier(e.target.value)}/></label>}
      <label>{mode === "change" ? "Mật khẩu hiện tại" : "Mật khẩu"}<input type="password" required minLength={mode === "register" ? 12 : 1} maxLength={128} autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={e=>setPassword(e.target.value)}/></label>
      {mode === "change" && <label>Mật khẩu mới (ít nhất 12 ký tự)<input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={nextPassword} onChange={e=>setNextPassword(e.target.value)}/></label>}
      {mode === "register" && <p>Mật khẩu ít nhất 12 ký tự. Tài khoản mới chưa có quyền truy cập căn hộ hoặc Operations.</p>}
      <button type="submit">{busy ? "Đang xử lý…" : mode === "register" ? "Tạo tài khoản" : mode === "change" ? "Lưu mật khẩu mới" : "Đăng nhập"}</button>
    </fieldset></form>
    <nav aria-label="Tài khoản">
      {mode !== "login" && <button onClick={()=>{setMode("login");setError("");setPassword("");}}>Về đăng nhập</button>}
      {audience === "resident" && mode === "login" && <button onClick={()=>{setMode("register");setError("");setPassword("");}}>Đăng ký cư dân</button>}
      {mode === "login" && <button onClick={()=>{setMode("change");setError("");setPassword("");}}>Đổi mật khẩu</button>}
      <button disabled={busy} onClick={()=>{setBusy(true);void call("logout",{}).then(()=>{setNotice("Đã đăng xuất.");setMode("login");}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Đăng xuất</button>
      <a href={home}>Về ứng dụng</a>
    </nav>
    <p>Quên mật khẩu hoặc chưa có quyền? Liên hệ quản trị viên. Hệ thống chưa cấu hình gửi mã khôi phục.</p>
  </div>;
}
