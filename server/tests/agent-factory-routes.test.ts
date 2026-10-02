import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { createFactoryClient } from "../../agent-factory/src/index.js";
import { createFactoryHandler } from "../../agent-factory/src/http.js";
import { eq, inArray, like } from "drizzle-orm";
import type {
  AgentCreationRequest,
  AgentDraft,
  FactoryCatalogueProjection,
  FactoryResourceFact,
  FactoryResult,
} from "../../agent-factory/src/contracts.js";
import {
  createAgentFactoryService,
  factoryConstructionId,
} from "../src/agents/factory.js";
import { createAgentProfileStore } from "../src/agents/profile-store.js";
import { createApp } from "../src/app.js";
import { registeredAgentFromRow } from "../src/copilot.js";
import { type AuditEventInput, createAuditStore } from "../src/audit.js";
import { loadConfig } from "../src/config.js";
import { createCredentialStore } from "../src/credentials.js";
import { createDatabase } from "../src/db/client.js";
import {
  agentProfiles,
  agents,
  credentials,
  mcpServers,
  mcpTools,
  mcpUserCredentials,
  pluginGrants,
  users,
} from "../src/db/schema";
import {
  hashAgentSpec,
  parseAgentSpec,
  renderCorePrompt,
} from "../../agent-factory/src/spec.js";
import { createPluginStore, type PluginStore } from "../src/plugins/store.js";
import { TEST_POOL, testDatabaseUrl } from "./support/database.js";
import { withRecordedIntent } from "../../agent-factory/tests/fixtures/factory-intent";
import { testEnvironment } from "./support/environment";

const database = createDatabase(testDatabaseUrl(), TEST_POOL);
const suite = randomUUID().slice(0, 8);
const alice = `factory_routes_alice_${suite}`;
const bob = `factory_routes_bob_${suite}`;
const admin = `factory_routes_admin_${suite}`;
const roles: Record<string, "user" | "admin"> = {
  [alice]: "user",
  [bob]: "user",
  [admin]: "admin",
};
const managedEndpoint = "https://managed.example.test/ag-ui";
const profiles = createAgentProfileStore(database, new URL(managedEndpoint));
const request: AgentCreationRequest = {
  name: "Notes",
  role: "Note summarizer",
  description:
    "Summarize supplied notes. Ask for notes when missing. Do not retrieve external data.",
};
const source = {
  kind: "request",
  field: "description",
  quote: "supplied notes",
} as const;
const toolRef = "mock/read";
// biome-ignore lint/suspicious/noExplicitAny: response and JSON columns are asserted field by field.
type Body = Record<string, any>;

function draft(): AgentDraft {
  return {
    goal: "Summarize supplied notes.",
    responsibilities: [{ statement: "Summarize supplied notes.", source }],
    constraints: [
      {
        statement: "Do not retrieve external data.",
        source: { ...source, quote: "Do not retrieve external data." },
      },
    ],
    procedure: ["Ask for notes when missing.", "Return a concise summary."],
    requirements: [
      {
        need: "Summarize supplied text.",
        fulfillment: "model_on_input",
        source,
        proposedRefs: [],
      },
    ],
    toolArguments: [],
    inputFacts: [
      { name: "notes", required: true, missingBehavior: "Ask for the notes." },
    ],
    outputExpectations: ["A concise summary grounded in the supplied notes."],
    acceptanceCriteria: ["The summary reflects the supplied notes."],
    unresolvedQuestions: [],
    unsupportedRequirements: [],
  };
}
function toolDraft(proposedRefs = [toolRef]): AgentDraft {
  return {
    ...draft(),
    requirements: [
      {
        need: "Read supplied text.",
        fulfillment: "tool",
        source,
        proposedRefs,
      },
    ],
    toolArguments: proposedRefs.map((ref) => ({
      ref,
      argument: "text",
      sourceKind: "user_input" as const,
      sourceRef: "notes",
      missingBehavior: "Ask for notes.",
    })),
  };
}
const tool = {
  kind: "tool" as const,
  ref: toolRef,
  name: "read",
  title: "Mock",
  description: "Read supplied text.",
  inputSchema: {
    type: "object",
    properties: { text: { type: "string" } },
    required: ["text"],
  },
  outputSchema: null,
  effect: "read" as const,
  destructive: false,
};
const pass = { verdict: "PASS", findings: [] };

/** Answers by stage, and counts every call; nothing here can reach a network. */
function model(
  generate: () => unknown,
  review: () => unknown = () => pass,
  onCall?: (prompt: string) => void,
) {
  const calls: string[] = [];
  const complete = async (prompt: string) => {
    calls.push(prompt);
    onCall?.(prompt);
    const response = withRecordedIntent(
      prompt.startsWith("FACTORY_REVIEW") ? review() : generate(),
    );
    if (response instanceof Error) throw response;
    return typeof response === "string" ? response : JSON.stringify(response);
  };
  return { calls, complete };
}

