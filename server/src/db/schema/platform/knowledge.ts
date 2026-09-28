/** Physical model for platform/knowledge. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../columns";
import { platformTenant, users } from "./identity";

export const platformKnowledgeBase = pgTable(
  "platform_knowledge_base",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    name: text("name").notNull(),
    classification: text("classification", {
      enum: ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"],
    }).notNull(),
    ownerId: text("owner_id").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_knowledge_base_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_knowledge_base_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_knowledge_base_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_knowledge_base_fk_1",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_knowledge_base_ix_0").on(t.ownerId),
    allowedValues(
      "platform_knowledge_base_classification_ck",
      t.classification,
      ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"],
    ),
    allowedValues("platform_knowledge_base_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_knowledge_base_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformKnowledgeSource = pgTable(
  "platform_knowledge_source",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    knowledgeBaseId: uuid("knowledge_base_id").notNull(),
    sourceType: text("source_type").notNull(),
    uri: text("uri").notNull(),
    title: text("title").notNull(),
    ownerId: text("owner_id").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_knowledge_source_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_knowledge_source_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_knowledge_source_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_knowledge_source_fk_1",
      columns: [t.tenantId, t.knowledgeBaseId],
      foreignColumns: [
        platformKnowledgeBase.tenantId,
        platformKnowledgeBase.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_knowledge_source_fk_2",
      columns: [t.ownerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_knowledge_source_ix_0").on(t.ownerId),
    index("platform_knowledge_source_ix_1").on(t.tenantId, t.knowledgeBaseId),
    check("platform_knowledge_source_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformKnowledgeRevision = pgTable(
  "platform_knowledge_revision",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    knowledgeSourceId: uuid("knowledge_source_id").notNull(),
    revisionNo: integer("revision_no").notNull(),
    contentHash: text("content_hash").notNull(),
    storageRef: text("storage_ref").notNull(),
    status: text("status", {
      enum: ["DRAFT", "APPROVED", "REJECTED", "REVOKED"],
    }).notNull(),
    approvedBy: text("approved_by"),
    approvedAt: timestamp("approved_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_knowledge_revision_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_knowledge_revision_uq_0").on(
      t.tenantId,
      t.knowledgeSourceId,
      t.revisionNo,
    ),
    unique("platform_knowledge_revision_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_knowledge_revision_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_knowledge_revision_fk_1",
      columns: [t.tenantId, t.knowledgeSourceId],
      foreignColumns: [
        platformKnowledgeSource.tenantId,
        platformKnowledgeSource.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_knowledge_revision_fk_2",
      columns: [t.approvedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_knowledge_revision_ix_0").on(
      t.tenantId,
      t.knowledgeSourceId,
    ),
    index("platform_knowledge_revision_ix_1").on(t.approvedBy),
    allowedValues("platform_knowledge_revision_status_ck", t.status, [
      "DRAFT",
      "APPROVED",
      "REJECTED",
      "REVOKED",
    ]),
    check("platform_knowledge_revision_ck_0", sql`revision_no > 0`),
    check(
      "platform_knowledge_revision_ck_1",
      sql`status <> 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)`,
    ),
    check("platform_knowledge_revision_ck_2", sql`version > 0`),
  ],
).enableRLS();
