/** Physical model for platform/audit. See docs/erd/README.md. */
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
import { platformTenant } from "./identity";

export const platformAuditEvent = pgTable(
  "platform_audit_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    eventType: text("event_type").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectRef: text("subject_ref").notNull(),
    actorType: text("actor_type", {
      enum: ["HUMAN", "SYSTEM", "AUTOMATION", "AGENT", "EXTERNAL_SERVICE"],
    }).notNull(),
    actorId: text("actor_id").notNull(),
    actorVersion: text("actor_version"),
    dataJson: jsonb("data_json").notNull(),
    correlationId: text("correlation_id").notNull(),
    traceId: text("trace_id").notNull(),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_audit_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_audit_event_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_audit_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    index("platform_audit_event_ix_0").on(
      t.tenantId,
      t.subjectType,
      t.subjectRef,
      t.occurredAt,
    ),
    allowedValues("platform_audit_event_actor_type_ck", t.actorType, [
      "HUMAN",
      "SYSTEM",
      "AUTOMATION",
      "AGENT",
      "EXTERNAL_SERVICE",
    ]),
  ],
).enableRLS();

export const platformOutboxEvent = pgTable(
  "platform_outbox_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    aggregateType: text("aggregate_type").notNull(),
    aggregateId: text("aggregate_id").notNull(),
    eventType: text("event_type").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    status: text("status", {
      enum: ["PENDING", "PROCESSING", "PUBLISHED", "FAILED"],
    }).notNull(),
    attemptCount: integer("attempt_count").notNull(),
    availableAt: timestamp("available_at", { withTimezone: true }).notNull(),
    lockedUntil: timestamp("locked_until", { withTimezone: true }),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    lastErrorCode: text("last_error_code"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_outbox_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_outbox_event_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_outbox_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    index("platform_outbox_event_ix_0").on(t.tenantId, t.status, t.availableAt),
    allowedValues("platform_outbox_event_status_ck", t.status, [
      "PENDING",
      "PROCESSING",
      "PUBLISHED",
      "FAILED",
    ]),
    check("platform_outbox_event_ck_0", sql`attempt_count >= 0`),
    check("platform_outbox_event_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const platformIdempotencyRecord = pgTable(
  "platform_idempotency_record",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    operation: text("operation").notNull(),
    actorId: text("actor_id").notNull(),
    requestHash: text("request_hash").notNull(),
    responseJson: jsonb("response_json"),
    status: text("status", {
      enum: ["IN_PROGRESS", "SUCCEEDED", "FAILED"],
    }).notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_idempotency_record_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_idempotency_record_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("platform_idempotency_record_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_idempotency_record_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_idempotency_record_status_ck", t.status, [
      "IN_PROGRESS",
      "SUCCEEDED",
      "FAILED",
    ]),
    check("platform_idempotency_record_ck_0", sql`version > 0`),
  ],
).enableRLS();