function harness(
  options: {
    generate?: () => unknown;
    review?: () => unknown;
    catalogue?: () => FactoryResult<FactoryCatalogueProjection>;
    facts?: Partial<Omit<FactoryResourceFact, "kind" | "ref" | "resource">>;
    now?: () => number;
    onCall?: (prompt: string) => void;
    mount?: boolean;
    remote?: { url: string; token: string };
    /** The real store, for both construction facts and the mounted `/api/plugins` grant routes. */
    plugins?: PluginStore;
  } = {},
) {
  const llm = model(
    options.generate ?? (() => draft()),
    options.review,
    options.onCall,
  );
  const audits: AuditEventInput[] = [];
  const factReads: string[] = [];
  const service = createAgentFactoryService({
    ...(options.remote
      ? { constructSpec: createFactoryClient(options.remote) }
      : { modelRef: "fixture/model", complete: llm.complete }),
    ...(options.now ? { now: options.now } : {}),
    profiles,
    auditStore: { insert: async (event) => void audits.push(event) },
    store: options.plugins ?? {
      factoryCatalogue: async () =>
        options.catalogue?.() ?? {
          ok: true,
          value: { tools: [tool], skills: [] },
        },
      factoryResourceFacts: async (ownerId, _agentId, refs) => {
        factReads.push(ownerId);
        return {
          ok: true,
          value: refs.map((ref) => ({
            ...ref,
            resource: ref.ref === toolRef ? tool : null,
            granted: false,
            configured: true,
            connected: true,
            ...options.facts,
          })),
        };
      },
    },
  });
  const args: unknown[] = new Array(createApp.length).fill(undefined);
  args[0] = loadConfig(testEnvironment());
  args[1] = {
    handler: () => new Response(null, { status: 204 }),
    api: {
      getSession: async ({ headers }: { headers: Headers }) => {
        const id = headers.get("x-test-user");
        return id
          ? { user: { id, email: `${id}@example.test`, name: id } }
          : null;
      },
    },
  };
  args[2] = {
    rolesForUser: async (id: string) => (roles[id] ? [roles[id]] : []),
  };
  // Position 10 is agentProfileStore (see agent-routes.test.ts); the factory is always last.
  args[9] = profiles;
  // Position 15 is pluginStore, which mounts the existing /api/plugins grant routes.
  if (options.plugins) args[14] = options.plugins;
  if (options.mount !== false) args[createApp.length - 1] = service;
  const app = (
    createApp as (...values: unknown[]) => ReturnType<typeof createApp>
  )(...args);
  const send = (
    path: string,
    init: {
      user?: string;
      method?: string;
      key?: string | null;
      body?: unknown;
      raw?: string;
    } = {},
  ) =>
    app.request(`http://openbot.test${path}`, {
      method: init.method ?? "POST",
      headers: {
        "content-type": "application/json",
        ...(init.user === undefined ? { "x-test-user": alice } : {}),
        ...(init.user ? { "x-test-user": init.user } : {}),
        ...(init.key === null
          ? {}
          : { "idempotency-key": init.key ?? randomUUID() }),
      },
      ...(init.method === "GET"
        ? {}
        : { body: init.raw ?? JSON.stringify(init.body ?? request) }),
    });
  return { app, send, llm, audits, factReads, service };
}

async function rowsFor(id: string) {
  return {
    agents: await database.select().from(agents).where(eq(agents.id, id)),
    profiles: await database
      .select()
      .from(agentProfiles)
      .where(eq(agentProfiles.agentId, id)),
  };
}

beforeAll(async () => {
  await database
    .insert(users)
    .values(
      [alice, bob, admin].map((id) => ({ id, email: `${id}@example.test` })),
    );
});
afterAll(async () => {
  await database.delete(agents).where(like(agents.id, "agent_factory_%"));
  await database.delete(agents).where(like(agents.name, `legacy-${suite}%`));
  await database.delete(users).where(inArray(users.id, [alice, bob, admin]));
  await database.$client.close();
});

