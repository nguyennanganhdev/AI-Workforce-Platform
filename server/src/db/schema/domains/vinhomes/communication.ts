/** Physical model for domains/vinhomes/communication. See docs/erd/README.md. */
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
import { allowedValues, createdAt, jsonb, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhResidentReport } from "./intake";
import { vhIncident } from "./operations";
import { vhProject } from "./property";

export const vhMessage = pgTable(
  "vh_message",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id").notNull(),
    residentReportId: uuid("resident_report_id"),
    body: text("body").notNull(),
    authorType: text("author_type", {
      enum: ["HUMAN", "SYSTEM", "AGENT"],
    }).notNull(),
    authorId: text("author_id").notNull(),
    visibility: text("visibility", {
      enum: ["INTERNAL", "RESIDENT_VISIBLE"],
    }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_message_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_message_uq_0").on(t.tenantId, t.id),
    unique("vh_message_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_message_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_message_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_message_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_message_fk_3",
      columns: [t.tenantId, t.projectId, t.residentReportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.projectId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_message_fk_4",
      columns: [t.tenantId, t.incidentId, t.residentReportId],
      foreignColumns: [
        vhResidentReport.tenantId,
        vhResidentReport.incidentId,
        vhResidentReport.id,
      ],
    }).onDelete("restrict"),
    index("vh_message_ix_0").on(t.tenantId, t.projectId, t.residentReportId),
    index("vh_message_ix_1").on(t.tenantId, t.projectId),
    index("vh_message_ix_2").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_message_author_type_ck", t.authorType, [
      "HUMAN",
      "SYSTEM",
      "AGENT",
    ]),
    allowedValues("vh_message_visibility_ck", t.visibility, [
      "INTERNAL",
      "RESIDENT_VISIBLE",
    ]),
  ],
).enableRLS();

export const vhBusinessEvent = pgTable(
  "vh_business_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    incidentId: uuid("incident_id"),
    subjectType: text("subject_type").notNull(),
    subjectId: uuid("subject_id").notNull(),
    eventType: text("event_type").notNull(),
    actorType: text("actor_type", {
      enum: ["HUMAN", "SYSTEM", "AUTOMATION", "AGENT", "EXTERNAL_SERVICE"],
    }).notNull(),
    actorId: text("actor_id").notNull(),
    actorVersion: text("actor_version"),
    data: jsonb("data").notNull(),
    correlationId: text("correlation_id").notNull(),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
    visibility: text("visibility", {
      enum: ["INTERNAL", "RESIDENT_VISIBLE"],
    }).notNull(),
    schemaVersion: integer("schema_version").notNull(),
    subjectVersion: bigint("subject_version", { mode: "bigint" }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_business_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_business_event_uq_0").on(t.tenantId, t.id),
    unique("vh_business_event_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_business_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_business_event_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_business_event_fk_2",
      columns: [t.tenantId, t.projectId, t.incidentId],
      foreignColumns: [
        vhIncident.tenantId,
        vhIncident.projectId,
        vhIncident.id,
      ],
    }).onDelete("restrict"),
    index("vh_business_event_ix_0").on(t.tenantId, t.incidentId, t.occurredAt),
    index("vh_business_event_ix_1").on(t.tenantId, t.projectId),
    index("vh_business_event_ix_2").on(t.tenantId, t.projectId, t.incidentId),
    allowedValues("vh_business_event_actor_type_ck", t.actorType, [
      "HUMAN",
      "SYSTEM",
      "AUTOMATION",
      "AGENT",
      "EXTERNAL_SERVICE",
    ]),
    allowedValues("vh_business_event_visibility_ck", t.visibility, [
      "INTERNAL",
      "RESIDENT_VISIBLE",
    ]),
    check("vh_business_event_ck_0", sql`schema_version > 0`),
    check("vh_business_event_ck_1", sql`subject_version > 0`),
  ],
).enableRLS();

export const vhNotification = pgTable(
  "vh_notification",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    businessEventId: uuid("business_event_id"),
    recipientId: text("recipient_id").notNull(),
    type: text("type").notNull(),
    subjectType: text("subject_type").notNull(),
    subjectId: uuid("subject_id").notNull(),
    title: text("title").notNull(),
    body: text("body").notNull(),
    readAt: timestamp("read_at", { withTimezone: true }),
    deliveryStatus: text("delivery_status", {
      enum: ["QUEUED", "DELIVERED", "FAILED"],
    }).notNull(),
    dedupeKey: text("dedupe_key").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_notification_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_notification_uq_0").on(t.tenantId, t.recipientId, t.dedupeKey),
    unique("vh_notification_uq_1").on(t.tenantId, t.id),
    unique("vh_notification_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_notification_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_fk_2",
      columns: [t.tenantId, t.projectId, t.businessEventId],
      foreignColumns: [
        vhBusinessEvent.tenantId,
        vhBusinessEvent.projectId,
        vhBusinessEvent.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_notification_fk_3",
      columns: [t.recipientId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_notification_ix_0").on(t.recipientId),
    index("vh_notification_ix_1").on(
      t.tenantId,
      t.projectId,
      t.businessEventId,
    ),
    index("vh_notification_ix_2").on(
      t.tenantId,
      t.recipientId,
      t.readAt,
      t.createdAt,
    ),
    index("vh_notification_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_notification_delivery_status_ck", t.deliveryStatus, [
      "QUEUED",
      "DELIVERED",
      "FAILED",
    ]),
    check("vh_notification_ck_0", sql`version > 0`),
  ],
).enableRLS();
