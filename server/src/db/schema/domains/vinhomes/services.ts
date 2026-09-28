/** Physical model for domains/vinhomes/services. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  char,
  check,
  date,
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
import { platformTenant, users } from "../../platform/identity";
import { vhMapPlace } from "./content";
import { vhChecklistVersion } from "./operations";
import { vhApartment, vhProject, vhPropertyMembership } from "./property";

export const vhHandover = pgTable(
  "vh_handover",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    residentMembershipId: uuid("resident_membership_id").notNull(),
    scheduledAt: timestamp("scheduled_at", { withTimezone: true }).notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    checklistVersionId: uuid("checklist_version_id"),
    status: text("status", {
      enum: ["SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED"],
    }).notNull(),
    note: text("note"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_handover_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_handover_uq_0").on(t.tenantId, t.id),
    unique("vh_handover_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_handover_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_handover_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_handover_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_handover_fk_3",
      columns: [t.tenantId, t.projectId, t.residentMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_handover_fk_4",
      columns: [t.tenantId, t.checklistVersionId],
      foreignColumns: [vhChecklistVersion.tenantId, vhChecklistVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_handover_fk_5",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.residentMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_handover_ix_0").on(t.tenantId, t.checklistVersionId),
    index("vh_handover_ix_1").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_handover_ix_2").on(
      t.tenantId,
      t.projectId,
      t.residentMembershipId,
    ),
    index("vh_handover_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_handover_status_ck", t.status, [
      "SCHEDULED",
      "CONFIRMED",
      "COMPLETED",
      "CANCELLED",
    ]),
    check("vh_handover_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhAccessCard = pgTable(
  "vh_access_card",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    membershipId: uuid("membership_id").notNull(),
    cardTokenRef: text("card_token_ref").notNull(),
    issuedAt: timestamp("issued_at", { withTimezone: true }),
    expiresAt: timestamp("expires_at", { withTimezone: true }),
    status: text("status", {
      enum: ["REQUESTED", "ACTIVE", "SUSPENDED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_access_card_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_access_card_uq_0").on(t.cardTokenRef),
    unique("vh_access_card_uq_1").on(t.tenantId, t.id),
    unique("vh_access_card_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_access_card_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_access_card_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_access_card_fk_2",
      columns: [t.tenantId, t.projectId, t.membershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_access_card_ix_0").on(t.tenantId, t.projectId, t.membershipId),
    index("vh_access_card_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_access_card_status_ck", t.status, [
      "REQUESTED",
      "ACTIVE",
      "SUSPENDED",
      "REVOKED",
    ]),
    check("vh_access_card_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhServiceRequest = pgTable(
  "vh_service_request",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    requesterMembershipId: uuid("requester_membership_id").notNull(),
    serviceType: text("service_type").notNull(),
    requestedStartAt: timestamp("requested_start_at", {
      withTimezone: true,
    }).notNull(),
    requestedEndAt: timestamp("requested_end_at", { withTimezone: true }),
    detailsJson: jsonb("details_json").notNull(),
    detailsSchemaVersion: integer("details_schema_version").notNull(),
    status: text("status", {
      enum: [
        "DRAFT",
        "SUBMITTED",
        "APPROVED",
        "REJECTED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
      ],
    }).notNull(),
    decisionReason: text("decision_reason"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_service_request_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_service_request_uq_0").on(t.tenantId, t.id),
    unique("vh_service_request_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_service_request_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_fk_3",
      columns: [t.tenantId, t.projectId, t.requesterMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_service_request_fk_4",
      columns: [
        t.tenantId,
        t.projectId,
        t.apartmentId,
        t.requesterMembershipId,
      ],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_service_request_ix_0").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_service_request_ix_1").on(
      t.tenantId,
      t.projectId,
      t.requesterMembershipId,
    ),
    index("vh_service_request_ix_2").on(t.tenantId, t.projectId),
    index("vh_service_request_ix_3").on(
      t.tenantId,
      t.apartmentId,
      t.status,
      t.createdAt,
    ),
    allowedValues("vh_service_request_status_ck", t.status, [
      "DRAFT",
      "SUBMITTED",
      "APPROVED",
      "REJECTED",
      "IN_PROGRESS",
      "COMPLETED",
      "CANCELLED",
    ]),
    check("vh_service_request_ck_0", sql`details_schema_version > 0`),
    check(
      "vh_service_request_ck_1",
      sql`requested_end_at IS NULL OR requested_end_at > requested_start_at`,
    ),
    check("vh_service_request_ck_2", sql`version > 0`),
  ],
).enableRLS();

export const vhVisitorPass = pgTable(
  "vh_visitor_pass",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    serviceRequestId: uuid("service_request_id").notNull(),
    visitorName: text("visitor_name").notNull(),
    vehiclePlate: text("vehicle_plate"),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }).notNull(),
    passTokenRef: text("pass_token_ref"),
    status: text("status", {
      enum: ["REQUESTED", "ACTIVE", "EXPIRED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_visitor_pass_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_visitor_pass_uq_0").on(t.tenantId, t.serviceRequestId),
    unique("vh_visitor_pass_uq_1").on(t.passTokenRef),
    unique("vh_visitor_pass_uq_2").on(t.tenantId, t.id),
    unique("vh_visitor_pass_uq_3").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_visitor_pass_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_visitor_pass_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_visitor_pass_fk_2",
      columns: [t.tenantId, t.projectId, t.serviceRequestId],
      foreignColumns: [
        vhServiceRequest.tenantId,
        vhServiceRequest.projectId,
        vhServiceRequest.id,
      ],
    }).onDelete("restrict"),
    index("vh_visitor_pass_ix_0").on(
      t.tenantId,
      t.projectId,
      t.serviceRequestId,
    ),
    index("vh_visitor_pass_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_visitor_pass_status_ck", t.status, [
      "REQUESTED",
      "ACTIVE",
      "EXPIRED",
      "REVOKED",
    ]),
    check("vh_visitor_pass_ck_0", sql`valid_until > valid_from`),
    check("vh_visitor_pass_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhChargingSession = pgTable(
  "vh_charging_session",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    requestedByMembershipId: uuid("requested_by_membership_id").notNull(),
    stationPlaceId: uuid("station_place_id").notNull(),
    connectorCode: text("connector_code").notNull(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    endedAt: timestamp("ended_at", { withTimezone: true }),
    energyWh: bigint("energy_wh", { mode: "bigint" }),
    amountMinor: bigint("amount_minor", { mode: "bigint" }),
    currency: char("currency", { length: 3 }).notNull(),
    providerRef: text("provider_ref"),
    status: text("status", {
      enum: ["REQUESTED", "ACTIVE", "COMPLETED", "FAILED", "CANCELLED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_charging_session_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_charging_session_uq_0").on(t.providerRef),
    unique("vh_charging_session_uq_1").on(t.tenantId, t.id),
    unique("vh_charging_session_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_charging_session_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_charging_session_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_charging_session_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_charging_session_fk_3",
      columns: [t.tenantId, t.projectId, t.requestedByMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_charging_session_fk_4",
      columns: [t.tenantId, t.projectId, t.stationPlaceId],
      foreignColumns: [
        vhMapPlace.tenantId,
        vhMapPlace.projectId,
        vhMapPlace.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_charging_session_fk_5",
      columns: [
        t.tenantId,
        t.projectId,
        t.apartmentId,
        t.requestedByMembershipId,
      ],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_charging_session_ix_0").on(
      t.tenantId,
      t.projectId,
      t.stationPlaceId,
    ),
    index("vh_charging_session_ix_1").on(
      t.tenantId,
      t.projectId,
      t.apartmentId,
    ),
    index("vh_charging_session_ix_2").on(t.tenantId, t.projectId),
    index("vh_charging_session_ix_3").on(
      t.tenantId,
      t.projectId,
      t.requestedByMembershipId,
    ),
    allowedValues("vh_charging_session_status_ck", t.status, [
      "REQUESTED",
      "ACTIVE",
      "COMPLETED",
      "FAILED",
      "CANCELLED",
    ]),
    check("vh_charging_session_ck_0", sql`energy_wh IS NULL OR energy_wh >= 0`),
    check(
      "vh_charging_session_ck_1",
      sql`amount_minor IS NULL OR amount_minor >= 0`,
    ),
    check(
      "vh_charging_session_ck_2",
      sql`ended_at IS NULL OR ended_at >= started_at`,
    ),
    check("vh_charging_session_ck_3", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_charging_session_ck_4", sql`version > 0`),
  ],
).enableRLS();

export const vhPetProfile = pgTable(
  "vh_pet_profile",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    ownerMembershipId: uuid("owner_membership_id").notNull(),
    name: text("name").notNull(),
    species: text("species").notNull(),
    breed: text("breed"),
    vaccinationValidUntil: date("vaccination_valid_until"),
    status: text("status", {
      enum: ["PENDING", "REGISTERED", "REJECTED", "ARCHIVED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_pet_profile_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_pet_profile_uq_0").on(t.tenantId, t.id),
    unique("vh_pet_profile_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_pet_profile_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_profile_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_profile_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_profile_fk_3",
      columns: [t.tenantId, t.projectId, t.ownerMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_pet_profile_fk_4",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.ownerMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_pet_profile_ix_0").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_pet_profile_ix_1").on(t.tenantId, t.projectId),
    index("vh_pet_profile_ix_2").on(
      t.tenantId,
      t.projectId,
      t.ownerMembershipId,
    ),
    allowedValues("vh_pet_profile_status_ck", t.status, [
      "PENDING",
      "REGISTERED",
      "REJECTED",
      "ARCHIVED",
    ]),
    check("vh_pet_profile_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhConstructionPermit = pgTable(
  "vh_construction_permit",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    serviceRequestId: uuid("service_request_id").notNull(),
    contractorName: text("contractor_name").notNull(),
    startDate: date("start_date").notNull(),
    endDate: date("end_date").notNull(),
    permittedHoursJson: jsonb("permitted_hours_json").notNull(),
    status: text("status", {
      enum: ["PENDING", "APPROVED", "REJECTED", "EXPIRED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_construction_permit_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_construction_permit_uq_0").on(t.tenantId, t.serviceRequestId),
    unique("vh_construction_permit_uq_1").on(t.tenantId, t.id),
    unique("vh_construction_permit_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_construction_permit_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_construction_permit_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_construction_permit_fk_2",
      columns: [t.tenantId, t.projectId, t.serviceRequestId],
      foreignColumns: [
        vhServiceRequest.tenantId,
        vhServiceRequest.projectId,
        vhServiceRequest.id,
      ],
    }).onDelete("restrict"),
    index("vh_construction_permit_ix_0").on(
      t.tenantId,
      t.projectId,
      t.serviceRequestId,
    ),
    index("vh_construction_permit_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_construction_permit_status_ck", t.status, [
      "PENDING",
      "APPROVED",
      "REJECTED",
      "EXPIRED",
      "REVOKED",
    ]),
    check("vh_construction_permit_ck_0", sql`end_date >= start_date`),
    check("vh_construction_permit_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhParkingPermit = pgTable(
  "vh_parking_permit",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    membershipId: uuid("membership_id").notNull(),
    vehiclePlate: text("vehicle_plate").notNull(),
    vehicleType: text("vehicle_type").notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    status: text("status", {
      enum: ["PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_parking_permit_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_parking_permit_uq_0").on(t.tenantId, t.id),
    unique("vh_parking_permit_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_parking_permit_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_parking_permit_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_parking_permit_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_parking_permit_fk_3",
      columns: [t.tenantId, t.projectId, t.membershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_parking_permit_fk_4",
      columns: [t.tenantId, t.projectId, t.apartmentId, t.membershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_parking_permit_ix_0").on(t.tenantId, t.projectId, t.membershipId),
    index("vh_parking_permit_ix_1").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_parking_permit_ix_2").on(t.tenantId, t.projectId),
    allowedValues("vh_parking_permit_status_ck", t.status, [
      "PENDING",
      "ACTIVE",
      "SUSPENDED",
      "EXPIRED",
      "REVOKED",
    ]),
    check(
      "vh_parking_permit_ck_0",
      sql`valid_until IS NULL OR valid_until > valid_from`,
    ),
    check("vh_parking_permit_ck_1", sql`version > 0`),
    uniqueIndex("vh_parking_active_plate_uq")
      .on(t.tenantId, t.projectId, t.vehiclePlate)
      .where(sql`${t.status} = 'ACTIVE'`),
  ],
).enableRLS();

export const vhFaceEnrollment = pgTable(
  "vh_face_enrollment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    membershipId: uuid("membership_id").notNull(),
    consentVersion: text("consent_version").notNull(),
    consentedAt: timestamp("consented_at", { withTimezone: true }).notNull(),
    providerSubjectRef: text("provider_subject_ref"),
    status: text("status", {
      enum: ["PENDING", "ACTIVE", "REJECTED", "REVOKED"],
    }).notNull(),
    revokedAt: timestamp("revoked_at", { withTimezone: true }),
    deletionRequestedAt: timestamp("deletion_requested_at", {
      withTimezone: true,
    }),
    deletionConfirmedAt: timestamp("deletion_confirmed_at", {
      withTimezone: true,
    }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_face_enrollment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_face_enrollment_uq_0").on(t.tenantId, t.id),
    unique("vh_face_enrollment_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_face_enrollment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_face_enrollment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_face_enrollment_fk_2",
      columns: [t.tenantId, t.projectId, t.membershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_face_enrollment_ix_0").on(
      t.tenantId,
      t.projectId,
      t.membershipId,
    ),
    index("vh_face_enrollment_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_face_enrollment_status_ck", t.status, [
      "PENDING",
      "ACTIVE",
      "REJECTED",
      "REVOKED",
    ]),
    check("vh_face_enrollment_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhIntercomEvent = pgTable(
  "vh_intercom_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    visitorPassId: uuid("visitor_pass_id"),
    providerEventId: text("provider_event_id").notNull(),
    eventType: text("event_type").notNull(),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
    outcome: text("outcome").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_intercom_event_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_intercom_event_uq_0").on(t.tenantId, t.providerEventId),
    unique("vh_intercom_event_uq_1").on(t.tenantId, t.id),
    unique("vh_intercom_event_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_intercom_event_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_intercom_event_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_intercom_event_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_intercom_event_fk_3",
      columns: [t.tenantId, t.projectId, t.visitorPassId],
      foreignColumns: [
        vhVisitorPass.tenantId,
        vhVisitorPass.projectId,
        vhVisitorPass.id,
      ],
    }).onDelete("restrict"),
    index("vh_intercom_event_ix_0").on(
      t.tenantId,
      t.projectId,
      t.visitorPassId,
    ),
    index("vh_intercom_event_ix_1").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_intercom_event_ix_2").on(t.tenantId, t.projectId),
  ],
).enableRLS();

export const vhCameraRequest = pgTable(
  "vh_camera_request",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    requesterMembershipId: uuid("requester_membership_id").notNull(),
    locationPlaceId: uuid("location_place_id").notNull(),
    fromAt: timestamp("from_at", { withTimezone: true }).notNull(),
    toAt: timestamp("to_at", { withTimezone: true }).notNull(),
    purpose: text("purpose").notNull(),
    status: text("status", {
      enum: ["SUBMITTED", "APPROVED", "REJECTED", "FULFILLED", "EXPIRED"],
    }).notNull(),
    reviewedBy: text("reviewed_by"),
    expiresAt: timestamp("expires_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_camera_request_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_camera_request_uq_0").on(t.tenantId, t.id),
    unique("vh_camera_request_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_camera_request_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_3",
      columns: [t.tenantId, t.projectId, t.requesterMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_4",
      columns: [t.tenantId, t.projectId, t.locationPlaceId],
      foreignColumns: [
        vhMapPlace.tenantId,
        vhMapPlace.projectId,
        vhMapPlace.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_5",
      columns: [t.reviewedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_camera_request_fk_6",
      columns: [
        t.tenantId,
        t.projectId,
        t.apartmentId,
        t.requesterMembershipId,
      ],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.apartmentId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_camera_request_ix_0").on(
      t.tenantId,
      t.projectId,
      t.locationPlaceId,
    ),
    index("vh_camera_request_ix_1").on(t.tenantId, t.projectId),
    index("vh_camera_request_ix_2").on(
      t.tenantId,
      t.projectId,
      t.requesterMembershipId,
    ),
    index("vh_camera_request_ix_3").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_camera_request_ix_4").on(t.reviewedBy),
    allowedValues("vh_camera_request_status_ck", t.status, [
      "SUBMITTED",
      "APPROVED",
      "REJECTED",
      "FULFILLED",
      "EXPIRED",
    ]),
    check("vh_camera_request_ck_0", sql`to_at > from_at`),
    check("vh_camera_request_ck_1", sql`version > 0`),
  ],
).enableRLS();