describe("POST /api/agent-factory/constructions", () => {
  test("A01 valid request is 201 with a private built-in agent and a verified, persisted spec", async () => {
    const { send, llm, audits } = harness();
    const key = randomUUID();
    const response = await send("/api/agent-factory/constructions", { key });
    expect(response.status).toBe(201);
    const body = (await response.json()) as Body;
    const id = factoryConstructionId(alice, key);
    expect(body.agent).toMatchObject({
      id,
      name: request.name,
      title: request.role,
      roleDescription: request.description,
      visibility: "private",
      builtIn: true,
      mine: true,
      canManage: true,
      endpoint: null,
      generated: { state: "ready", specHash: body.verification.specHash },
    });
    expect(body.readiness).toEqual({ state: "ready", blockers: [] });
    expect(body.verification).toMatchObject({
      construction: "PASS",
      attempts: 1,
      specHash: hashAgentSpec(body.spec),
    });
    expect(llm.calls).toHaveLength(2);
    const {
      agents: [row],
      profiles: [profile],
    } = await rowsFor(id);
    // Built-in even though this deployment has a managed endpoint the legacy create would choose.
    expect(row?.type).toBe("built_in");
    const configuration = row?.configuration as Body;
    expect(Object.keys(configuration).sort()).toEqual([
      "factory",
      "systemPrompt",
    ]);
    expect(configuration.systemPrompt).toBe(renderCorePrompt(body.spec));
    expect(configuration.factory.spec).toEqual(body.spec);
    expect(configuration.factory.state).toBe("ready");
    expect(profile).toMatchObject({
      ownerUserId: alice,
      visibility: "private",
    });
    // Metadata-only audit: stages, the outcome and the existing bot.created event.
    expect(
      audits.map(({ eventType, payload }) => [eventType, payload.stage]),
    ).toEqual([
      ["configuration.changed", "generate"],
      ["configuration.changed", "review"],
      ["configuration.changed", "outcome"],
      ["bot.created", undefined],
    ]);
    expect(audits.every(({ targetId }) => targetId === id)).toBe(true);
    const audited = JSON.stringify(audits);
    expect(audited).not.toContain(request.description);
    expect(audited).not.toContain("Summarize supplied notes.");
  });

  test("A02 missing key, forged fields, bad JSON and oversized bodies are 400 before any model call", async () => {
    const { send, llm } = harness();
    const cases = [
      [{ key: null }, "IDEMPOTENCY_KEY_INVALID"],
      [{ key: "has space" }, "IDEMPOTENCY_KEY_INVALID"],
      [{ key: "k".repeat(129) }, "IDEMPOTENCY_KEY_INVALID"],
      [{ body: { ...request, visibility: "public" } }, "INVALID_SCHEMA"],
      [{ body: { ...request, id: "agent_forged" } }, "INVALID_SCHEMA"],
      [{ body: { ...request, name: "   " } }, "INVALID_SCHEMA"],
      [{ body: [request] }, "INVALID_SCHEMA"],
      [{ raw: "{not json" }, "INVALID_BODY"],
      [
        {
          raw: JSON.stringify({ ...request, description: "x".repeat(40_000) }),
        },
        "INVALID_BODY",
      ],
    ] as const;
    for (const [init, code] of cases) {
      const response = await send("/api/agent-factory/constructions", init);
      expect(response.status).toBe(400);
      const body = (await response.json()) as Body;
      expect(body.issues.map(({ code }: { code: string }) => code)).toContain(
        code,
      );
      expect(body.retryable).toBe(false);
      expect(Object.keys(body).sort()).toEqual([
        "code",
        "constructionId",
        "error",
        "issues",
        "retryable",
      ]);
    }
    expect(llm.calls).toHaveLength(0);
    const unauthenticated = await send("/api/agent-factory/constructions", {
      user: "",
    });
    expect(unauthenticated.status).toBe(401);
    expect(llm.calls).toHaveLength(0);
  });

  test("A03 a required tool that does not exist is 422 with no rows", async () => {
    const { send, llm } = harness({
      generate: () => toolDraft([]),
      catalogue: () => ({ ok: true, value: { tools: [], skills: [] } }),
    });
    const key = randomUUID();
    const response = await send("/api/agent-factory/constructions", { key });
    expect(response.status).toBe(422);
    const body = (await response.json()) as Body;
    expect(body.code).toBe("BLOCKED_RESOURCE");
    expect(llm.calls).toHaveLength(1);
    expect(await rowsFor(factoryConstructionId(alice, key))).toEqual({
      agents: [],
      profiles: [],
    });
  });

  test("a LOW intent reading is 422 NEEDS_INPUT naming what is missing, with one call and no rows", async () => {
    const missing = ["what the assistant should do", "what it should return"];
    const { send, llm } = harness({
      generate: () => ({
        intent: {
          normalizedGoal: "Assist the user.",
          taskType: "general_assistance",
          explicitRequirements: [],
          inferredRequirements: [],
          confidence: "LOW",
          missingInformation: missing,
        },
      }),
    });
    const key = randomUUID();
    const response = await send("/api/agent-factory/constructions", { key });
    expect(response.status).toBe(422);
    const body = (await response.json()) as Body;
    expect(body.code).toBe("NEEDS_INPUT");
    expect(body.retryable).toBe(false);
    expect(
      body.issues.map(
        ({ path, message }: { path: string; message: string }) => [
          path,
          message,
        ],
      ),
    ).toEqual(
      missing.map((entry, index) => [
        `intent.missingInformation.${index}`,
        entry,
      ]),
    );
    expect(llm.calls).toHaveLength(1);
    expect(await rowsFor(factoryConstructionId(alice, key))).toEqual({
      agents: [],
      profiles: [],
    });
  });

  test("A04 an existing but ungranted tool is 202 pending with zero grants", async () => {
    const { send, llm } = harness({ generate: () => toolDraft() });
    const key = randomUUID();
    const response = await send("/api/agent-factory/constructions", { key });
    expect(response.status).toBe(202);
    const body = (await response.json()) as Body;
    const id = factoryConstructionId(alice, key);
    expect(body.readiness.state).toBe("pending_resources");
    expect(
      body.readiness.blockers.map(({ code }: { code: string }) => code),
    ).toEqual(["GRANT_REQUIRED"]);
    expect(body.agent.generated.state).toBe("pending_resources");
    expect(body.spec.resources.map(({ ref }: { ref: string }) => ref)).toEqual([
      toolRef,
    ]);
    expect(llm.calls).toHaveLength(2);
    const [row] = (await rowsFor(id)).agents;
    expect(((row?.configuration ?? {}) as Body).factory.state).toBe(
      "pending_resources",
    );
    expect(
      await database
        .select()
        .from(pluginGrants)
        .where(eq(pluginGrants.agentId, id)),
    ).toEqual([]);
  });

  test("A05 semantic failure after one repair, and repeated invalid output, are 422 with no rows", async () => {
    const failing = {
      verdict: "FAIL",
      findings: [
        {
          code: "INTENT_MISMATCH",
          path: "generatedSkill.procedure",
          evidenceRefs: ["request.description"],
          message: "Missing step.",
        },
      ],
    };
    for (const [generate, review, calls] of [
      [() => draft(), () => failing, 4],
      [() => "not json", () => pass, 2],
    ] as const) {
      const { send, llm } = harness({ generate, review });
      const key = randomUUID();
      const response = await send("/api/agent-factory/constructions", { key });
      expect(response.status).toBe(422);
      const body = (await response.json()) as Body;
      expect(body.issues.map(({ code }: { code: string }) => code)).toContain(
        "ATTEMPTS_EXHAUSTED",
      );
      expect(body.retryable).toBe(false);
      expect(llm.calls).toHaveLength(calls);
      expect((await rowsFor(factoryConstructionId(alice, key))).agents).toEqual(
        [],
      );
    }
  });

  test("A06 model and catalogue dependency failures are 503 without provider text or rows", async () => {
    for (const options of [
      { generate: () => new Error("provider said: secret diagnostic body") },
      {
        catalogue: () =>
          ({
            ok: false,
            issues: [
              {
                code: "DEPENDENCY_UNAVAILABLE",
                path: "",
                sourceStage: "dependency",
                evidenceRefs: [],
                message: "Resource facts could not be read.",
              },
            ],
          }) as const,
      },
    ]) {
      const { send } = harness(options);
      const key = randomUUID();
      const response = await send("/api/agent-factory/constructions", { key });
      expect(response.status).toBe(503);
      const text = await response.text();
      expect(text).not.toContain("secret diagnostic");
      expect(JSON.parse(text).retryable).toBe(true);
      expect((await rowsFor(factoryConstructionId(alice, key))).agents).toEqual(
        [],
      );
    }
  });

  test("504 outer deadline: no later review call and no late save", async () => {
    let elapsed = 0;
    const { send, llm } = harness({
      now: () => elapsed,
      // The first call consumes the entire 90-second outer budget on the controlled clock.
      onCall: () => {
        elapsed = 90_001;
      },
    });
    const key = randomUUID();
    const response = await send("/api/agent-factory/constructions", { key });
    expect(response.status).toBe(504);
    const body = (await response.json()) as Body;
    expect(body).toMatchObject({ code: "DEADLINE_EXCEEDED", retryable: true });
    expect(llm.calls).toHaveLength(1);
    await Bun.sleep(20);
    expect((await rowsFor(factoryConstructionId(alice, key))).agents).toEqual(
      [],
    );
  });

  test("identical retry replays without model calls; a changed body is 409; a deleted result is 410", async () => {
    const { send, llm } = harness();
    const key = randomUUID();
    const first = await send("/api/agent-factory/constructions", { key });
    expect(first.status).toBe(201);
    const created = (await first.json()) as Body;
    const replay = await send("/api/agent-factory/constructions", { key });
    expect(replay.status).toBe(201);
    expect(await replay.json()).toEqual(created);
    expect(llm.calls).toHaveLength(2);
    const conflict = await send("/api/agent-factory/constructions", {
      key,
      body: { ...request, name: "Other" },
    });
    expect(conflict.status).toBe(409);
    expect(((await conflict.json()) as Body).code).toBe("IDEMPOTENCY_CONFLICT");
    // Another actor's identical key is a different construction.
    const other = await send("/api/agent-factory/constructions", {
      key,
      user: bob,
    });
    expect(other.status).toBe(201);
    expect(((await other.json()) as Body).agent.id).toBe(
      factoryConstructionId(bob, key),
    );
    await profiles.softDelete({ id: alice, role: "user" }, created.agent.id);
    const gone = await send("/api/agent-factory/constructions", { key });
    expect(gone.status).toBe(410);
    expect(llm.calls).toHaveLength(4);
    expect((await rowsFor(created.agent.id)).agents).toHaveLength(1);
  });
});

