import { expect, test } from "vitest";
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
test("staff adapter requires backend role after password authentication", async () => {
  const original = globalThis.fetch;
  let allowed = false;
  globalThis.fetch = (async (url: RequestInfo | URL) => String(url).endsWith('/login') ? Response.json({user: {id: 'person'}}) : allowed ? Response.json({role: 'staff', dataMode: 'database'}) : Response.json({detail: 'Forbidden'}, {status: 403})) as typeof fetch;
  try {
    expect('register' in staffAuthService).toBe(false);
    await expect(staffAuthService.signIn({identifier: 'person@example.test', password: 'testpassword'})).rejects.toThrow('chưa được cấp quyền');
    allowed = true;
    expect(await staffAuthService.signIn({identifier: 'person@example.test', password: 'testpassword'})).toEqual({role: 'staff'});
  } finally {globalThis.fetch = original;}
});
