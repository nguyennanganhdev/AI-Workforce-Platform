/** Physical model for domains/vinhomes/property. See docs/erd/README.md. */
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
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import {
  platformTenant,
  platformTenantMembership,
  users,
} from "../../platform/identity";

export const vhProject = pgTable(
  "vh_project",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_project_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_project_uq_0").on(t.tenantId, t.code),
    unique("vh_project_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_project_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    allowedValues("vh_project_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("vh_project_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhTower = pgTable(
  "vh_tower",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    status: text("status", { enum: ["ACTIVE", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_tower_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_tower_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_tower_uq_1").on(t.tenantId, t.id),
    unique("vh_tower_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_tower_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_tower_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_tower_ix_0").on(t.tenantId, t.projectId),
    allowedValues("vh_tower_status_ck", t.status, ["ACTIVE", "RETIRED"]),
    check("vh_tower_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhApartment = pgTable(
  "vh_apartment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    towerId: uuid("tower_id").notNull(),
    code: text("code").notNull(),
    floor: integer("floor").notNull(),
    status: text("status", { enum: ["ACTIVE", "VACANT", "RETIRED"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_apartment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_apartment_uq_0").on(t.tenantId, t.towerId, t.code),
    unique("vh_apartment_uq_1").on(t.tenantId, t.id),
    unique("vh_apartment_uq_2").on(t.tenantId, t.projectId, t.id),
    unique("vh_apartment_uq_3").on(t.tenantId, t.projectId, t.towerId, t.id),
    foreignKey({
      name: "vh_apartment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_apartment_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_apartment_fk_2",
      columns: [t.tenantId, t.projectId, t.towerId],
      foreignColumns: [vhTower.tenantId, vhTower.projectId, vhTower.id],
    }).onDelete("restrict"),
    index("vh_apartment_ix_0").on(t.tenantId, t.projectId, t.towerId),
    index("vh_apartment_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_apartment_status_ck", t.status, [
      "ACTIVE",
      "VACANT",
      "RETIRED",
    ]),
    check("vh_apartment_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhPropertyMembership = pgTable(
  "vh_property_membership",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    userId: text("user_id").notNull(),
    towerId: uuid("tower_id"),
    apartmentId: uuid("apartment_id"),
    membershipType: text("membership_type", {
      enum: ["RESIDENT", "MANAGER", "STAFF", "CONTRACTOR"],
    }).notNull(),
    residentRole: text("resident_role", {
      enum: ["OWNER", "TENANT", "HOUSEHOLD"],
    }),
    grantedByUserId: text("granted_by_user_id").notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    revokedAt: timestamp("revoked_at", { withTimezone: true }),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "REVOKED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_property_membership_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_property_membership_uq_0").on(t.tenantId, t.id),
    unique("vh_property_membership_uq_1").on(t.tenantId, t.projectId, t.id),
    unique("vh_property_membership_uq_2").on(
      t.tenantId,
      t.projectId,
      t.apartmentId,
      t.id,
    ),
    unique("vh_property_membership_uq_3").on(
      t.tenantId,
      t.projectId,
      t.userId,
      t.id,
    ),
    foreignKey({
      name: "vh_property_membership_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_2",
      columns: [t.userId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_3",
      columns: [t.tenantId, t.projectId, t.towerId],
      foreignColumns: [vhTower.tenantId, vhTower.projectId, vhTower.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_4",
      columns: [t.tenantId, t.projectId, t.towerId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.towerId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_5",
      columns: [t.grantedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_property_membership_fk_6",
      columns: [t.tenantId, t.userId],
      foreignColumns: [
        platformTenantMembership.tenantId,
        platformTenantMembership.userId,
      ],
    }).onDelete("restrict"),
    index("vh_property_membership_ix_0").on(t.userId),
    index("vh_property_membership_ix_1").on(t.tenantId, t.projectId, t.towerId),
    index("vh_property_membership_ix_2").on(
      t.tenantId,
      t.userId,
      t.status,
      t.validFrom,
      t.validUntil,
    ),
    index("vh_property_membership_ix_3").on(t.tenantId, t.projectId),
    index("vh_property_membership_ix_4").on(
      t.tenantId,
      t.projectId,
      t.towerId,
      t.apartmentId,
    ),
    index("vh_property_membership_ix_5").on(t.grantedByUserId),
    allowedValues(
      "vh_property_membership_membership_type_ck",
      t.membershipType,
      ["RESIDENT", "MANAGER", "STAFF", "CONTRACTOR"],
    ),
    allowedValues("vh_property_membership_resident_role_ck", t.residentRole, [
      "OWNER",
      "TENANT",
      "HOUSEHOLD",
    ]),
    allowedValues("vh_property_membership_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "REVOKED",
    ]),
    check(
      "vh_property_membership_ck_0",
      sql`valid_until IS NULL OR valid_until > valid_from`,
    ),
    check(
      "vh_property_membership_ck_1",
      sql`(membership_type = 'RESIDENT' AND apartment_id IS NOT NULL AND resident_role IS NOT NULL) OR (membership_type <> 'RESIDENT' AND resident_role IS NULL)`,
    ),
    check(
      "vh_property_membership_ck_2",
      sql`apartment_id IS NULL OR tower_id IS NOT NULL`,
    ),
    check(
      "vh_property_membership_ck_3",
      sql`status <> 'REVOKED' OR revoked_at IS NOT NULL`,
    ),
    check("vh_property_membership_ck_4", sql`version > 0`),
  ],
).enableRLS();

export const vhMembershipApplication = pgTable(
  "vh_membership_application",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    requestedApartmentId: uuid("requested_apartment_id").notNull(),
    applicantUserId: text("applicant_user_id").notNull(),
    requestedRole: text("requested_role", {
      enum: ["OWNER", "TENANT", "HOUSEHOLD"],
    }).notNull(),
    status: text("status", {
      enum: ["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"],
    }).notNull(),
    reviewedBy: text("reviewed_by"),
    reviewedAt: timestamp("reviewed_at", { withTimezone: true }),
    decisionNote: text("decision_note"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_membership_application_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_membership_application_uq_0").on(t.tenantId, t.id),
    unique("vh_membership_application_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_membership_application_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_fk_2",
      columns: [t.tenantId, t.projectId, t.requestedApartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_fk_3",
      columns: [t.applicantUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_membership_application_fk_4",
      columns: [t.reviewedBy],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_membership_application_ix_0").on(t.applicantUserId),
    index("vh_membership_application_ix_1").on(t.reviewedBy),
    index("vh_membership_application_ix_2").on(t.tenantId, t.projectId),
    index("vh_membership_application_ix_3").on(
      t.tenantId,
      t.projectId,
      t.requestedApartmentId,
    ),
    allowedValues(
      "vh_membership_application_requested_role_ck",
      t.requestedRole,
      ["OWNER", "TENANT", "HOUSEHOLD"],
    ),
    allowedValues("vh_membership_application_status_ck", t.status, [
      "PENDING",
      "APPROVED",
      "REJECTED",
      "WITHDRAWN",
    ]),
    check("vh_membership_application_ck_0", sql`version > 0`),
  ],
).enableRLS();
