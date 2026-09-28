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
    unique("platform_capability_uq_0").on(t.tenantId, t.code),
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
    check("platform_capability_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformModelProfile = pgTable(
  "platform_model_profile",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    providerRef: text("provider_ref").notNull(),
    modelRef: text("model_ref").notNull(),
    configJson: jsonb("config_json").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_model_profile_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_model_profile_uq_0").on(t.tenantId, t.code),
    unique("platform_model_profile_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_model_profile_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_model_profile_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_model_profile_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformMcpServer = pgTable(
  "platform_mcp_server",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: text("name").notNull(),
    endpointRef: text("endpoint_ref").notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_mcp_server_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_mcp_server_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_mcp_server_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_mcp_server_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_mcp_server_ix_0").on(t.ownerId),
    allowedValues("platform_mcp_server_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_mcp_server_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformMcpServerVersion = pgTable(
  "platform_mcp_server_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    mcpServerId: uuid("mcp_server_id").notNull(),
    versionNo: integer("version_no").notNull(),
    schemaHash: text("schema_hash").notNull(),
    fingerprint: text("fingerprint").notNull(),
    securityStatus: text("security_status", {
      enum: ["PENDING", "APPROVED", "REJECTED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_mcp_server_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_mcp_server_version_uq_0").on(
      t.tenantId,
      t.mcpServerId,
      t.versionNo,
    ),
    unique("platform_mcp_server_version_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_mcp_server_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_mcp_server_version_fk_1",
      columns: [t.tenantId, t.mcpServerId],
      foreignColumns: [platformMcpServer.tenantId, platformMcpServer.id],
    }).onDelete("restrict"),
    index("platform_mcp_server_version_ix_0").on(t.tenantId, t.mcpServerId),
    allowedValues(
      "platform_mcp_server_version_security_status_ck",
      t.securityStatus,
      ["PENDING", "APPROVED", "REJECTED", "REVOKED"],
    ),
    check("platform_mcp_server_version_ck_0", sql`version_no > 0`),
    check("platform_mcp_server_version_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformTool = pgTable(
  "platform_tool",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    effectType: text("effect_type", {
      enum: ["READ", "WRITE", "EXTERNAL_SIDE_EFFECT"],
    }).notNull(),
    riskLevel: text("risk_level", {
      enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tool_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tool_uq_0").on(t.tenantId, t.code),
    unique("platform_tool_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_tool_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_tool_effect_type_ck", t.effectType, [
      "READ",
      "WRITE",
      "EXTERNAL_SIDE_EFFECT",
    ]),
    allowedValues("platform_tool_risk_level_ck", t.riskLevel, [
      "LOW",
      "MEDIUM",
      "HIGH",
      "CRITICAL",
    ]),
    check("platform_tool_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformToolVersion = pgTable(
  "platform_tool_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    toolId: uuid("tool_id").notNull(),
    mcpServerVersionId: uuid("mcp_server_version_id"),
    versionNo: integer("version_no").notNull(),
    inputSchema: jsonb("input_schema").notNull(),
    outputSchema: jsonb("output_schema").notNull(),
    fingerprint: text("fingerprint").notNull(),
    status: text("status", {
      enum: ["DRAFT", "APPROVED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_tool_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_tool_version_uq_0").on(t.tenantId, t.toolId, t.versionNo),
    unique("platform_tool_version_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_tool_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_tool_version_fk_1",
      columns: [t.tenantId, t.toolId],
      foreignColumns: [platformTool.tenantId, platformTool.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_tool_version_fk_2",
      columns: [t.tenantId, t.mcpServerVersionId],
      foreignColumns: [
        platformMcpServerVersion.tenantId,
        platformMcpServerVersion.id,
      ],
    }).onDelete("restrict"),
    index("platform_tool_version_ix_0").on(t.tenantId, t.mcpServerVersionId),
    index("platform_tool_version_ix_1").on(t.tenantId, t.toolId),
    allowedValues("platform_tool_version_status_ck", t.status, [
      "DRAFT",
      "APPROVED",
      "REVOKED",
    ]),
    check("platform_tool_version_ck_0", sql`version_no > 0`),
    check("platform_tool_version_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformSkill = pgTable(
  "platform_skill",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: text("name").notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_skill_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_skill_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_skill_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_skill_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_skill_ix_0").on(t.ownerId),
    allowedValues("platform_skill_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_skill_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformSkillVersion = pgTable(
  "platform_skill_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    skillId: uuid("skill_id").notNull(),
    versionNo: integer("version_no").notNull(),
    contentRef: text("content_ref").notNull(),
    checksum: text("checksum").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_skill_version_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_skill_version_uq_0").on(
      t.tenantId,
      t.skillId,
      t.versionNo,
    ),
    unique("platform_skill_version_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_skill_version_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_skill_version_fk_1",
      columns: [t.tenantId, t.skillId],
      foreignColumns: [platformSkill.tenantId, platformSkill.id],
    }).onDelete("restrict"),
    index("platform_skill_version_ix_0").on(t.tenantId, t.skillId),
    check("platform_skill_version_ck_0", sql`version_no > 0`),
  ],
).enableRLS();
