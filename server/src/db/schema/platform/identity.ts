/** Physical model for platform/identity. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { users } from "../core";

export { users } from "../core";

export const platformTenant = pgTable(
  "platform_tenant",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tenant_tenant_policy", {
      for: "all",
      using: sql`${t.id} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.id} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tenant_uq_0").on(t.code),
    allowedValues("platform_tenant_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_tenant_ck_0", sql`version > 0`),
  ],
).enableRLS();

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

export const platformRole = pgTable(
  "platform_role",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    scopeType: text("scope_type", {
      enum: ["TENANT", "DOMAIN", "PROJECT", "RESOURCE"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_role_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_role_uq_0").on(t.tenantId, t.code),
    unique("platform_role_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_role_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_role_scope_type_ck", t.scopeType, [
      "TENANT",
      "DOMAIN",
      "PROJECT",
      "RESOURCE",
    ]),
    check("platform_role_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformMembershipRole = pgTable(
  "platform_membership_role",
  {
    tenantId: uuid("tenant_id").notNull(),
    membershipId: uuid("membership_id").notNull(),
    roleId: uuid("role_id").notNull(),
    scopeJson: jsonb("scope_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_membership_role_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.membershipId, t.roleId] }),
    foreignKey({
      name: "platform_membership_role_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_membership_role_fk_1",
      columns: [t.tenantId, t.membershipId],
      foreignColumns: [
        platformTenantMembership.tenantId,
        platformTenantMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_membership_role_fk_2",
      columns: [t.tenantId, t.roleId],
      foreignColumns: [platformRole.tenantId, platformRole.id],
    }).onDelete("restrict"),
    index("platform_membership_role_ix_0").on(t.tenantId, t.roleId),
    index("platform_membership_role_ix_1").on(t.tenantId, t.membershipId),
  ],
).enableRLS();
