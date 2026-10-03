import { afterAll, beforeAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { LLMock } from "@copilotkit/aimock";
import { MCPMock } from "@copilotkit/aimock/mcp";
import { and, eq, inArray, sql } from "drizzle-orm";
import { Hono } from "hono";
import type {
  AgentDraft,
  FactoryResult,
} from "../../agent-factory/src/contracts.js";
import {
  assessFactoryReadiness,
  createAgentFactoryService,
  factoryConstructionId,
  readFactoryCatalogue,
} from "../src/agents/factory.js";
import { createAgentFactoryRoutes } from "../src/agents/factory-routes.js";
import { createAgentProfileStore } from "../src/agents/profile-store.js";
import type { AppVariables } from "../src/auth/guards.js";
import { createAuditStore } from "../src/audit.js";
import { createCredentialStore } from "../src/credentials.js";
import { createDatabase } from "../src/db/client.js";
import {
  agentProfiles,
  agents,
  auditEvents,
  composioConnections,
  credentials,
  mcpServers,
  mcpTools,
  mcpUserCredentials,
  pluginGrants,
  skills,
  skillTools,
  users,
} from "../src/db/schema/index.js";
import {
  FACTORY_LIMITS,
  fingerprintFactoryResource,
  hashAgentSpec,
  parseAgentSpec,
  renderCorePrompt,
  resolveDraftResources,
} from "../../agent-factory/src/spec.js";
import {
  createModelCompleter,
  type ModelCallObservation,
} from "../src/routing/model.js";
import type { FactoryObservation } from "../../agent-factory/src/service.js";
import type { ComposioBroker } from "../src/plugins/broker.js";
import { createPluginStore } from "../src/plugins/store.js";
import {
  compileRecorded,
  withRecordedIntent,
} from "../../agent-factory/tests/fixtures/factory-intent.js";
import { TEST_POOL, testDatabaseUrl } from "./support/database.js";

const database = createDatabase(testDatabaseUrl(), TEST_POOL);
const suite = randomUUID().slice(0, 8);
const alice = `factory_alice_${suite}`;
const bob = `factory_bob_${suite}`;
const agentId = `factory_agent_${suite}`;
const serverId = `factory_mock_${suite}`;
const ref = `${serverId}/read_notes`;
const aliceSkill = `factory_alice_skill_${suite}`;
const bobSkill = `factory_bob_skill_${suite}`;
const sharedSkill = `factory_shared_skill_${suite}`;
const brokerId = `factory_broker_${suite}`;
const toolkit = `factory_app_${suite}`;
const secretId = randomUUID();
const tokenId = randomUUID();
const mock = new MCPMock();
let mockUrl = "";
let businessCalls = 0;
let secretCalls = 0;
let brokerCalls = 0;
let policyCalls = 0;
const broker = new Proxy({} as ComposioBroker, {
  get() {
    brokerCalls++;
    throw new Error("Factory must not contact the broker.");
  },
});
const store = createPluginStore({
  database,
  auditStore: createAuditStore(database),
  encryptionKey: "x".repeat(44),
  broker,
  credentials: new Proxy(createCredentialStore(database), {
    get() {
      return async () => {
        secretCalls++;
        throw new Error("Factory must not access the credential vault.");
      };
    },
  }),
  policy: () => {
    policyCalls++;
    return { mode: "enforce", deny: ["true"], allow: [] };
  },
  exchangeRefreshToken: async () => {
    secretCalls++;
    throw new Error("Factory must not refresh tokens.");
  },
  registerClient: async () => {
    secretCalls++;
    throw new Error("Factory must not register OAuth clients.");
  },
});
const actor = { id: alice, isAdmin: false };
const request = {
  name: "Notes",
  role: "Note reader",
  description: "Read supplied notes with the listed resources.",
};
const source = {
  kind: "request",
  field: "description",
  quote: "supplied notes",
} as const;

function accepted<T>(result: FactoryResult<T>): T {
  expect(result.ok).toBe(true);
  if (!result.ok) throw new Error(JSON.stringify(result.issues));
  return result.value;
}
function codes<T>(result: FactoryResult<T>): string[] {
  expect(result.ok).toBe(false);
  return result.ok ? [] : result.issues.map(({ code }) => code);
}
function draftFor(tools: string[] = [ref]): AgentDraft {
  return {
    goal: "Read supplied notes.",
    responsibilities: [{ statement: "Read supplied notes.", source }],
    constraints: [],
    generatedSkill: {
      name: "Note reading",
      objective: "Read supplied notes and return a summary.",
      procedure: ["Read supplied notes.", "Return a summary."],
      toolUsageGuidance: tools.map((toolRef) => ({
        toolRef,
        whenToUse: "When the notes must be read.",
        purpose: "Read the notes.",
        guidance: "Call it with the notes query and summarize what it returns.",
      })),
      constraints: [],
      completionCriteria: ["Reflect supplied notes."],
    },
    requirements: tools.map((ref) => ({
      need: "Read notes.",
      fulfillment: "tool" as const,
      source,
      proposedRefs: [ref],
    })),
    toolArguments: tools
      .filter((tool) => tool === ref)
      .map((ref) => ({
        ref,
        argument: "query",
        sourceKind: "user_input",
        sourceRef: "notes",
        missingBehavior: "Ask for notes.",
      })),
    inputFacts: [
      { name: "notes", required: true, missingBehavior: "Ask for notes." },
    ],
    outputExpectations: ["A summary."],
    unresolvedQuestions: [],
    unsupportedRequirements: [],
  };
}
async function artifact(tools: string[] = [ref]) {
  const catalogue = accepted(await readFactoryCatalogue(store, actor));
  const draft = draftFor(tools);
  const resources = accepted(resolveDraftResources(request, draft, catalogue));
  return accepted(
    compileRecorded(request, draft, {
      resources,
      catalogueRefs: catalogue.tools.map(({ ref }) => ref),
    }),
  );
}
/**
 * The resources of an agent stored by compiler version 1: the same tools plus a selected catalogue
 * skill. Construction no longer produces these, and BE readiness still has to serve them.
 */
async function legacyArtifact(skillRef: string) {
  const { spec } = await artifact();
  const projection = accepted(await store.factoryCatalogue(actor));
  const skill = projection.skills.find(({ ref }) => ref === skillRef);
  if (!skill) throw new Error("Expected the skill in BE's projection.");
  return {
    spec: {
      ...spec,
      resources: [
        ...spec.resources,
        {
          kind: "skill" as const,
          ref: skillRef,
          requirementIds: ["r1"],
          fingerprint: fingerprintFactoryResource(skill),
          argumentSources: [],
        },
      ],
    },
  };
}

beforeAll(async () => {
  mock
    .addTool({
      name: "read_notes",
      description: "Read supplied notes.",
      inputSchema: {
        type: "object",
        properties: { query: { type: "string" } },
        required: ["query"],
      },
    })
    .onToolCall("read_notes", () => {
      businessCalls++;
      return "Never called during construction.";
    });
  mockUrl = await mock.start();
  await database.insert(users).values([
    { id: alice, email: `${alice}@example.test` },
    { id: bob, email: `${bob}@example.test` },
  ]);
  await database.insert(agents).values({
    id: agentId,
    name: "Fixture",
    type: "built_in",
    configuration: { systemPrompt: "Fixture." },
  });
  await database.insert(credentials).values([
    {
      id: secretId,
      kind: "mcp_oauth_client",
      provider: "notion",
      encryptedValue: "PRIVATE_ENCRYPTED_CLIENT",
      keyId: `factory_client_${suite}`,
      metadata: { private: "PRIVATE_METADATA" },
    },
    {
      id: tokenId,
      kind: "mcp_user_token",
      provider: "notion",
      encryptedValue: "PRIVATE_ENCRYPTED_TOKEN",
      keyId: bob,
      metadata: { private: "PRIVATE_METADATA" },
    },
  ]);
  await database.insert(mcpServers).values([
    {
      id: serverId,
      title: "Notes fixture",
      vendor: "Fixture",
      url: mockUrl,
      provenance: "custom",
      addedBy: bob,
      lastError: "PRIVATE_ERROR",
    },
    {
      id: "notion",
      title: "Notion",
      vendor: "Notion",
      url: "https://mcp.notion.com/mcp",
      provenance: "first-party",
      credentialId: secretId,
    },
    {
      id: brokerId,
      title: "Broker fixture",
      vendor: "Fixture",
      url: `composio://${toolkit}`,
      provenance: "composio",
      authScheme: "NO_AUTH",
    },
  ]);
  // Populate the existing MCP cache through its actual protocol/transport; generation reads only that cache.
  expect(await store.refreshTools(serverId, alice)).toEqual({ tools: 1 });
  await database.insert(mcpTools).values([
    {
      serverId: "notion",
      name: "search",
      description: "Search notes.",
      inputSchema: { type: "object", properties: {} },
      effect: "read",
    },
    {
      serverId: brokerId,
      name: "read",
      description: "Read.",
      inputSchema: { type: "object", properties: {} },
      effect: "read",
    },
  ]);
  for (const [slug, ownerUserId] of [
    [aliceSkill, alice],
    [bobSkill, bob],
    [sharedSkill, null],
  ] as const) {
    await database.insert(skills).values({
      id: slug,
      slug,
      ownerUserId,
      title: slug,
      summary: "Notes instruction",
      instructions: "Summarize supplied notes.",
      origin: "PRIVATE_ORIGIN",
      installedBy: "PRIVATE_INSTALLER",
    });
  }
  await database
    .insert(skillTools)
    .values({ skillId: aliceSkill, ref, declaredBy: "PRIVATE_DECLARER" });
  await database.insert(mcpUserCredentials).values({
    serverId: "notion",
    userId: bob,
    credentialId: tokenId,
    scope: "read",
  });
});

afterAll(async () => {
  await database
    .delete(skills)
    .where(inArray(skills.slug, [aliceSkill, bobSkill, sharedSkill]));
  await database
    .delete(mcpServers)
    .where(
      inArray(mcpServers.id, [
        serverId,
        "notion",
        brokerId,
        `factory_overflow_${suite}`,
      ]),
    );
  await database
    .delete(credentials)
    .where(inArray(credentials.id, [secretId, tokenId]));
  await database
    .delete(composioConnections)
    .where(eq(composioConnections.toolkit, toolkit));
  await database.delete(agents).where(eq(agents.id, agentId));
  await database.delete(users).where(inArray(users.id, [alice, bob]));
  await mock.stop();
});

test("I01 actor-visible projection excludes private skills and storage metadata", async () => {
  // BE's projection still lists visible skills, for readiness of agents stored with one.
  const catalogue = accepted(await store.factoryCatalogue(actor));
  expect(catalogue.skills.map(({ ref }) => ref)).toContain(aliceSkill);
  expect(catalogue.skills.map(({ ref }) => ref)).toContain(sharedSkill);
  expect(catalogue.skills.map(({ ref }) => ref)).not.toContain(bobSkill);
  expect(
    accepted(
      await store.factoryCatalogue({ id: alice, isAdmin: true }),
    ).skills.map(({ ref }) => ref),
  ).toContain(bobSkill);
  // What construction resolves against is tools only: no skill reaches it, visible or not.
  const prepared = accepted(await readFactoryCatalogue(store, actor));
  expect(Object.keys(prepared).sort()).toEqual(["defaultToolRefs", "tools"]);
  expect(JSON.stringify(prepared)).not.toContain(aliceSkill);
  const facts = accepted(
    await store.factoryResourceFacts(alice, agentId, [
      { kind: "skill", ref: bobSkill },
    ]),
  );
  expect(facts[0]!.resource).toBeNull();
  const serialized = JSON.stringify({ catalogue, facts });
  for (const privateValue of [
    mockUrl,
    "https://mcp.notion.com",
    "composio://",
    "PRIVATE_",
    "grantedTo",
    "ownerUserId",
    "installedBy",
    "credentialId",
    "addedBy",
    "lastError",
  ])
    expect(serialized).not.toContain(privateValue);
  expect(
    codes(await store.factoryCatalogue({ id: "", isAdmin: true })),
  ).toContain("UNAUTHENTICATED");
});

test("I02 MCPMock-discovered refs resolve exactly with stored schema/effect evidence and no side effects", async () => {
  const grantsBefore = await database
    .select()
    .from(pluginGrants)
    .where(eq(pluginGrants.agentId, agentId));
  const auditBefore = await database
    .select({ count: sql<number>`count(*)::int` })
    .from(auditEvents);
  const catalogue = accepted(await readFactoryCatalogue(store, actor));
  const tool = catalogue.tools.find((tool) => tool.ref === ref)!;
  expect(tool.inputSchema.required).toEqual(["query"]);
  expect(tool.outputSchema).toBeNull();
  const spec = (await artifact()).spec;
  expect(spec.resources[0]!.ref).toBe(ref);
  expect(spec.resources[0]!.fingerprint).toBe(tool.fingerprint);
  const narrowReader = {
    factoryCatalogue: store.factoryCatalogue,
    factoryResourceFacts: store.factoryResourceFacts,
  };
  const readiness = accepted(
    await assessFactoryReadiness(narrowReader, actor, agentId, spec),
  );
  expect(readiness.state).toBe("pending_resources");
  expect(readiness.blockers.map(({ code }) => code)).toEqual([
    "GRANT_REQUIRED",
  ]);
  expect(
    await database
      .select()
      .from(pluginGrants)
      .where(eq(pluginGrants.agentId, agentId)),
  ).toEqual(grantsBefore);
  expect(
    await database
      .select({ count: sql<number>`count(*)::int` })
      .from(auditEvents),
  ).toEqual(auditBefore);
  expect([businessCalls, secretCalls, brokerCalls, policyCalls]).toEqual([
    0, 0, 0, 0,
  ]);
});

test("I03 unknown and removed resources are controlled failures even when their grants survive", async () => {
  const catalogue = accepted(await readFactoryCatalogue(store, actor));
  expect(
    codes(
      resolveDraftResources(
        request,
        draftFor([`${serverId}/invented`]),
        catalogue,
      ),
    ),
  ).toContain("UNKNOWN_RESOURCE");
  const { spec } = await artifact();
  await database.insert(pluginGrants).values({ kind: "mcp", ref, agentId });
  const [row] = await database
    .select()
    .from(mcpTools)
    .where(
      and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
    );
  await database
    .delete(mcpTools)
    .where(
      and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
    );
  try {
    expect(
      accepted(
        await assessFactoryReadiness(store, actor, agentId, spec),
      ).blockers.map(({ code }) => code),
    ).toContain("RESOURCE_MISSING");
    const facts = accepted(
      await store.factoryResourceFacts(alice, agentId, [{ kind: "tool", ref }]),
    );
    expect(facts[0]!.granted).toBe(true);
    expect(facts[0]!.resource).toBeNull();
  } finally {
    await database.insert(mcpTools).values(row!);
    await database
      .delete(pluginGrants)
      .where(
        and(
          eq(pluginGrants.kind, "mcp"),
          eq(pluginGrants.ref, ref),
          eq(pluginGrants.agentId, agentId),
        ),
      );
  }
});

test("I04 exact grants, configuration and the creator connection are independent facts", async () => {
  const { spec } = await artifact(["notion/search"]);
  let readiness = accepted(
    await assessFactoryReadiness(store, actor, agentId, spec),
  );
  expect(readiness.blockers.map(({ code }) => code).sort()).toEqual([
    "CONNECTION_REQUIRED",
    "GRANT_REQUIRED",
  ]);
  await database
    .insert(pluginGrants)
    .values({ kind: "mcp", ref: "notion/search", agentId });
  readiness = accepted(
    await assessFactoryReadiness(store, actor, agentId, spec),
  );
  expect(readiness.blockers.map(({ code }) => code)).toEqual([
    "CONNECTION_REQUIRED",
  ]);
  // Bob's connection must never make Alice ready, even when an administrator inspects her agent.
  expect(
    accepted(
      await assessFactoryReadiness(
        store,
        { id: alice, isAdmin: true },
        agentId,
        spec,
      ),
    ).state,
  ).toBe("pending_resources");
  await database.insert(mcpUserCredentials).values({
    serverId: "notion",
    userId: alice,
    credentialId: tokenId,
    scope: "read",
  });
  expect(
    accepted(await assessFactoryReadiness(store, actor, agentId, spec)).state,
  ).toBe("ready");
  await database
    .update(credentials)
    .set({ revokedAt: new Date() })
    .where(eq(credentials.id, secretId));
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.map(({ code }) => code),
  ).toEqual(["CONFIGURATION_REQUIRED"]);
  await database
    .update(credentials)
    .set({ revokedAt: null })
    .where(eq(credentials.id, secretId));
  await database
    .update(credentials)
    .set({ revokedAt: new Date() })
    .where(eq(credentials.id, tokenId));
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.map(({ code }) => code),
  ).toEqual(["CONNECTION_REQUIRED"]);
  await database
    .update(credentials)
    .set({ revokedAt: null })
    .where(eq(credentials.id, tokenId));
  expect([businessCalls, secretCalls, brokerCalls, policyCalls]).toEqual([
    0, 0, 0, 0,
  ]);
});

