import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type FormEvent,
} from "react";
import {
  IconArrowLeft,
  IconArrowUpRight,
  IconEye,
  IconEyeOff,
  IconHome,
  IconInfoCircle,
  IconLock,
  IconPhone,
  IconUser,
} from "@tabler/icons-react";
import { Neighborhood } from "../../components/Illustrations";
import {
  normalizePhone,
  residentAuthService,
  validateAuth,
  type AuthMode,
  type AuthValues,
  type ResidentAuthService,
} from "./auth-service";
import "./auth.css";

const content = {
  login: {
    title: "Đăng nhập tài khoản",
    subtitle: "Vui lòng nhập thông tin của bạn",
    action: "Đăng nhập",
  },
  register: {
    title: "Tạo tài khoản cư dân",
    subtitle: "Kết nối với ngôi nhà của bạn",
    action: "Đăng ký",
  },
  "forgot-password": {
    title: "Quên mật khẩu?",
    subtitle: "Mình sẽ giúp bạn tìm lại kết nối",
    action: "Tiếp tục",
  },
};

export function AuthPage({
  mode,
  service = residentAuthService,
}: {
  mode: AuthMode;
  service?: ResidentAuthService;
}) {
  const [values, setValues] = useState<AuthValues>({
    fullName: "",
    phone: "",
    password: "",
    confirmPassword: "",
  });
  const [touched, setTouched] = useState<
    Partial<Record<keyof AuthValues, boolean>>
  >({});
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);
  const mounted = useRef(true);
  const submitting = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const errors = validateAuth(mode, values);
  const copy = content[mode];
  useEffect(() => {
    mounted.current = true;
    document.title = `${copy.title} — Nhà`;
    heading.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
    return () => {
      mounted.current = false;
    };
  }, [copy.title]);

  function update(field: keyof AuthValues, value: string) {
    setValues((previous) => ({ ...previous, [field]: value }));
    setNotice("");
  }
  const blur = (field: keyof AuthValues) =>
    setTouched((previous) => ({ ...previous, [field]: true }));
  const errorFor = (field: keyof AuthValues) =>
    touched[field] ? errors[field] : undefined;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setTouched({
      fullName: true,
      phone: true,
      password: true,
      confirmPassword: true,
    });
    if (Object.keys(errors).length) {
      const field = Object.keys(errors)[0];
      event.currentTarget
        .querySelector<HTMLInputElement>(`[name="${field}"]`)
        ?.focus();
      return;
    }
    submitting.current = true;
    setPending(true);
    setNotice("");
    try {
      const phone = normalizePhone(values.phone);
      if (mode === "login")
        await service.signIn({ phone, password: values.password });
      else if (mode === "register")
        await service.register({
          fullName: values.fullName.trim(),
          phone,
          password: values.password,
        });
      else await service.requestPasswordReset(phone);
      if (!mounted.current) return;
      setFailed(false);
      if (mode === "login") location.assign("/#/");
      else {
        setValues((previous) => ({
          ...previous,
          password: "",
          confirmPassword: "",
        }));
        setTouched({});
        setNotice(
          mode === "register"
            ? "Đã tiếp nhận thông tin. Vui lòng làm theo hướng dẫn xác minh từ hệ thống."
            : "Nếu thông tin phù hợp với tài khoản, hệ thống sẽ gửi hướng dẫn khôi phục.",
        );
      }
    } catch (error) {
      if (!mounted.current) return;
      setFailed(true);
      setNotice(
        error instanceof Error
          ? error.message
          : "Chưa thể kết nối. Vui lòng thử lại.",
      );
    } finally {
      submitting.current = false;
      if (mounted.current) setPending(false);
    }
  }

  const fields = { values, update, blur, errorFor, disabled: pending };
  return (
    <main className={`resident-auth resident-auth--${mode}`}>
      <aside
        className="resident-auth-story"
        aria-label="Nhà, không gian dành cho cư dân"
      >
        <a href="/#/" className="resident-auth-wordmark">
          <span>
            <IconHome size={25} stroke={1.8} />
          </span>
          nhà.
        </a>
        <div className="resident-auth-story-copy">
          <span className="resident-auth-eyebrow">
            MỘT KẾT NỐI. NGÀN AN TÂM.
          </span>
          <h2>
            Chào mừng bạn
            <br />
            về nhà.
          </h2>
          <p>
            Từ những điều nhỏ mỗi ngày,
            <br />
            đến một cuộc sống thật thảnh thơi.
          </p>
        </div>
        <Neighborhood />
        <p className="resident-auth-story-footer">
          Không gian riêng cho cộng đồng cư dân.
        </p>
      </aside>
      <section
        className="resident-auth-panel"
        aria-labelledby="resident-auth-title"
      >
        <header className="resident-auth-hero">
          <div className="resident-auth-topbar">
            <a
              href={mode === "login" ? "/#/" : "/login"}
              className="resident-auth-back"
              aria-label={
                mode === "login" ? "Về trang Trợ lý" : "Quay lại đăng nhập"
              }
            >
              <IconArrowLeft size={23} />
            </a>
            <span
              className="resident-auth-language"
              aria-label="Ngôn ngữ: Tiếng Việt"
            >
              <span aria-hidden="true">★</span>VIE
            </span>
          </div>
          <div className="resident-auth-heading">
            <h1 id="resident-auth-title" ref={heading} tabIndex={-1}>
              {copy.title}
            </h1>
            <p>{copy.subtitle}</p>
          </div>
        </header>
        <div className="resident-auth-body">
          {mode === "forgot-password" && (
            <p className="resident-auth-intro">
              Nhập số điện thoại bạn đã dùng để đăng ký. Hướng dẫn khôi phục sẽ
              được gửi sau khi hệ thống xác minh.
            </p>
          )}
          <form
            onSubmit={submit}
            noValidate
            aria-label={copy.title}
            aria-busy={pending}
          >
            {mode === "register" && (
              <AuthField
                {...fields}
                field="fullName"
                label="Họ và tên"
                icon={IconUser}
                autoComplete="name"
                maxLength={100}
              />
            )}
            <AuthField
              {...fields}
              field="phone"
              label="Số điện thoại"
              icon={IconPhone}
              type="tel"
              autoComplete="tel-national"
              maxLength={20}
              suffix={`${normalizePhone(values.phone).replace(/\D/g, "").length}/10`}
            />
            {mode !== "forgot-password" && (
              <AuthField
                {...fields}
                field="password"
                label="Mật khẩu"
                icon={IconLock}
                type="password"
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                maxLength={128}
              />
            )}
            {mode === "register" && (
              <>
                <p className="resident-auth-password-hint">
                  Dùng ít nhất 8 ký tự cho mật khẩu của bạn.
                </p>
                <AuthField
                  {...fields}
                  field="confirmPassword"
                  label="Nhập lại mật khẩu"
                  icon={IconLock}
                  type="password"
                  autoComplete="new-password"
                  maxLength={128}
                />
              </>
            )}
            {mode === "login" && (
              <div className="resident-auth-forgot">
                <a href="/forgot-password">Quên mật khẩu?</a>
              </div>
            )}
            {notice && (
              <div
                className={`resident-auth-notice ${failed ? "is-error" : ""}`}
                role={failed ? "alert" : "status"}
              >
                <IconInfoCircle size={19} />
                <p>{notice}</p>
              </div>
            )}
            <button
              className="resident-auth-submit"
              type="submit"
              disabled={pending}
            >
              {pending ? (
                <>
                  <span className="resident-auth-spinner" />
                  Đang xử lý…
                </>
              ) : (
                copy.action
              )}
            </button>
          </form>
          <p className="resident-auth-switch">
            {mode === "login" ? (
              <>
                Bạn chưa có tài khoản cư dân? <a href="/register">Đăng ký</a>
              </>
            ) : mode === "register" ? (
              <>
                Bạn đã có tài khoản? <a href="/login">Đăng nhập</a>
              </>
            ) : (
              <a href="/login">Quay lại đăng nhập</a>
            )}
          </p>
          {mode === "register" && (
            <p className="resident-auth-membership">
              Tài khoản sẽ được liên kết với căn hộ sau khi xác minh thông tin
              cư dân.
            </p>
          )}
          <div className="resident-auth-demo">
            <a href="/#/">
              Khám phá bản trải nghiệm <IconArrowUpRight size={16} />
            </a>
            <p>Giao diện mẫu · Chưa kết nối dịch vụ tài khoản</p>
          </div>
        </div>
        <footer className="resident-auth-footer">
          <IconHome size={15} />
          Nhà là nơi được quan tâm.
        </footer>
      </section>
    </main>
  );
}

