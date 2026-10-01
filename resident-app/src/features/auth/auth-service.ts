/** Resident-only integration port. Never import staff UI/auth implementation here. */
export type LoginInput = { phone: string; password: string };
export type RegisterInput = LoginInput & { fullName: string };
export type ResidentAuthResult = {
  nextStep: "verification-required" | "membership-pending" | "ready";
};
export interface ResidentAuthService {
  identityMode?: "email";
  signIn(input: LoginInput): Promise<ResidentAuthResult>;
  register(input: RegisterInput): Promise<ResidentAuthResult>;
  requestPasswordReset(phone: string): Promise<void>;
}

async function authRequest(path: string, body?: object) {
  const response = await fetch(`/api/business${path}`, {
    method: body ? "POST" : "GET", credentials: "include",
    ...(body ? {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {}),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Không kết nối được tài khoản (${response.status}).`);
  return data;
}

export const residentAuthService: ResidentAuthService = {
  identityMode: "email",
  async signIn({phone, password}) {
    await authRequest("/auth/login", {identifier: phone.trim(), password});
    const session = await authRequest("/auth/session");
    if (session.membershipStatus === "pending") return {nextStep: "membership-pending"};
    const profile = await authRequest("/resident/me");
    return {nextStep: profile.units.length ? "ready" : "verification-required"};
  },
  async register({fullName, phone, password}) {
    await authRequest("/auth/register", {name: fullName, email: phone.trim(), password});
    return {nextStep: "membership-pending"};
  },
  async requestPasswordReset() {
    throw new Error(
      "Khôi phục mật khẩu chưa được kết nối. Chưa có mã xác minh nào được gửi.",
    );
  },
};

export type AuthMode = "login" | "register" | "forgot-password";
export type AuthValues = {
  fullName: string;
  phone: string;
  password: string;
  confirmPassword: string;
};
export type AuthErrors = Partial<Record<keyof AuthValues, string>>;

export function normalizePhone(value: string): string {
  const compact = value.replace(/[\s().-]/g, "");
  return compact.startsWith("+84") ? `0${compact.slice(3)}` : compact;
}

export function validateAuth(mode: AuthMode, values: AuthValues, identityMode?: "email"): AuthErrors {
  const errors: AuthErrors = {};
  if (identityMode === "email") {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.phone.trim()) || values.phone.trim().length > 254)
      errors.phone = "Nhập địa chỉ email hợp lệ.";
  } else if (!/^0\d{9}$/.test(normalizePhone(values.phone)))
    errors.phone = "Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.";
  if (mode === "register") {
    const name = values.fullName.trim();
    if (name.length < 2 || name.length > 100)
      errors.fullName = "Họ và tên cần từ 2 đến 100 ký tự.";
    if (values.password.length < (identityMode ? 12 : 8) || values.password.length > 128)
      errors.password = `Mật khẩu cần từ ${identityMode ? 12 : 8} đến 128 ký tự.`;
    if (!values.confirmPassword)
      errors.confirmPassword = "Nhập lại mật khẩu để xác nhận.";
    else if (values.confirmPassword !== values.password)
      errors.confirmPassword = "Mật khẩu nhập lại chưa khớp.";
  } else if (mode === "login" && !values.password) {
    errors.password = "Vui lòng nhập mật khẩu.";
  } else if (mode === "login" && values.password.length > 128) {
    errors.password = "Mật khẩu tối đa 128 ký tự.";
  }
  return errors;
}
