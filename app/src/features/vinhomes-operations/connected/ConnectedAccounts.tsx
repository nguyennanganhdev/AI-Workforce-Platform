import { useEffect, useState, type FormEvent } from "react";
type Account = {id:string;name:string;email:string;role:string;status:string;administrator:boolean;management_unit_id:string|null};
type Unit = {id:string;name:string};
const roles:Record<string,string>={customer:"Cư dân",staff:"Nhân viên",management:"Ban quản lý"};
export function ConnectedAccounts() {
  const [items,setItems]=useState<Account[]>([]),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({name:"",email:"",password:"",role:"customer",unit:""});
  const [units,setUnits]=useState<Unit[]>([]);
  async function api(path="",init:RequestInit={}) {
    const r=await fetch(path==="/management-units"?"/api/business/auth/management-units":`/api/business/auth/accounts${path}`,{credentials:"include",...init,headers:{"Content-Type":"application/json"}});
    const body=await r.json();if(!r.ok)throw new Error(typeof body.detail === "string" ? body.detail : "Không cập nhật được tài khoản.");return body;
  }
  const load=async()=>{setItems((await api()).items);setUnits((await api("/management-units")).items);};
  // A management account works in one unit (its tickets, room and agents) or, with none chosen, in the whole tenant.
  const scoped=(role:string,unit:string|null)=>({role,...(role==="management"&&unit?{management_unit_id:unit}:{})});
  const unitField=(value:string|null,change:(unit:string)=>void)=><label>Đơn vị quản lý<select disabled={busy} value={value||""} onChange={e=>change(e.target.value)}><option value="">Toàn bộ khu</option>{units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select></label>;
  useEffect(()=>{void load().catch(e=>setError(e.message));},[]);
  async function run(action:()=>Promise<unknown>) {if(busy)return;setBusy(true);setError("");try{await action();await load();}catch(e){setError(e instanceof Error?e.message:"Lỗi kết nối.");}finally{setBusy(false);}}
  function create(e:FormEvent){e.preventDefault();void run(async()=>{await api("",{method:"POST",body:JSON.stringify({name:form.name,email:form.email,password:form.password,...scoped(form.role,form.unit)})});setForm({...form,name:"",email:"",password:""});});}
  return <><p>BQL làm việc trong đơn vị quản lý được chọn: ticket, phòng nhóm và agent của đơn vị đó; không chọn đơn vị thì có quyền trên toàn bộ khu. Nhân viên chỉ xử lý công việc được phân công. Cư dân cần xác minh căn hộ trước khi gửi phản ánh.</p>{error&&<p role="alert" className="ws-notice error">{error}</p>}
    <form className="ws-card" onSubmit={create}><h2>Tạo tài khoản</h2><fieldset disabled={busy}><div className="ws-row"><label>Họ và tên<input required minLength={2} maxLength={100} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Mật khẩu ban đầu<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{Object.entries(roles).map(([r,label])=><option key={r} value={r}>{label}</option>)}</select></label>{form.role==="management"&&unitField(form.unit,unit=>setForm({...form,unit}))}</div><button type="submit">Tạo tài khoản</button></fieldset></form>
    <section className="ws-card"><h2>Tài khoản và quyền truy cập</h2>{items.map(a=><article className="ws-ticket" key={a.id}><strong>{a.name}</strong><p>{a.email} · {a.administrator ? "Quản trị viên" : roles[a.role]} · {a.status}</p>{!a.administrator&&<div className="ws-row"><label>Vai trò<select disabled={busy} value={a.role} onChange={e=>setItems(items.map(x=>x.id===a.id?{...x,role:e.target.value}:x))}>{Object.entries(roles).map(([r,label])=><option key={r} value={r}>{label}</option>)}</select></label>{a.role==="management"&&unitField(a.management_unit_id,unit=>setItems(items.map(x=>x.id===a.id?{...x,management_unit_id:unit||null}:x)))}<button disabled={busy} onClick={()=>void run(()=>api(`/${a.id}`,{method:"PATCH",body:JSON.stringify({...scoped(a.role,a.management_unit_id),status:"active"})}))}>{a.status === "pending" ? "Duyệt tài khoản" : "Lưu quyền / kích hoạt"}</button><button disabled={busy||a.status === "suspended"} onClick={()=>void run(()=>api(`/${a.id}`,{method:"PATCH",body:JSON.stringify({role:a.role,status:"suspended"})}))}>Khóa truy cập</button></div>}</article>)}</section>
  </>;
}
