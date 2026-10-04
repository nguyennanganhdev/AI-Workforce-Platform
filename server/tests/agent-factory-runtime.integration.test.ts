import { afterAll, beforeAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import type { AbstractAgent } from "@ag-ui/client";
import { LLMock } from "@copilotkit/aimock";
import { MCPMock } from "@copilotkit/aimock/mcp";
import { and, eq, inArray } from "drizzle-orm";
import { Hono } from "hono";
import {
  COMPUTER_GUIDANCE,
  PROVENANCE_GUIDANCE,
} from "../../shared/bot-prompt.js";
import type { AgentDraft } from "../../agent-factory/src/contracts.js";
import {
  createAgentFactoryService,
  createFactoryRuntimeReadiness,
} from "../src/agents/factory.js";
import { createAgentFactoryRoutes } from "../src/agents/factory-routes.js";
import { createAgentProfileStore } from "../src/agents/profile-store.js";
import type { AgentActor } from "../src/agents/profile-types.js";
import { createRuntimeAgentLoader } from "../src/agents/runtime-agents.js";
import { createAuditStore } from "../src/audit.js";
import type { AppVariables } from "../src/auth/guards.js";
import { createChannelStore } from "../src/channels/routes.js";
import { createThreadIdentity } from "../src/channels/thread-identity.js";
import { type RegisteredAgent, resolveRuntimeAgents } from "../src/copilot.js";
import { createCredentialStore } from "../src/credentials.js";
import { createDatabase } from "../src/db/client.js";
import {
  agents,
  channels,
  credentials,
  mcpServers,
  mcpTools,
  mcpUserCredentials,
  pluginGrants,
  users,
} from "../src/db/schema/index.js";
import { createPluginRoutes } from "../src/plugins/routes.js";
import { createPluginStore } from "../src/plugins/store.js";
import { grantedTools, REFUSAL_MARKER } from "../src/plugins/tools.js";
import { withRecordedIntent } from "../../agent-factory/tests/fixtures/factory-intent.js";
import { TEST_POOL, testDatabaseUrl } from "./support/database.js";

/*
 * R01–R08: generated coworkers through the production runtime path. Created through the factory
 * API, loaded by the common loader with the production readiness reader, built by
 * `resolveRuntimeAgents` into a real BuiltInAgent, answered by LLMock and calling MCPMock through
 * `PluginStore.callTool`. Grants go through the existing plugin grant routes.
 */
const database = createDatabase(testDatabaseUrl(), TEST_POOL);
const suite = randomUUID().slice(0, 8);
const alice = `factory_rt_alice_${suite}`;
const bob = `factory_rt_bob_${suite}`;
const admin = `factory_rt_admin_${suite}`;
const roles: Record<string, AgentActor["role"]> = {
  [alice]: "user",
  [bob]: "user",
  [admin]: "admin",
};
const actor = (id: string): AgentActor => ({ id, role: roles[id] ?? "user" });
const serverId = `factory_rt_mcp_${suite}`;
const ref = `${serverId}/read_notes`;
// A catalogue entry that needs each person's own OAuth connection.
const oauthRef = "notion/search";
const clientSecretId = randomUUID();
const aliceTokenId = randomUUID();
const bobTokenId = randomUUID();
const model = { provider: "openai" as const, defaultModel: "fixture-model" };
const mock = new MCPMock();
let businessCalls = 0;

const store = createPluginStore({
  database,
  auditStore: createAuditStore(database),
  credentials: createCredentialStore(database),
  encryptionKey: "x".repeat(44),
  policy: () => ({ mode: "enforce", deny: [], allow: ["true"] }),
});
const profiles = createAgentProfileStore(database, undefined);
const channelStore = createChannelStore(
  database,
  profiles,
  createThreadIdentity(`factory-rt-${suite}`),
);
// The production gate, exactly as index.ts injects it.
const readiness = createFactoryRuntimeReadiness(store);
let readinessCalls: string[] = [];
const loader = createRuntimeAgentLoader(
  database,
  undefined,
  undefined,
  async (who, row) => {
    readinessCalls.push(row.id);
    return readiness(who, row);
  },
);

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
function draftFor(tools: string[]): AgentDraft {
  return {
    goal: "Read supplied notes.",
    responsibilities: [{ statement: "Read supplied notes.", source }],
    constraints: [],
    procedure: ["Read supplied notes.", "Return a summary."],
    requirements: tools.length
      ? tools.map((tool) => ({
          need: "Read notes.",
          fulfillment: "tool" as const,
          source,
          proposedRefs: [tool],
        }))
      : [
          {
            need: "Summarize supplied text.",
            fulfillment: "model_on_input" as const,
            source,
            proposedRefs: [],
          },
        ],
    toolArguments: tools
      .filter((tool) => tool === ref)
      .map((tool) => ({
        ref: tool,
        argument: "query",
        sourceKind: "user_input" as const,
        sourceRef: "notes",
        missingBehavior: "Ask for notes.",
      })),
    inputFacts: [
      { name: "notes", required: true, missingBehavior: "Ask for notes." },
    ],
    outputExpectations: ["A summary."],
    acceptanceCriteria: ["Reflect supplied notes."],
    unresolvedQuestions: [],
    unsupportedRequirements: [],
  };
}

/** Factory API, plugin grant routes, one authenticated actor per request header. */
function api(tools: string[], profileStore = profiles) {
  const service = createAgentFactoryService({
    store,
    profiles: profileStore,
    modelRef: "fixture/model",
    complete: async (prompt) =>
      JSON.stringify(
        prompt.startsWith("FACTORY_REVIEW")
          ? { verdict: "PASS", findings: [] }
          : withRecordedIntent(draftFor(tools)),
      ),
  });
  const app = new Hono<{ Variables: AppVariables }>();
  const requireUser = async (
    context: Parameters<Parameters<typeof app.use>[1]>[0],
    next: () => Promise<void>,
  ) => {
    const id = context.req.header("x-user") ?? alice;
    context.set("actor", {
      id,
      email: `${id}@example.test`,
      role: roles[id] ?? "user",
    });
    await next();
  };
  app.route(
    "/api/agent-factory",
    createAgentFactoryRoutes(service, requireUser),
  );
  app.route(
    "/api/plugins",
    createPluginRoutes(store, requireUser, async () => true),
  );
  const call = async (
    method: string,
    path: string,
    user: string,
    body?: unknown,
    headers: Record<string, string> = {},
  ) => {
    const response = await app.request(`http://test${path}`, {
      method,
      headers: {
        "content-type": "application/json",
        "x-user": user,
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    return {
      status: response.status,
      // biome-ignore lint/suspicious/noExplicitAny: response bodies are asserted field by field.
      body: (await response.json().catch(() => null)) as any,
    };
  };
  return {
    create: () =>
      call("POST", "/api/agent-factory/constructions", alice, request, {
        "idempotency-key": randomUUID(),
      }),
    recheck: (id: string, specHash: string, user = alice) =>
      call("POST", `/api/agent-factory/${id}/recheck`, user, { specHash }),
    grant: (agentId: string, grantRef = ref) =>
      call("POST", "/api/plugins/grants", admin, {
        kind: "mcp",
        ref: grantRef,
        agentId,
      }),
    revoke: (agentId: string, grantRef = ref) =>
      call(
        "DELETE",
        `/api/plugins/grants?kind=mcp&ref=${encodeURIComponent(grantRef)}&agentId=${encodeURIComponent(agentId)}`,
        admin,
      ),
  };
}

const createdAgentIds: string[] = [];
async function created(tools: string[] = [], profileStore = profiles) {
  const response = await api(tools, profileStore).create();
  expect([201, 202]).toContain(response.status);
  createdAgentIds.push(response.body.agent.id);
  return response.body as {
    agent: { id: string };
    spec: unknown;
    verification: { specHash: string };
    readiness: { state: string };
  };
}

async function roster(who: string): Promise<RegisteredAgent[]> {
  return loader(actor(who));
}

/** The production built-in path for one Bot, with the same tool loading a run uses. */
async function built(
  who: string,
  agentId: string,
  recorder?: LLMock,
  load = loader,
): Promise<AbstractAgent> {
  const agents = await resolveRuntimeAgents(
    () => load(actor(who)),
    model,
    async () => "synthetic-model-key",
    undefined,
    (botId) => grantedTools({ store, botId, actorId: who }),
    undefined,
    COMPUTER_GUIDANCE,
    undefined,
    undefined,
    undefined,
    undefined,
    // Headless callers (routines, handoff) resolve exactly one Bot through the same loader.
    agentId,
  );
  const agent = agents[agentId]?.clone();
  if (!agent) throw new Error(`no ${agentId} was built`);
  if (recorder) expect(recorder.getRequests()).toHaveLength(0);
  return agent;
}

async function withModel<T>(
  configure: (recorder: LLMock) => void,
  work: (recorder: LLMock) => Promise<T>,
): Promise<T> {
  const recorder = new LLMock();
  const previous = process.env.OPENAI_BASE_URL;
  try {
    process.env.OPENAI_BASE_URL = await recorder.start();
    configure(recorder);
    return await work(recorder);
  } finally {
    if (previous === undefined) delete process.env.OPENAI_BASE_URL;
    else process.env.OPENAI_BASE_URL = previous;
    await recorder.stop();
  }
}

async function ask(agent: AbstractAgent, content: string) {
  agent.addMessage({ id: randomUUID(), role: "user", content });
  const error = await agent.runAgent().then(
    () => null,
    (reason: unknown) => reason,
  );
  return { error, last: agent.messages.at(-1) };
}

const occurrences = (haystack: string, needle: string) =>
  haystack.split(needle).length - 1;
const escaped = (text: string) => JSON.stringify(text).slice(1, -1);

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
      return "NOTES: the fixture notes.";
    });
  const mockUrl = await mock.start();
  await database
    .insert(users)
    .values(
      [alice, bob, admin].map((id) => ({ id, email: `${id}@example.test` })),
    );
  await database.insert(credentials).values([
    {
      id: clientSecretId,
      kind: "mcp_oauth_client",
      provider: "notion",
      encryptedValue: "SYNTHETIC_CLIENT",
      keyId: `factory_rt_client_${suite}`,
      metadata: {},
    },
    ...[aliceTokenId, bobTokenId].map((id, index) => ({
      id,
      kind: "mcp_user_token" as const,
      provider: "notion",
      encryptedValue: "SYNTHETIC_TOKEN",
      keyId: index === 0 ? alice : bob,
      metadata: {},
    })),
  ]);
  await database.insert(mcpServers).values([
    {
      id: serverId,
      title: "Notes fixture",
      vendor: "Fixture",
      url: mockUrl,
      provenance: "custom",
      addedBy: admin,
    },
    {
      id: "notion",
      title: "Notion",
      vendor: "Notion",
      url: "https://mcp.notion.com/mcp",
      provenance: "first-party",
      credentialId: clientSecretId,
    },
  ]);
  // Discovered through the real protocol; construction and runtime read only this cache.
  expect(await store.refreshTools(serverId, admin)).toEqual({ tools: 1 });
  await database.insert(mcpTools).values({
    serverId: "notion",
    name: "search",
    description: "Search notes.",
    inputSchema: { type: "object", properties: {} },
    effect: "read",
  });
  // Bob, not Alice, is connected to the OAuth vendor.
  await database.insert(mcpUserCredentials).values({
    serverId: "notion",
    userId: bob,
    credentialId: bobTokenId,
    scope: "read",
  });
});

