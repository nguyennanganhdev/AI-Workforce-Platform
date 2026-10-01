import { expect, test } from "bun:test";
import {
  StaffAuthError,
  staffAuthService,
  validateStaffCredentials,
} from "../src/features/vinhomes-operations/auth/auth-service";

test("staff login requires the assigned identifier and password, without a new-password policy", () => {
  expect(
    validateStaffCredentials({ identifier: "  ", password: "" }).identifier,
  ).not.toBe("");
  expect(
    validateStaffCredentials({ identifier: "NV-101", password: "" }).password,
  ).not.toBe("");
  for (const identifier of ["NV-101", "staff@example.test"]) {
    expect(
      validateStaffCredentials({ identifier, password: "legacy" }),
    ).toEqual({ identifier: "", password: "" });
  }
});
test("staff adapter cannot create accounts or report a successful login before BE integration", async () => {
  expect("register" in staffAuthService).toBe(false);
  try {
    await staffAuthService.signIn({
      identifier: "NV-101",
      password: "example-password",
    });
    throw new Error("Unexpected successful login");
  } catch (error) {
    expect(error).toBeInstanceOf(StaffAuthError);
    expect((error as StaffAuthError).code).toBe("unavailable");
  }
});
