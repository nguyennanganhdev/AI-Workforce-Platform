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
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../columns";
import { platformTenant } from "./identity";

export const platformEventReceipt = pgTable(
  "platform_event_receipt",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    consumer: text("consumer").notNull(),
    producerNamespace: text("producer_namespace").notNull(),
    eventId: text("event_id").notNull(),
    payloadHash: text("payload_hash").notNull(),
    subjectRef: text("subject_ref"),
    subjectVersion: bigint("subject_version", { mode: "bigint" }),
    correlationId: text("correlation_id").notNull(),
    status: text("status", {
      enum: ["RECEIVED", "PROCESSING", "PROCESSED", "FAILED", "DEAD_LETTER"],
    }).notNull(),
    attemptCount: integer("attempt_count").notNull(),
    availableAt: timestamp("available_at", { withTimezone: true }).notNull(),
    leaseOwner: text("lease_owner"),
    leaseExpiresAt: timestamp("lease_expires_at", { withTimezone: true }),
    processedAt: timestamp("processed_at", { withTimezone: true }),
    lastErrorCode: text("last_error_code"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_event_receipt_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_event_receipt_uq_0").on(
      t.tenantId,
      t.consumer,
      t.producerNamespace,
      t.eventId,
    ),
    unique("platform_event_receipt_uq_1").on(t.tenantId, t.id),
    index("platform_event_receipt_ready_ix").on(
      t.tenantId,
      t.status,
      t.availableAt,
    ),
    foreignKey({
      name: "platform_event_receipt_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("platform_event_receipt_status_ck", t.status, [
      "RECEIVED",
      "PROCESSING",
      "PROCESSED",
      "FAILED",
      "DEAD_LETTER",
    ]),
    check("platform_event_receipt_ck_0", sql`attempt_count >= 0`),
    check(
      "platform_event_receipt_ck_1",
      sql`(lease_owner IS NULL) = (lease_expires_at IS NULL)`,
    ),
    check(
      "platform_event_receipt_ck_2",
      sql`status<>'PROCESSED' OR processed_at IS NOT NULL`,
    ),
    check("platform_event_receipt_ck_3", sql`version > 0`),
  ],
).enableRLS();