afterAll(async () => {
  if (createdAgentIds.length)
    await database.delete(agents).where(inArray(agents.id, createdAgentIds));
  await database
    .delete(mcpServers)
    .where(inArray(mcpServers.id, [serverId, "notion"]));
  await database
    .delete(credentials)
    .where(inArray(credentials.id, [clientSecretId, aliceTokenId, bobTokenId]));
  await database.delete(users).where(inArray(users.id, [alice, bob, admin]));
  await mock.stop();
  await database.$client.close();
});

test("R01/R08 a ready generated agent answers through the real BuiltInAgent with its core prompt and guidance once", async () => {
  const artifact = await created();
  expect(artifact.readiness.state).toBe("ready");
  const [row] = await database
    .select()
    .from(agents)
    .where(eq(agents.id, artifact.agent.id));
  const corePrompt = String(
    (row?.configuration as { systemPrompt?: unknown } | undefined)
      ?.systemPrompt,
  );
  const systemMessages = await withModel(
    (recorder) =>
      recorder.onMessage(/.*/, { content: "R01 generated answer." }),
    async (recorder) => {
      const bodies: string[] = [];
      // Two loads: the core prompt must survive a reload unchanged.
      for (const attempt of [1, 2]) {
        const agent = await built(alice, artifact.agent.id);
        const { error, last } = await ask(agent, `Summarize note ${attempt}.`);
        expect(error).toBeNull();
        expect(last).toMatchObject({
          role: "assistant",
          content: "R01 generated answer.",
        });
        expect(recorder.getRequests()).toHaveLength(attempt);
        bodies.push(JSON.stringify(recorder.getRequests()[attempt - 1]?.body));
      }
      return bodies;
    },
  );
  for (const body of systemMessages) {
    expect(occurrences(body, escaped(corePrompt.trim()))).toBe(1);
    expect(occurrences(body, escaped(PROVENANCE_GUIDANCE))).toBe(1);
    expect(occurrences(body, escaped(COMPUTER_GUIDANCE))).toBe(1);
  }
  const loaded = (await roster(alice)).find(
    ({ id }) => id === artifact.agent.id,
  );
  expect(loaded).toEqual({
    id: artifact.agent.id,
    name: request.name,
    type: "built_in",
    systemPrompt: corePrompt.trim(),
  });
});

