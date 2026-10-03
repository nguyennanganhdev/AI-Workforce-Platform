import { afterAll, beforeAll, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import type { AbstractAgent } from "@ag-ui/client";
import { LLMock } from "@copilotkit/aimock";
import { and, eq, inArray, sql } from "drizzle-orm";
import { Hono } from "hono";
import { COMPUTER_GUIDANCE } from "../../shared/bot-prompt.js";
import type {
  AgentDraft,
  AgentSpec,
  FactoryCatalogue,
} from "../../agent-factory/src/contracts.js";
import {
  createAgentFactoryService,
  createFactoryRuntimeReadiness,
  readFactoryCatalogue,
} from "../src/agents/factory.js";
import { createAgentFactoryRoutes } from "../src/agents/factory-routes.js";
import { createAgentProfileStore } from "../src/agents/profile-store.js";
import type { AgentActor } from "../src/agents/profile-types.js";
import { createRuntimeAgentLoader } from "../src/agents/runtime-agents.js";
import { createAuditStore } from "../src/audit.js";
import type { AppVariables } from "../src/auth/guards.js";
import { resolveRuntimeAgents } from "../src/copilot.js";
import { createCredentialStore } from "../src/credentials.js";
import { createDatabase } from "../src/db/client.js";
import {
  agents,
  auditEvents,
  mcpServers,
  mcpTools,
  users,
} from "../src/db/schema/index.js";
import { createPluginRoutes } from "../src/plugins/routes.js";
import { createPluginStore } from "../src/plugins/store.js";
import {
  grantedSkills,
  grantedTools,
  REFUSAL_MARKER,
} from "../src/plugins/tools.js";
import { withRecordedIntent } from "../../agent-factory/tests/fixtures/factory-intent.js";
import { TEST_POOL, testDatabaseUrl } from "./support/database.js";

/*
 * The Web Researcher path, end to end below the browser: Tavily added from the catalogue through
 * `PluginStore.addServer`, the coworker created through the factory API from three fields with its
 * research method generated rather than selected (this suite installs no skill at all), the one
 * tool granted through the existing grant route, and one real BuiltInAgent turn that calls
 * `tavily/tavily_search` through `PluginStore.callTool`. Only two boundaries are fixtures: the
 * model (LLMock) and Tavily's HTTP endpoint.
 */
const database = createDatabase(testDatabaseUrl(), TEST_POOL);
const suite = randomUUID().slice(0, 8);
const alice = `tavily_alice_${suite}`;
const admin = `tavily_admin_${suite}`;
const roles: Record<string, AgentActor["role"]> = {
  [alice]: "user",
  [admin]: "admin",
};
const actor = (id: string): AgentActor => ({ id, role: roles[id] ?? "user" });
const toolRef = "tavily/tavily_search";
const TAVILY_URL = "https://api.tavily.com/search";
// Shaped like a key and unmistakable in an assertion; never a real one.
const KEY = `tvly-TEST-${suite}-never-real`;
const model = { provider: "openai" as const, defaultModel: "fixture-model" };

const store = createPluginStore({
  database,
  auditStore: createAuditStore(database),
  credentials: createCredentialStore(database),
  encryptionKey: "x".repeat(44),
  policy: () => ({ mode: "enforce", deny: [], allow: ["true"] }),
});
const profiles = createAgentProfileStore(database, undefined);
// The production gate, exactly as index.ts injects it.
const loader = createRuntimeAgentLoader(
  database,
  undefined,
  undefined,
  createFactoryRuntimeReadiness(store),
);

const request = {
  name: "Web Researcher",
  role: "Internet Research Agent",
  description: [
    "Research information on the Internet based on the user's request.",
    "Find relevant sources, compare information from multiple sources,",
    "identify uncertainty or conflicting claims, and return a concise",
    "research report with source URLs. Do not invent unsupported facts.",
  ].join("\n"),
};
const quoted = (quote: string) =>
  ({ kind: "request", field: "description", quote }) as const;

const STEPS = [
  "Turn the request into specific search queries.",
  "Search the web and read at least three sources.",
  "Compare the sources and name conflicts or uncertainty.",
  "Write a concise report with the URL beside each claim.",
];

/**
 * What a model would answer, built ONLY from the catalogue the factory put in its prompt: the tool
 * is whichever one is named `tavily_search`, and the skill is written here, for this request,
 * guiding that tool and no other. Nothing names a ref the catalogue did not supply, so a catalogue
 * missing the tool produces a draft the resolver refuses.
 */
function draftFrom(catalogue: FactoryCatalogue): AgentDraft {
  const tool = catalogue.tools.find(({ name }) => name === "tavily_search");
  return {
    goal: "Research a question on the Internet and report what the sources say.",
    responsibilities: [
      {
        statement: "Research information on the Internet for the request.",
        source: quoted("Research information on the Internet"),
      },
      {
        statement: "Compare information from multiple sources.",
        source: quoted("compare information from multiple sources"),
      },
      {
        statement: "Identify uncertainty or conflicting claims.",
        source: quoted("identify uncertainty or conflicting claims"),
      },
      {
        statement: "Return a concise research report with source URLs.",
        source: quoted("research report with source URLs"),
      },
    ],
    constraints: [
      {
        statement: "Do not invent unsupported facts.",
        source: quoted("Do not invent unsupported facts"),
      },
    ],
    generatedSkill: {
      name: "Sourced web research",
      objective:
        "Answer a research request from several web sources, each claim beside its URL.",
      procedure: STEPS,
      toolUsageGuidance: tool
        ? [
            {
              toolRef: tool.ref,
              whenToUse: "For every search query the request turns into.",
              purpose: "Find sources on the public web.",
              guidance:
                "Send one focused query at a time, keep each result's url with its extract, and search again when fewer than three sources cover a point.",
            },
          ]
        : [],
      constraints: ["State nothing that no retrieved source supports."],
      completionCriteria: ["Every claim names the URL of its source."],
    },
    requirements: [
      {
        need: "Search the public web for relevant sources.",
        fulfillment: "tool",
        source: quoted("Find relevant sources"),
        proposedRefs: tool ? [tool.ref] : [],
      },
      {
        need: "Compare the sources and write the report.",
        fulfillment: "model_on_input",
        source: quoted("compare information from multiple sources"),
        proposedRefs: [],
      },
    ],
    toolArguments: tool
      ? [
          {
            ref: tool.ref,
            argument: "query",
            sourceKind: "user_input",
            sourceRef: "research request",
            missingBehavior: "Ask what to research.",
          },
        ]
      : [],
    inputFacts: [
      {
        name: "research request",
        required: true,
        missingBehavior: "Ask what to research.",
      },
    ],
    outputExpectations: ["A concise research report with source URLs."],
    unresolvedQuestions: [],
    unsupportedRequirements: [],
  };
}

const prompts: string[] = [];
const service = createAgentFactoryService({
  store,
  profiles,
  modelRef: "fixture/model",
  complete: async (prompt) => {
    prompts.push(prompt);
    if (prompt.startsWith("FACTORY_REVIEW"))
      return JSON.stringify({ verdict: "PASS", findings: [] });
    const data = JSON.parse(prompt.slice(prompt.indexOf("DATA_JSON=") + 10));
    return JSON.stringify(withRecordedIntent(draftFrom(data.catalogue)));
  },
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
app.route("/api/agent-factory", createAgentFactoryRoutes(service, requireUser));
app.route(
  "/api/plugins",
  createPluginRoutes(store, requireUser, async () => true),
);
async function call(
  method: string,
  path: string,
  user: string,
  body?: unknown,
  headers: Record<string, string> = {},
) {
  const response = await app.request(`http://test${path}`, {
    method,
    headers: { "content-type": "application/json", "x-user": user, ...headers },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return {
    status: response.status,
    // biome-ignore lint/suspicious/noExplicitAny: response bodies are asserted field by field.
    body: (await response.json().catch(() => null)) as any,
  };
}

/** The production built-in path for one Bot, with the same tool loading a run uses. */
async function built(agentId: string): Promise<AbstractAgent> {
  const resolved = await resolveRuntimeAgents(
    () => loader(actor(alice)),
    model,
    async () => "synthetic-model-key",
    undefined,
    (botId) => grantedTools({ store, botId, actorId: alice }),
    undefined,
    COMPUTER_GUIDANCE,
    undefined,
    undefined,
    undefined,
    undefined,
    agentId,
  );
  const agent = resolved[agentId]?.clone();
  if (!agent) throw new Error(`no ${agentId} was built`);
  return agent;
}

const realFetch = globalThis.fetch;
const realKey = process.env.TAVILY_API_KEY;
const tavilyRequests: { headers: unknown; body: unknown }[] = [];
const SOURCES = [
  "https://docs.temporal.io/temporal",
  "https://docs.temporal.io/workflows",
  "https://temporal.io/blog/workflow-engine-principles",
];
let createdAgentId: string | undefined;

async function auditFor(eventType: string) {
  return database
    .select({ payload: auditEvents.payload })
    .from(auditEvents)
    .where(
      and(
        eq(auditEvents.eventType, eventType),
        eq(auditEvents.targetId, toolRef),
        sql`${auditEvents.payload}->>'bot' = ${createdAgentId ?? ""}`,
      ),
    );
}

beforeAll(async () => {
  process.env.TAVILY_API_KEY = KEY;
  // Only Tavily's address is a fixture; the model fixture and everything else stay real requests.
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input) !== TAVILY_URL) return realFetch(input, init);
    tavilyRequests.push({
      headers: init?.headers,
      body: JSON.parse(String(init?.body)),
    });
    return new Response(
      JSON.stringify({
        results: SOURCES.map((url, index) => ({
          title: `Temporal source ${index + 1}`,
          url,
          content: `Extract ${index + 1} about durable execution.`,
          score: 0.9,
        })),
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  await database
    .insert(users)
    .values([alice, admin].map((id) => ({ id, email: `${id}@example.test` })));
});

afterAll(async () => {
  globalThis.fetch = realFetch;
  if (realKey === undefined) delete process.env.TAVILY_API_KEY;
  else process.env.TAVILY_API_KEY = realKey;
  if (createdAgentId)
    await database.delete(agents).where(eq(agents.id, createdAgentId));
  await database.delete(mcpServers).where(eq(mcpServers.id, "tavily"));
  await database.delete(users).where(inArray(users.id, [alice, admin]));
  await database.$client.close();
});

test("Tavily is discovered from the catalogue: one read tool, no credential row, no vendor call", async () => {
  const added = await store.addServer({ key: "tavily", by: admin });
  expect(added).toMatchObject({ id: "tavily", title: "Tavily" });

  const [row] = await database
    .select()
    .from(mcpServers)
    .where(eq(mcpServers.id, "tavily"));
  expect(row).toMatchObject({
    url: TAVILY_URL,
    provenance: "first-party",
    credentialId: null,
    lastError: null,
  });
  const tools = await database
    .select()
    .from(mcpTools)
    .where(eq(mcpTools.serverId, "tavily"));
  expect(tools.map(({ name, effect }) => [name, effect])).toEqual([
    ["tavily_search", "read"],
  ]);
  // Listing is this deployment's own code: adding the connector asked Tavily nothing.
  expect(tavilyRequests).toHaveLength(0);
  expect(JSON.stringify([row, tools])).not.toContain(KEY);
});

test("construction sees the search tool and no skill: none is installed, and none would be read", async () => {
  const catalogue = await readFactoryCatalogue(store, {
    id: alice,
    isAdmin: false,
  });
  if (!catalogue.ok) throw new Error(JSON.stringify(catalogue.issues));
  expect(
    catalogue.value.tools.find(({ ref }) => ref === toolRef),
  ).toMatchObject({
    kind: "tool",
    name: "tavily_search",
    title: "Tavily",
    effect: "read",
    destructive: false,
    inputSchema: { required: ["query"] },
  });
  expect(Object.keys(catalogue.value).sort()).toEqual([
    "defaultToolRefs",
    "tools",
  ]);
  // What the model is shown carries no key, no address and no credential field.
  const exposed = JSON.stringify(catalogue.value);
  expect(exposed).not.toContain(KEY);
  expect(exposed).not.toContain("api.tavily.com");
  expect(exposed).not.toMatch(/credential|authorization|bearer/i);
});

test("three fields → the factory resolves the tool and generates the skill → pending → existing grant → ready → a real turn searches Tavily", async () => {
  const response = await call(
    "POST",
    "/api/agent-factory/constructions",
    alice,
    request,
    { "idempotency-key": randomUUID() },
  );
  // Verified and saved, but not runnable: discovery is not authorization.
  expect(response.status).toBe(202);
  const id: string = response.body.agent.id;
  createdAgentId = id;
  const spec: AgentSpec = response.body.spec;
  expect(spec.identity).toEqual(request);
  expect(
    spec.resources.map(({ kind, ref }) => `${kind}:${ref}`).sort(),
  ).toEqual([`tool:${toolRef}`]);
  // The research method is part of the verified artifact, not a resource to be granted.
  if (spec.schemaVersion !== 2) throw new Error("expected a generated skill");
  expect(spec.generatedSkill.procedure).toEqual(STEPS);
  expect(spec.generatedSkill.toolUsageGuidance.map((g) => g.toolRef)).toEqual([
    toolRef,
  ]);
  expect(spec.defaultTools).toEqual([]);
  expect(response.body.verification.warnings).toEqual([
    expect.objectContaining({ code: "NO_DEFAULT_TOOL" }),
  ]);
  expect(
    spec.resources.find(({ kind }) => kind === "tool")?.argumentSources,
  ).toEqual([
    {
      argument: "query",
      sourceKind: "user_input",
      sourceRef: "research request",
      missingBehavior: "Ask what to research.",
    },
  ]);
  expect(response.body.verification).toMatchObject({
    construction: "PASS",
    attempts: 1,
  });
  expect(response.body.readiness.state).toBe("pending_resources");
  expect(
    response.body.readiness.blockers
      .map(
        ({ code, evidenceRefs }: { code: string; evidenceRefs: string[] }) =>
          `${code}:${evidenceRefs[0]}`,
      )
      .sort(),
  ).toEqual([`GRANT_REQUIRED:${toolRef}`]);

  // The refs came from the catalogue in the generation prompt, and the factory granted nothing.
  expect(
    prompts.filter((prompt) => prompt.startsWith("FACTORY_GENERATE")),
  ).toHaveLength(1);
  expect(prompts.join("\n")).not.toContain(KEY);
  expect(prompts.join("\n")).not.toContain("skill_instruction");
  expect(await store.listForAgent(id)).toEqual({ tools: [], skills: [] });
  expect(
    (await loader(actor(alice))).find((agent) => agent.id === id)?.type,
  ).toBe("unavailable");

  // The existing grant route, as an administrator, for exactly the one displayed resource.
  expect(
    (
      await call("POST", "/api/plugins/grants", alice, {
        kind: "mcp",
        ref: toolRef,
        agentId: id,
      })
    ).status,
  ).toBe(403);
  expect(
    (
      await call("POST", "/api/plugins/grants", admin, {
        kind: "mcp",
        ref: toolRef,
        agentId: id,
      })
    ).status,
  ).toBe(200);
  const rechecked = await call(
    "POST",
    `/api/agent-factory/${id}/recheck`,
    alice,
    { specHash: response.body.verification.specHash },
  );
  expect(rechecked.status).toBe(200);
  expect(rechecked.body.readiness).toEqual({ state: "ready", blockers: [] });

  // What the existing runtime loads for this Bot: no skill grant, and the tool under its runtime name.
  expect(await grantedSkills({ store, botId: id })).toEqual([]);
  const [tool] = await grantedTools({ store, botId: id, actorId: alice });
  expect(tool).toMatchObject({
    name: "mcp__tavily__tavily_search",
    ref: toolRef,
  });
  if (!tool) throw new Error("the granted tool must be offered");

  const recorder = new LLMock();
  const previousBase = process.env.OPENAI_BASE_URL;
  try {
    process.env.OPENAI_BASE_URL = await recorder.start();
    recorder.onToolResult("call_search", {
      content: `Temporal is a durable execution platform. Sources: ${SOURCES.join(" ")}`,
    });
    recorder.onMessage(/Temporal/, {
      toolCalls: [
        {
          id: "call_search",
          name: tool.name,
          arguments: JSON.stringify({
            query: "Temporal architecture",
            max_results: 3,
          }),
        },
      ],
    });
    const agent = await built(id);
    agent.addMessage({
      id: randomUUID(),
      role: "user",
      content: "Research Temporal's architecture.",
    });
    await agent.runAgent();
    expect(agent.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: expect.stringContaining(SOURCES[0] as string),
    });

    const sent = recorder.getRequests().map(({ body }) => JSON.stringify(body));
    expect(sent).toHaveLength(2);
    // The model was offered the tool, on the compiled prompt, and then read the normalized results.
    expect(sent[0]).toContain("mcp__tavily__tavily_search");
    expect(sent[0]).toContain("Web Researcher");
    // The generated skill reaches the runtime as part of the stored prompt: every step, and the
    // guidance for the one tool it may call. Nothing asked the Factory again.
    for (const step of STEPS) expect(sent[0]).toContain(step);
    expect(sent[0]).toContain("Tool usage guidance");
    expect(sent[0]).toContain("search again when fewer than three sources");
    for (const url of SOURCES) expect(sent[1]).toContain(url);
    expect(sent.join("\n")).not.toContain(KEY);
  } finally {
    if (previousBase === undefined) delete process.env.OPENAI_BASE_URL;
    else process.env.OPENAI_BASE_URL = previousBase;
    await recorder.stop();
  }

  // Exactly one vendor request: the key in the header, the model's arguments in the body.
  expect(tavilyRequests).toEqual([
    {
      headers: {
        authorization: `Bearer ${KEY}`,
        "content-type": "application/json",
      },
      body: { query: "Temporal architecture", max_results: 3 },
    },
  ]);
  const succeeded = await auditFor("mcp.call_succeeded");
  expect(succeeded).toHaveLength(1);
  expect(succeeded[0]?.payload).toMatchObject({
    actor: alice,
    server: "tavily",
    tool: "tavily_search",
    effect: "read",
    reachedAs: "deployment",
  });

  // Nothing persisted or recorded for this coworker carries the key.
  const [stored] = await database
    .select({ configuration: agents.configuration })
    .from(agents)
    .where(eq(agents.id, id));
  const trail = await database
    .select({ payload: auditEvents.payload })
    .from(auditEvents)
    .where(
      sql`${auditEvents.payload}::text like ${`%${id}%`} or ${auditEvents.targetId} in ('tavily', ${toolRef})`,
    );
  expect(trail.length).toBeGreaterThan(0);
  expect(JSON.stringify([response.body, stored, trail])).not.toContain(KEY);
});

test("without TAVILY_API_KEY the granted tool answers that search is not configured, and the trail records it", async () => {
  if (!createdAgentId) throw new Error("the coworker must exist");
  const [tool] = await grantedTools({
    store,
    botId: createdAgentId,
    actorId: alice,
  });
  if (!tool) throw new Error("the granted tool must be offered");
  const before = tavilyRequests.length;
  delete process.env.TAVILY_API_KEY;
  try {
    const answer = String(await tool.execute({ query: "anything" }));
    expect(answer).toContain("TAVILY_API_KEY is not set");
    expect(answer).not.toContain(REFUSAL_MARKER);
  } finally {
    process.env.TAVILY_API_KEY = KEY;
  }
  expect(tavilyRequests).toHaveLength(before);
  const failed = await auditFor("mcp.call_failed");
  expect(failed).toHaveLength(1);
  expect(JSON.stringify(failed)).toContain("TAVILY_API_KEY is not set");
  expect(JSON.stringify(failed)).not.toContain(KEY);
});

test("revoking the tool through the existing route blocks the next load and the direct call", async () => {
  if (!createdAgentId) throw new Error("the coworker must exist");
  const [tool] = await grantedTools({
    store,
    botId: createdAgentId,
    actorId: alice,
  });
  if (!tool) throw new Error("the granted tool must be offered");
  const before = tavilyRequests.length;
  expect(
    (
      await call(
        "DELETE",
        `/api/plugins/grants?kind=mcp&ref=${encodeURIComponent(toolRef)}&agentId=${encodeURIComponent(createdAgentId)}`,
        admin,
      )
    ).status,
  ).toBe(200);
  expect(
    (await loader(actor(alice))).find((agent) => agent.id === createdAgentId),
  ).toMatchObject({
    type: "unavailable",
    reason: expect.stringContaining("GRANT_REQUIRED"),
  });
  expect(String(await tool.execute({ query: "anything" }))).toContain(
    REFUSAL_MARKER,
  );
  expect(tavilyRequests).toHaveLength(before);
});
