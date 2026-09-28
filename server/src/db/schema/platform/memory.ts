/** Physical model for platform/memory. See docs/erd/README.md. */
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformTenant, users } from "./identity";

export const platformMemoryNamespace = pgTable(
  "platform_memory_namespace",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    namespaceType: text("namespace_type", {
      enum: ["TENANT", "DOMAIN", "USER", "AGENT"],
    }).notNull(),
    subjectRef: text("subject_ref").notNull(),
    retentionPolicy: jsonb("retention_policy").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_memory_namespace_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_memory_namespace_uq_0").on(
      t.tenantId,
      t.namespaceType,
      t.subjectRef,
    ),
    unique("platform_memory_namespace_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_memory_namespace_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues(
      "platform_memory_namespace_namespace_type_ck",
      t.namespaceType,
      ["TENANT", "DOMAIN", "USER", "AGENT"],
    ),
    allowedValues("platform_memory_namespace_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_memory_namespace_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformMemoryItem = pgTable(
  "platform_memory_item",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    memoryNamespaceId: uuid("memory_namespace_id").notNull(),
    memoryType: text("memory_type").notNull(),
    sourceType: text("source_type").notNull(),
    sourceRef: text("source_ref").notNull(),
    status: text("status", {
      enum: ["DRAFT", "ACTIVE", "REDACTED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_memory_item_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_memory_item_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_memory_item_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_memory_item_fk_1",
      columns: [t.tenantId, t.memoryNamespaceId],
      foreignColumns: [
        platformMemoryNamespace.tenantId,
        platformMemoryNamespace.id,
      ],
    }).onDelete("restrict"),
    index("platform_memory_item_ix_0").on(t.tenantId, t.memoryNamespaceId),
    allowedValues("platform_memory_item_status_ck", t.status, [
      "DRAFT",
      "ACTIVE",
      "REDACTED",
      "RETIRED",
    ]),
    check("platform_memory_item_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const platformMemoryRevision = pgTable(
  "platform_memory_revision",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    memoryItemId: uuid("memory_item_id").notNull(),
    revisionNo: integer("revision_no").notNull(),
    contentRef: text("content_ref").notNull(),
    contentHash: text("content_hash").notNull(),
    redactionStatus: text("redaction_status", {
      enum: ["CLEAN", "REDACTED", "BLOCKED"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_memory_revision_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_memory_revision_uq_0").on(
      t.tenantId,
      t.memoryItemId,
      t.revisionNo,
    ),
    unique("platform_memory_revision_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_memory_revision_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_memory_revision_fk_1",
      columns: [t.tenantId, t.memoryItemId],
      foreignColumns: [platformMemoryItem.tenantId, platformMemoryItem.id],
    }).onDelete("restrict"),
    index("platform_memory_revision_ix_0").on(t.tenantId, t.memoryItemId),
    allowedValues(
      "platform_memory_revision_redaction_status_ck",
      t.redactionStatus,
      ["CLEAN", "REDACTED", "BLOCKED"],
    ),
    check("platform_memory_revision_ck_0", sql`revision_no > 0`),
  ],
).enableRLS();

export const platformMemoryReview = pgTable(
  "platform_memory_review",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    memoryRevisionId: uuid("memory_revision_id").notNull(),
    reviewerId: text("reviewer_id").notNull(),
    decision: text("decision", {
      enum: ["APPROVED", "REJECTED", "REVOKED"],
    }).notNull(),
    reason: text("reason").notNull(),
    reviewedAt: timestamp("reviewed_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_memory_review_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_memory_review_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_memory_review_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_memory_review_fk_1",
      columns: [t.tenantId, t.memoryRevisionId],
      foreignColumns: [
        platformMemoryRevision.tenantId,
        platformMemoryRevision.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_memory_review_fk_2",
      columns: [t.reviewerId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_memory_review_ix_0").on(t.reviewerId),
    index("platform_memory_review_ix_1").on(t.tenantId, t.memoryRevisionId),
    allowedValues("platform_memory_review_decision_ck", t.decision, [
      "APPROVED",
      "REJECTED",
      "REVOKED",
    ]),
  ],
).enableRLS();

export const platformMemoryVectorRef = pgTable(
  "platform_memory_vector_ref",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    memoryRevisionId: uuid("memory_revision_id").notNull(),
    qdrantCollection: text("qdrant_collection").notNull(),
    qdrantPointId: uuid("qdrant_point_id").notNull(),
    embeddingModel: text("embedding_model").notNull(),
    dimension: integer("dimension").notNull(),
    syncStatus: text("sync_status", {
      enum: ["PENDING", "SYNCED", "DELETE_PENDING", "DELETED", "FAILED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_memory_vector_ref_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_memory_vector_ref_uq_0").on(
      t.tenantId,
      t.memoryRevisionId,
    ),
    unique("platform_memory_vector_ref_uq_1").on(
      t.qdrantCollection,
      t.qdrantPointId,
    ),
    unique("platform_memory_vector_ref_uq_2").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_memory_vector_ref_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_memory_vector_ref_fk_1",
      columns: [t.tenantId, t.memoryRevisionId],
      foreignColumns: [
        platformMemoryRevision.tenantId,
        platformMemoryRevision.id,
      ],
    }).onDelete("restrict"),
    allowedValues("platform_memory_vector_ref_sync_status_ck", t.syncStatus, [
      "PENDING",
      "SYNCED",
      "DELETE_PENDING",
      "DELETED",
      "FAILED",
    ]),
    check("platform_memory_vector_ref_ck_0", sql`dimension > 0`),
    check("platform_memory_vector_ref_ck_1", sql`version > 0`),
  ],
).enableRLS();