test("R01/R08 on a managed-endpoint deployment the generated agent still runs in-process on its core prompt", async () => {
  // Legacy creation on this deployment would point a new coworker at the managed Bot.
  const managedUrl = new URL("http://managed-bot.invalid/agui");
  const managedProfiles = createAgentProfileStore(database, managedUrl);
  const managedLoader = createRuntimeAgentLoader(
    database,
    undefined,
    { endpoint: managedUrl, token: "managed-fixture-token" },
    readiness,
  );
  const artifact = await created([], managedProfiles);
  expect(artifact.readiness.state).toBe("ready");
  const [row] = await database
    .select()
    .from(agents)
    .where(eq(agents.id, artifact.agent.id));
  expect(row?.type).toBe("built_in");
  // No managed endpoint is written: only the compiler-owned prompt and the canonical artifact.
  expect(Object.keys(row?.configuration ?? {}).sort()).toEqual([
    "factory",
    "systemPrompt",
  ]);
  const corePrompt = String(
    (row?.configuration as { systemPrompt?: unknown } | undefined)
      ?.systemPrompt,
  );
  expect(
    (await managedLoader(actor(alice))).find(
      ({ id }) => id === artifact.agent.id,
    ),
  ).toEqual({
    id: artifact.agent.id,
    name: request.name,
    type: "built_in",
    systemPrompt: corePrompt.trim(),
  });
  const body = await withModel(
    (recorder) =>
      recorder.onMessage(/.*/, { content: "Managed deployment answer." }),
    async (recorder) => {
      const agent = await built(
        alice,
        artifact.agent.id,
        recorder,
        managedLoader,
      );
      const { error, last } = await ask(agent, "Summarize this note.");
      expect(error).toBeNull();
      expect(last).toMatchObject({
        role: "assistant",
        content: "Managed deployment answer.",
      });
      expect(recorder.getRequests()).toHaveLength(1);
      return JSON.stringify(recorder.getRequests()[0]?.body);
    },
  );
  expect(occurrences(body, escaped(corePrompt.trim()))).toBe(1);
  expect(body).not.toContain("managed-fixture-token");
});