test("I05 a granted skill and its declarations do not authorize its required tool", async () => {
  const catalogue = accepted(await readFactoryCatalogue(store, actor));
  // A catalogue skill is not something construction can bind.
  expect(
    codes(resolveDraftResources(request, draftFor([aliceSkill]), catalogue)),
  ).toContain("UNKNOWN_RESOURCE");
  const { spec } = await legacyArtifact(aliceSkill);
  await database
    .insert(pluginGrants)
    .values({ kind: "skill", ref: aliceSkill, agentId });
  const readiness = accepted(
    await assessFactoryReadiness(store, actor, agentId, spec),
  );
  expect(
    readiness.blockers.map(({ code, evidenceRefs }) => [code, evidenceRefs]),
  ).toEqual([["GRANT_REQUIRED", [ref]]]);
  expect((await store.decide("mcp", ref, agentId)).allowed).toBe(false);
});

test("I06 metadata, schema, effect, destructive facts and skill content/declarations change fingerprints", async () => {
  const { spec } = await legacyArtifact(aliceSkill);
  const original = accepted(await readFactoryCatalogue(store, actor));
  const initialTool = original.tools.find((tool) => tool.ref === ref)!;
  const [row] = await database
    .select()
    .from(mcpTools)
    .where(
      and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
    );
  for (const patch of [
    { description: "Changed operation." },
    { effect: initialTool.effect === "read" ? "write" : "read" },
    { destructive: !initialTool.destructive },
    {
      inputSchema: {
        type: "object",
        properties: { query: { type: "number" } },
        required: ["query"],
      },
    },
  ]) {
    await database
      .update(mcpTools)
      .set(patch)
      .where(
        and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
      );
    expect(
      accepted(
        await assessFactoryReadiness(store, actor, agentId, spec),
      ).blockers.map(({ code }) => code),
    ).toContain("RESOURCE_CHANGED");
    await database
      .update(mcpTools)
      .set(row!)
      .where(
        and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
      );
  }
  await database
    .update(skills)
    .set({ instructions: "New instructions." })
    .where(eq(skills.slug, aliceSkill));
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.some(
      ({ code, evidenceRefs }) =>
        code === "RESOURCE_CHANGED" && evidenceRefs.includes(aliceSkill),
    ),
  ).toBe(true);
  await database
    .update(skills)
    .set({ instructions: "Summarize supplied notes." })
    .where(eq(skills.slug, aliceSkill));
  await database.delete(skillTools).where(eq(skillTools.skillId, aliceSkill));
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.some(
      ({ code, evidenceRefs }) =>
        code === "RESOURCE_CHANGED" && evidenceRefs.includes(aliceSkill),
    ),
  ).toBe(true);
});

