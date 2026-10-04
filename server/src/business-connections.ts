/** Account/connector host for the business deployment. Agent turns run in Coordination. */
import { Hono } from "hono";
import { createBusinessAuth } from "./auth/business";
import { createRequireUser, createRoleRepository, type AppVariables } from "./auth/guards";
import { createDatabase } from "./db/client";
import { createAuditStore } from "./audit";
import { createCredentialStore } from "./credentials";
import { createPluginStore } from "./plugins/store";
import { createPluginRoutes } from "./plugins/routes";
import { createPolicyStore, DEFAULT_ACTION_POLICY } from "./computer/policy-store";
import { createAgentProfileStore } from "./agents/profile-store";
import { redirectUriFor } from "./plugins/oauth";

const required = (name: string) => {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
};
const tenantId = required("OPENBOT_BUSINESS_TENANT_ID");
const workspaceId = required("OPENBOT_BUSINESS_WORKSPACE_ID");
if (![tenantId, workspaceId].every((id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)))
  throw new Error("Business tenant and workspace must be UUIDs");
const database = createDatabase(required("DATABASE_URL"), { tenantId, workspaceId });
const [databaseRole] = await database.$client`select rolsuper,rolbypassrls from pg_roles where rolname=current_user`;
if (databaseRole.rolsuper || databaseRole.rolbypassrls) throw new Error("Account service requires a restricted database role");
const origins = required("TRUSTED_ORIGINS").split(",").map((value) => new URL(value.trim()).origin);
const auth = createBusinessAuth(required("OPENBOT_BUSINESS_AUTH_URL"), origins);
const roles = createRoleRepository(database);
const requireUser = createRequireUser(auth, roles);
const encryptionKey = required("KEY_ENCRYPTION_KEY");
const policy = createPolicyStore(DEFAULT_ACTION_POLICY, database);
await policy.load();
const publicUrl = process.env.OPENBOT_PUBLIC_URL;
const profiles = createAgentProfileStore(database, undefined);
const plugins = createPluginStore({ database, credentials: createCredentialStore(database),
  auditStore: createAuditStore(database), encryptionKey, policy: () => policy.get(),
  redirectUri: publicUrl ? redirectUriFor(publicUrl) : undefined });
const app = new Hono<{ Variables: AppVariables }>();
app.onError(() => Response.json({ error: "Account service is unavailable" }, { status: 503 }));
app.use("/api/*", async (context, next) => {
  if (!["GET", "HEAD", "OPTIONS"].includes(context.req.method) &&
    !origins.includes(context.req.header("origin") ?? ""))
    return context.json({ error: "Origin refused" }, 403);
  context.header("cache-control", "no-store");
  await next();
});
app.get("/health", async (context) => {
  await database.$client`select 1`;
  return context.json({ status: "ready", service: "business-connections" });
});
app.all("/api/auth/*", (context) => auth.handler(context.req.raw));
app.get("/api/capabilities", (context) => context.json({ authProviders: [], ssoConfigured: false,
  businessLogin: "/operations/login", generativeUi: false, runtime: "business-coordination" }));
app.get("/api/me", requireUser, (context) => context.json({ user: { ...context.var.actor, onboarding: null } }));
app.route("/api/plugins", createPluginRoutes(plugins, requireUser,
  async (actor, botId) => (await profiles.get(actor, botId)) !== null,
  { encryptionKey, personHasAccess: async (id) => (await roles.rolesForUser(id)).length > 0,
    botsMayCallBack: false, publicUrl, appUrl: publicUrl }));
Bun.serve({ hostname: "0.0.0.0", port: Number(process.env.PORT ?? 3001), fetch: app.fetch });