test("R02 a pending agent stays visible but produces zero model and tool calls, also on the headless path", async () => {
  const artifact = await created([ref]);
  expect(artifact.readiness.state).toBe("pending_resources");
  const loaded = (await roster(alice)).find(
    ({ id }) => id === artifact.agent.id,
  );
  expect(loaded).toMatchObject({ type: "unavailable" });
  const before = businessCalls;
  await withModel(
    (recorder) => recorder.onMessage(/.*/, { content: "must not answer" }),
    async (recorder) => {
      const agent = await built(alice, artifact.agent.id, recorder);
      const { error, last } = await ask(agent, "Read my notes.");
      expect(error).not.toBeNull();
      expect(last?.role).toBe("user");
      expect(recorder.getRequests()).toHaveLength(0);
    },
  );
  expect(businessCalls).toBe(before);
  expect(
    await database
      .select()
      .from(pluginGrants)
      .where(eq(pluginGrants.agentId, artifact.agent.id)),
  ).toEqual([]);
});

test("R03/R04 grant route → recheck → real tool call; revocation blocks the next load and the direct call", async () => {
  const routes = api([ref]);
  const artifact = await created([ref]);
  const id = artifact.agent.id;
  expect((await routes.grant(id)).status).toBe(200);
  // Persisted pending stays pending until an explicit recheck; the loader never flips state.
  expect((await roster(alice)).find((agent) => agent.id === id)?.type).toBe(
    "unavailable",
  );
  const rechecked = await routes.recheck(id, artifact.verification.specHash);
  expect(rechecked.status).toBe(200);
  expect(rechecked.body.readiness).toEqual({ state: "ready", blockers: [] });

  const [tool] = await grantedTools({ store, botId: id, actorId: alice });
  if (!tool) throw new Error("the granted tool must be offered");
  const before = businessCalls;
  await withModel(
    (recorder) => {
      recorder.onToolResult("call_r03", { content: "R03 used the notes." });
      recorder.onMessage(/R03/, {
        toolCalls: [
          {
            id: "call_r03",
            name: tool.name,
            arguments: JSON.stringify({ query: "quarterly" }),
          },
        ],
      });
    },
    async (recorder) => {
      const agent = await built(alice, id);
      const { error, last } = await ask(agent, "R03 read my notes.");
      expect(error).toBeNull();
      expect(last).toMatchObject({
        role: "assistant",
        content: "R03 used the notes.",
      });
      expect(recorder.getRequests()).toHaveLength(2);
      expect(JSON.stringify(recorder.getRequests()[1]?.body)).toContain(
        "NOTES: the fixture notes.",
      );
    },
  );
  expect(businessCalls).toBe(before + 1);

  // R04: revoke through the existing route. A tool list captured before revocation models a run
  // already in flight; callTool is still the final authority and refuses it.
  expect((await routes.revoke(id)).status).toBe(200);
  const blocked = (await roster(alice)).find((agent) => agent.id === id);
  expect(blocked).toMatchObject({
    type: "unavailable",
    reason: expect.stringContaining("GRANT_REQUIRED"),
  });
  await withModel(
    (recorder) => recorder.onMessage(/.*/, { content: "must not answer" }),
    async (recorder) => {
      const { error } = await ask(await built(alice, id, recorder), "Again.");
      expect(error).not.toBeNull();
      expect(recorder.getRequests()).toHaveLength(0);
    },
  );
  const direct = await tool.execute({ query: "quarterly" });
  expect(String(direct)).toContain(REFUSAL_MARKER);
  expect(businessCalls).toBe(before + 1);
});