test("broker facts reuse the recorded scheme and the owner account without vendor probes", async () => {
  const toolRef = `${brokerId}/read`;
  const { spec } = await artifact([toolRef]);
  await database
    .insert(pluginGrants)
    .values({ kind: "mcp", ref: toolRef, agentId });
  expect(
    accepted(await assessFactoryReadiness(store, actor, agentId, spec)).state,
  ).toBe("ready");
  await database
    .update(mcpServers)
    .set({ authScheme: "API_KEY" })
    .where(eq(mcpServers.id, brokerId));
  await database.insert(composioConnections).values({ toolkit, userId: bob });
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.map(({ code }) => code),
  ).toEqual(["CONNECTION_REQUIRED"]);
  await database.insert(composioConnections).values({ toolkit, userId: alice });
  expect(
    accepted(await assessFactoryReadiness(store, actor, agentId, spec)).state,
  ).toBe("ready");
  await database
    .update(mcpServers)
    .set({ authScheme: null })
    .where(eq(mcpServers.id, brokerId));
  expect(
    accepted(
      await assessFactoryReadiness(store, actor, agentId, spec),
    ).blockers.map(({ code }) => code),
  ).toEqual(["CONFIGURATION_REQUIRED"]);
  expect([businessCalls, secretCalls, brokerCalls, policyCalls]).toEqual([
    0, 0, 0, 0,
  ]);
});

