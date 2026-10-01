export type StaffCredentials = { identifier: string; password: string };
export type StaffAuthErrorCode =
  | "invalid-credentials"
  | "locked"
  | "unavailable";
export class StaffAuthError extends Error {
  constructor(public code: StaffAuthErrorCode) {
    super(code);
  }
}
export const staffAuthMessages: Record<StaffAuthErrorCode, string> = {
  "invalid-credentials":
    "Tài khoản hoặc mật khẩu chưa đúng. Vui lòng kiểm tra lại.",
  locked:
    "Tài khoản đang bị khóa hoặc ngừng cấp quyền. Vui lòng liên hệ quản trị viên.",
  unavailable:
    "Chưa kết nối dịch vụ tài khoản nhân viên. Bạn có thể xem giao diện bằng bản trải nghiệm bên dưới.",
};
export interface StaffAuthService {
  signIn(input: StaffCredentials): Promise<void>;
}
export const staffAuthService: StaffAuthService = {
  async signIn() {
    throw new StaffAuthError("unavailable");
  },
};
export function validateStaffCredentials(input: StaffCredentials) {
  return {
    identifier: !input.identifier.trim()
      ? "Nhập tài khoản được quản trị viên cấp."
      : input.identifier.trim().length > 128
        ? "Tài khoản tối đa 128 ký tự."
        : "",
    password: !input.password
      ? "Nhập mật khẩu của bạn."
      : input.password.length > 128
        ? "Mật khẩu tối đa 128 ký tự."
        : "",
  };
}