test("R05 a changed compiled resource blocks execution and recheck cannot silently accept it", async () => {
  const routes = api([ref]);
  const artifact = await created([ref]);
  const id = artifact.agent.id;
  expect((await routes.grant(id)).status).toBe(200);
  expect(
    (await routes.recheck(id, artifact.verification.specHash)).status,
  ).toBe(200);
  expect((await roster(alice)).find((agent) => agent.id === id)?.type).toBe(
    "built_in",
  );
  const [original] = await database
    .select()
    .from(mcpTools)
    .where(
      and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
    );
  try {
    await database
      .update(mcpTools)
      .set({ description: "Read and forward notes elsewhere." })
      .where(
        and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
      );
    expect(
      (await roster(alice)).find((agent) => agent.id === id),
    ).toMatchObject({
      type: "unavailable",
      reason: expect.stringContaining("changed"),
    });
    const before = businessCalls;
    await withModel(
      (recorder) => recorder.onMessage(/.*/, { content: "must not answer" }),
      async (recorder) => {
        const { error } = await ask(await built(alice, id, recorder), "Read.");
        expect(error).not.toBeNull();
        expect(recorder.getRequests()).toHaveLength(0);
      },
    );
    expect(businessCalls).toBe(before);
    const recheck = await routes.recheck(id, artifact.verification.specHash);
    expect(recheck.status).toBe(409);
    expect(
      recheck.body.issues.map(({ code }: { code: string }) => code),
    ).toContain("RESOURCE_CHANGED");
    const [row] = await database.select().from(agents).where(eq(agents.id, id));
    // The semantic fingerprint was not rewritten to match the changed resource.
    expect(
      (row?.configuration as { factory?: { spec: unknown } } | undefined)
        ?.factory?.spec,
    ).toEqual(artifact.spec);
  } finally {
    if (original)
      await database
        .update(mcpTools)
        .set({ description: original.description })
        .where(
          and(eq(mcpTools.serverId, serverId), eq(mcpTools.name, "read_notes")),
        );
  }
});

