import { describe, expect, test } from "vitest";
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
  test("administrator signing in on resident form goes to administration without apartment verification", async () => {
    const original = globalThis.fetch;
    const paths: string[] = [];
    globalThis.fetch = (async (url: RequestInfo | URL) => {
      paths.push(String(url));
      return Response.json(String(url).endsWith('/session') ? {membershipStatus: 'active', administrator: true} : {units: []});
    }) as typeof fetch;
    try {
      expect(await residentAuthService.signIn(valid)).toEqual({nextStep: 'administration'});
      expect(paths.includes('/api/business/resident/me')).toBe(false);
    } finally { globalThis.fetch = original; }
  });
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
  test("real auth routes pending and unverified residents without granting access", async () => {
    const original = globalThis.fetch;
    const paths: string[] = [];
    let pending = true;
    globalThis.fetch = (async (url: RequestInfo | URL) => {
      paths.push(String(url));
      return Response.json(String(url).endsWith('/session') ? {membershipStatus: pending ? 'pending' : 'active'} : String(url).endsWith('/resident/me') ? {units: []} : {});
    }) as typeof fetch;
    try {
      expect(await residentAuthService.signIn(valid)).toEqual({nextStep: 'membership-pending'});
      expect(paths.includes('/api/business/resident/me')).toBe(false);
      pending = false;
      expect(await residentAuthService.signIn(valid)).toEqual({nextStep: 'verification-required'});
      expect(await residentAuthService.register(valid)).toEqual({nextStep: 'membership-pending'});
      await expect(residentAuthService.requestPasswordReset(valid.phone)).rejects.toThrow('Chưa có mã xác minh');
    } finally {globalThis.fetch = original;}
  });
  test("live form validates email and the backend password minimum", () => {
    expect(validateAuth('register', {...valid, phone: 'person@example.test'}, 'email')).toEqual({});
    expect(validateAuth('register', {...valid, phone: 'person@example.test', password: 'shortpass'}, 'email').password).toBeDefined();
    expect(validateAuth('login', {...valid, phone: 'invalid'}, 'email').phone).toBeDefined();
  });

  async function signInAs(session: object, units: unknown[] = []) {
    const original = globalThis.fetch;
    const paths: string[] = [];
    globalThis.fetch = (async (url: RequestInfo | URL) => {
      paths.push(String(url));
      return Response.json(String(url).endsWith("/session") ? { membershipStatus: "active", administrator: false, ...session } : { units });
    }) as typeof fetch;
    try { return { result: await residentAuthService.signIn(valid), paths }; } finally { globalThis.fetch = original; }
  }
  test("one sign-in page sends staff to the operations app on the page that fits their role", async () => {
    const staff = await signInAs({ operationsRole: "staff", audiences: ["operations"] });
    expect(staff.result).toEqual({ nextStep: "operations", operationsPath: "/operations/my-tasks" });
    expect(staff.paths.includes("/api/business/resident/me")).toBe(false);
    const manager = await signInAs({ operationsRole: "management", audiences: ["operations"] });
    expect(manager.result).toEqual({ nextStep: "operations", operationsPath: "/operations/kanban" });
  });
  test("a resident stays in the resident app, and an account that is both is asked where to go", async () => {
    expect((await signInAs({ operationsRole: null, audiences: ["resident"] }, [{ id: "u1" }])).result).toEqual({ nextStep: "ready" });
    expect((await signInAs({ audiences: ["resident"] }, [])).result).toEqual({ nextStep: "verification-required" });
    expect((await signInAs({ operationsRole: "staff", audiences: ["resident", "operations"] }, [{ id: "u1" }])).result)
      .toEqual({ nextStep: "choose", operationsPath: "/operations/my-tasks" });
    // Both, but no home linked yet: the resident side has nothing to open, so the staff side does.
    expect((await signInAs({ operationsRole: "staff", audiences: ["resident", "operations"] }, [])).result)
      .toEqual({ nextStep: "operations", operationsPath: "/operations/my-tasks" });
  });
});
