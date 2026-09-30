import { describe, expect, test } from "bun:test";
import {
  normalizePhone,
  residentAuthService,
  validateAuth,
  type AuthValues,
} from "../src/features/auth/auth-service";

const valid: AuthValues = {
  fullName: "Cư dân thử nghiệm",
  phone: "0900000000",
  password: "example-password",
  confirmPassword: "example-password",
};

describe("Resident auth boundary", () => {
  test("normalizes common local and country-code phone input without accepting non-phone text", () => {
    expect(normalizePhone("+84 900 000 000")).toBe("0900000000");
    expect(normalizePhone("0900-000-000")).toBe("0900000000");
    expect(
      validateAuth("login", { ...valid, phone: "+84 900 000 000" }),
    ).toEqual({});
    for (const phone of [
      "0900",
      "09000000000",
      "090000000a",
      "",
      "1900000000",
    ]) {
      expect(validateAuth("login", { ...valid, phone }).phone).toBeDefined();
    }
  });
  test("registration checks identity and exact password confirmation", () => {
    expect(validateAuth("register", valid)).toEqual({});
    const errors = validateAuth("register", {
      ...valid,
      fullName: " ",
      password: "123",
      confirmPassword: "1234",
    });
    expect(errors.fullName).toBeDefined();
    expect(errors.password).toBeDefined();
    expect(errors.confirmPassword).toBeDefined();
    expect(
      validateAuth("register", {
        ...valid,
        confirmPassword: `${valid.password} `,
      }).confirmPassword,
    ).toBeDefined();
  });
  test("reset needs only a phone and login does not enforce new-account minimum password length", () => {
    expect(
      validateAuth("forgot-password", {
        ...valid,
        fullName: "",
        password: "",
        confirmPassword: "",
      }),
    ).toEqual({});
    expect(validateAuth("login", { ...valid, password: "legacy" })).toEqual({});
    expect(
      validateAuth("login", { ...valid, password: "" }).password,
    ).toBeDefined();
    expect(
      validateAuth("login", { ...valid, password: "x".repeat(129) }).password,
    ).toBeDefined();
  });
  test("unconfigured adapter never reports successful login, registration or sent reset code", async () => {
    await expect(residentAuthService.signIn(valid)).rejects.toThrow(
      "chưa được kết nối",
    );
    await expect(residentAuthService.register(valid)).rejects.toThrow(
      "tài khoản chưa được tạo",
    );
    await expect(
      residentAuthService.requestPasswordReset(valid.phone),
    ).rejects.toThrow("Chưa có mã xác minh");
  });
});
