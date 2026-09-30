/**
 * Vinhomes portal accounts (bản trải nghiệm).
 *
 * Residents register themselves (họ tên, số điện thoại, căn hộ, mật khẩu); BQL and staff accounts are
 * issued by the admin, represented here by fixed demo accounts. Registered residents live in this
 * browser's localStorage with a SHA-256 password digest, never the password itself. The real backend
 * (Better Auth) replaces this module; screens only use signIn / registerResident / destinationFor.
 */
import { PERSONA_PROFILES, type OperationsPersona } from '@/features/vinhomes-operations/types/persona';
import { DEMO_RESIDENT } from '@/features/vinhomes-resident/mock/profile';

export type AccountRole = 'RESIDENT' | 'STAFF';

export interface PortalAccount {
  id: string;
  role: AccountRole;
  name: string;
  /** 10 chữ số, không khoảng trắng. */
  phone: string;
  /** STAFF only: the operations role the account opens into. */
  persona?: OperationsPersona;
  /** RESIDENT only. */
  towerCode?: string;
  apartmentCode?: string;
}

interface StoredResident extends PortalAccount {
  passwordDigest: string;
}

/** Mật khẩu chung của các tài khoản dùng thử. */
export const DEMO_PASSWORD = 'Vinhomes@2026';

export const TOWERS = ['S1.01', 'S1.02', 'S1.03', 'S1.05', 'S2.01', 'S2.02', 'S2.03', 'S2.05'];

export const ROLE_LABELS: Record<OperationsPersona | 'RESIDENT', string> = {
  RESIDENT: 'Cư dân',
  MANAGER: 'Ban quản lý',
  STAFF_TECHNICAL: 'Kỹ thuật viên',
  STAFF_SANITATION_A5: 'Nhân viên vệ sinh',
  STAFF_SECURITY: 'Nhân viên an ninh',
  SUPERVISOR: 'Giám sát',
  QC_INSPECTOR: 'Nghiệm thu',
  CONTRACTOR: 'Nhà thầu',
};

export const normalizePhone = (value: string) => value.replace(/[\s.-]/g, '');

const staff = (persona: OperationsPersona): PortalAccount => {
  const p = PERSONA_PROFILES[persona];
  return { id: p.id, role: 'STAFF', name: p.name, phone: normalizePhone(p.phone), persona };
};

/** Tài khoản dùng thử: một cư dân và các vai trò nhân viên đang có trong app vận hành. */
export const DEMO_ACCOUNTS: PortalAccount[] = [
  {
    id: DEMO_RESIDENT.userId,
    role: 'RESIDENT',
    name: DEMO_RESIDENT.name,
    phone: normalizePhone(DEMO_RESIDENT.phone),
    towerCode: DEMO_RESIDENT.towerCode,
    apartmentCode: DEMO_RESIDENT.apartmentCode,
  },
  staff('MANAGER'),
  staff('STAFF_TECHNICAL'),
  staff('STAFF_SANITATION_A5'),
  staff('STAFF_SECURITY'),
];

export function roleLabel(account: Pick<PortalAccount, 'role' | 'persona'>): string {
  return account.role === 'RESIDENT' ? ROLE_LABELS.RESIDENT : ROLE_LABELS[account.persona ?? 'MANAGER'];
}

/** Trang mở ra sau khi đăng nhập, theo vai trò. */
export function destinationFor(account: Pick<PortalAccount, 'role' | 'persona'>): '/resident' | '/operations' | '/operations/my-tasks' {
  if (account.role === 'RESIDENT') return '/resident';
  return account.persona === 'MANAGER' ? '/operations' : '/operations/my-tasks';
}

// ---------- Validation ----------

export interface LoginValues {
  phone: string;
  password: string;
}

export interface RegisterValues extends LoginValues {
  name: string;
  towerCode: string;
  apartmentCode: string;
  confirmPassword: string;
}

export type FieldErrors<T> = Partial<Record<keyof T, string>>;

const phoneError = (phone: string) =>
  /^0\d{9}$/.test(normalizePhone(phone)) ? undefined : 'Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.';

export function validateLogin(values: LoginValues): FieldErrors<LoginValues> {
  const errors: FieldErrors<LoginValues> = {};
  const phone = phoneError(values.phone);
  if (phone) errors.phone = phone;
  if (!values.password) errors.password = 'Vui lòng nhập mật khẩu.';
  return errors;
}

export function validateRegister(values: RegisterValues): FieldErrors<RegisterValues> {
  const errors: FieldErrors<RegisterValues> = {};
  if (values.name.trim().length < 2) errors.name = 'Vui lòng nhập họ và tên.';
  const phone = phoneError(values.phone);
  if (phone) errors.phone = phone;
  if (!TOWERS.includes(values.towerCode)) errors.towerCode = 'Chọn tòa bạn đang ở.';
  if (!/^\d{3,4}$/.test(values.apartmentCode.trim())) errors.apartmentCode = 'Nhập số căn hộ, ví dụ 1208.';
  if (values.password.length < 8 || values.password.length > 128) errors.password = 'Mật khẩu cần từ 8 đến 128 ký tự.';
  else if (values.confirmPassword !== values.password) errors.confirmPassword = 'Mật khẩu nhập lại chưa khớp.';
  return errors;
}

// ---------- Storage ----------

const ACCOUNTS_KEY = 'vhm_portal_v1_residents';

async function digest(phone: string, password: string): Promise<string> {
  const bytes = new TextEncoder().encode(`${phone}:${password}`);
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function readResidents(): StoredResident[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(ACCOUNTS_KEY) ?? '[]');
    return Array.isArray(value) ? (value as StoredResident[]) : [];
  } catch {
    return [];
  }
}

const publicPart = ({ passwordDigest: _, ...account }: StoredResident): PortalAccount => account;

export class AuthError extends Error {}

/** Returns the account for a correct phone + password, otherwise throws AuthError. */
export async function signIn(values: LoginValues): Promise<PortalAccount> {
  const phone = normalizePhone(values.phone);
  const demo = DEMO_ACCOUNTS.find((a) => a.phone === phone);
  if (demo && values.password === DEMO_PASSWORD) return demo;
  const stored = readResidents().find((a) => a.phone === phone);
  if (stored && stored.passwordDigest === (await digest(phone, values.password))) return publicPart(stored);
  throw new AuthError('Số điện thoại hoặc mật khẩu chưa đúng.');
}

export async function registerResident(values: RegisterValues): Promise<PortalAccount> {
  const phone = normalizePhone(values.phone);
  const residents = readResidents();
  if (DEMO_ACCOUNTS.some((a) => a.phone === phone) || residents.some((a) => a.phone === phone)) {
    throw new AuthError('Số điện thoại này đã có tài khoản. Bạn đăng nhập nhé.');
  }
  const account: StoredResident = {
    id: `usr-res-${crypto.randomUUID().slice(0, 8)}`,
    role: 'RESIDENT',
    name: values.name.trim().replace(/\s+/g, ' '),
    phone,
    towerCode: values.towerCode,
    apartmentCode: values.apartmentCode.trim(),
    passwordDigest: await digest(phone, values.password),
  };
  try {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify([...residents, account]));
  } catch {
    throw new AuthError('Chưa lưu được tài khoản trên trình duyệt này. Bạn thử lại nhé.');
  }
  return publicPart(account);
}
