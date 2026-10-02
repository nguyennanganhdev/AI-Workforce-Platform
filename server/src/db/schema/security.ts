/** V3 security extension: metadata, ordered alert deliveries and durable ACKs. */
import { sql } from "drizzle-orm";
import { pgTable, uuid, text, integer, timestamp, foreignKey, unique, check, pgPolicy } from "drizzle-orm/pg-core";
import { tenants, buildings, users, tickets } from "./tables";

const tenantPolicy = (name: string) => pgPolicy(name, {
  for: "all",
  using: sql`tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid`,
  withCheck: sql`tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid`,
});

export const securityCameras = pgTable("security_cameras", {
  id: uuid("id").primaryKey().defaultRandom(),
  tenantId: uuid("tenant_id").notNull().references(() => tenants.id),
  buildingId: uuid("building_id").notNull(),
  code: text("code").notNull(), name: text("name").notNull(), location: text("location").notNull(),
  status: text("status").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
}, (t) => [
  unique("security_cameras_tenant_key").on(t.tenantId, t.id),
  unique("security_cameras_code").on(t.tenantId, t.buildingId, t.code),
  foreignKey({ columns: [t.tenantId, t.buildingId], foreignColumns: [buildings.tenantId, buildings.id] }),
  check("security_cameras_status", sql`status IN ('online','offline','maintenance')`),
  tenantPolicy("security_cameras_tenant"),
]).enableRLS();

export const securityEmergencyContacts = pgTable("security_emergency_contacts", {
  id: uuid("id").primaryKey().defaultRandom(), tenantId: uuid("tenant_id").notNull().references(() => tenants.id),
  buildingId: uuid("building_id").notNull(), userId: text("user_id").notNull().references(() => users.id),
  name: text("name").notNull(), roleLabel: text("role_label").notNull(), phone: text("phone").notNull(),
  position: integer("position").notNull(), ackTimeoutSeconds: integer("ack_timeout_seconds").notNull().default(60),
  status: text("status").notNull().default("active"),
}, (t) => [
  unique("security_contacts_tenant_key").on(t.tenantId, t.id),
  unique("security_contacts_order").on(t.tenantId, t.buildingId, t.position),
  foreignKey({ columns: [t.tenantId, t.buildingId], foreignColumns: [buildings.tenantId, buildings.id] }),
  check("security_contacts_values", sql`position > 0 AND ack_timeout_seconds BETWEEN 5 AND 3600 AND status IN ('active','disabled')`),
  tenantPolicy("security_contacts_tenant"),
]).enableRLS();

export const securityAlerts = pgTable("security_alerts", {
  id: uuid("id").primaryKey().defaultRandom(), tenantId: uuid("tenant_id").notNull().references(() => tenants.id),
  ticketId: uuid("ticket_id").notNull(), createdBy: text("created_by").notNull().references(() => users.id),
  message: text("message").notNull(), idempotencyKey: text("idempotency_key").notNull(), requestHash: text("request_hash").notNull(),
  status: text("status").notNull().default("open"), version: integer("version").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
}, (t) => [
  unique("security_alerts_tenant_key").on(t.tenantId, t.id),
  unique("security_alerts_idempotency").on(t.tenantId, t.ticketId, t.idempotencyKey),
  foreignKey({ columns: [t.tenantId, t.ticketId], foreignColumns: [tickets.tenantId, tickets.id] }),
  check("security_alerts_status", sql`status IN ('open','acknowledged','exhausted') AND version >= 0`),
  tenantPolicy("security_alerts_tenant"),
]).enableRLS();

export const securityAlertDeliveries = pgTable("security_alert_deliveries", {
  id: uuid("id").primaryKey().defaultRandom(), tenantId: uuid("tenant_id").notNull().references(() => tenants.id),
  alertId: uuid("alert_id").notNull(), contactId: uuid("contact_id").notNull(),
  recipientUserId: text("recipient_user_id").notNull().references(() => users.id),
  position: integer("position").notNull(), ackTimeoutSeconds: integer("ack_timeout_seconds").notNull(),
  status: text("status").notNull().default("waiting"),
  notifiedAt: timestamp("notified_at", { withTimezone: true }), deadlineAt: timestamp("deadline_at", { withTimezone: true }),
  acknowledgedAt: timestamp("acknowledged_at", { withTimezone: true }),
}, (t) => [
  unique("security_deliveries_tenant_key").on(t.tenantId, t.id),
  unique("security_deliveries_order").on(t.tenantId, t.alertId, t.position),
  foreignKey({ columns: [t.tenantId, t.alertId], foreignColumns: [securityAlerts.tenantId, securityAlerts.id] }),
  foreignKey({ columns: [t.tenantId, t.contactId], foreignColumns: [securityEmergencyContacts.tenantId, securityEmergencyContacts.id] }),
  check("security_deliveries_status", sql`status IN ('waiting','pending','acknowledged','timed_out','cancelled') AND position > 0 AND ack_timeout_seconds BETWEEN 5 AND 3600`),
  tenantPolicy("security_deliveries_tenant"),
]).enableRLS();
