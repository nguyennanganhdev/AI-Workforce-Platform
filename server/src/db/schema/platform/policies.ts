/** Physical model for platform/policies. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  text,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../columns";
import { platformTenant, users } from "./identity";

export const platformPolicy = pgTable(
  "platform_policy",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    policyType: text("policy_type").notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_policy_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_policy_uq_0").on(t.tenantId, t.code),
    unique("platform_policy_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_policy_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_policy_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_policy_ix_0").on(t.ownerId),
    allowedValues("platform_policy_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_policy_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformPolicyVersion = pgTable(
  "platform_policy_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    policyId: uuid("policy_id").notNull(),
    versionNo: integer("version_no").notNull(),
    language: text("language").notNull(),
    contentRef: text("content_ref").notNull(),
    contentHash: text("content_hash").notNull(),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_policy_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_policy_version_uq_0").on(
      t.tenantId,
      t.policyId,
      t.versionNo,
    ),
    unique("platform_policy_version_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_policy_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_policy_version_fk_1",
      columns: [t.tenantId, t.policyId],
      foreignColumns: [platformPolicy.tenantId, platformPolicy.id],
    }).onDelete("restrict"),
    index("platform_policy_version_ix_0").on(t.tenantId, t.policyId),
    allowedValues("platform_policy_version_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "RETIRED",
    ]),
    check("platform_policy_version_ck_0", sql`version_no > 0`),
    check("platform_policy_version_ck_1", sql`version > 0`),
  ],
).enableRLS();
