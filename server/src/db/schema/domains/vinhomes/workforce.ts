/** Persistence for coordination and field operations. See docs/erd/SYSTEM_FLOW.md. */
import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhProject, vhPropertyMembership } from "./property";

export const vhTeam = pgTable(
  "vh_team",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    name: text("name").notNull(),
    specialty: text("specialty", {
      enum: ["TECHNICAL", "SANITATION", "SECURITY", "LANDSCAPE", "MULTI"],
    }).notNull(),
    status: text("status", { enum: ["ACTIVE", "INACTIVE"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_team_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_team_uq_0").on(t.tenantId, t.projectId, t.code),
    unique("vh_team_uq_1").on(t.tenantId, t.id),
    unique("vh_team_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_team_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_team_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_team_ix_1").on(t.tenantId, t.projectId),
    allowedValues("vh_team_specialty_ck", t.specialty, [
      "TECHNICAL",
      "SANITATION",
      "SECURITY",
      "LANDSCAPE",
      "MULTI",
    ]),
    allowedValues("vh_team_status_ck", t.status, ["ACTIVE", "INACTIVE"]),
    check("vh_team_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhTeamMember = pgTable(
  "vh_team_member",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    teamId: uuid("team_id").notNull(),
    propertyMembershipId: uuid("property_membership_id").notNull(),
    role: text("role", {
      enum: ["LEAD", "TECHNICIAN", "DISPATCHER"],
    }).notNull(),
    validFrom: timestamp("valid_from", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    status: text("status", { enum: ["ACTIVE", "INACTIVE"] }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_team_member_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_team_member_uq_0").on(t.tenantId, t.id),
    unique("vh_team_member_uq_1").on(t.tenantId, t.projectId, t.id),
    unique("vh_team_member_uq_2").on(t.tenantId, t.projectId, t.teamId, t.id),
    foreignKey({
      name: "vh_team_member_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_team_member_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_team_member_fk_2",
      columns: [t.tenantId, t.projectId, t.teamId],
      foreignColumns: [vhTeam.tenantId, vhTeam.projectId, vhTeam.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_team_member_fk_3",
      columns: [t.tenantId, t.projectId, t.propertyMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    index("vh_team_member_ix_1").on(t.tenantId, t.projectId),
    index("vh_team_member_ix_2").on(
      t.tenantId,
      t.projectId,
      t.propertyMembershipId,
    ),
    index("vh_team_member_ix_3").on(t.tenantId, t.projectId, t.teamId),
    allowedValues("vh_team_member_role_ck", t.role, [
      "LEAD",
      "TECHNICIAN",
      "DISPATCHER",
    ]),
    allowedValues("vh_team_member_status_ck", t.status, ["ACTIVE", "INACTIVE"]),
    check(
      "vh_team_member_ck_0",
      sql`valid_until IS NULL OR valid_until > valid_from`,
    ),
    check("vh_team_member_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhStaffSkill = pgTable(
  "vh_staff_skill",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    propertyMembershipId: uuid("property_membership_id").notNull(),
    skillCode: text("skill_code").notNull(),
    proficiency: text("proficiency", {
      enum: ["BASIC", "QUALIFIED", "EXPERT"],
    }).notNull(),
    certificateRef: text("certificate_ref"),
    verifiedByUserId: text("verified_by_user_id").notNull(),
    verifiedAt: timestamp("verified_at", { withTimezone: true }).notNull(),
    validUntil: timestamp("valid_until", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_staff_skill_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_staff_skill_uq_0").on(
      t.tenantId,
      t.propertyMembershipId,
      t.skillCode,
    ),
    unique("vh_staff_skill_uq_1").on(t.tenantId, t.id),
    unique("vh_staff_skill_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_staff_skill_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_staff_skill_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_staff_skill_fk_2",
      columns: [t.tenantId, t.projectId, t.propertyMembershipId],
      foreignColumns: [
        vhPropertyMembership.tenantId,
        vhPropertyMembership.projectId,
        vhPropertyMembership.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_staff_skill_fk_3",
      columns: [t.verifiedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_staff_skill_ix_1").on(t.tenantId, t.projectId),
    index("vh_staff_skill_ix_2").on(
      t.tenantId,
      t.projectId,
      t.propertyMembershipId,
    ),
    index("vh_staff_skill_ix_3").on(t.verifiedByUserId),
    allowedValues("vh_staff_skill_proficiency_ck", t.proficiency, [
      "BASIC",
      "QUALIFIED",
      "EXPERT",
    ]),
    check(
      "vh_staff_skill_ck_0",
      sql`valid_until IS NULL OR valid_until > verified_at`,
    ),
    check("vh_staff_skill_ck_1", sql`version > 0`),
  ],
).enableRLS();

export const vhStaffShift = pgTable(
  "vh_staff_shift",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    teamMemberId: uuid("team_member_id").notNull(),
    startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
    endsAt: timestamp("ends_at", { withTimezone: true }).notNull(),
    status: text("status", {
      enum: ["PLANNED", "CONFIRMED", "COMPLETED", "CANCELLED"],
    }).notNull(),
    timezone: text("timezone").notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_staff_shift_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_staff_shift_uq_0").on(t.tenantId, t.id),
    unique("vh_staff_shift_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_staff_shift_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_staff_shift_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_staff_shift_fk_2",
      columns: [t.tenantId, t.projectId, t.teamMemberId],
      foreignColumns: [
        vhTeamMember.tenantId,
        vhTeamMember.projectId,
        vhTeamMember.id,
      ],
    }).onDelete("restrict"),
    index("vh_staff_shift_ix_1").on(t.tenantId, t.projectId),
    index("vh_staff_shift_ix_2").on(t.tenantId, t.projectId, t.teamMemberId),
    allowedValues("vh_staff_shift_status_ck", t.status, [
      "PLANNED",
      "CONFIRMED",
      "COMPLETED",
      "CANCELLED",
    ]),
    check("vh_staff_shift_ck_0", sql`ends_at > starts_at`),
    check("vh_staff_shift_ck_1", sql`version > 0`),
  ],
).enableRLS();
