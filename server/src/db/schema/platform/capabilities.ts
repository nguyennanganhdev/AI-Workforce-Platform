/** Physical model for platform/capabilities. See docs/erd/README.md. */
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformTenant, users } from "./identity";

export const platformCapability = pgTable(
  "platform_capability",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    versionNo: integer("version_no").notNull(),
    sourceType: text("source_type").notNull(),
    sourceRef: text("source_ref").notNull(),
    configJson: jsonb("config_json").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    type: text("type").notNull(),
    description: text("description"),
    riskLevel: text("risk_level", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_capability_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_capability_uq_0").on(t.tenantId, t.type, t.code, t.versionNo),
    unique("platform_capability_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_capability_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_capability_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_capability_ix_0").on(t.ownerId),
    allowedValues("platform_capability_risk_level_ck", t.riskLevel, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    allowedValues("platform_capability_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    allowedValues("platform_capability_type_ck", t.type, ["MODEL", "MCP_TOOL", "SKILL", "KNOWLEDGE", "POLICY", "CONNECTOR"]),
    check("platform_capability_revision_ck", sql`version_no > 0`),
    check("platform_capability_config_ck", sql`jsonb_typeof(config_json) = 'object' AND length(source_type) > 0 AND length(source_ref) > 0`),
    check("platform_capability_ck_0", sql`version > 0`),
  ],
).enableRLS();