test("R06 readiness uses the stored creator's connection, never an administrator's or another person's", async () => {
  const routes = api([oauthRef]);
  const artifact = await created([oauthRef]);
  const id = artifact.agent.id;
  expect((await routes.grant(id, oauthRef)).status).toBe(200);
  // Bob is connected; Alice (the creator) is not. An administrator's recheck changes nothing.
  const pending = await routes.recheck(
    id,
    artifact.verification.specHash,
    admin,
  );
  expect(pending.status).toBe(409);
  expect(pending.body.issues.map(({ code }: { code: string }) => code)).toEqual(
    ["CONNECTION_REQUIRED"],
  );
  for (const who of [alice, admin])
    expect((await roster(who)).find((agent) => agent.id === id)?.type).toBe(
      "unavailable",
    );
  await database.insert(mcpUserCredentials).values({
    serverId: "notion",
    userId: alice,
    credentialId: aliceTokenId,
    scope: "read",
  });
  try {
    expect(
      (await routes.recheck(id, artifact.verification.specHash, admin)).status,
    ).toBe(200);
    for (const who of [alice, admin])
      expect((await roster(who)).find((agent) => agent.id === id)?.type).toBe(
        "built_in",
      );
    // Alice's connection going away blocks the next load for everyone, the administrator included.
    await database
      .update(credentials)
      .set({ revokedAt: new Date() })
      .where(eq(credentials.id, aliceTokenId));
    expect(
      (await roster(admin)).find((agent) => agent.id === id),
    ).toMatchObject({
      type: "unavailable",
      reason: expect.stringContaining("CONNECTION_REQUIRED"),
    });
    // Bob never sees Alice's private coworker at all.
    expect((await roster(bob)).some((agent) => agent.id === id)).toBe(false);
  } finally {
    await database
      .delete(mcpUserCredentials)
      .where(
        and(
          eq(mcpUserCredentials.serverId, "notion"),
          eq(mcpUserCredentials.userId, alice),
        ),
      );
  }
});

test("R07 a deleted generated agent is a history tombstone and is never readiness-checked", async () => {
  const artifact = await created();
  const id = artifact.agent.id;
  const channel = await channelStore.create(actor(alice), [id]);
  try {
    await profiles.softDelete(actor(alice), id);
    readinessCalls = [];
    expect(await roster(alice)).toContainEqual({
      id,
      name: request.name,
      type: "unavailable",
      reason: `${request.name} has been deleted and can no longer run. Its conversations remain readable.`,
    });
    expect(readinessCalls).not.toContain(id);
    expect((await roster(bob)).some((agent) => agent.id === id)).toBe(false);
  } finally {
    await database.delete(channels).where(eq(channels.id, channel.id));
  }
});
