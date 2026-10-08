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
  signIn(input: StaffCredentials): Promise<void | {role: string}>;
}
export const staffAuthService: StaffAuthService = {
  async signIn(input) {
    const response = await fetch("/api/business/auth/login", {method: "POST", credentials: "include",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(input)});
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      if (response.status === 401) throw new StaffAuthError("invalid-credentials");
      throw new Error(typeof data?.detail === "string" ? data.detail : "Không kết nối được dịch vụ đăng nhập.");
    }
    const me = await fetch("/api/business/operations/me", {credentials: "include"});
    if (me.status === 403) {
      const refusal = (await me.json().catch(() => null))?.detail;
      // This account signs in at the other staff address: it is told so, and no sign-in is left behind here.
      if (refusal?.code === "WRONG_DOOR") {
        await fetch("/api/business/auth/logout", {method: "POST", credentials: "include"}).catch(() => undefined);
        throw new Error(refusal.message);
      }
      throw new Error("Tài khoản chưa được cấp quyền nhân viên/BQL. Liên hệ quản trị viên để được hỗ trợ.");
    }
    if (!me.ok) throw new Error("Không tải được quyền truy cập. Vui lòng thử đăng nhập lại.");
    const identity = await me.json();
    if (identity.dataMode !== "database" || !["admin", "management", "staff"].includes(identity.role))
      throw new Error("Danh tính hoặc chế độ backend không hợp lệ.");
    return {role: identity.role};
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
