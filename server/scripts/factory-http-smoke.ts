import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { eq } from "drizzle-orm";
import {
  createFactoryClient,
  hashAgentSpec,
  type FactoryArtifactResponse,
  type AgentSpec,
} from "../../agent-factory/src/index.js";
import {
  assessFactoryReadiness,
  readFactoryCatalogue,
  readStoredArtifact,
} from "../src/agents/factory.js";
import { createAgentProfileStore } from "../src/agents/profile-store.js";
import { createAuditStore } from "../src/audit.js";
import { loadConfig } from "../src/config.js";
import { createCredentialStore } from "../src/credentials.js";
import { createDatabase } from "../src/db/client.js";
import { auditEvents, pluginGrants } from "../src/db/schema/index.js";
import { createPluginStore } from "../src/plugins/store.js";

// Paid, opt-in verification against running production HTTP services. No grant mutations.
const request = {
  name: "Web Researcher",
  role: "Internet Research Agent",
  description:
    "Tìm kiếm thông tin trên Internet và tổng hợp câu trả lời có dẫn nguồn.",
};
const config = loadConfig();
const factoryUrl = process.env.FACTORY_SERVICE_URL;
const token = process.env.FACTORY_SERVICE_TOKEN;
assert(factoryUrl && token, "Configure Factory service URL/token.");
assert(
  config.singleUser,
  "This local smoke requires the existing single-user deployment configuration.",
);
const backendUrl = `http://127.0.0.1:${config.port}`;
const secrets = Object.entries(process.env)
  .filter(
    ([name, value]) =>
      /KEY|TOKEN|SECRET|PASSWORD/.test(name) && value && value.length >= 8,
  )
  .map(([, value]) => value ?? "");
