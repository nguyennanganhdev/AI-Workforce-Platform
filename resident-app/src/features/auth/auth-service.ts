/** Resident-only integration port. Never import staff UI/auth implementation here. */
export type LoginInput = { phone: string; password: string };
export type RegisterInput = LoginInput & { fullName: string };
export type ResidentAuthResult = {
  nextStep: "verification-required" | "membership-pending" | "ready";
};
export interface ResidentAuthService {
  signIn(input: LoginInput): Promise<ResidentAuthResult>;
  register(input: RegisterInput): Promise<ResidentAuthResult>;
  requestPasswordReset(phone: string): Promise<void>;
}

// Deliberately unavailable until BE supplies the resident identity contract.
// No credentials, accounts, session tokens or passwords are persisted by this adapter.
export const residentAuthService: ResidentAuthService = {
  async signIn() {
    throw new Error(
      "Đăng nhập chưa được kết nối. Bạn có thể khám phá bản trải nghiệm bên dưới.",
    );
  },
  async register() {
    throw new Error(
      "Đăng ký chưa được kết nối. Thông tin của bạn chưa được gửi và tài khoản chưa được tạo.",
    );
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

export function validateAuth(mode: AuthMode, values: AuthValues): AuthErrors {
  const errors: AuthErrors = {};
  if (!/^0\d{9}$/.test(normalizePhone(values.phone)))
    errors.phone = "Nhập số điện thoại gồm 10 chữ số, bắt đầu bằng 0.";
  if (mode === "register") {
    const name = values.fullName.trim();
    if (name.length < 2 || name.length > 100)
      errors.fullName = "Họ và tên cần từ 2 đến 100 ký tự.";
    if (values.password.length < 8 || values.password.length > 128)
      errors.password = "Mật khẩu cần từ 8 đến 128 ký tự.";
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
