import { describe, test, expect } from "bun:test";
import {
  isConfiguredAdmin,
  roleForEmail,
  strongestRole,
  rolesForUser,
} from "../src/auth/roles";
import type { Database } from "../src/db/client";
describe("canonical platform roles", () => {
  test("normalizes admin email and permits phone-only users", () => {
    expect(
      isConfiguredAdmin(" ADMIN@example.test ", ["admin@example.test"]),
    ).toBe(true);
    expect(isConfiguredAdmin(null, ["admin@example.test"])).toBe(false);
    expect(roleForEmail("new@example.test", [])).toBe("customer");
  });
  test("does not grant legacy user rows platform authority", () => {
    expect(strongestRole(["staff", "management"])).toBe("management");
    expect(strongestRole(["customer", "admin"])).toBe("admin");
    expect(strongestRole([])).toBeUndefined();
  });
  test("a suspended identity is refused before role lookup", async () => {
    let reads = 0;
    const db = {
      select: () => {
        reads++;
        return {
          from: () => ({ where: async () => [{ status: "suspended" }] }),
        };
      },
    } as unknown as Database;
    expect(await rolesForUser(db, "suspended-user")).toEqual([]);
    expect(reads).toBe(1);
  });
});
