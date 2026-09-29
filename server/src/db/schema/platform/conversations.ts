import { agents, channels } from "../core";
/** Persistence for coordination and field operations. See docs/erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../columns";
import { platformAgentVersion } from "./agents";
import { platformTenant, users } from "./identity";

export const channelSubjects = pgTable(
  "channel_subjects",
  {
    tenantId: uuid("tenant_id").notNull(),
    channelId: text("channel_id").notNull(),
    domainNamespace: text("domain_namespace").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectRef: text("subject_ref").notNull(),
    relationship: text("relationship", {
      enum: ["INTAKE", "TRACKING", "FOLLOW_UP"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("channel_subjects_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      name: "channel_subjects_pk",
      columns: [
        t.tenantId,
        t.channelId,
        t.domainNamespace,
        t.subjectType,
        t.subjectRef,
      ],
    }),
    foreignKey({
      name: "channel_subjects_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_subjects_fk_1",
      columns: [t.tenantId, t.channelId],
      foreignColumns: [channels.tenantId, channels.id],
    }).onDelete("restrict"),
    index("channel_subjects_ix_1").on(t.tenantId, t.channelId),
    allowedValues("channel_subjects_relationship_ck", t.relationship, [
      "INTAKE",
      "TRACKING",
      "FOLLOW_UP",
    ]),
  ],
).enableRLS();

export const channelMessages = pgTable(
  "channel_messages",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    channelId: text("channel_id").notNull(),
    sequenceNo: bigint("sequence_no", { mode: "bigint" }).notNull(),
    role: text("role", { enum: ["USER", "ASSISTANT", "SYSTEM"] }).notNull(),
    authorUserId: text("author_user_id"),
    authorAgentId: text("author_agent_id"),
    contentParts: jsonb("content_parts")
      .$type<unknown[]>()
      .notNull()
      .default(sql`'[]'::jsonb`),
    agentVersionId: uuid("agent_version_id"),
    body: text("body").notNull(),
    contentSchemaVersion: integer("content_schema_version").notNull(),
    metadataJson: jsonb("metadata_json").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    replyToMessageId: uuid("reply_to_message_id"),
    sourceEventRef: text("source_event_ref"),
    sourceSubjectVersion: bigint("source_subject_version", { mode: "bigint" }),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("channel_messages_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    foreignKey({
      name: "channel_messages_agent_fk",
      columns: [t.tenantId, t.authorAgentId],
      foreignColumns: [agents.tenantId, agents.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_messages_agent_version_fk",
      columns: [t.tenantId, t.authorAgentId, t.agentVersionId],
      foreignColumns: [
        platformAgentVersion.tenantId,
        platformAgentVersion.agentId,
        platformAgentVersion.id,
      ],
    }).onDelete("restrict"),
    check(
      "channel_messages_parts_ck",
      sql`jsonb_typeof(content_parts) = 'array'`,
    ),
    unique("channel_messages_uq_0").on(t.tenantId, t.channelId, t.sequenceNo),
    unique("channel_messages_uq_1").on(
      t.tenantId,
      t.channelId,
      t.idempotencyKey,
    ),
    unique("channel_messages_uq_2").on(t.tenantId, t.id),
    unique("channel_messages_uq_3").on(t.tenantId, t.channelId, t.id),
    foreignKey({
      name: "channel_messages_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_messages_fk_1",
      columns: [t.tenantId, t.channelId],
      foreignColumns: [channels.tenantId, channels.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_messages_fk_2",
      columns: [t.authorUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_messages_fk_3",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "channel_messages_fk_4",
      columns: [t.tenantId, t.channelId, t.replyToMessageId],
      foreignColumns: [t.tenantId, t.channelId, t.id],
    }).onDelete("restrict"),
    index("channel_messages_ix_0").on(t.authorUserId),
    index("channel_messages_ix_2").on(t.tenantId, t.agentVersionId),
    index("channel_messages_ix_3").on(t.tenantId, t.channelId),
    index("channel_messages_ix_4").on(
      t.tenantId,
      t.channelId,
      t.replyToMessageId,
    ),
    allowedValues("channel_messages_role_ck", t.role, [
      "USER",
      "ASSISTANT",
      "SYSTEM",
    ]),
    check("channel_messages_ck_0", sql`sequence_no > 0`),
    check("channel_messages_ck_1", sql`content_schema_version > 0`),
    check(
      "channel_messages_ck_2",
      sql`(role='USER' AND author_user_id IS NOT NULL AND author_agent_id IS NULL AND agent_version_id IS NULL) OR (role='ASSISTANT' AND author_agent_id IS NOT NULL AND author_user_id IS NULL) OR (role='SYSTEM' AND author_user_id IS NULL AND author_agent_id IS NULL AND agent_version_id IS NULL)`,
    ),
  ],
).enableRLS();