test("store catalogue overflow, cancellation and blocked DB reads fail closed", async () => {
  const extra = `factory_overflow_${suite}`;
  await database.insert(mcpServers).values({
    id: extra,
    title: "Overflow",
    vendor: "Fixture",
    url: "https://example.test",
    provenance: "custom",
  });
  await database.insert(mcpTools).values(
    Array.from({ length: FACTORY_LIMITS.tools + 1 }, (_, index) => ({
      serverId: extra,
      name: `t${index}`,
      inputSchema: { type: "object" },
    })),
  );
  try {
    expect(codes(await readFactoryCatalogue(store, actor))).toContain(
      "CATALOGUE_TOO_LARGE",
    );
  } finally {
    await database.delete(mcpServers).where(eq(mcpServers.id, extra));
  }
  const [originalTool] = await database
    .select()
    .from(mcpTools)
    .where(
      and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
    );
  const oversized = "文".repeat(FACTORY_LIMITS.catalogueBytes);
  try {
    await database
      .update(mcpTools)
      .set({
        inputSchema: { type: "object", description: oversized },
      })
      .where(
        and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
      );
    expect(codes(await readFactoryCatalogue(store, actor))).toContain(
      "CATALOGUE_TOO_LARGE",
    );
    expect(
      codes(
        await store.factoryResourceFacts(alice, agentId, [
          { kind: "tool", ref },
        ]),
      ),
    ).toContain("CATALOGUE_TOO_LARGE");
  } finally {
    await database
      .update(mcpTools)
      .set(originalTool!)
      .where(
        and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
      );
  }
  try {
    await database
      .update(skills)
      .set({ instructions: oversized })
      .where(eq(skills.slug, aliceSkill));
    expect(codes(await readFactoryCatalogue(store, actor))).toContain(
      "CATALOGUE_TOO_LARGE",
    );
    expect(
      codes(
        await store.factoryResourceFacts(alice, agentId, [
          { kind: "skill", ref: aliceSkill },
        ]),
      ),
    ).toContain("CATALOGUE_TOO_LARGE");
  } finally {
    await database
      .update(skills)
      .set({ instructions: "Summarize supplied notes." })
      .where(eq(skills.slug, aliceSkill));
  }
  expect(
    codes(
      await readFactoryCatalogue(store, actor, { signal: AbortSignal.abort() }),
    ),
  ).toContain("CANCELLED");
  await database.transaction(async (tx) => {
    await tx.execute(sql`lock table mcp_tools in access exclusive mode`);
    const result = await readFactoryCatalogue(store, actor, { timeoutMs: 30 });
    expect(codes(result)).toContain("READ_TIMEOUT");
    expect(JSON.stringify(result)).not.toContain("select");
  });
});