describe("GET and recheck", () => {
  test("A07 only the owner or an administrator can read or recheck; others see 404", async () => {
    const { send, factReads } = harness({ generate: () => toolDraft() });
    const created = (await (
      await send("/api/agent-factory/constructions")
    ).json()) as Body;
    const path = `/api/agent-factory/${created.agent.id}`;
    const recheck = { body: { specHash: created.verification.specHash } };
    for (const user of [bob]) {
      expect((await send(path, { user, method: "GET" })).status).toBe(404);
      expect((await send(`${path}/recheck`, { user, ...recheck })).status).toBe(
        404,
      );
    }
    const owner = await send(path, { method: "GET" });
    expect(owner.status).toBe(200);
    expect(((await owner.json()) as Body).spec).toEqual(created.spec);
    factReads.length = 0;
    const inspected = await send(path, { user: admin, method: "GET" });
    expect(inspected.status).toBe(200);
    const body = (await inspected.json()) as Body;
    expect(body.agent.mine).toBe(false);
    // Readiness is always the stored creator's facts, never the inspecting administrator's.
    expect(factReads).toEqual([alice]);
    expect(
      (await send(`${path}/recheck`, { user: admin, ...recheck })).status,
    ).toBe(409);
    expect(factReads).toEqual([alice, alice]);
    // A legacy agent is not a construction.
    const legacy = await profiles.create(
      { id: alice, role: "user" },
      {
        name: `legacy-${suite}`,
        title: "Legacy",
        roleDescription: "Legacy.",
        visibility: "private",
      },
    );
    expect(
      (await send(`/api/agent-factory/${legacy.id}`, { method: "GET" })).status,
    ).toBe(404);
  });

  test("recheck takes exactly {specHash}; a stale hash is 409 and pending stays 409 without model calls", async () => {
    const { send, llm } = harness({ generate: () => toolDraft() });
    const created = (await (
      await send("/api/agent-factory/constructions")
    ).json()) as Body;
    const path = `/api/agent-factory/${created.agent.id}/recheck`;
    for (const body of [
      {},
      { specHash: "not-a-hash" },
      { specHash: created.verification.specHash, grant: true },
    ])
      expect((await send(path, { body })).status).toBe(400);
    const stale = await send(path, { body: { specHash: "0".repeat(64) } });
    expect(stale.status).toBe(409);
    expect(((await stale.json()) as Body).code).toBe("SPEC_CHANGED");
    const pending = await send(path, {
      body: { specHash: created.verification.specHash },
    });
    expect(pending.status).toBe(409);
    expect(await pending.json()).toMatchObject({
      code: "RESOURCES_PENDING",
      retryable: false,
      issues: [{ code: "GRANT_REQUIRED" }],
    });
    expect(llm.calls).toHaveLength(2);
    const stored = parseAgentSpec(
      (
        ((await rowsFor(created.agent.id)).agents[0]?.configuration ??
          {}) as Body
      ).factory.spec,
    );
    expect(stored.ok && stored.value).toEqual(created.spec);
  });
});

