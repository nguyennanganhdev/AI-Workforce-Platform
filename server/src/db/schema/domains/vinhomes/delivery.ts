/** Physical model for domains/vinhomes/delivery. See docs/erd/README.md. */
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
import { platformTenant, users } from "../../platform/identity";
import { vhBusinessEvent } from "./communication";
import { vhProject } from "./property";

export const vhCommandReceipt = pgTable(
  "vh_command_receipt",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    commandType: text("command_type").notNull(),
    actorUserId: text("actor_user_id").notNull(),
    payloadHash: text("payload_hash").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectId: uuid("subject_id"),
    responseJson: jsonb("response_json"),
    status: text("status", { enum: ["IN_PROGRESS", "COMPLETED"] }).notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    expiresAt: timestamp("expires_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_command_receipt_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_command_receipt_uq_0").on(
      t.tenantId,
      t.actorUserId,
      t.commandType,
      t.idempotencyKey,
    ),
    unique("vh_command_receipt_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_command_receipt_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_command_receipt_actor_fk",
      columns: [t.actorUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    allowedValues("vh_command_receipt_status_ck", t.status, [
      "IN_PROGRESS",
      "COMPLETED",
    ]),
    check(
      "vh_command_receipt_completed_ck",
      sql`status <> 'COMPLETED' OR (completed_at IS NOT NULL AND response_json IS NOT NULL)`,
    ),
    check("vh_command_receipt_version_ck", sql`version > 0`),
  ],
).enableRLS();

export const vhOutbox = pgTable(
  "vh_outbox",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    businessEventId: uuid("business_event_id").notNull(),
    destination: text("destination").notNull(),
    payloadJson: jsonb("payload_json").notNull(),
    attemptCount: integer("attempt_count").notNull(),
    availableAt: timestamp("available_at", { withTimezone: true }).notNull(),
    lockedUntil: timestamp("locked_until", { withTimezone: true }),
    deliveredAt: timestamp("delivered_at", { withTimezone: true }),
    lastErrorCode: text("last_error_code"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_outbox_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_outbox_uq_0").on(t.tenantId, t.businessEventId, t.destination),
    unique("vh_outbox_uq_1").on(t.tenantId, t.id),
    unique("vh_outbox_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_outbox_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_outbox_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_outbox_fk_2",
      columns: [t.tenantId, t.projectId, t.businessEventId],
      foreignColumns: [
        vhBusinessEvent.tenantId,
        vhBusinessEvent.projectId,
        vhBusinessEvent.id,
      ],
    }).onDelete("restrict"),
    index("vh_outbox_ix_0").on(t.tenantId, t.projectId, t.businessEventId),
    index("vh_outbox_ix_1").on(t.tenantId, t.projectId),
    check("vh_outbox_ck_0", sql`attempt_count >= 0`),
    check("vh_outbox_ck_1", sql`version > 0`),
    index("vh_outbox_pending_ix")
      .on(t.availableAt)
      .where(sql`${t.deliveredAt} IS NULL`),
  ],
).enableRLS();