function noSecrets(value: unknown) {
  const text = JSON.stringify(value);
  assert(
    !secrets.some((secret) => text.includes(secret)),
    "Secret found in verification output.",
  );
}
async function json(url: string, init?: RequestInit) {
  const response = await fetch(url, {
    ...init,
    redirect: "error",
    signal: AbortSignal.timeout(100_000),
  });
  const body: unknown = await response.json();
  noSecrets(body);
  return { status: response.status, body };
}
const database = createDatabase(config.databaseUrl, { max: 2 });
try {
  const probe = await fetch(`${backendUrl}/api/agent-factory/__smoke_probe__`, {
    signal: AbortSignal.timeout(5000),
    redirect: "error",
  });
  const probeBody = (await probe.json().catch(() => null)) as {
    code?: string;
  } | null;
  assert(
    probe.status === 404 && probeBody?.code === "NOT_FOUND",
    "BE Factory integration is detached or inaccessible. Run this historical smoke only after the BE team reconnects it.",
  );
  const factoryHealth = await json(`${factoryUrl}/health`);
  const backendHealth = await json(`${backendUrl}/health`);
  assert.equal(factoryHealth.status, 200);
  assert.equal(backendHealth.status, 200);
  const authStatuses: number[] = [];
  for (const authorization of [undefined, "Bearer incorrect-service-token"]) {
    const rejected = await json(`${factoryUrl}/v1/constructions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
      },
      body: JSON.stringify({ request, catalogue: { tools: [], skills: [] } }),
    });
    assert.equal(rejected.status, 401);
    assert.equal((rejected.body as { code: string }).code, "UNAUTHENTICATED");
    authStatuses.push(rejected.status);
  }
  const who = await json(`${backendUrl}/api/me`);
  assert.equal(who.status, 200);
  const actor = (who.body as { user: { id: string; role: "admin" | "staff" } })
    .user;
  assert(
    actor.id && actor.role,
    "Backend did not authenticate the configured actor.",
  );
  const store = createPluginStore({
    database,
    auditStore: createAuditStore(database),
    credentials: createCredentialStore(database),
    encryptionKey: config.keyEncryptionKey,
    policy: () => {
      throw new Error("This construction smoke must not execute tools.");
    },
  });
  const catalogue = await readFactoryCatalogue(store, {
    id: actor.id,
    isAdmin: actor.role === "admin",
  });
  assert(catalogue.ok, "Current scoped catalogue could not be read.");
  const grantsBefore = await database
    .select()
    .from(pluginGrants)
    .orderBy(pluginGrants.kind, pluginGrants.ref, pluginGrants.agentId);
  const constructed = await createFactoryClient({ url: factoryUrl, token })(
    request,
    catalogue.value,
  );
  assert(
    constructed.ok,
    `Real Factory construction failed: ${!constructed.ok ? constructed.issues.map(({ code }) => code).join(",") : ""}`,
  );
  noSecrets(constructed.value);
  assert(
    !constructed.value.intent.inferredRequirements.some((need) =>
      /prefer|primary|official|concise|at least/i.test(need),
    ),
    "Request-only intent imported an unrequested skill preference or method.",
  );
  const checkSpec = (spec: AgentSpec) => {
    assert.deepEqual(spec.identity, request);
    assert(
      spec.requirements.some(({ fulfillment }) => fulfillment === "tool"),
      "Internet research requires an external resource.",
    );
    if (catalogue.value.tools.some(({ ref }) => ref === "tavily/tavily_search"))
      assert(
        spec.resources.some(({ ref }) => ref === "tavily/tavily_search"),
        "Available research resource was not resolved.",
      );
    // The research method is generated with the agent, not a catalogue skill it must be granted.
    assert(
      spec.schemaVersion === 2 &&
        spec.generatedSkill.procedure.length > 0 &&
        spec.resources.every(({ kind }) => kind === "tool"),
      "Construction did not generate the agent's skill.",
    );
    assert(
      spec.resources.every((resource) =>
        catalogue.value.tools.some(
          (entry) =>
            entry.ref === resource.ref &&
            entry.fingerprint === resource.fingerprint,
        ),
      ),
      "A required resource is outside the current catalogue.",
    );
  };
  checkSpec(constructed.value.spec);
  const key = `real-http-smoke-${randomUUID()}`;
  const created = await json(`${backendUrl}/api/agent-factory/constructions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(request),
  });
  assert(
    [201, 202].includes(created.status),
    `Backend construction failed with HTTP ${created.status}.`,
  );
  const artifact = created.body as FactoryArtifactResponse<{ id: string }>;
  checkSpec(artifact.spec);
  assert.equal(artifact.verification.construction, "PASS");
  assert.equal(artifact.verification.semanticReview.verdict, "PASS");
  assert.equal(artifact.verification.specHash, hashAgentSpec(artifact.spec));
  const profiles = createAgentProfileStore(
    database,
    config.managedAgent?.endpoint,
  );
  const persisted = await profiles.readConstruction(actor, artifact.agent.id);
  assert(persisted, "Backend did not persist the construction.");
  noSecrets(persisted.configuration);
  const intact = readStoredArtifact(persisted);
  assert(
    intact.ok,
    "Persisted artifact failed Backend integrity verification.",
  );
  assert.deepEqual(intact.value.spec, artifact.spec);
  const readiness = await assessFactoryReadiness(
    store,
    { id: actor.id, isAdmin: actor.role === "admin" },
    artifact.agent.id,
    artifact.spec,
  );
  assert(readiness.ok, "Fresh owner readiness could not be read.");
  assert.deepEqual(readiness.value, artifact.readiness);
  assert.equal(created.status, readiness.value.state === "ready" ? 201 : 202);
  assert.equal(intact.value.state, readiness.value.state);
  assert.deepEqual(
    await database
      .select()
      .from(pluginGrants)
      .orderBy(pluginGrants.kind, pluginGrants.ref, pluginGrants.agentId),
    grantsBefore,
    "Construction mutated grants.",
  );
  const audits = await database
    .select()
    .from(auditEvents)
    .where(eq(auditEvents.targetId, artifact.agent.id));
  assert(audits.length > 0, "Backend creation audit is missing.");
  noSecrets(audits);
  const inspected = await json(
    `${backendUrl}/api/agent-factory/${artifact.agent.id}`,
  );
  assert.equal(inspected.status, 200);
  assert.deepEqual((inspected.body as typeof artifact).spec, artifact.spec);
  const evidence = {
    checkedAt: new Date().toISOString(),
    factoryHealth: factoryHealth.status,
    backendHealth: backendHealth.status,
    missingAndWrongBearer: authStatuses,
    factory: constructed.value,
    backend: {
      status: created.status,
      artifact,
      persistenceIntegrity: "PASS",
      inspection: inspected.status,
      grantsUnchanged: true,
      auditSecretsAbsent: true,
    },
  };
  noSecrets(evidence);
  const output = new URL(
    "../../.logs/factory-real-http-smoke.json",
    import.meta.url,
  );
  await mkdir(new URL(".", output), { recursive: true });
  await writeFile(output, `${JSON.stringify(evidence, null, 2)}\n`);
  console.log(
    JSON.stringify(
      {
        ...evidence,
        factory: {
          intent: constructed.value.intent,
          requiredResources: constructed.value.spec.resources.map(
            ({ kind, ref }) => ({ kind, ref }),
          ),
          verification: constructed.value.verification,
        },
        backend: {
          ...evidence.backend,
          artifact: {
            agentId: artifact.agent.id,
            readiness: artifact.readiness,
            verification: artifact.verification,
          },
        },
      },
      null,
      2,
    ),
  );
  console.log(`Evidence: ${output.pathname}`);
} catch (error) {
  // Assertions use fixed messages/codes; provider/database payloads and credentials are not printed.
  console.error(
    error instanceof assert.AssertionError
      ? error.message
      : "Factory HTTP smoke failed; inspect configuration and service health.",
  );
  process.exitCode = 1;
} finally {
  await database.$client.close();
}