test("I07 LLMock drives shell generation/review with exactly two HTTP requests for ready and pending artifacts", async () => {
  for (const required of [false, true]) {
    const llmock = new LLMock();
    const oldBase = process.env.OPENAI_BASE_URL;
    const usage: ModelCallObservation[] = [];
    const stages: FactoryObservation[] = [];
    const grantRows = await database
      .select()
      .from(pluginGrants)
      .where(eq(pluginGrants.agentId, agentId));
    try {
      process.env.OPENAI_BASE_URL = await llmock.start();
      llmock.onMessage(/^FACTORY_GENERATE/, {
        content: JSON.stringify(
          withRecordedIntent(draftFor(required ? [ref] : [])),
        ),
      });
      llmock.onMessage(/^FACTORY_REVIEW/, {
        content: JSON.stringify({ verdict: "PASS", findings: [] }),
      });
      const service = createAgentFactoryService({
        store,
        modelRef: "openai/fixture",
        complete: createModelCompleter({
          model: { provider: "openai", defaultModel: "fixture" },
          resolveApiKey: async () => "synthetic-fixture",
          timeoutMs: 20_000,
          outputTokenBudget: 4096,
          observe: (event) => usage.push(event),
        }),
        observe: (event) => stages.push(event),
      });
      const result = accepted(await service.construct(actor, request));
      expect(result.verification.construction).toBe("PASS");
      const readiness = accepted(
        await assessFactoryReadiness(
          store,
          actor,
          `ungranted_${suite}`,
          result.spec,
        ),
      );
      expect(readiness.state).toBe(required ? "pending_resources" : "ready");
      if (required)
        expect(
          readiness.blockers.some(({ code }) => code === "GRANT_REQUIRED"),
        ).toBe(true);
      expect(llmock.getRequests()).toHaveLength(2);
      expect(stages.map(({ stage, attempt }) => [stage, attempt])).toEqual([
        ["generate", 1],
        ["review", 1],
      ]);
      expect(usage).toHaveLength(2);
      expect(usage.every(({ status }) => status === "success")).toBe(true);
      expect(
        await database
          .select()
          .from(pluginGrants)
          .where(eq(pluginGrants.agentId, agentId)),
      ).toEqual(grantRows);
      expect([businessCalls, secretCalls, brokerCalls, policyCalls]).toEqual([
        0, 0, 0, 0,
      ]);
    } finally {
      if (oldBase === undefined) delete process.env.OPENAI_BASE_URL;
      else process.env.OPENAI_BASE_URL = oldBase;
      await llmock.stop();
    }
  }
});

