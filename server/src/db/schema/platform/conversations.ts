/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
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

export const platformConversation = pgTable(
  "platform_conversation",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    ownerUserId: text("owner_user_id").notNull(),
    channel: text("channel", {
      enum: ["WEB", "MOBILE", "EMAIL", "VOICE", "EXTERNAL"],
    }).notNull(),
    externalProvider: text("external_provider"),
    externalThreadRef: text("external_thread_ref"),
    locale: text("locale").notNull(),
    status: text("status", { enum: ["OPEN", "CLOSED", "ARCHIVED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_conversation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_conversation_uq_0").on(
      t.tenantId,
      t.externalProvider,
      t.externalThreadRef,
    ),
    unique("platform_conversation_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_conversation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_fk_1",
      columns: [t.ownerUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("platform_conversation_ix_0").on(t.ownerUserId),
    allowedValues("platform_conversation_channel_ck", t.channel, [
      "WEB",
      "MOBILE",
      "EMAIL",
      "VOICE",
      "EXTERNAL",
    ]),
    allowedValues("platform_conversation_status_ck", t.status, [
      "OPEN",
      "CLOSED",
      "ARCHIVED",
    ]),
    check(
      "platform_conversation_ck_0",
      sql`(external_provider IS NULL) = (external_thread_ref IS NULL)`,
    ),
    check("platform_conversation_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformConversationSubject = pgTable(
  "platform_conversation_subject",
  {
    tenantId: uuid("tenant_id").notNull(),
    conversationId: uuid("conversation_id").notNull(),
    domainNamespace: text("domain_namespace").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectRef: text("subject_ref").notNull(),
    relationship: text("relationship", {
      enum: ["INTAKE", "TRACKING", "FOLLOW_UP"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_conversation_subject_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      name: "platform_conversation_subject_pk",
      columns: [
        t.tenantId,
        t.conversationId,
        t.domainNamespace,
        t.subjectType,
        t.subjectRef,
      ],
    }),
    foreignKey({
      name: "platform_conversation_subject_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_subject_fk_1",
      columns: [t.tenantId, t.conversationId],
      foreignColumns: [platformConversation.tenantId, platformConversation.id],
    }).onDelete("restrict"),
    index("platform_conversation_subject_ix_1").on(
      t.tenantId,
      t.conversationId,
    ),
    allowedValues(
      "platform_conversation_subject_relationship_ck",
      t.relationship,
      ["INTAKE", "TRACKING", "FOLLOW_UP"],
    ),
  ],
).enableRLS();

export const platformConversationMessage = pgTable(
  "platform_conversation_message",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    conversationId: uuid("conversation_id").notNull(),
    sequenceNo: bigint("sequence_no", { mode: "bigint" }).notNull(),
    role: text("role", { enum: ["USER", "ASSISTANT", "SYSTEM"] }).notNull(),
    authorUserId: text("author_user_id"),
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
    pgPolicy("platform_conversation_message_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_conversation_message_uq_0").on(
      t.tenantId,
      t.conversationId,
      t.sequenceNo,
    ),
    unique("platform_conversation_message_uq_1").on(
      t.tenantId,
      t.conversationId,
      t.idempotencyKey,
    ),
    unique("platform_conversation_message_uq_2").on(t.tenantId, t.id),
    unique("platform_conversation_message_uq_3").on(
      t.tenantId,
      t.conversationId,
      t.id,
    ),
    foreignKey({
      name: "platform_conversation_message_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_message_fk_1",
      columns: [t.tenantId, t.conversationId],
      foreignColumns: [platformConversation.tenantId, platformConversation.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_message_fk_2",
      columns: [t.authorUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_message_fk_3",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_conversation_message_fk_4",
      columns: [t.tenantId, t.conversationId, t.replyToMessageId],
      foreignColumns: [t.tenantId, t.conversationId, t.id],
    }).onDelete("restrict"),
    index("platform_conversation_message_ix_0").on(t.authorUserId),
    index("platform_conversation_message_ix_2").on(
      t.tenantId,
      t.agentVersionId,
    ),
    index("platform_conversation_message_ix_3").on(
      t.tenantId,
      t.conversationId,
    ),
    index("platform_conversation_message_ix_4").on(
      t.tenantId,
      t.conversationId,
      t.replyToMessageId,
    ),
    allowedValues("platform_conversation_message_role_ck", t.role, [
      "USER",
      "ASSISTANT",
      "SYSTEM",
    ]),
    check("platform_conversation_message_ck_0", sql`sequence_no > 0`),
    check(
      "platform_conversation_message_ck_1",
      sql`content_schema_version > 0`,
    ),
    check(
      "platform_conversation_message_ck_2",
      sql`(role='USER' AND author_user_id IS NOT NULL AND agent_version_id IS NULL) OR (role='ASSISTANT' AND agent_version_id IS NOT NULL AND author_user_id IS NULL) OR (role='SYSTEM' AND agent_version_id IS NULL AND author_user_id IS NULL)`,
    ),
  ],
).enableRLS();
