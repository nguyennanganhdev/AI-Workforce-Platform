/** P0 authorization extension. Identity remains owned by the external IAM. */
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
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "./columns";
import { users } from "./core";
import { platformTenantMembership } from "./platform/identity";
import { platformTenant } from "./tenant";
import { tenantId, tenantPolicy } from "./tenant-scope";

export const authExternalIdentity = pgTable(
  "auth_external_identity",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: tenantId(),
    localUserId: text("local_user_id")
      .notNull()
      .references(() => users.id, { onDelete: "restrict" }),
    provider: text("provider").notNull(),
    issuer: text("issuer").notNull(),
    externalSubject: text("external_subject").notNull(),
    status: text("status").notNull().default("ACTIVE"),
    lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    tenantPolicy("auth_external_identity_tenant_policy", t.tenantId),
    unique("auth_external_identity_issuer_subject_uq").on(
      t.issuer,
      t.externalSubject,
    ),
    index("auth_external_identity_user_ix").on(t.tenantId, t.localUserId),
    allowedValues("auth_external_identity_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "REVOKED",
    ]),
    check(
      "auth_external_identity_subject_ck",
      sql`length(trim(${t.issuer})) > 0 AND length(trim(${t.externalSubject})) > 0`,
    ),
    check("auth_external_identity_version_ck", sql`${t.version} > 0`),
  ],
).enableRLS();

/** Global roles are read-only templates for tenant application roles. */
export const authRole = pgTable(
  "auth_role",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").references(() => platformTenant.id, {
      onDelete: "restrict",
    }),
    domainNamespace: text("domain_namespace").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    roleType: text("role_type").notNull(),
    status: text("status").notNull().default("ACTIVE"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("auth_role_read_policy", {
      for: "select",
      using: sql`${t.tenantId} IS NULL OR ${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    tenantPolicy("auth_role_write_policy", t.tenantId),
    uniqueIndex("auth_role_global_code_uq")
      .on(t.domainNamespace, t.code)
      .where(sql`${t.tenantId} IS NULL`),
    uniqueIndex("auth_role_tenant_code_uq")
      .on(t.tenantId, t.domainNamespace, t.code)
      .where(sql`${t.tenantId} IS NOT NULL`),
    allowedValues("auth_role_type_ck", t.roleType, ["SYSTEM", "CUSTOM"]),
    allowedValues("auth_role_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check(
      "auth_role_ownership_ck",
      sql`(${t.roleType} = 'SYSTEM' AND ${t.tenantId} IS NULL) OR (${t.roleType} = 'CUSTOM' AND ${t.tenantId} IS NOT NULL)`,
    ),
    check("auth_role_version_ck", sql`${t.version} > 0`),
  ],
).enableRLS();

/** Permission definitions are deployment-owned; tenant services only read them. */
export const authPermission = pgTable(
  "auth_permission",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    domainNamespace: text("domain_namespace").notNull(),
    code: text("code").notNull(),
    resource: text("resource").notNull(),
    action: text("action").notNull(),
    riskLevel: text("risk_level").notNull(),
    description: text("description").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("auth_permission_read_policy", {
      for: "select",
      using: sql`true`,
    }),
    unique("auth_permission_code_uq").on(t.domainNamespace, t.code),
    allowedValues("auth_permission_risk_ck", t.riskLevel, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
  ],
).enableRLS();

export const authRolePermission = pgTable(
  "auth_role_permission",
  {
    roleId: uuid("role_id")
      .notNull()
      .references(() => authRole.id, { onDelete: "restrict" }),
    permissionId: uuid("permission_id")
      .notNull()
      .references(() => authPermission.id, { onDelete: "restrict" }),
    createdAt: createdAt(),
  },
  (t) => [
    primaryKey({ columns: [t.roleId, t.permissionId] }),
    index("auth_role_permission_permission_ix").on(t.permissionId),
    pgPolicy("auth_role_permission_read_policy", {
      for: "select",
      using: sql`EXISTS (SELECT 1 FROM auth_role r WHERE r.id = ${t.roleId})`,
    }),
    pgPolicy("auth_role_permission_write_policy", {
      for: "all",
      using: sql`EXISTS (SELECT 1 FROM auth_role r WHERE r.id = ${t.roleId} AND r.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)`,
      withCheck: sql`EXISTS (SELECT 1 FROM auth_role r WHERE r.id = ${t.roleId} AND r.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)`,
    }),
  ],
).enableRLS();

export const authRoleAssignment = pgTable(
  "auth_role_assignment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: tenantId(),
    userId: text("user_id").notNull(),
    roleId: uuid("role_id")
      .notNull()
      .references(() => authRole.id, { onDelete: "restrict" }),
    domainNamespace: text("domain_namespace").notNull(),
    scopeType: text("scope_type").notNull(),
    scopeRef: text("scope_ref").notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    status: text("status").notNull().default("ACTIVE"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    tenantPolicy("auth_role_assignment_tenant_policy", t.tenantId),
    foreignKey({
      name: "auth_role_assignment_membership_fk",
      columns: [t.tenantId, t.userId],
      foreignColumns: [
        platformTenantMembership.tenantId,
        platformTenantMembership.userId,
      ],
    }).onDelete("restrict"),
    index("auth_role_assignment_context_ix").on(
      t.tenantId,
      t.userId,
      t.status,
      t.validUntil,
    ),
    index("auth_role_assignment_role_ix").on(t.roleId),
    unique("auth_role_assignment_period_uq").on(
      t.tenantId,
      t.userId,
      t.roleId,
      t.domainNamespace,
      t.scopeType,
      t.scopeRef,
      t.validFrom,
    ),
    allowedValues("auth_role_assignment_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "REVOKED",
    ]),
    allowedValues("auth_role_assignment_scope_ck", t.scopeType, [
      "TENANT",
      "DOMAIN",
      "PROJECT",
      "TOWER",
      "APARTMENT",
      "RESOURCE",
    ]),
    check(
      "auth_role_assignment_period_ck",
      sql`${t.validUntil} IS NULL OR ${t.validUntil} > ${t.validFrom}`,
    ),
    check("auth_role_assignment_ref_ck", sql`length(trim(${t.scopeRef})) > 0`),
    check("auth_role_assignment_version_ck", sql`${t.version} > 0`),
  ],
).enableRLS();
