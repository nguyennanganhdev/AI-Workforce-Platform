/** Physical model for platform/bindings. See docs/erd/README.md. */
import { sql } from "drizzle-orm";
import {
  foreignKey,
  index,
  pgPolicy,
  pgTable,
  primaryKey,
  text,
  uuid,
} from "drizzle-orm/pg-core";
import { allowedValues, createdAt, jsonb } from "../columns";
import { platformAgentVersion } from "./agents";
import {
  platformCapability,
  platformModelProfile,
  platformSkillVersion,
  platformToolVersion,
} from "./capabilities";
import { platformTenant } from "./identity";
import { platformKnowledgeBase } from "./knowledge";
import { platformPolicyVersion } from "./policies";

export const platformAgentCapabilityBinding = pgTable(
  "platform_agent_capability_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    capabilityId: uuid("capability_id").notNull(),
    scopeJson: jsonb("scope_json").notNull(),
    constraintsJson: jsonb("constraints_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_capability_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.agentVersionId, t.capabilityId] }),
    foreignKey({
      name: "platform_agent_capability_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_capability_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_capability_binding_fk_2",
      columns: [t.tenantId, t.capabilityId],
      foreignColumns: [platformCapability.tenantId, platformCapability.id],
    }).onDelete("restrict"),
    index("platform_agent_capability_binding_ix_0").on(
      t.tenantId,
      t.agentVersionId,
    ),
    index("platform_agent_capability_binding_ix_1").on(
      t.tenantId,
      t.capabilityId,
    ),
  ],
).enableRLS();

export const platformAgentModelBinding = pgTable(
  "platform_agent_model_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    modelProfileId: uuid("model_profile_id").notNull(),
    constraintsJson: jsonb("constraints_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_model_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.agentVersionId] }),
    foreignKey({
      name: "platform_agent_model_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_model_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_model_binding_fk_2",
      columns: [t.tenantId, t.modelProfileId],
      foreignColumns: [platformModelProfile.tenantId, platformModelProfile.id],
    }).onDelete("restrict"),
    index("platform_agent_model_binding_ix_0").on(t.tenantId, t.modelProfileId),
  ],
).enableRLS();

export const platformAgentToolBinding = pgTable(
  "platform_agent_tool_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    toolVersionId: uuid("tool_version_id").notNull(),
    allowedScope: jsonb("allowed_scope").notNull(),
    constraintsJson: jsonb("constraints_json").notNull(),
    approvalPolicyRef: text("approval_policy_ref"),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_tool_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.agentVersionId, t.toolVersionId] }),
    foreignKey({
      name: "platform_agent_tool_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_tool_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_tool_binding_fk_2",
      columns: [t.tenantId, t.toolVersionId],
      foreignColumns: [platformToolVersion.tenantId, platformToolVersion.id],
    }).onDelete("restrict"),
    index("platform_agent_tool_binding_ix_0").on(t.tenantId, t.agentVersionId),
    index("platform_agent_tool_binding_ix_1").on(t.tenantId, t.toolVersionId),
  ],
).enableRLS();

export const platformAgentSkillBinding = pgTable(
  "platform_agent_skill_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    skillVersionId: uuid("skill_version_id").notNull(),
    configJson: jsonb("config_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_skill_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.agentVersionId, t.skillVersionId] }),
    foreignKey({
      name: "platform_agent_skill_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_skill_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_skill_binding_fk_2",
      columns: [t.tenantId, t.skillVersionId],
      foreignColumns: [platformSkillVersion.tenantId, platformSkillVersion.id],
    }).onDelete("restrict"),
    index("platform_agent_skill_binding_ix_0").on(t.tenantId, t.agentVersionId),
    index("platform_agent_skill_binding_ix_1").on(t.tenantId, t.skillVersionId),
  ],
).enableRLS();

export const platformAgentKnowledgeBinding = pgTable(
  "platform_agent_knowledge_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    knowledgeBaseId: uuid("knowledge_base_id").notNull(),
    scopeJson: jsonb("scope_json").notNull(),
    retrievalPolicyJson: jsonb("retrieval_policy_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_knowledge_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({ columns: [t.tenantId, t.agentVersionId, t.knowledgeBaseId] }),
    foreignKey({
      name: "platform_agent_knowledge_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_knowledge_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_knowledge_binding_fk_2",
      columns: [t.tenantId, t.knowledgeBaseId],
      foreignColumns: [
        platformKnowledgeBase.tenantId,
        platformKnowledgeBase.id,
      ],
    }).onDelete("restrict"),
    index("platform_agent_knowledge_binding_ix_0").on(
      t.tenantId,
      t.agentVersionId,
    ),
    index("platform_agent_knowledge_binding_ix_1").on(
      t.tenantId,
      t.knowledgeBaseId,
    ),
  ],
).enableRLS();

export const platformAgentPolicyBinding = pgTable(
  "platform_agent_policy_binding",
  {
    tenantId: uuid("tenant_id").notNull(),
    agentVersionId: uuid("agent_version_id").notNull(),
    policyVersionId: uuid("policy_version_id").notNull(),
    phase: text("phase", {
      enum: ["PRE_RUN", "PRE_TOOL", "POST_TOOL", "OUTPUT"],
    }).notNull(),
    configJson: jsonb("config_json").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    pgPolicy("platform_agent_policy_binding_tenant_policy", {
      for: "all",
      using: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
      withCheck: sql`${t.tenantId} = nullif(current_setting('app.tenant_id', true), '')::uuid`,
    }),
    primaryKey({
      columns: [t.tenantId, t.agentVersionId, t.policyVersionId, t.phase],
    }),
    foreignKey({
      name: "platform_agent_policy_binding_fk_0",
      columns: [t.tenantId],
      foreignColumns: [platformTenant.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_policy_binding_fk_1",
      columns: [t.tenantId, t.agentVersionId],
      foreignColumns: [platformAgentVersion.tenantId, platformAgentVersion.id],
    }).onDelete("restrict"),
    foreignKey({
      name: "platform_agent_policy_binding_fk_2",
      columns: [t.tenantId, t.policyVersionId],
      foreignColumns: [
        platformPolicyVersion.tenantId,
        platformPolicyVersion.id,
      ],
    }).onDelete("restrict"),
    index("platform_agent_policy_binding_ix_0").on(
      t.tenantId,
      t.agentVersionId,
    ),
    index("platform_agent_policy_binding_ix_1").on(
      t.tenantId,
      t.policyVersionId,
    ),
    allowedValues("platform_agent_policy_binding_phase_ck", t.phase, [
      "PRE_RUN",
      "PRE_TOOL",
      "POST_TOOL",
      "OUTPUT",
    ]),
  ],
).enableRLS();