type FieldProps = {
  field: keyof AuthValues;
  label: string;
  icon: ComponentType<{ size?: number; stroke?: number }>;
  type?: "text" | "tel" | "password";
  autoComplete: string;
  maxLength: number;
  suffix?: string;
  values: AuthValues;
  update: (field: keyof AuthValues, value: string) => void;
  blur: (field: keyof AuthValues) => void;
  errorFor: (field: keyof AuthValues) => string | undefined;
  disabled: boolean;
};
function AuthField({
  field,
  label,
  icon: Icon,
  type = "text",
  autoComplete,
  maxLength,
  suffix,
  values,
  update,
  blur,
  errorFor,
  disabled,
}: FieldProps) {
  const [visible, setVisible] = useState(false);
  const error = errorFor(field);
  const id = `resident-auth-${field}`;
  return (
    <div className={`resident-auth-field ${error ? "has-error" : ""}`}>
      <div className="resident-auth-field-row">
        <span className="resident-auth-field-icon">
          <Icon size={25} stroke={1.55} />
        </span>
        <div className="resident-auth-input-wrap">
          <label htmlFor={id}>{label}</label>
          <input
            id={id}
            name={field}
            type={type === "password" && visible ? "text" : type}
            value={values[field]}
            onChange={(event) => update(field, event.target.value)}
            onBlur={() => blur(field)}
            autoComplete={autoComplete}
            maxLength={maxLength}
            disabled={disabled}
            required
            aria-invalid={!!error}
            aria-describedby={error ? `${id}-error` : undefined}
            placeholder={
              type === "password"
                ? "Nhập mật khẩu của bạn"
                : field === "phone"
                  ? "Nhập số điện thoại"
                  : "Nhập họ và tên"
            }
            inputMode={type === "tel" ? "tel" : undefined}
            autoCapitalize={type === "password" ? "none" : undefined}
            spellCheck={false}
          />
        </div>
        {type === "password" ? (
          <button
            className="resident-auth-eye"
            type="button"
            aria-label={`${visible ? "Ẩn" : "Hiện"} ${label.toLowerCase()}`}
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            {visible ? (
              <IconEyeOff size={24} stroke={1.6} />
            ) : (
              <IconEye size={24} stroke={1.6} />
            )}
          </button>
        ) : (
          suffix && (
            <span className="resident-auth-counter" aria-hidden="true">
              {suffix}
            </span>
          )
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className="resident-auth-field-error">
          {error}
        </p>
      )}
    </div>
  );
}
