import { and, eq, sql } from "drizzle-orm";
import type { Database } from "../db/client";
import {
  platformAdmins,
  tenantMemberships,
  scopedUserRoles,
  accessScopes,
  users,
} from "../db/schema";

export type OpenBotRole = "admin" | "management" | "staff" | "customer";
export function isConfiguredAdmin(
  email: string | null,
  initialAdminEmails: readonly string[],
): boolean {
  return (
    email !== null &&
    initialAdminEmails.some(
      (value) => value.trim().toLowerCase() === email.trim().toLowerCase(),
    )
  );
}
export function roleForEmail(
  email: string,
  emails: readonly string[],
): OpenBotRole {
  return isConfiguredAdmin(email, emails) ? "admin" : "customer";
}
export async function rolesForUser(
  database: Database,
  userId: string,
): Promise<OpenBotRole[]> {
  const [user] = await database
    .select({ status: users.status })
    .from(users)
    .where(eq(users.id, userId));
  if (!user || user.status !== "active") return [];
  const admins = await database
    .select()
    .from(platformAdmins)
    .where(eq(platformAdmins.userId, userId));
  if (admins.length) return ["admin"];
  const rows = await database
    .select({ role: scopedUserRoles.roleCode })
    .from(scopedUserRoles)
    .innerJoin(
      tenantMemberships,
      eq(tenantMemberships.id, scopedUserRoles.membershipId),
    )
    .where(
      and(
        eq(tenantMemberships.userId, userId),
        eq(tenantMemberships.status, "active"),
        sql`${scopedUserRoles.validFrom} <= now() and (${scopedUserRoles.validTo} is null or ${scopedUserRoles.validTo}>now())`,
        sql`${scopedUserRoles.tenantId}=nullif(current_setting('app.tenant_id',true),'')::uuid`,
      ),
    );
  return [...new Set(rows.map((r) => r.role as OpenBotRole))];
}
/** Canonical writes only through platform admins and scoped tenant roles. */
export async function setRole(
  database: Database,
  userId: string,
  role: OpenBotRole,
): Promise<OpenBotRole> {
  await database.transaction(async (tx) => {
    // Serialize admin changes, including the last-admin guard.
    await tx.execute(sql`select pg_advisory_xact_lock(7823941)`);
    const [user] = await tx
      .select({ id: users.id })
      .from(users)
      .where(eq(users.id, userId));
    if (!user) throw new Error("User does not exist");
    if (role === "admin") {
      await tx.insert(platformAdmins).values({ userId }).onConflictDoNothing();
      await tx
        .update(users)
        .set({ status: "active" })
        .where(eq(users.id, userId));
      return;
    }
    const existing = await tx.select().from(platformAdmins);
    if (existing.length === 1 && existing[0]?.userId === userId)
      throw new Error("Cannot remove the last platform administrator");
    // This compatibility endpoint assigns only a customer tenant role. Management/staff
    // require an explicit geographical scope through the scoped-role service.
    if (role !== "customer")
      throw new Error("Management/staff require an explicit access scope");
    const [scope] = await tx
      .select()
      .from(accessScopes)
      .where(
        and(
          eq(accessScopes.kind, "tenant"),
          sql`${accessScopes.tenantId}=nullif(current_setting('app.tenant_id',true),'')::uuid`,
        ),
      );
    if (!scope) throw new Error("Tenant scope has not been initialized");
    await tx.delete(platformAdmins).where(eq(platformAdmins.userId, userId));
    const [membership] = await tx
      .insert(tenantMemberships)
      .values({
        tenantId: scope.tenantId,
        userId,
        status: "active",
        joinedAt: new Date(),
      })
      .onConflictDoUpdate({
        target: [tenantMemberships.tenantId, tenantMemberships.userId],
        set: { status: "active", endedAt: null },
      })
      .returning();
    if (!membership) throw new Error("Membership could not be created");
    // Preserve scoped staff/management grants: changing the platform-admin switch does not erase them.
    const grants = await tx
      .select()
      .from(scopedUserRoles)
      .where(
        and(
          eq(scopedUserRoles.membershipId, membership.id),
          eq(scopedUserRoles.scopeId, scope.id),
          eq(scopedUserRoles.roleCode, "customer"),
          sql`${scopedUserRoles.validTo} is null`,
        ),
      );
    if (!grants.length)
      await tx
        .insert(scopedUserRoles)
        .values({
          tenantId: scope.tenantId,
          membershipId: membership.id,
          scopeId: scope.id,
          roleCode: "customer",
          grantedBy: userId,
          validFrom: new Date(),
        });
    await tx
      .update(users)
      .set({ status: "active" })
      .where(eq(users.id, userId));
  });
  return role;
}
export async function seedRole(
  database: Database,
  userId: string,
  email: string,
  emails: readonly string[],
): Promise<OpenBotRole> {
  return setRole(database, userId, roleForEmail(email, emails));
}
export async function applyConfiguredAdmin(
  database: Database,
  userId: string,
  emails: readonly string[],
): Promise<boolean> {
  if (!emails.length) return false;
  const [user] = await database
    .select({ email: users.email })
    .from(users)
    .where(eq(users.id, userId));
  if (!user || !isConfiguredAdmin(user.email, emails)) return false;
  const old = await database
    .select()
    .from(platformAdmins)
    .where(eq(platformAdmins.userId, userId));
  await setRole(database, userId, "admin");
  return old.length === 0;
}
export function strongestRole(
  roles: readonly OpenBotRole[],
): OpenBotRole | undefined {
  return (["admin", "management", "staff", "customer"] as const).find((r) =>
    roles.includes(r),
  );
}
