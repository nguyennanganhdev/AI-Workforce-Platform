/** Physical model for platform/deployments. See docs/erd/README.md. */
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
import { allowedValues, createdAt, mutableColumns } from "../columns";
import { platformAgentVersion } from "./agents";
import { platformDomainInstallation } from "./domains";
import { platformTenant } from "./identity";

export const platformAgentDeployment = pgTable(
  "platform_agent_deployment",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    domainInstallationId: uuid("domain_installation_id"),
    environment: text("environment").notNull(),
    scopeType: text("scope_type").notNull(),
    scopeRef: text("scope_ref").notNull(),
    status: text("status", {
      enum: ["ACTIVE", "SUSPENDED", "RETIRED"],
    }).notNull(),
    deployedAt: timestamp("deployed_at", { withTimezone: true }).notNull(),
    retiredAt: timestamp("retired_at", { withTimezone: true }),
    previousDeploymentId: uuid("previous_deployment_id"),
    createdAt: createdAt(),
    ...mutableColumns(),
  },
  (t) => [
    pgPolicy("platform_agent_deployment_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    unique("platform_agent_deployment_uq_0").on(t.tenantId, t.id),
    foreignKey({
      name: "platform_agent_deployment_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_deployment_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_deployment_fk_2",
      columns: [t.tenantId, t.domainInstallationId],
      foreignColumns: [
        platformDomainInstallation.tenantId,
        platformDomainInstallation.id,
      ],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_deployment_fk_3",
      columns: [t.tenantId, t.previousDeploymentId],
      foreignColumns: [t.tenantId, t.id],
    }).onDelete("restrict"),
    index("platform_agent_deployment_ix_0").on(t.tenantId, t.agentVersionId),
    index("platform_agent_deployment_ix_1").on(
      t.tenantId,
      t.domainInstallationId,
    ),
    index("platform_agent_deployment_ix_2").on(
      t.tenantId,
      t.previousDeploymentId,
    ),
    allowedValues("platform_agent_deployment_status_ck", t.status, [
      "ACTIVE",
      "SUSPENDED",
      "RETIRED",
    ]),
    check("platform_agent_deployment_ck_0", sql`version > 0`),
  ],
).enableRLS();
