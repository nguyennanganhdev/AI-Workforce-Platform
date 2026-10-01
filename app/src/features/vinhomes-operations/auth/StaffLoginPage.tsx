import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  IconArrowLeft,
  IconArrowRight,
  IconBuildingCommunity,
  IconEye,
  IconEyeOff,
  IconLock,
  IconShieldCheck,
  IconUser,
  IconHelpCircle,
} from "@tabler/icons-react";
import {
  StaffAuthError,
  staffAuthMessages,
  staffAuthService,
  validateStaffCredentials,
  type StaffAuthService,
} from "./auth-service";
import { startOperationsPreview } from "./demo-access";
import "./auth.css";
import { readWorkspace } from "../workspace/service";
import { roleLabels } from "../workspace/model";

export function StaffLoginPage({
  service = staffAuthService,
}: {
  service?: StaffAuthService;
}) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [help, setHelp] = useState(false);
  const [previewId,setPreviewId]=useState("demo-tech");
  const [previewData]=useState(()=>{try{return {accounts:readWorkspace().accounts,error:""};}catch{return {accounts:[],error:"Không đọc được danh sách tài khoản mẫu. Kiểm tra dữ liệu workspace trên trình duyệt."};}});
  const busy = useRef(false);
  const mounted = useRef(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const errors = validateStaffCredentials({ identifier, password });
  useEffect(() => {
    mounted.current = true;
    const previous = document.title;
    document.title = "Đăng nhập nhân viên — Vinhomes Operations";
    return () => {
      mounted.current = false;
      document.title = previous;
    };
  }, []);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [help]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    setSubmitted(true);
    if (errors.identifier || errors.password) {
      event.currentTarget
        .querySelector<HTMLInputElement>(
          `[name="${errors.identifier ? "identifier" : "password"}"]`,
        )
        ?.focus();
      return;
    }
    busy.current = true;
    setPending(true);
    setNotice("");
    try {
      await service.signIn({ identifier: identifier.trim(), password });
      if (mounted.current) {
        setPassword("");
        setSubmitted(false);
        // The live adapter must restore the real identity before enabling the workspaces.
        setNotice(
          "Đã tiếp nhận đăng nhập. Luồng phiên làm việc cần được kết nối với backend trước khi truy cập dữ liệu thực.",
        );
      }
    } catch (error) {
      if (mounted.current)
        setNotice(
          error instanceof StaffAuthError
            ? staffAuthMessages[error.code]
            : "Không thể kết nối. Vui lòng thử lại sau.",
        );
    } finally {
      busy.current = false;
      if (mounted.current) setPending(false);
    }
  }
  return (
    <main className="staff-auth">
      <aside className="staff-auth-story">
        <div className="staff-auth-brand">
          <IconBuildingCommunity size={32} />
          <span>
            VINHOMES<small>OPERATIONS PLATFORM</small>
          </span>
        </div>
        <div>
          <p className="staff-auth-eyebrow">DÀNH CHO ĐỘI NGŨ VẬN HÀNH</p>
          <h2>
            Mỗi công việc.
            <br />
            Một cộng đồng
            <br />
            an tâm hơn.
          </h2>
          <p>
            Không gian làm việc dành cho đội ngũ kỹ thuật, an ninh, vệ sinh và
            ban quản lý.
          </p>
        </div>
        <div className="staff-auth-story-note">
          <IconShieldCheck size={25} />
          <span>
            Tài khoản được cấp bởi quản trị viên.
            <br />
            Quyền truy cập theo công việc của bạn.
          </span>
        </div>
      </aside>
      <section className="staff-auth-panel">
        <div className="staff-auth-mobile-brand">
          <IconBuildingCommunity size={24} /> Vinhomes Operations
        </div>
        <div className="staff-auth-form-wrap">
          <span className="staff-auth-mark">
            {help ? <IconHelpCircle size={28} /> : <IconLock size={28} />}
          </span>
          <p className="staff-auth-eyebrow">TÀI KHOẢN NHÂN VIÊN</p>
          <h1 ref={heading} tabIndex={-1}>
            {help ? "Cần hỗ trợ đăng nhập?" : "Chào mừng trở lại"}
          </h1>
          <p className="staff-auth-description">
            {help
              ? "Quản trị viên sẽ hỗ trợ kiểm tra tài khoản và cấp lại quyền truy cập cho bạn."
              : "Đăng nhập bằng tài khoản được cấp để bắt đầu công việc của bạn."}
          </p>
          {help ? (
            <div className="staff-auth-help">
              <ol>
                <li>
                  Liên hệ quản trị viên hoặc ban quản lý tại nơi bạn làm việc.
                </li>
                <li>Cung cấp mã nhân viên và bộ phận để được kiểm tra.</li>
                <li>
                  Làm theo hướng dẫn đặt lại mật khẩu hoặc kích hoạt tài khoản.
                </li>
              </ol>
              <p>Không gửi mật khẩu hiện tại cho người hỗ trợ.</p>
              <button
                className="staff-auth-submit"
                onClick={() => setHelp(false)}
              >
                <IconArrowLeft size={18} /> Quay lại đăng nhập
              </button>
            </div>
          ) : (
            <>
              <form noValidate onSubmit={submit}>
                <label htmlFor="staff-identifier">Tài khoản được cấp</label>
                <div className="staff-auth-input">
                  <IconUser size={20} />
                  <input
                    id="staff-identifier"
                    name="identifier"
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    placeholder="Mã nhân viên hoặc email được cấp"
                    maxLength={128}
                    value={identifier}
                    disabled={pending}
                    onChange={(e) => {
                      setIdentifier(e.target.value);
                      setNotice("");
                    }}
                    aria-invalid={submitted && !!errors.identifier}
                    aria-describedby={
                      submitted && errors.identifier
                        ? "staff-identifier-error"
                        : undefined
                    }
                  />
                </div>
                {submitted && errors.identifier && (
                  <p
                    className="staff-auth-error"
                    id="staff-identifier-error"
                    role="alert"
                  >
                    {errors.identifier}
                  </p>
                )}
                <label htmlFor="staff-password">Mật khẩu</label>
                <div className="staff-auth-input">
                  <IconLock size={20} />
                  <input
                    id="staff-password"
                    name="password"
                    type={visible ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Nhập mật khẩu"
                    maxLength={128}
                    value={password}
                    disabled={pending}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setNotice("");
                    }}
                    aria-invalid={submitted && !!errors.password}
                    aria-describedby={
                      submitted && errors.password
                        ? "staff-password-error"
                        : undefined
                    }
                  />
                  <button
                    type="button"
                    aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                    aria-pressed={visible}
                    onClick={() => setVisible((v) => !v)}
                  >
                    {visible ? <IconEyeOff size={20} /> : <IconEye size={20} />}
                  </button>
                </div>
                {submitted && errors.password && (
                  <p
                    className="staff-auth-error"
                    id="staff-password-error"
                    role="alert"
                  >
                    {errors.password}
                  </p>
                )}
                <button
                  type="button"
                  className="staff-auth-forgot"
                  onClick={() => {
                    setHelp(true);
                    setPassword("");
                    setSubmitted(false);
                    setNotice("");
                  }}
                  disabled={pending}
                >
                  Quên mật khẩu?
                </button>
                {notice && (
                  <p className="staff-auth-notice" role="alert">
                    {notice}
                  </p>
                )}
                <button
                  className="staff-auth-submit"
                  disabled={pending}
                  aria-busy={pending}
                >
                  {pending ? "Đang đăng nhập…" : "Đăng nhập"}
                  <IconArrowRight size={19} />
                </button>
              </form>
              <p className="staff-auth-provision">
                Chưa có tài khoản?{" "}
                <button
                  disabled={pending}
                  onClick={() => {
                    setHelp(true);
                    setPassword("");
                    setSubmitted(false);
                    setNotice("");
                  }}
                >
                  Liên hệ quản trị viên
                </button>
              </p>
            </>
          )}
          {help && notice && (
            <p className="staff-auth-notice" role="alert">
              {notice}
            </p>
          )}
          <div className="staff-auth-preview">
            <label htmlFor="preview-account" style={{display:"block",fontSize:12,color:"#65748b",textAlign:"left"}}>Tài khoản để xem giao diện mẫu</label>
            <select id="preview-account" value={previewId} onChange={e=>setPreviewId(e.target.value)} style={{width:"100%",minHeight:44,border:"1px solid #dce3ee",borderRadius:10,padding:8,fontSize:14,marginTop:8,background:"white",color:"#202b40"}}>{previewData.accounts.filter(a=>a.status==="active"&&a.role!=="resident").map(a=><option key={a.id} value={a.id}>{a.identifier} · {roleLabels[a.role]} · {a.scope}</option>)}</select>
            {previewData.error&&<p role="alert">{previewData.error}</p>}
            <button
              disabled={pending}
              onClick={() => {
                try {
                  startOperationsPreview(previewId);
                } catch (error) {
                  setNotice(
                    error instanceof Error?error.message:"Không mở được bản trải nghiệm.",
                  );
                }
              }}
            >
              Xem bản trải nghiệm <IconArrowRight size={16} />
            </button>
            <p>Dữ liệu mẫu · Chưa kết nối đăng nhập</p>
          </div>
        </div>
        <footer className="staff-auth-footer">
          <IconShieldCheck size={16} /> Hệ thống dành cho nhân sự được cấp quyền
        </footer>
      </section>
    </main>
  );
}