test("I07 LLMock semantic repair uses four real requests, static repair uses three", async () => {
  for (const semantic of [false, true]) {
    const llmock = new LLMock();
    const oldBase = process.env.OPENAI_BASE_URL;
    const stages: FactoryObservation[] = [];
    try {
      process.env.OPENAI_BASE_URL = await llmock.start();
      const good = withRecordedIntent(draftFor([])) as ReturnType<
        typeof draftFor
      >;
      const bad = semantic
        ? {
            ...good,
            generatedSkill: {
              ...good.generatedSkill,
              procedure: ["incomplete summary"],
            },
          }
        : "not json";
      llmock.onMessage(/^FACTORY_GENERATE(?:(?!FACTORY_REPAIR)[\s\S])*$/, {
        content: typeof bad === "string" ? bad : JSON.stringify(bad),
      });
      llmock.onMessage(/FACTORY_REPAIR:/, { content: JSON.stringify(good) });
      llmock.onMessage(/^FACTORY_REVIEW(?=[\s\S]*incomplete summary)/, {
        content: JSON.stringify({
          verdict: "FAIL",
          findings: [
            {
              code: "INTENT_MISMATCH",
              path: "generatedSkill.procedure",
              evidenceRefs: ["request.description"],
              message: "Missing note reading.",
            },
          ],
        }),
      });
      llmock.onMessage(/^FACTORY_REVIEW(?:(?!incomplete summary)[\s\S])*$/, {
        content: JSON.stringify({ verdict: "PASS", findings: [] }),
      });
      const service = createAgentFactoryService({
        store,
        modelRef: "openai/fixture",
        observe: (event) => stages.push(event),
        complete: createModelCompleter({
          model: { provider: "openai", defaultModel: "fixture" },
          resolveApiKey: async () => "synthetic-fixture",
          timeoutMs: 20_000,
          outputTokenBudget: 4096,
        }),
      });
      const result = accepted(await service.construct(actor, request));
      expect(result.verification.attempts).toBe(2);
      expect(llmock.getRequests()).toHaveLength(semantic ? 4 : 3);
      expect(stages.map(({ stage }) => stage)).toEqual(
        semantic
          ? ["generate", "review", "repair", "review"]
          : ["generate", "repair", "review"],
      );
    } finally {
      if (oldBase === undefined) delete process.env.OPENAI_BASE_URL;
      else process.env.OPENAI_BASE_URL = oldBase;
      await llmock.stop();
    }
  }
});

