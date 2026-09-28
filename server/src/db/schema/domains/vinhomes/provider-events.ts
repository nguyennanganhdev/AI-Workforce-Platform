/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../../columns";
import { platformTenant } from "../../platform/identity";

export const vhProviderEvent = pgTable(
  "vh_provider_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    provider: text("provider").notNull(),
    providerEventId: text("provider_event_id").notNull(),
    eventType: text("event_type").notNull(),
    payloadHash: text("payload_hash").notNull(),
    sanitizedPayloadJson: jsonb("sanitized_payload_json").notNull(),
    signatureVerifiedAt: timestamp("signature_verified_at", {
      withTimezone: true,
    }).notNull(),
    receivedAt: timestamp("received_at", { withTimezone: true }).notNull(),
    subjectType: text("subject_type"),
    subjectRef: text("subject_ref"),
    status: text("status", {
      enum: ["RECEIVED", "PROCESSING", "PROCESSED", "REJECTED"],
    }).notNull(),
    attemptCount: integer("attempt_count").notNull(),
    processedAt: timestamp("processed_at", { withTimezone: true }),
    rejectionReason: text("rejection_reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_provider_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_provider_event_uq_0").on(
      t.tenantId,
      t.provider,
      t.providerEventId,
    ),
    unique("vh_provider_event_uq_1").on(t.tenantId, t.id),
    index("vh_provider_event_received_ix").on(
      t.tenantId,
      t.status,
      t.receivedAt,
    ),
    foreignKey({
      name: "vh_provider_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("vh_provider_event_status_ck", t.status, [
      "RECEIVED",
      "PROCESSING",
      "PROCESSED",
      "REJECTED",
    ]),
    check("vh_provider_event_ck_0", sql`attempt_count >= 0`),
    check(
      "vh_provider_event_ck_1",
      sql`status<>'PROCESSED' OR processed_at IS NOT NULL`,
    ),
    check("vh_provider_event_ck_2", sql`signature_verified_at >= received_at`),
    check("vh_provider_event_ck_3", sql`version > 0`),
  ],
).enableRLS();
