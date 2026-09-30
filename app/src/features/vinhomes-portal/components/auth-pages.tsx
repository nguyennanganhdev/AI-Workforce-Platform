import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { motion, useReducedMotion } from 'motion/react';
import { IconAlertCircle, IconArrowLeft, IconEye, IconEyeOff, IconLoader2 } from '@tabler/icons-react';
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import heroPhoto from '../assets/ocean-park-dusk.jpg';
import {
  AuthError,
  DEMO_ACCOUNTS,
  DEMO_PASSWORD,
  TOWERS,
  destinationFor,
  registerResident,
  roleLabel,
  signIn,
  validateLogin,
  validateRegister,
  type FieldErrors,
  type LoginValues,
  type PortalAccount,
  type RegisterValues,
} from '../auth/accounts';
import { endSession, getSession, startSession } from '../auth/session';
import { PORTAL_FONT, Wordmark, accentButton, accentText } from './brand';

const EASE = [0.16, 1, 0.3, 1] as const;
const INPUT = 'h-11 rounded-xl bg-background px-3.5 text-[15px] md:text-[15px]';

function AuthShell({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <div lang="vi" className={cn(PORTAL_FONT, 'grid min-h-[100dvh] bg-background text-foreground antialiased lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]')}>
      <aside className="relative isolate hidden overflow-hidden bg-zinc-950 p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <motion.img
          src={heroPhoto}
          alt="Khu đô thị Vinhomes Ocean Park lúc hoàng hôn"
          className="absolute inset-0 -z-20 size-full object-cover object-[62%_center]"
          initial={reduce ? false : { scale: 1.06 }}
          animate={{ scale: 1 }}
          transition={{ duration: 2, ease: EASE }}
        />
        <div className="absolute inset-0 -z-10 bg-gradient-to-t from-zinc-950/90 via-zinc-950/35 to-zinc-950/50" />
        <Wordmark onPhoto />
        <div className="max-w-md">
          <p className="text-3xl leading-tight font-semibold tracking-tight text-balance">Một tài khoản, mở đúng phần việc của bạn.</p>
          <p className="mt-3 text-[15px] leading-relaxed text-white/75">Cư dân vào trợ lý cư dân. Ban quản lý và nhân viên vào màn hình vận hành theo vai trò.</p>
        </div>
      </aside>

      <main className="flex min-w-0 flex-col px-4 py-6 sm:px-8">
        <div className="flex items-center justify-between lg:justify-end">
          <Wordmark className="lg:hidden" />
          <Link to="/vinhomes" className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
            <IconArrowLeft className="size-4" /> Trang chủ
          </Link>
        </div>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            {children}
          </motion.div>
        </div>
      </main>
    </div>
  );
}

function FormAlert({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="flex gap-2 rounded-xl bg-destructive/10 px-3.5 py-3 text-sm text-destructive">
      <IconAlertCircle className="mt-0.5 size-4 shrink-0" />
      {children}
    </p>
  );
}

function PasswordInput({
  id,
  value,
  onChange,
  invalid,
  autoComplete,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  invalid: boolean;
  autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        aria-invalid={invalid}
        className={cn(INPUT, 'pr-12')}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        className="absolute inset-y-0 right-1 my-auto flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        {visible ? <IconEyeOff className="size-5" stroke={1.5} /> : <IconEye className="size-5" stroke={1.5} />}
      </button>
    </div>
  );
}