// biome-ignore lint/suspicious/noExplicitAny: JSON columns are asserted field by field.
type FactoryBody = Record<string, any>;
// Step 4: persisted constructions through the real PluginStore facts and the real profile store.
const profiles = createAgentProfileStore(
  database,
  new URL("https://managed.example.test/ag-ui"),
);
const owner = {
  id: alice,
  role: "user" as const,
  email: `${alice}@example.test`,
};
function stagedModel(tools: string[] = [ref]) {
  const calls: string[] = [];
  return {
    calls,
    complete: async (prompt: string) => {
      calls.push(prompt);
      return JSON.stringify(
        prompt.startsWith("FACTORY_REVIEW")
          ? { verdict: "PASS", findings: [] }
          : withRecordedIntent(draftFor(tools)),
      );
    },
  };
}
function persistingService(llm = stagedModel()) {
  return createAgentFactoryService({
    store,
    profiles,
    modelRef: "fixture/model",
    complete: llm.complete,
  });
}
async function removeConstructions(ids: string[]) {
  if (ids.length) await database.delete(agents).where(inArray(agents.id, ids));
}

test("A09 pending recheck is 409, then 200 after the existing grant flow, with no model call or grant write", async () => {
  const llm = stagedModel();
  const service = persistingService(llm);
  const app = new Hono<{ Variables: AppVariables }>()
    .use(async (context, next) => {
      context.set("actor", {
        ...owner,
        role: context.req.header("x-admin") ? "admin" : "user",
        id: context.req.header("x-admin") ? bob : alice,
      });
      await next();
    })
    .route(
      "/api/agent-factory",
      createAgentFactoryRoutes(service, async (_c, next) => next()),
    );
  const key = randomUUID();
  const id = factoryConstructionId(alice, key);
  try {
    const created = await app.request(
      "http://test/api/agent-factory/constructions",
      {
        method: "POST",
        headers: { "idempotency-key": key, "content-type": "application/json" },
        body: JSON.stringify(request),
      },
    );
    expect(created.status).toBe(202);
    const artifact = (await created.json()) as FactoryBody;
    expect(
      artifact.readiness.blockers.map(({ code }: { code: string }) => code),
    ).toEqual(["GRANT_REQUIRED"]);
    const recheck = (headers: Record<string, string> = {}) =>
      app.request(`http://test/api/agent-factory/${id}/recheck`, {
        method: "POST",
        headers: { "content-type": "application/json", ...headers },
        body: JSON.stringify({ specHash: artifact.verification.specHash }),
      });
    expect((await recheck()).status).toBe(409);
    expect(
      await database
        .select()
        .from(pluginGrants)
        .where(eq(pluginGrants.agentId, id)),
    ).toEqual([]);
    // The existing administrator grant path, not anything the factory does.
    await store.grant("mcp", ref, id, bob);
    // An administrator's recheck still reads Alice's (the creator's) facts.
    const ready = await recheck({ "x-admin": "1" });
    expect(ready.status).toBe(200);
    const body = (await ready.json()) as FactoryBody;
    expect(body.readiness).toEqual({ state: "ready", blockers: [] });
    expect(body.agent.generated).toEqual({
      state: "ready",
      specHash: artifact.verification.specHash,
    });
    const [row] = await database.select().from(agents).where(eq(agents.id, id));
    expect(((row?.configuration ?? {}) as FactoryBody).factory.state).toBe(
      "ready",
    );
    expect(((row?.configuration ?? {}) as FactoryBody).factory.spec).toEqual(
      artifact.spec,
    );
    expect(llm.calls).toHaveLength(2);
    expect(
      await database
        .select()
        .from(pluginGrants)
        .where(eq(pluginGrants.agentId, id)),
    ).toHaveLength(1);
    expect([businessCalls, secretCalls, brokerCalls]).toEqual([0, 0, 0]);
  } finally {
    await removeConstructions([id]);
  }
});