describe("composition", () => {
  test("A08 legacy POST /api/agents is unchanged and the roster marks generated rows", async () => {
    const { send } = harness();
    const generated = (await (
      await send("/api/agent-factory/constructions")
    ).json()) as Body;
    const legacy = await send("/api/agents", {
      key: null,
      body: {
        name: `legacy-${suite}-post`,
        title: "Legacy",
        roleDescription: "Legacy role.",
        visibility: "private",
      },
    });
    expect(legacy.status).toBe(201);
    const legacyBody = (await legacy.json()) as Body;
    // Legacy precedence: the managed endpoint, as before; no generated facts.
    expect(legacyBody.agent.endpoint).toBe(managedEndpoint);
    // The legacy expression is untouched: this test config names no managed agent to compare with.
    expect(legacyBody.agent.builtIn).toBe(false);
    expect("generated" in legacyBody.agent).toBe(false);
    const [legacyRow] = (await rowsFor(legacyBody.agent.id)).agents;
    expect(legacyRow?.type).toBe("remote_ag_ui");
    const roster = (await (
      await send("/api/agents", { method: "GET", key: null })
    ).json()) as { agents: Body[] };
    const listed = roster.agents.find(({ id }) => id === generated.agent.id);
    expect(listed).toMatchObject({
      builtIn: true,
      endpoint: null,
      generated: { state: "ready", specHash: generated.verification.specHash },
    });
    expect(listed).not.toHaveProperty("spec");
    // The legacy edit/copy paths refuse the generated row with the stable code.
    for (const [path, method, body] of [
      [
        `/api/agents/${generated.agent.id}`,
        "PATCH",
        { ...request, title: "x", roleDescription: "x", visibility: "private" },
      ],
      [`/api/agents/${generated.agent.id}/duplicate`, "POST", {}],
    ] as const) {
      const response = await send(path, { method, body, key: null });
      expect(response.status).toBe(409);
      expect(((await response.json()) as Body).code).toBe(
        "GENERATED_CONFIGURATION_IMMUTABLE",
      );
    }
  });

  test("the factory is unmounted without a service and never shadows /api/agents/:agentId", async () => {
    const { send } = harness({ mount: false });
    expect((await send("/api/agent-factory/constructions")).status).toBe(404);
    const { send: mounted } = harness();
    const response = await mounted("/api/agents/agent-factory", {
      method: "GET",
      key: null,
    });
    expect(response.status).toBe(404);
    expect(((await response.json()) as Body).error).toBe("Agent not found.");
  });
});

