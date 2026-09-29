/** Physical model for platform/identity. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../columns";
import { users } from "../core";

export { users } from "../core";

export { platformTenant } from "../tenant";
import { platformTenant } from "../tenant";

export const platformTenantMembership = pgTable(
  "platform_tenant_membership",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "REVOKED"],
    }).notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tenant_membership_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tenant_membership_uq_0").on(t.tenantId, t.userId),
    unique("platform_tenant_membership_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_tenant_membership_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_tenant_membership_fk_1",
      columns: [t.userId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_tenant_membership_ix_0").on(t.userId),
    allowedValues("platform_tenant_membership_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "REVOKED",
    ]),
    check(
      "platform_tenant_membership_ck_0",
      sql`valid_until IS NULL OR valid_until > valid_from`,
    ),
    check("platform_tenant_membership_ck_1", sql`version > 0`),
  ],
).enableRLS();
