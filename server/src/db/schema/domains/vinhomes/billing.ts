/** Physical model for domains/vinhomes/billing. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  bigint,
  char,
  check,
  date,
  foreignKey,
  index,
  integer,
  numeric,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  timestamp,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, mutableColumns } from "../../columns";
import { platformTenant, users } from "../../platform/identity";
import { vhApartment, vhProject } from "./property";

export const vhFeeSchedule = pgTable(
  "vh_fee_schedule",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    code: text("code").notNull(),
    versionNo: integer("version_no").notNull(),
    effectiveFrom: timestamp("effective_from", {
      withTimezone: true,
    }).notNull(),
    effectiveUntil: timestamp("effective_until", { withTimezone: true }),
    description: text("description").notNull(),
    amountMinor: bigint("amount_minor", { mode: "bigint" }).notNull(),
    currency: char("currency", { length: 3 }).notNull(),
    billingUnit: text("billing_unit").notNull(),
    status: text("status", {
      enum: ["DRAFT", "PUBLISHED", "RETIRED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_fee_schedule_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_fee_schedule_uq_0").on(
      t.tenantId,
      t.projectId,
      t.code,
      t.versionNo,
    ),
    unique("vh_fee_schedule_uq_1").on(t.tenantId, t.id),
    unique("vh_fee_schedule_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_fee_schedule_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_fee_schedule_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    index("vh_fee_schedule_ix_0").on(t.tenantId, t.projectId),
    allowedValues("vh_fee_schedule_status_ck", t.status, [
      "DRAFT",
      "PUBLISHED",
      "RETIRED",
    ]),
    check("vh_fee_schedule_ck_0", sql`version_no > 0`),
    check("vh_fee_schedule_ck_1", sql`amount_minor >= 0`),
    check(
      "vh_fee_schedule_ck_2",
      sql`effective_until IS NULL OR effective_until > effective_from`,
    ),
    check("vh_fee_schedule_ck_3", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_fee_schedule_ck_4", sql`version > 0`),
  ],
).enableRLS();

export const vhInvoice = pgTable(
  "vh_invoice",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    apartmentId: uuid("apartment_id").notNull(),
    billedToUserId: text("billed_to_user_id").notNull(),
    invoiceNumber: text("invoice_number").notNull(),
    periodStart: date("period_start").notNull(),
    periodEnd: date("period_end").notNull(),
    dueAt: timestamp("due_at", { withTimezone: true }).notNull(),
    totalMinor: bigint("total_minor", { mode: "bigint" }).notNull(),
    currency: char("currency", { length: 3 }).notNull(),
    status: text("status", {
      enum: ["DRAFT", "ISSUED", "PARTIALLY_PAID", "PAID", "VOID"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_invoice_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_invoice_uq_0").on(t.tenantId, t.invoiceNumber),
    unique("vh_invoice_uq_1").on(t.tenantId, t.id),
    unique("vh_invoice_uq_2").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_invoice_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_fk_2",
      columns: [t.tenantId, t.projectId, t.apartmentId],
      foreignColumns: [
        vhApartment.tenantId,
        vhApartment.projectId,
        vhApartment.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_fk_3",
      columns: [t.billedToUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_invoice_ix_0").on(t.billedToUserId),
    index("vh_invoice_ix_1").on(t.tenantId, t.apartmentId, t.status, t.dueAt),
    index("vh_invoice_ix_2").on(t.tenantId, t.projectId, t.apartmentId),
    index("vh_invoice_ix_3").on(t.tenantId, t.projectId),
    allowedValues("vh_invoice_status_ck", t.status, [
      "DRAFT",
      "ISSUED",
      "PARTIALLY_PAID",
      "PAID",
      "VOID",
    ]),
    check("vh_invoice_ck_0", sql`period_end >= period_start`),
    check("vh_invoice_ck_1", sql`total_minor >= 0`),
    check("vh_invoice_ck_2", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_invoice_ck_3", sql`version > 0`),
  ],
).enableRLS();

export const vhInvoiceLine = pgTable(
  "vh_invoice_line",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    invoiceId: uuid("invoice_id").notNull(),
    feeScheduleId: uuid("fee_schedule_id"),
    description: text("description").notNull(),
    quantity: numeric("quantity").notNull(),
    unitPriceMinor: bigint("unit_price_minor", { mode: "bigint" }).notNull(),
    totalMinor: bigint("total_minor", { mode: "bigint" }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_invoice_line_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_invoice_line_uq_0").on(t.tenantId, t.id),
    unique("vh_invoice_line_uq_1").on(t.tenantId, t.projectId, t.id),
    foreignKey({
      name: "vh_invoice_line_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_line_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_line_fk_2",
      columns: [t.tenantId, t.projectId, t.invoiceId],
      foreignColumns: [vhInvoice.tenantId, vhInvoice.projectId, vhInvoice.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_invoice_line_fk_3",
      columns: [t.tenantId, t.projectId, t.feeScheduleId],
      foreignColumns: [
        vhFeeSchedule.tenantId,
        vhFeeSchedule.projectId,
        vhFeeSchedule.id,
      ],
    }).onDelete("restrict"),
    index("vh_invoice_line_ix_0").on(t.tenantId, t.projectId, t.invoiceId),
    index("vh_invoice_line_ix_1").on(t.tenantId, t.projectId),
    index("vh_invoice_line_ix_2").on(t.tenantId, t.projectId, t.feeScheduleId),
    check("vh_invoice_line_ck_0", sql`quantity > 0`),
    check("vh_invoice_line_ck_1", sql`unit_price_minor >= 0`),
    check("vh_invoice_line_ck_2", sql`total_minor >= 0`),
    check(
      "vh_invoice_line_ck_3",
      sql`total_minor = round(quantity * unit_price_minor)`,
    ),
    check("vh_invoice_line_ck_4", sql`version > 0`),
  ],
).enableRLS();

export const vhPaymentAttempt = pgTable(
  "vh_payment_attempt",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    invoiceId: uuid("invoice_id").notNull(),
    initiatedByUserId: text("initiated_by_user_id").notNull(),
    amountMinor: bigint("amount_minor", { mode: "bigint" }).notNull(),
    currency: char("currency", { length: 3 }).notNull(),
    provider: text("provider").notNull(),
    providerPaymentRef: text("provider_payment_ref"),
    idempotencyKey: text("idempotency_key").notNull(),
    status: text("status", {
      enum: [
        "PENDING",
        "REQUIRES_ACTION",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "SIMULATED",
      ],
    }).notNull(),
    confirmedAt: timestamp("confirmed_at", { withTimezone: true }),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_payment_attempt_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_payment_attempt_uq_0").on(t.tenantId, t.idempotencyKey),
    unique("vh_payment_attempt_uq_1").on(t.provider, t.providerPaymentRef),
    unique("vh_payment_attempt_uq_2").on(t.tenantId, t.id),
    unique("vh_payment_attempt_uq_3").on(t.tenantId, t.projectId, t.id),
    unique("vh_payment_attempt_uq_4").on(
      t.tenantId,
      t.projectId,
      t.invoiceId,
      t.id,
    ),
    foreignKey({
      name: "vh_payment_attempt_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_attempt_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_attempt_fk_2",
      columns: [t.tenantId, t.projectId, t.invoiceId],
      foreignColumns: [vhInvoice.tenantId, vhInvoice.projectId, vhInvoice.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_attempt_fk_3",
      columns: [t.initiatedByUserId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_payment_attempt_ix_0").on(t.tenantId, t.projectId, t.invoiceId),
    index("vh_payment_attempt_ix_1").on(t.tenantId, t.projectId),
    index("vh_payment_attempt_ix_2").on(t.initiatedByUserId),
    allowedValues("vh_payment_attempt_status_ck", t.status, [
      "PENDING",
      "REQUIRES_ACTION",
      "SUCCEEDED",
      "FAILED",
      "CANCELLED",
      "SIMULATED",
    ]),
    check("vh_payment_attempt_ck_0", sql`amount_minor > 0`),
    check(
      "vh_payment_attempt_ck_1",
      sql`status <> 'SUCCEEDED' OR (provider_payment_ref IS NOT NULL AND confirmed_at IS NOT NULL)`,
    ),
    check("vh_payment_attempt_ck_2", sql`currency ~ '^[A-Z]{3}$'`),
    check("vh_payment_attempt_ck_3", sql`version > 0`),
  ],
).enableRLS();

export const vhPaymentAllocation = pgTable(
  "vh_payment_allocation",
  {
    tenantId: uuid("tenant_id").notNull(),
    projectId: uuid("project_id").notNull(),
    paymentAttemptId: uuid("payment_attempt_id").notNull(),
    invoiceId: uuid("invoice_id").notNull(),
    amountMinor: bigint("amount_minor", { mode: "bigint" }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_payment_allocation_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.paymentAttemptId, t.invoiceId] }),
    foreignKey({
      name: "vh_payment_allocation_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_allocation_fk_1",
      columns: [t.tenantId, t.projectId],
      foreignColumns: [vhProject.tenantId, vhProject.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_allocation_fk_2",
      columns: [t.tenantId, t.projectId, t.invoiceId, t.paymentAttemptId],
      foreignColumns: [
        vhPaymentAttempt.tenantId,
        vhPaymentAttempt.projectId,
        vhPaymentAttempt.invoiceId,
        vhPaymentAttempt.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_payment_allocation_fk_3",
      columns: [t.tenantId, t.projectId, t.invoiceId],
      foreignColumns: [vhInvoice.tenantId, vhInvoice.projectId, vhInvoice.id],
    }).onDelete("restrict"),
    index("vh_payment_allocation_ix_0").on(
      t.tenantId,
      t.projectId,
      t.invoiceId,
      t.paymentAttemptId,
    ),
    index("vh_payment_allocation_ix_1").on(
      t.tenantId,
      t.projectId,
      t.invoiceId,
    ),
    index("vh_payment_allocation_ix_2").on(t.tenantId, t.projectId),
    check("vh_payment_allocation_ck_0", sql`amount_minor > 0`),
  ],
).enableRLS();

export const vhLoyaltyAccount = pgTable(
  "vh_loyalty_account",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    userId: text("user_id").notNull(),
    provider: text("provider").notNull(),
    externalAccountRef: text("external_account_ref"),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "CLOSED"],
    }).notNull(),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("vh_loyalty_account_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_loyalty_account_uq_0").on(t.tenantId, t.userId, t.provider),
    unique("vh_loyalty_account_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_loyalty_account_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_loyalty_account_fk_1",
      columns: [t.userId],
      foreignColumns: [users.id],
    }).onDelete("restrict"),
    index("vh_loyalty_account_ix_0").on(t.userId),
    allowedValues("vh_loyalty_account_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "CLOSED",
    ]),
    check("vh_loyalty_account_ck_0", sql`version > 0`),
  ],
).enableRLS();

export const vhLoyaltyEntry = pgTable(
  "vh_loyalty_entry",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    accountId: uuid("account_id").notNull(),
    pointsDelta: bigint("points_delta", { mode: "bigint" }).notNull(),
    reason: text("reason").notNull(),
    providerEventId: text("provider_event_id").notNull(),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("vh_loyalty_entry_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("vh_loyalty_entry_uq_0").on(t.tenantId, t.providerEventId),
    unique("vh_loyalty_entry_uq_1").on(t.tenantId, t.id),
    foreignKey({
      name: "vh_loyalty_entry_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "vh_loyalty_entry_fk_1",
      columns: [t.tenantId, t.accountId],
      foreignColumns: [vhLoyaltyAccount.tenantId, vhLoyaltyAccount.id],
    }).onDelete("restrict"),
    index("vh_loyalty_entry_ix_0").on(t.tenantId, t.accountId),
    check("vh_loyalty_entry_ck_0", sql`points_delta <> 0`),
  ],
).enableRLS();