function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <button type="submit" disabled={pending} className={cn(accentButton, 'mt-2 w-full')}>
      {pending && <IconLoader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

const formatPhone = (phone: string) => phone.replace(/^(\d{4})(\d{3})(\d{3})$/, '$1 $2 $3');

// ---------------------------------------------------------------------------------------------------

export function LoginPage({ requiredRole }: { requiredRole?: 'resident' | 'staff' }) {
  const navigate = useNavigate();
  const ids = { phone: useId(), password: useId() };
  const [session, setSession] = useState(getSession);
  const [values, setValues] = useState<LoginValues>({ phone: '', password: '' });
  const [errors, setErrors] = useState<FieldErrors<LoginValues>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const enter = (account: PortalAccount) => navigate({ to: destinationFor(account) });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    const found = validateLogin(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setPending(true);
    try {
      const account = await signIn(values);
      startSession(account);
      enter(account);
    } catch (e) {
      setFormError(e instanceof AuthError ? e.message : 'Chưa đăng nhập được, bạn thử lại nhé.');
      setPending(false);
    }
  };

  const fillDemo = (account: PortalAccount) => {
    setValues({ phone: formatPhone(account.phone), password: DEMO_PASSWORD });
    setErrors({});
    setFormError(null);
  };

  return (
    <AuthShell>
      <h1 className="text-3xl font-semibold tracking-tight">Đăng nhập</h1>
      <p className="mt-2 text-[15px] text-muted-foreground">
        {requiredRole === 'resident'
          ? 'Đăng nhập tài khoản cư dân để mở trợ lý cư dân.'
          : requiredRole === 'staff'
            ? 'Đăng nhập tài khoản Ban quản lý hoặc nhân viên để mở màn hình vận hành.'
            : 'Dùng số điện thoại đã đăng ký. Hệ thống mở đúng phần việc theo vai trò của bạn.'}
      </p>

      {session && (
        <div className="mt-6 flex flex-col gap-3 rounded-2xl border bg-muted/40 p-4">
          <p className="text-sm">
            Bạn đang đăng nhập: <span className="font-medium">{session.name}</span> ({roleLabel(session)})
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={cn(accentButton, 'h-9 px-4 text-sm')} onClick={() => enter(session)}>
              Tiếp tục
            </button>
            <button
              type="button"
              className="h-9 rounded-full px-4 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => {
                endSession();
                setSession(null);
              }}
            >
              Đăng xuất
            </button>
          </div>
        </div>
      )}

      <form onSubmit={submit} noValidate className="mt-8">
        <FieldGroup className="gap-5">
          {formError && <FormAlert>{formError}</FormAlert>}
          <Field>
            <FieldLabel htmlFor={ids.phone}>Số điện thoại</FieldLabel>
            <Input
              id={ids.phone}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={values.phone}
              onChange={(e) => setValues((v) => ({ ...v, phone: e.target.value }))}
              aria-invalid={!!errors.phone}
              className={INPUT}
            />
            <FieldError>{errors.phone}</FieldError>
          </Field>
          <Field>
            <FieldLabel htmlFor={ids.password}>Mật khẩu</FieldLabel>
            <PasswordInput
              id={ids.password}
              value={values.password}
              onChange={(password) => setValues((v) => ({ ...v, password }))}
              invalid={!!errors.password}
              autoComplete="current-password"
            />
            <FieldError>{errors.password}</FieldError>
            <FieldDescription>Quên mật khẩu? Liên hệ Ban quản lý tòa để được cấp lại.</FieldDescription>
          </Field>
          <SubmitButton pending={pending}>Đăng nhập</SubmitButton>
        </FieldGroup>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Chưa có tài khoản cư dân?{' '}
        <Link to="/vinhomes/register" className={cn('font-medium underline-offset-4 hover:underline', accentText)}>
          Đăng ký
        </Link>
      </p>

      <section className="mt-10 border-t pt-6" aria-labelledby="demo-accounts">
        <h2 id="demo-accounts" className="text-sm font-medium">
          Tài khoản dùng thử
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Chọn một tài khoản để điền sẵn. Mật khẩu chung: <span className="font-medium text-foreground">{DEMO_PASSWORD}</span>
        </p>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {DEMO_ACCOUNTS.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => fillDemo(a)}
                className="flex w-full flex-col items-start rounded-2xl border px-3.5 py-2.5 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-teal-600/40"
              >
                <span className="text-sm font-medium">{roleLabel(a)}</span>
                <span className="text-xs text-muted-foreground">{a.name}</span>
                <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{formatPhone(a.phone)}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </AuthShell>
  );
}

// ---------------------------------------------------------------------------------------------------

