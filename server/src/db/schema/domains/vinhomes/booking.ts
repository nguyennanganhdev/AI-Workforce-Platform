/** Physical model for domains/vinhomes/booking. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  boolean,
  char,
  check,
  foreignKey,
  index,
  integer,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb, mutableColumns } from "../../columns";
import { platformTenant } from "../../platform/identity";
import { vhMapPlace } from "./content";
import { vhApartment, vhProject, vhPropertyMembership } from "./property";

export const vhFacility = pgTable(
  "vh_facility",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    placeId: uuid("place_id"),
    code: text("code").notNull(),
    name: text("name").notNull(),
    category: text("category").notNull(),
    capacity: integer("capacity").notNull(),
    feeMinor: bigint("fee_minor", { mode: "bigint" }).notNull(),
    currency: char("currency", { length: 3 }).notNull(),
    bookingPolicyJson: jsonb("booking_policy_json").notNull(),
    exclusiveResource: boolean("exclusive_resource").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "MAINTENANCE", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_facility_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_facility_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_facility_uq_1").on(t.tenantId, t.id),
    unique("vh_facility_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_facility_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_facility_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_facility_fk_2",
      columns: [t.tenantId, t.projectId, t.placeId],
      foreignColumns: [
        vhMapPlace.tenantId,
        vhMapPlace.projectId,
        vhMapPlace.id,
      ],
    }).onDelete("restrict"),
    index("vh_facility_ix_0").on(t.tenantId, t.projectId, t.placeId),
    index("vh_facility_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_facility_status_ck", t.status, [
      "ACTIVE",
      "MAINTENANCE",
      "RETIRED",
    ]),
    check("vh_facility_ck_0", sql`capacity > 0`),
    check("vh_facility_ck_1", sql`fee_minor >= 0`),
    check("vh_facility_ck_2", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_facility_ck_3", sql`version > 0`),
  ],
).enableRLS();

export const vhTimeSlot = pgTable(
  "vh_time_slot",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    facilityId: uuid("facility_id").notNull(),
    startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
    endsAt: timestamp("ends_at", { withTimezone: true }).notNull(),
    capacity: integer("capacity").notNull(),
    status: text("status", { enum: ["OPEN", "BLOCKED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_time_slot_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_time_slot_uq_0").on(
      t.tenantId,
      t.facilityId,
      t.startsAt,
      t.endsAt,
    ),
    unique("vh_time_slot_uq_1").on(t.tenantId, t.id),
    unique("vh_time_slot_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_time_slot_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_time_slot_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_time_slot_fk_2",
      columns: [t.tenantId, t.projectId, t.facilityId],
      foreignColumns: [
        vhFacility.tenantId,
        vhFacility.projectId,
        vhFacility.id,
      ],
    }).onDelete("restrict"),
    index("vh_time_slot_ix_0").on(t.tenantId, t.projectId, t.facilityId),
    index("vh_time_slot_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_time_slot_status_ck", t.status, ["OPEN", "BLOCKED"]),
    check("vh_time_slot_ck_0", sql`ends_at > starts_at`),
    check("vh_time_slot_ck_1", sql`capacity > 0`),
    check("vh_time_slot_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhBooking = pgTable(
  "vh_booking",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    slotId: uuid("slot_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    bookedByMembershipId: uuid("booked_by_membership_id").notNull(),
    partySize: integer("party_size").notNull(),
    status: text("status", {
      enum: ["HELD", "CONFIRMED", "CANCELLED", "EXPIRED", "COMPLETED"],
    }).notNull(),
    holdExpiresAt: timestamp("hold_expires_at", { withTimezone: true }),
    priceMinor: bigint("price_minor", { mode: "bigint" }).notNull(),
    currency: char("currency", { length: 3 }).notNull(),
    cancelledAt: timestamp("cancelled_at", { withTimezone: true }),
    cancellationReason: text("cancellation_reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_booking_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_booking_uq_0").on(t.tenantId, t.id),
    unique("vh_booking_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_booking_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_booking_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_booking_fk_2",
      columns: [t.tenantId, t.projectId, t.slotId],
      foreignColumns: [
        vhTimeSlot.tenantId,
        vhTimeSlot.projectId,
        vhTimeSlot.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_booking_fk_3",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_booking_fk_4",
      columns: [t.tenantId, t.projectId, t.bookedByMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_booking_fk_5",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.bookedByMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_booking_ix_0").on(t.tenantId, t.apartmentId, t.createdAt),
    index("vh_booking_ix_1").on(
      t.tenantId,
      t.slotId,
      t.status,
      t.holdExpiresAt,
    ),
    index("vh_booking_ix_2").on(t.tenantId, t.projectId),
    index("vh_booking_ix_3").on(t.tenantId, t.projectId, t.slotId),
    index("vh_booking_ix_4").on(
      t.tenantId,
      t.projectId,
      t.bookedByMembershipId,
    ),
    index("vh_booking_ix_5").on(t.tenantId, t.projectId, t.apartmentId),
    allowedValues("vh_booking_status_ck", t.status, [
      "HELD",
      "CONFIRMED",
      "CANCELLED",
      "EXPIRED",
      "COMPLETED",
    ]),
    check("vh_booking_ck_0", sql`party_size > 0`),
    check("vh_booking_ck_1", sql`price_minor >= 0`),
    check(
      "vh_booking_ck_2",
      sql`status <> 'HELD' OR hold_expires_at IS NOT NULL`,
    ),
    check("vh_booking_ck_3", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_booking_ck_4", sql`version > 0`),
    uniqueIndex("vh_booking_live_member_slot_uq")
      .on(t.tenantId, t.slotId, t.bookedByMembershipId)
      .where(sql`${t.status} IN ('HELD', 'CONFIRMED')`),
  ],
).enableRLS();