test("I09 same-key replay, different-body conflict, concurrent first requests and soft-delete replay", async () => {
  const key = randomUUID();
  const id = factoryConstructionId(alice, key);
  try {
    const llm = stagedModel([]);
    const service = persistingService(llm);
    // Two first requests race: both may do model work, exactly one row and profile commit.
    const [left, right] = await Promise.all([
      service.create(owner, request, key),
      service.create(owner, request, key),
    ]);
    expect(left.ok && right.ok).toBe(true);
    if (!left.ok || !right.ok) throw new Error("expected both to succeed");
    expect(left.artifact.agent.id).toBe(id);
    expect(right.artifact.agent.id).toBe(id);
    expect([left.outcome, right.outcome].sort()).toEqual([
      "created",
      "replayed",
    ]);
    expect(right.artifact.spec).toEqual(left.artifact.spec);
    expect(
      await database.select().from(agents).where(eq(agents.id, id)),
    ).toHaveLength(1);
    expect(
      await database
        .select()
        .from(agentProfiles)
        .where(eq(agentProfiles.agentId, id)),
    ).toHaveLength(1);
    const callsAfterRace = llm.calls.length;
    const replay = await service.create(owner, request, key);
    expect(replay.ok && replay.outcome).toBe("replayed");
    expect(llm.calls).toHaveLength(callsAfterRace);
    const conflict = await service.create(
      owner,
      { ...request, role: "Other" },
      key,
    );
    expect(!conflict.ok && conflict.issues.map(({ code }) => code)).toEqual([
      "IDEMPOTENCY_CONFLICT",
    ]);
    await profiles.softDelete(owner, id);
    const gone = await service.create(owner, request, key);
    expect(!gone.ok && gone.issues.map(({ code }) => code)).toEqual([
      "CONSTRUCTION_DELETED",
    ]);
    expect(llm.calls).toHaveLength(callsAfterRace);
    expect(
      await database.select().from(agents).where(eq(agents.id, id)),
    ).toHaveLength(1);
  } finally {
    await removeConstructions([id]);
  }
});

test("I10 persisted prompt, hash and spec equal the verified artifact and the inspection response", async () => {
  const key = randomUUID();
  const id = factoryConstructionId(alice, key);
  try {
    const service = persistingService();
    const created = await service.create(owner, request, key);
    if (!created.ok) throw new Error(JSON.stringify(created.issues));
    const [row] = await database.select().from(agents).where(eq(agents.id, id));
    const configuration = row?.configuration as FactoryBody;
    const spec = parseAgentSpec(configuration.factory.spec);
    if (!spec.ok) throw new Error("stored spec must parse");
    expect(spec.value).toEqual(created.artifact.spec);
    expect(hashAgentSpec(spec.value)).toBe(
      configuration.factory.verification.specHash,
    );
    expect(configuration.factory.verification).toEqual(
      created.artifact.verification,
    );
    expect(configuration.systemPrompt).toBe(renderCorePrompt(spec.value));
    expect(configuration.factory.requestHash).toMatch(/^[a-f0-9]{64}$/);
    expect(id).toBe(`agent_factory_${configuration.factory.creationKeyHash}`);
    const read = await service.read(owner, id);
    expect(read.ok && read.artifact.spec).toEqual(created.artifact.spec);
    // An integrity break is refused rather than trusted.
    await database
      .update(agents)
      .set({ configuration: { ...configuration, systemPrompt: "Tampered." } })
      .where(eq(agents.id, id));
    const tampered = await service.read(owner, id);
    expect(!tampered.ok && tampered.issues.map(({ code }) => code)).toEqual([
      "ARTIFACT_INVALID",
    ]);
  } finally {
    await removeConstructions([id]);
  }
});

test("a save stalled past the outer deadline rolls back: DEADLINE_EXCEEDED and no late row", async () => {
  const key = randomUUID();
  const id = factoryConstructionId(alice, key);
  const held = Promise.withResolvers<void>();
  const entered = Promise.withResolvers<void>();
  // Another transaction holds the same primary key uncommitted, so the save waits on it.
  const blocker = database
    .transaction(async (tx) => {
      await tx.insert(agents).values({
        id,
        name: "blocker",
        type: "built_in",
        configuration: {},
      });
      entered.resolve();
      await held.promise;
      throw new Error("roll back the blocker");
    })
    .catch(() => undefined);
  try {
    await entered.promise;
    const llm = stagedModel([]);
    const result = await persistingService(llm).create(owner, request, key, {
      timeoutMs: 1_500,
    });
    expect(!result.ok && result.issues.map(({ code }) => code)).toEqual([
      "DEADLINE_EXCEEDED",
    ]);
    expect(llm.calls).toHaveLength(2);
  } finally {
    held.resolve();
    await blocker;
  }
  await Bun.sleep(50);
  expect(await database.select().from(agents).where(eq(agents.id, id))).toEqual(
    [],
  );
  expect(
    await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, id)),
  ).toEqual([]);
});