const EMPTY_REGISTER: RegisterValues = { name: '', phone: '', towerCode: '', apartmentCode: '', password: '', confirmPassword: '' };

export function RegisterPage() {
  const navigate = useNavigate();
  const ids = {
    name: useId(),
    phone: useId(),
    tower: useId(),
    apartment: useId(),
    password: useId(),
    confirm: useId(),
  };
  const [values, setValues] = useState<RegisterValues>(EMPTY_REGISTER);
  const [errors, setErrors] = useState<FieldErrors<RegisterValues>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const set = (key: keyof RegisterValues) => (value: string) => setValues((v) => ({ ...v, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    const found = validateRegister(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setPending(true);
    try {
      const account = await registerResident(values);
      startSession(account);
      navigate({ to: '/resident' });
    } catch (e) {
      setFormError(e instanceof AuthError ? e.message : 'Chưa tạo được tài khoản, bạn thử lại nhé.');
      setPending(false);
    }
  };

  return (
    <AuthShell>
      <h1 className="text-3xl font-semibold tracking-tight">Đăng ký cư dân</h1>
      <p className="mt-2 text-[15px] text-muted-foreground">Thông tin căn hộ giúp yêu cầu của bạn tới đúng Ban quản lý tòa.</p>

      <form onSubmit={submit} noValidate className="mt-8">
        <FieldGroup className="gap-5">
          {formError && <FormAlert>{formError}</FormAlert>}
          <Field>
            <FieldLabel htmlFor={ids.name}>Họ và tên</FieldLabel>
            <Input id={ids.name} autoComplete="name" value={values.name} onChange={(e) => set('name')(e.target.value)} aria-invalid={!!errors.name} className={INPUT} />
            <FieldError>{errors.name}</FieldError>
          </Field>
          <Field>
            <FieldLabel htmlFor={ids.phone}>Số điện thoại</FieldLabel>
            <Input
              id={ids.phone}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={values.phone}
              onChange={(e) => set('phone')(e.target.value)}
              aria-invalid={!!errors.phone}
              className={INPUT}
            />
            <FieldError>{errors.phone}</FieldError>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field>
              <FieldLabel htmlFor={ids.tower}>Tòa</FieldLabel>
              <select
                id={ids.tower}
                value={values.towerCode}
                onChange={(e) => set('towerCode')(e.target.value)}
                aria-invalid={!!errors.towerCode}
                className={cn(
                  INPUT,
                  'w-full border border-input outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:bg-input/30',
                )}
              >
                <option value="">Chọn tòa</option>
                {TOWERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <FieldError>{errors.towerCode}</FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor={ids.apartment}>Số căn hộ</FieldLabel>
              <Input
                id={ids.apartment}
                inputMode="numeric"
                value={values.apartmentCode}
                onChange={(e) => set('apartmentCode')(e.target.value)}
                aria-invalid={!!errors.apartmentCode}
                className={INPUT}
              />
              <FieldError>{errors.apartmentCode}</FieldError>
            </Field>
          </div>
          <Field>
            <FieldLabel htmlFor={ids.password}>Mật khẩu</FieldLabel>
            <PasswordInput id={ids.password} value={values.password} onChange={set('password')} invalid={!!errors.password} autoComplete="new-password" />
            {errors.password ? <FieldError>{errors.password}</FieldError> : <FieldDescription>Ít nhất 8 ký tự.</FieldDescription>}
          </Field>
          <Field>
            <FieldLabel htmlFor={ids.confirm}>Nhập lại mật khẩu</FieldLabel>
            <PasswordInput id={ids.confirm} value={values.confirmPassword} onChange={set('confirmPassword')} invalid={!!errors.confirmPassword} autoComplete="new-password" />
            <FieldError>{errors.confirmPassword}</FieldError>
          </Field>
          <SubmitButton pending={pending}>Tạo tài khoản</SubmitButton>
        </FieldGroup>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Đã có tài khoản?{' '}
        <Link to="/vinhomes/login" className={cn('font-medium underline-offset-4 hover:underline', accentText)}>
          Đăng nhập
        </Link>
      </p>
    </AuthShell>
  );
}
