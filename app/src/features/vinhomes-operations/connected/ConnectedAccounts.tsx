import { useEffect, useState, type FormEvent } from "react";
type Account = {id:string;name:string;email:string;role:string;status:string;administrator:boolean};
const roles:Record<string,string>={customer:"Cư dân",staff:"Nhân viên",management:"Ban quản lý"};
export function ConnectedAccounts() {
  const [items,setItems]=useState<Account[]>([]),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({name:"",email:"",password:"",role:"customer"});
  async function api(path="",init:RequestInit={}) {
    const r=await fetch(`/api/business/auth/accounts${path}`,{credentials:"include",...init,headers:{"Content-Type":"application/json"}});
    const body=await r.json();if(!r.ok)throw new Error(typeof body.detail === "string" ? body.detail : "Không cập nhật được tài khoản.");return body;
  }
  const load=async()=>setItems((await api()).items);
  useEffect(()=>{void load().catch(e=>setError(e.message));},[]);
  async function run(action:()=>Promise<unknown>) {if(busy)return;setBusy(true);setError("");try{await action();await load();}catch(e){setError(e instanceof Error?e.message:"Lỗi kết nối.");}finally{setBusy(false);}}
  function create(e:FormEvent){e.preventDefault();void run(async()=>{await api("",{method:"POST",body:JSON.stringify(form)});setForm({...form,name:"",email:"",password:""});});}
  return <><p>BQL được cấp quyền trong tenant hiện tại. Nhân viên chỉ xử lý công việc được phân công. Cư dân cần xác minh căn hộ trước khi gửi phản ánh.</p>{error&&<p role="alert" className="ws-notice error">{error}</p>}
    <form className="ws-card" onSubmit={create}><h2>Tạo tài khoản</h2><fieldset disabled={busy}><div className="ws-row"><label>Họ và tên<input required minLength={2} maxLength={100} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Mật khẩu ban đầu<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{Object.entries(roles).map(([r,label])=><option key={r} value={r}>{label}</option>)}</select></label></div><button type="submit">Tạo tài khoản</button></fieldset></form>
    <section className="ws-card"><h2>Tài khoản và quyền truy cập</h2>{items.map(a=><article className="ws-ticket" key={a.id}><strong>{a.name}</strong><p>{a.email} · {a.administrator ? "Quản trị viên" : roles[a.role]} · {a.status}</p>{!a.administrator&&<div className="ws-row"><label>Vai trò<select disabled={busy} value={a.role} onChange={e=>setItems(items.map(x=>x.id===a.id?{...x,role:e.target.value}:x))}>{Object.entries(roles).map(([r,label])=><option key={r} value={r}>{label}</option>)}</select></label><button disabled={busy} onClick={()=>void run(()=>api(`/${a.id}`,{method:"PATCH",body:JSON.stringify({role:a.role,status:"active"})}))}>{a.status === "pending" ? "Duyệt tài khoản" : "Lưu quyền / kích hoạt"}</button><button disabled={busy||a.status === "suspended"} onClick={()=>void run(()=>api(`/${a.id}`,{method:"PATCH",body:JSON.stringify({role:a.role,status:"suspended"})}))}>Khóa truy cập</button></div>}</article>)}</section>
  </>;
}