/*
 * A10/A11: the approval path the UI drives is the existing grant route, with the real PluginStore
 * behind both it and the factory's readiness facts. A person-OAuth catalogue app, so readiness
 * depends on the stored creator's own connection.
 */
describe("approval authority", () => {
  const driveRef = "google-drive/search_files";
  const clientId = randomUUID();
  const adminTokenId = randomUUID();
  const aliceTokenId = randomUUID();
  const plugins = createPluginStore({
    database,
    auditStore: createAuditStore(database),
    credentials: createCredentialStore(database),
    encryptionKey: "x".repeat(44),
    policy: () => ({ mode: "enforce", deny: [], allow: ["true"] }),
  });
  const driveDraft = () => ({ ...toolDraft([driveRef]), toolArguments: [] });
  const codes = (issues: { code: string }[]) =>
    issues.map(({ code }) => code).sort();
  const grantsFor = (agentId: string) =>
    database
      .select()
      .from(pluginGrants)
      .where(eq(pluginGrants.agentId, agentId));

  beforeAll(async () => {
    await database.insert(credentials).values([
      {
        id: clientId,
        kind: "mcp_oauth_client",
        provider: "google-drive",
        encryptedValue: "SYNTHETIC_CLIENT",
        keyId: `factory_routes_client_${suite}`,
        metadata: {},
      },
      ...[
        [adminTokenId, admin],
        [aliceTokenId, alice],
      ].map(([id, owner]) => ({
        id: id as string,
        kind: "mcp_user_token" as const,
        provider: "google-drive",
        encryptedValue: "SYNTHETIC_TOKEN",
        keyId: owner as string,
        metadata: {},
      })),
    ]);
    await database.insert(mcpServers).values({
      id: "google-drive",
      title: "Google Drive",
      vendor: "Google",
      url: "https://www.googleapis.com/drive/v3",
      provenance: "first-party",
      credentialId: clientId,
    });
    await database.insert(mcpTools).values({
      serverId: "google-drive",
      name: "search_files",
      description: "Search files.",
      inputSchema: { type: "object", properties: {} },
      effect: "read",
    });
    // The administrator is connected to the vendor; the creator is not, yet.
    await database.insert(mcpUserCredentials).values({
      serverId: "google-drive",
      userId: admin,
      credentialId: adminTokenId,
      scope: "read",
    });
  });
  afterAll(async () => {
    await database.delete(pluginGrants).where(eq(pluginGrants.ref, driveRef));
    await database.delete(mcpServers).where(eq(mcpServers.id, "google-drive"));
    await database
      .delete(credentials)
      .where(inArray(credentials.id, [clientId, adminTokenId, aliceTokenId]));
  });

  test("A10 a non-admin creator's forged MCP grant is refused and the agent stays pending", async () => {
    const { send } = harness({ plugins, generate: driveDraft });
    const created = await send("/api/agent-factory/constructions");
    expect(created.status).toBe(202);
    const body = (await created.json()) as Body;
    const id = body.agent.id as string;
    expect(codes(body.readiness.blockers)).toEqual([
      "CONNECTION_REQUIRED",
      "GRANT_REQUIRED",
    ]);
    // Exactly what the UI's Approve button sends, crafted by the creator themselves.
    const forged = await send("/api/plugins/grants", {
      key: null,
      body: { kind: "mcp", ref: driveRef, agentId: id },
    });
    expect(forged.status).toBe(403);
    expect(((await forged.json()) as Body).error).toBe(
      "An administrator decides which Bots may reach a tool.",
    );
    expect(await grantsFor(id)).toEqual([]);
    // The factory has no grant path of its own, and recheck cannot carry one.
    expect(
      (await send(`/api/agent-factory/${id}/grants`, { key: null })).status,
    ).toBe(404);
    const recheck = await send(`/api/agent-factory/${id}/recheck`, {
      key: null,
      body: { specHash: body.verification.specHash },
    });
    expect(recheck.status).toBe(409);
    expect(codes(((await recheck.json()) as Body).issues)).toEqual([
      "CONNECTION_REQUIRED",
      "GRANT_REQUIRED",
    ]);
    expect(await grantsFor(id)).toEqual([]);
  });

  test("A11 an administrator's grant and own connection cannot clear the creator's connection prerequisite", async () => {
    const { send } = harness({ plugins, generate: driveDraft });
    const body = (await (
      await send("/api/agent-factory/constructions")
    ).json()) as Body;
    const id = body.agent.id as string;
    const specHash = body.verification.specHash as string;
    const granted = await send("/api/plugins/grants", {
      user: admin,
      key: null,
      body: { kind: "mcp", ref: driveRef, agentId: id },
    });
    expect(granted.status).toBe(200);
    expect(await grantsFor(id)).toHaveLength(1);
    // Granted now, but the administrator's own account does not stand in for the creator's.
    for (const user of [admin, alice]) {
      const recheck = await send(`/api/agent-factory/${id}/recheck`, {
        user,
        key: null,
        body: { specHash },
      });
      expect(recheck.status).toBe(409);
      expect(codes(((await recheck.json()) as Body).issues)).toEqual([
        "CONNECTION_REQUIRED",
      ]);
    }
    const inspected = (await (
      await send(`/api/agent-factory/${id}`, { user: admin, method: "GET" })
    ).json()) as Body;
    expect(inspected.readiness.state).toBe("pending_resources");
    expect(inspected.agent.generated.state).toBe("pending_resources");
    // The creator connects their own account; only then does a recheck make it ready.
    await database.insert(mcpUserCredentials).values({
      serverId: "google-drive",
      userId: alice,
      credentialId: aliceTokenId,
      scope: "read",
    });
    const ready = await send(`/api/agent-factory/${id}/recheck`, {
      key: null,
      body: { specHash },
    });
    expect(ready.status).toBe(200);
    expect(((await ready.json()) as Body).agent.generated.state).toBe("ready");
  });
});

