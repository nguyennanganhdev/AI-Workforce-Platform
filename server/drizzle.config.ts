import { defineConfig } from "drizzle-kit";

const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error(
    "DATABASE_URL must be configured before running a database migration command",
  );
}

export default defineConfig({
  dialect: "postgresql",
  /**
   * Every schema file, listed explicitly.
   *
   * Files missing from this list are invisible to `generate`; existing tables still work, but the
   * next generated migration treats them as absent. Add the file here in the same change that adds
   * the schema file.
   */
  schema: [
    "./src/db/schema/core.ts",
    "./src/db/schema/computer.ts",
    "./src/db/schema/coworker.ts",
    "./src/db/schema/components.ts",
    "./src/db/schema/plugins.ts",
    "./src/db/schema/work.ts",
    "./src/db/schema/voice.ts",
    "./src/db/schema/domains/vinhomes/attachments.ts",
    "./src/db/schema/domains/vinhomes/billing.ts",
    "./src/db/schema/domains/vinhomes/booking.ts",
    "./src/db/schema/domains/vinhomes/communication.ts",
    "./src/db/schema/domains/vinhomes/content.ts",
    "./src/db/schema/domains/vinhomes/delivery.ts",
    "./src/db/schema/domains/vinhomes/evidence.ts",
    "./src/db/schema/domains/vinhomes/files.ts",
    "./src/db/schema/domains/vinhomes/intake.ts",
    "./src/db/schema/domains/vinhomes/operations.ts",
    "./src/db/schema/domains/vinhomes/property.ts",
    "./src/db/schema/domains/vinhomes/services.ts",
    "./src/db/schema/platform/agents.ts",
    "./src/db/schema/platform/audit.ts",
    "./src/db/schema/platform/bindings.ts",
    "./src/db/schema/platform/capabilities.ts",
    "./src/db/schema/platform/deployments.ts",
    "./src/db/schema/platform/domains.ts",
    "./src/db/schema/platform/evaluation.ts",
    "./src/db/schema/platform/identity.ts",
    "./src/db/schema/platform/knowledge.ts",
    "./src/db/schema/platform/memory.ts",
    "./src/db/schema/platform/policies.ts",
    "./src/db/schema/platform/runtime.ts",
    "./src/db/schema/domains/vinhomes/assets.ts",
    "./src/db/schema/domains/vinhomes/dispatch.ts",
    "./src/db/schema/domains/vinhomes/provider-events.ts",
    "./src/db/schema/domains/vinhomes/resident-updates.ts",
    "./src/db/schema/domains/vinhomes/sla.ts",
    "./src/db/schema/domains/vinhomes/workforce.ts",
    "./src/db/schema/platform/collaboration.ts",
    "./src/db/schema/platform/conversations.ts",
    "./src/db/schema/platform/event-delivery.ts",
  ],
  out: "./drizzle",
  dbCredentials: {
    url: databaseUrl,
  },
});