// Real loopback HTTP at the new boundary, real dedicated DB at the existing BE boundary.
describe("BE -> standalone Factory HTTP", () => {
  const token = "test-only-service-token-0123456789";

  test("creates, persists, replays, reads and rechecks without rebuilding; auth stays in BE", async () => {
    const llm = model(() => draft());
    let httpCalls = 0;
    const handler = createFactoryHandler({
      token,
      modelRef: "remote/fixture",
      complete: llm.complete,
    });
    const remote = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch: async (input) => {
        httpCalls++;
        const body = await input.clone().json();
        expect(body.catalogue.tools[0]).not.toHaveProperty("fingerprint");
        return handler(input);
      },
    });
    try {
      const { send, audits } = harness({
        remote: { url: remote.url.href, token },
      });
      expect(
        (await send("/api/agent-factory/constructions", { user: "" })).status,
      ).toBe(401);
      expect(httpCalls).toBe(0);
      const key = randomUUID();
      const response = await send("/api/agent-factory/constructions", { key });
      expect(response.status).toBe(201);
      const body = (await response.json()) as Body;
      const id = body.agent.id;
      expect(body.agent.generated.state).toBe("ready");
      expect(body.verification.semanticReview.modelRef).toBe("remote/fixture");
      const rows = await rowsFor(id);
      expect(rows.agents).toHaveLength(1);
      expect(rows.profiles).toHaveLength(1);
      expect((rows.agents[0]!.configuration as Body).factory.spec).toEqual(
        body.spec,
      );
      expect(
        (await send("/api/agent-factory/constructions", { key })).status,
      ).toBe(201);
      expect(
        (
          await send("/api/agent-factory/constructions", {
            key,
            body: { ...request, name: "Different" },
          })
        ).status,
      ).toBe(409);
      expect(
        (await send(`/api/agent-factory/${id}`, { method: "GET" })).status,
      ).toBe(200);
      expect(
        (await send(`/api/agent-factory/${id}`, { method: "GET", user: bob }))
          .status,
      ).toBe(404);
      expect(
        (
          await send(`/api/agent-factory/${id}/recheck`, {
            body: { specHash: body.verification.specHash },
          })
        ).status,
      ).toBe(200);
      expect(httpCalls).toBe(1);
      expect(llm.calls).toHaveLength(2);
      expect(audits.some(({ eventType }) => eventType === "bot.created")).toBe(
        true,
      );
      expect(JSON.stringify(audits)).not.toContain(token);
    } finally {
      remote.stop(true);
    }
  });

  test("a remote tool binding stays pending until BE observes the owner's grant", async () => {
    const llm = model(() => toolDraft());
    const remote = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch: createFactoryHandler({
        token,
        modelRef: "fixture",
        complete: llm.complete,
      }),
    });
    try {
      const facts = { granted: false, connected: true, configured: true };
      const { send } = harness({
        remote: { url: remote.url.href, token },
        facts,
      });
      const response = await send("/api/agent-factory/constructions");
      expect(response.status).toBe(202);
      const body = (await response.json()) as Body;
      const path = `/api/agent-factory/${body.agent.id}/recheck`;
      const input = { body: { specHash: body.verification.specHash } };
      expect(body.spec.resources[0].ref).toBe(toolRef);
      expect((await send(path, input)).status).toBe(409);
      facts.granted = true;
      expect((await send(path, input)).status).toBe(200);
      expect(llm.calls).toHaveLength(2);
    } finally {
      remote.stop(true);
    }
  });

  test("a default tool BE declares crosses HTTP, is stored with the generated skill, blocks nothing and grants nothing", async () => {
    // Stands in for whatever knowledge-retrieval tool BE registers; the Factory knows no such ref.
    const knowledge = {
      ...tool,
      ref: "kb/query",
      name: "query",
      title: "Knowledge",
      description: "Retrieve passages from internal documents.",
    };
    const llm = model(() => draft());
    let sent: Body | undefined;
    const handler = createFactoryHandler({
      token,
      modelRef: "remote/fixture",
      complete: llm.complete,
    });
    const remote = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch: async (input) => {
        sent = (await input.clone().json()) as Body;
        return handler(input);
      },
    });
    try {
      const { send, factReads } = harness({
        remote: { url: remote.url.href, token },
        catalogue: () => ({
          ok: true,
          value: {
            tools: [tool, knowledge],
            // Still projected by BE; it must not cross the wire or matter.
            skills: [
              {
                kind: "skill",
                ref: "notes-method",
                title: "Notes",
                description: "A method.",
                instructions: "Summarize.",
                toolRefs: [],
              },
            ],
            defaultToolRefs: ["kb/query"],
          },
        }),
      });
      const response = await send("/api/agent-factory/constructions");
      // Ready at once: the default tool is offered, not required, so there is nothing to grant.
      expect(response.status).toBe(201);
      const body = (await response.json()) as Body;
      const id: string = body.agent.id;
      expect(sent?.catalogue.defaultToolRefs).toEqual(["kb/query"]);
      expect(sent?.catalogue).not.toHaveProperty("skills");
      expect(body.spec.schemaVersion).toBe(2);
      expect(body.spec.resources).toEqual([]);
      expect(body.spec.defaultTools.map(({ ref }: Body) => ref)).toEqual([
        "kb/query",
      ]);
      expect(body.verification.warnings).toEqual([]);
      expect(body.spec.generatedSkill.procedure).toEqual([
        "Ask for notes when missing.",
        "Return a concise summary.",
      ]);
      expect(body.readiness).toEqual({ state: "ready", blockers: [] });
      // Persisted as one verified artifact, and that stored prompt is what the runtime runs.
      const [row] = (await rowsFor(id)).agents;
      const configuration = row!.configuration as Body;
      expect(configuration.factory.spec).toEqual(body.spec);
      expect(configuration.factory.verification.specHash).toBe(
        hashAgentSpec(body.spec),
      );
      expect(configuration.systemPrompt).toBe(renderCorePrompt(body.spec));
      const runnable = registeredAgentFromRow({
        id,
        name: row!.name,
        type: "built_in",
        configuration,
        title: "",
        roleDescription: "",
      });
      expect(runnable).toMatchObject({ type: "built_in" });
      const prompt = (runnable as { systemPrompt: string }).systemPrompt;
      for (const text of [
        "## Procedure",
        "Return a concise summary.",
        "## Completion criteria",
        '## Default tools (available; use one only when the task needs it)\n["kb/query"]',
      ])
        expect(prompt).toContain(text);
      expect(
        await database
          .select()
          .from(pluginGrants)
          .where(eq(pluginGrants.agentId, id)),
      ).toEqual([]);
      // Readiness was read for the owner and asked about no resource at all.
      expect(factReads).toEqual([alice]);
      expect(llm.calls).toHaveLength(2);
    } finally {
      remote.stop(true);
    }
  });

  test("unavailable, unauthenticated and corrupt remote responses never persist an agent", async () => {
    const llm = model(() => draft());
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: llm.complete,
    });
    let mode: "corrupt" | "unavailable" | "auth" = "corrupt";
    let httpCalls = 0;
    const remote = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch: async (input) => {
        httpCalls++;
        if (mode === "unavailable")
          return new Response("private service diagnostics", { status: 500 });
        if (mode === "auth") return handler(input);
        const response = await handler(input);
        return Response.json({
          ...(await response.json()),
          systemPrompt: "tampered",
        });
      },
    });
    const url = remote.url.href;
    try {
      for (const failure of ["corrupt", "unavailable", "auth"] as const) {
        mode = failure;
        const { send } = harness({
          remote: {
            url,
            token:
              failure === "auth"
                ? "wrong-token-012345678901234567890123"
                : token,
          },
        });
        const key = randomUUID();
        const response = await send("/api/agent-factory/constructions", {
          key,
        });
        expect(response.status).toBe(failure === "corrupt" ? 409 : 503);
        expect(await response.text()).not.toContain(
          "private service diagnostics",
        );
        expect(
          (await rowsFor(factoryConstructionId(alice, key))).agents,
        ).toHaveLength(0);
        expect(
          (await rowsFor(factoryConstructionId(alice, key))).profiles,
        ).toHaveLength(0);
      }
      expect(httpCalls).toBe(3); // No retry or in-process fallback.
    } finally {
      remote.stop(true);
    }
    const { send } = harness({ remote: { url, token } });
    const key = randomUUID();
    expect(
      (await send("/api/agent-factory/constructions", { key })).status,
    ).toBe(503);
    expect(
      (await rowsFor(factoryConstructionId(alice, key))).agents,
    ).toHaveLength(0);
  });
});
