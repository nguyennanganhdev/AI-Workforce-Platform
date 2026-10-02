import { afterEach, describe, expect, spyOn, test } from "bun:test";
import { LLMock } from "@copilotkit/aimock";
import { z } from "zod";
import { factoryCompletionOptions } from "../src/agents/factory";
import {
  normalizeModelBaseUrls,
  resolveRuntimeAgents,
  runtimeModelForEnvironment,
} from "../src/copilot";
import { encryptSecret, resolveModelApiKey } from "../src/credentials";
import {
  anthropicMessagesUrl,
  createModelCompleter,
  type ModelCallObservation,
} from "../src/routing/model";
import { validateTenantPackage } from "../src/tenant-package";

const encryptionKey = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
const originalEnvironment = {
  OPENAI_BASE_URL: process.env.OPENAI_BASE_URL,
  ANTHROPIC_BASE_URL: process.env.ANTHROPIC_BASE_URL,
};
afterEach(() => {
  for (const [key, value] of Object.entries(originalEnvironment)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

const packageModel = {
  provider: "openai" as const,
  defaultModel: "gpt-5.6-terra",
};
const anthropicModel = {
  provider: "anthropic" as const,
  defaultModel: "claude-sonnet-4-5",
};

describe("deployment API-key provider selection", () => {
  test("normalizes optional SDK base URLs and native selector URLs", () => {
    const environment = { OPENAI_BASE_URL: "", ANTHROPIC_BASE_URL: "  " };
    normalizeModelBaseUrls(environment);
    expect(environment).toEqual({});
    const custom = {
      OPENAI_BASE_URL: " https://openai.example/v1 ",
      ANTHROPIC_BASE_URL: " https://anthropic.example/v1 ",
    };
    normalizeModelBaseUrls(custom);
    expect(custom).toEqual({
      OPENAI_BASE_URL: "https://openai.example/v1",
      ANTHROPIC_BASE_URL: "https://anthropic.example/v1",
    });
    for (const [base, expected] of [
      ["https://gateway.example", "https://gateway.example/v1"],
      ["https://gateway.example/proxy", "https://gateway.example/proxy/v1"],
      [" https://gateway.example/proxy/ ", "https://gateway.example/proxy/v1"],
      ["https://gateway.example/proxy/v1/", "https://gateway.example/proxy/v1"],
      ["https://gateway.example/v2/", "https://gateway.example/v2"],
    ]) {
      const environment = { ANTHROPIC_BASE_URL: base };
      normalizeModelBaseUrls(environment);
      expect(environment.ANTHROPIC_BASE_URL).toBe(expected);
      expect(anthropicMessagesUrl(environment)).toBe(`${expected}/messages`);
      normalizeModelBaseUrls(environment);
      expect(environment.ANTHROPIC_BASE_URL).toBe(expected);
    }
    for (const value of [undefined, "", "  "]) {
      expect(anthropicMessagesUrl({ ANTHROPIC_BASE_URL: value })).toBe(
        "https://api.anthropic.com/v1/messages",
      );
    }
    for (const value of [
      "https://gateway.example",
      "https://gateway.example/v1",
      " https://gateway.example/v1/ ",
    ]) {
      expect(anthropicMessagesUrl({ ANTHROPIC_BASE_URL: value })).toBe(
        "https://gateway.example/v1/messages",
      );
    }
  });

  test("accepts an Anthropic tenant package without changing its credential reference", () => {
    const result = validateTenantPackage({
      brand: "tenant: { id: provider-test, product_name: Provider Test }",
      agents: "agents: []",
      channels: "channels: []",
      model:
        "model: { provider: anthropic, credential_secret_ref: primary-model, default_model: claude-sonnet-4-5 }",
      knowledge: "sources: []",
      themeCss: "",
    });
    expect(result.model).toEqual({
      ...anthropicModel,
      credentialSecretRef: "primary-model",
    });
  });

  test("the desktop Anthropic choice overrides the OpenAI package model", () => {
    expect(
      runtimeModelForEnvironment(packageModel, {
        BOT_PROVIDER: " anthropic ",
        BOT_MODEL: " claude-sonnet-4-5 ",
        OPENAI_BASE_URL: "",
      }),
    ).toEqual(anthropicModel);
    expect(
      runtimeModelForEnvironment(packageModel, {
        BOT_PROVIDER: "anthropic",
        BOT_MODEL: "",
      }),
    ).toEqual(anthropicModel);
  });

  test("an unset choice preserves the package while an empty desktop provider selects OpenAI", () => {
    expect(runtimeModelForEnvironment(anthropicModel, {})).toEqual(
      anthropicModel,
    );
    expect(
      runtimeModelForEnvironment(anthropicModel, {
        BOT_PROVIDER: "",
        BOT_MODEL: "",
      }),
    ).toEqual(packageModel);
    expect(
      runtimeModelForEnvironment(packageModel, {
        BOT_MODEL: "unselected-model",
      }),
    ).toEqual(packageModel);
    expect(
      runtimeModelForEnvironment(packageModel, {
        BOT_PROVIDER: "openai",
        BOT_MODEL: "local-model",
        OPENAI_BASE_URL: "http://localhost:11434/v1",
      }),
    ).toEqual({ provider: "openai", defaultModel: "local-model" });
  });

  test("credentials stay provider-scoped and a rotated stored key is read on the next call", async () => {
    let encryptedValue = await encryptSecret(
      encryptionKey,
      "stored-anthropic-one",
    );
    const asked: unknown[] = [];
    const resolve = () =>
      resolveModelApiKey({
        encryptionKey,
        provider: "anthropic",
        keyId: "primary-model",
        reader: {
          readModelSecret: async (input) => {
            asked.push(input);
            return { encryptedValue };
          },
        },
        environment: {
          OPENAI_API_KEY: "wrong-provider",
          ANTHROPIC_API_KEY: "environment-anthropic",
        },
      });
    expect(await resolve()).toBe("stored-anthropic-one");
    encryptedValue = await encryptSecret(encryptionKey, "stored-anthropic-two");
    expect(await resolve()).toBe("stored-anthropic-two");
    expect(asked).toEqual(
      Array(2).fill({ provider: "anthropic", keyId: "primary-model" }),
    );
    const noStored = {
      encryptionKey,
      provider: "anthropic" as const,
      keyId: "primary-model",
      reader: { readModelSecret: async () => null },
    };
    expect(
      await resolveModelApiKey({
        ...noStored,
        environment: {
          OPENAI_API_KEY: "wrong-provider",
          ANTHROPIC_API_KEY: " synthetic-anthropic ",
        },
      }),
    ).toBe("synthetic-anthropic");
    expect(
      await resolveModelApiKey({
        ...noStored,
        environment: { OPENAI_API_KEY: "wrong-provider" },
      }),
    ).toBeNull();
    await expect(
      resolveModelApiKey({
        ...noStored,
        reader: {
          readModelSecret: async () => ({ encryptedValue: "corrupt" }),
        },
        environment: { ANTHROPIC_API_KEY: "must-not-fallback" },
      }),
    ).rejects.toThrow("Credential envelope is invalid");
  });
});

test.each([
  { suffix: "", prefix: "" },
  { suffix: "/proxy", prefix: "/proxy" },
  { suffix: "/v1", prefix: "" },
  { suffix: "/proxy/v1/", prefix: "/proxy" },
])(
  "Anthropic built-ins execute tools with a rotated key and base suffix '$suffix'",
  async ({ suffix, prefix }) => {
    const mock = new LLMock();
    const executed: unknown[] = [];
    const keys: (string | null)[] = [];
    const paths: string[] = [];
    let proxy: ReturnType<typeof Bun.serve> | undefined;
    try {
      const base = await mock.start();
      proxy = Bun.serve({
        hostname: "127.0.0.1",
        port: 0,
        async fetch(request) {
          keys.push(request.headers.get("x-api-key"));
          const path = new URL(request.url).pathname;
          paths.push(path);
          return fetch(`${base}${path.slice(prefix.length)}`, {
            method: "POST",
            headers: request.headers,
            body: await request.text(),
          });
        },
      });
      process.env.ANTHROPIC_BASE_URL = `${proxy.url.origin}${suffix}`;
      normalizeModelBaseUrls();
      process.env.OPENAI_BASE_URL = base;
      mock.on({ hasToolResult: true }, { content: "The balance is 42." });
      mock.onMessage(/balance/, {
        toolCalls: [
          {
            id: "balance-call",
            name: "read_balance",
            arguments: { account: "demo" },
          },
        ],
      });
      const model = runtimeModelForEnvironment(packageModel, {
        BOT_PROVIDER: "anthropic",
        BOT_MODEL: "claude-sonnet-4-5",
      });
      let encryptedValue = await encryptSecret(
        encryptionKey,
        "stored-anthropic-one",
      );
      const resolve = () =>
        resolveModelApiKey({
          encryptionKey,
          provider: model.provider,
          keyId: "primary-model",
          environment: {},
          reader: { readModelSecret: async () => ({ encryptedValue }) },
        });
      for (const key of ["stored-anthropic-one", "stored-anthropic-two"]) {
        encryptedValue = await encryptSecret(encryptionKey, key);
        const agents = await resolveRuntimeAgents(
          async () => [
            {
              id: "general-assistant",
              name: "General Assistant",
              type: "built_in",
              systemPrompt: "Answer using the granted balance tool.",
            },
          ],
          model,
          resolve,
          undefined,
          async () => [
            {
              name: "read_balance",
              ref: "bank/read_balance",
              description: "Read the balance.",
              parameters: z.object({ account: z.string() }),
              execute: async (args) => {
                executed.push(args);
                return "42";
              },
            },
          ],
        );
        const agent = agents["general-assistant"]?.clone();
        if (!agent) throw new Error("The built-in agent was not constructed");
        agent.addMessage({
          id: "request",
          role: "user",
          content: "Read my balance.",
        });
        await agent.runAgent();
        expect(agent.messages.at(-1)).toMatchObject({
          role: "assistant",
          content: "The balance is 42.",
        });
      }
      expect(executed).toEqual([{ account: "demo" }, { account: "demo" }]);
      const requests = mock.getRequests();
      expect(requests).toHaveLength(4);
      expect(requests.map((entry) => entry.path)).toEqual(
        Array(4).fill("/v1/messages"),
      );
      expect(paths).toEqual(Array(4).fill(`${prefix}/v1/messages`));
      expect(keys).toEqual([
        "stored-anthropic-one",
        "stored-anthropic-one",
        "stored-anthropic-two",
        "stored-anthropic-two",
      ]);
      expect(
        requests.every((entry) => entry.body?.model === "claude-sonnet-4-5"),
      ).toBe(true);
      expect(requests[1]?.body?.messages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ role: "tool", content: "42" }),
        ]),
      );
    } finally {
      await proxy?.stop(true);
      await mock.stop();
    }
  },
);

test.each([
  {
    provider: "anthropic" as const,
    defaultModel: "claude-sonnet-4-5",
    expectedUrl: "https://api.anthropic.com/v1/messages",
  },
  {
    provider: "openai" as const,
    defaultModel: "gpt-5.6-terra",
    expectedUrl: "https://api.openai.com/v1/responses",
  },
])(
  "blank base URLs reach the official $provider endpoint through the real SDK",
  async ({ expectedUrl, ...model }) => {
    const mock = new LLMock();
    const originalFetch = globalThis.fetch;
    const urls: string[] = [];
    const keys: (string | null)[] = [];
    let interception:
      | ReturnType<typeof spyOn<typeof globalThis, "fetch">>
      | undefined;
    try {
      const base = await mock.start();
      mock.onMessage("Hello", { content: "Hello back." });
      process.env.ANTHROPIC_BASE_URL = "";
      process.env.OPENAI_BASE_URL = "";
      normalizeModelBaseUrls();
      // Keep the SDK's request intact while redirecting only its transport to local fake HTTP.
      interception = spyOn(globalThis, "fetch").mockImplementation(
        (input, init) => {
          const request = new Request(input, init);
          urls.push(request.url);
          keys.push(
            request.headers.get(
              model.provider === "anthropic" ? "x-api-key" : "authorization",
            ),
          );
          return originalFetch(`${base}${new URL(request.url).pathname}`, {
            method: request.method,
            headers: request.headers,
            body: request.body,
          });
        },
      );
      const agents = await resolveRuntimeAgents(
        async () => [
          {
            id: "general-assistant",
            name: "General Assistant",
            type: "built_in",
            systemPrompt: "Answer simply.",
          },
        ],
        model,
        async () => "synthetic-key",
      );
      const agent = agents["general-assistant"]?.clone();
      if (!agent) throw new Error("The built-in agent was not constructed");
      agent.addMessage({ id: "request", role: "user", content: "Hello" });
      await agent.runAgent();
      expect(agent.messages.at(-1)).toMatchObject({
        role: "assistant",
        content: "Hello back.",
      });
      expect(urls).toEqual([expectedUrl]);
      expect(keys).toEqual([
        model.provider === "anthropic"
          ? "synthetic-key"
          : "Bearer synthetic-key",
      ]);
    } finally {
      interception?.mockRestore();
      await mock.stop();
    }
  },
);

test("the production selector speaks native Anthropic and rereads its key", async () => {
  const seen: {
    path: string;
    key: string | null;
    authorization: string | null;
    version: string | null;
    body: Record<string, unknown>;
  }[] = [];
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    async fetch(request) {
      seen.push({
        path: new URL(request.url).pathname,
        key: request.headers.get("x-api-key"),
        authorization: request.headers.get("authorization"),
        version: request.headers.get("anthropic-version"),
        body: await request.json(),
      });
      return Response.json({
        content: [
          { type: "thinking", thinking: "private" },
          { type: "text", text: '{"skills":' },
          { type: "text", text: '["bank"]}' },
        ],
      });
    },
  });
  try {
    process.env.ANTHROPIC_BASE_URL = `${server.url.origin}/v1/`;
    process.env.OPENAI_BASE_URL = `${server.url.origin}/v1`;
    let key = "synthetic-one";
    const complete = createModelCompleter({
      model: anthropicModel,
      resolveApiKey: async () => key,
    });
    expect(await complete("Choose bank tools; return JSON.")).toBe(
      '{"skills":["bank"]}',
    );
    key = "synthetic-two";
    expect(await complete("Choose bank tools; return JSON.")).toBe(
      '{"skills":["bank"]}',
    );
    expect(seen.map((entry) => entry.key)).toEqual([
      "synthetic-one",
      "synthetic-two",
    ]);
    for (const entry of seen) {
      expect(entry.path).toBe("/v1/messages");
      expect(entry.authorization).toBeNull();
      expect(entry.version).toBe("2023-06-01");
      expect(entry.body).toMatchObject({
        model: "claude-sonnet-4-5",
        max_tokens: expect.any(Number),
        messages: [
          { role: "user", content: "Choose bank tools; return JSON." },
        ],
      });
      expect(entry.body).not.toHaveProperty("response_format");
      expect(entry.body).not.toHaveProperty("temperature");
    }
  } finally {
    await server.stop(true);
  }
});

async function bounded<T>(promise: Promise<T>, boundary: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`Fixture ${boundary} timed out`)),
          1500,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

test("cancelling an Anthropic selector closes its in-flight HTTP request", async () => {
  const entered = Promise.withResolvers<void>();
  const closed = Promise.withResolvers<void>();
  const release = Promise.withResolvers<void>();
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    async fetch(request) {
      await request.text();
      request.signal.addEventListener("abort", () => closed.resolve(), {
        once: true,
      });
      entered.resolve();
      await release.promise;
      return Response.json({ content: [{ type: "text", text: "late reply" }] });
    },
  });
  try {
    process.env.ANTHROPIC_BASE_URL = server.url.origin;
    process.env.OPENAI_BASE_URL = server.url.origin;
    const controller = new AbortController();
    const complete = createModelCompleter({
      model: anthropicModel,
      resolveApiKey: async () => "synthetic-key",
    });
    const run = complete("Choose tools.", controller.signal);
    const outcome = run.then(
      () => ({ rejected: false }),
      () => ({ rejected: true }),
    );
    await bounded(entered.promise, "request arrival");
    controller.abort();
    expect(await bounded(outcome, "fetch abort")).toEqual({ rejected: true });
    await bounded(closed.promise, "server abort");
  } finally {
    release.resolve();
    await server.stop(true);
  }
}, 5000);

describe("Factory completion limits and observations (I07)", () => {
  test.each(["openai", "anthropic"] as const)(
    "%s defaults, output budgets and exact provider usage",
    async (provider) => {
      const observations: ModelCallObservation[] = [];
      const bodies: Record<string, unknown>[] = [];
      let includeUsage = true;
      const server = Bun.serve({
        port: 0,
        hostname: "127.0.0.1",
        async fetch(request) {
          bodies.push(await request.json());
          return Response.json(
            provider === "openai"
              ? {
                  choices: [{ message: { content: "{}" } }],
                  ...(includeUsage
                    ? {
                        usage: {
                          prompt_tokens: 37,
                          completion_tokens: 11,
                          total_tokens: 48,
                          prompt_tokens_details: { cached_tokens: 5 },
                          completion_tokens_details: { reasoning_tokens: 3 },
                        },
                      }
                    : {}),
                }
              : {
                  content: [{ type: "text", text: "{}" }],
                  ...(includeUsage
                    ? {
                        usage: {
                          input_tokens: 37,
                          output_tokens: 11,
                          cache_creation_input_tokens: 5,
                          cache_read_input_tokens: 3,
                          cache_creation: { ephemeral_5m_input_tokens: 5 },
                        },
                      }
                    : {}),
                },
          );
        },
      });
      try {
        process.env.OPENAI_BASE_URL = server.url.origin;
        process.env.ANTHROPIC_BASE_URL = server.url.origin;
        const base = {
          model: provider === "openai" ? packageModel : anthropicModel,
          resolveApiKey: async () => "synthetic-fixture",
          observe: (event: ModelCallObservation) => observations.push(event),
        };
        await createModelCompleter(base)("JSON");
        await createModelCompleter({
          ...base,
          timeoutMs: 20_000,
          outputTokenBudget: 4096,
        })("JSON");
        includeUsage = false;
        await createModelCompleter(base)("JSON");
        expect(bodies).toHaveLength(3);
        expect(bodies[0]).not.toHaveProperty("temperature");
        if (provider === "anthropic") {
          expect(bodies[0]?.max_tokens).toBe(1024);
          expect(bodies[1]?.max_tokens).toBe(4096);
          expect(bodies[0]).not.toHaveProperty("response_format");
        } else {
          expect(bodies[0]).not.toHaveProperty("max_completion_tokens");
          expect(bodies[1]?.max_completion_tokens).toBe(4096);
          expect(bodies[0]?.response_format).toEqual({ type: "json_object" });
        }
        expect(observations).toHaveLength(3);
        for (const event of observations.slice(0, 2)) {
          expect(event.status).toBe("success");
          expect(event.httpStatus).toBe(200);
          expect(event.usage).toEqual({
            inputTokens: 37,
            outputTokens: 11,
            totalTokens: provider === "openai" ? 48 : null,
            details:
              provider === "openai"
                ? {
                    prompt_tokens_details: { cached_tokens: 5 },
                    completion_tokens_details: { reasoning_tokens: 3 },
                  }
                : {
                    cache_creation_input_tokens: 5,
                    cache_read_input_tokens: 3,
                    cache_creation: { ephemeral_5m_input_tokens: 5 },
                  },
          });
          expect(event.durationMs).toBeGreaterThanOrEqual(0);
        }
        expect(observations[2]?.usage).toBeNull();
        expect(JSON.stringify(observations)).not.toContain("synthetic-fixture");
      } finally {
        await server.stop(true);
      }
    },
  );

  test("HTTP errors and malformed content emit one observation without retry or exposing response bodies", async () => {
    let requests = 0;
    let mode = "http";
    const events: ModelCallObservation[] = [];
    const server = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      fetch() {
        requests++;
        return mode === "http"
          ? new Response("secret diagnostic", { status: 503 })
          : Response.json({ choices: [] });
      },
    });
    try {
      process.env.OPENAI_BASE_URL = server.url.origin;
      const complete = createModelCompleter({
        model: packageModel,
        resolveApiKey: async () => "fixture",
        observe: (event) => events.push(event),
      });
      await expect(complete("JSON")).rejects.toThrow(
        "router model answered 503",
      );
      mode = "content";
      await expect(complete("JSON")).rejects.toThrow("no text");
      expect(requests).toBe(2);
      expect(events.map(({ status }) => status)).toEqual([
        "http_error",
        "error",
      ]);
      expect(events.every(({ usage }) => usage === null)).toBe(true);
      expect(JSON.stringify(events)).not.toContain("secret diagnostic");
    } finally {
      await server.stop(true);
    }
  });

  test("missing key, stalled key lookup and cancellation make no HTTP request or fallback", async () => {
    const events: ModelCallObservation[] = [];
    const base = {
      model: packageModel,
      observe: (event: ModelCallObservation) => events.push(event),
    };
    await expect(
      createModelCompleter({ ...base, resolveApiKey: async () => null })(
        "JSON",
      ),
    ).rejects.toThrow("no model key");
    const lateKey = Promise.withResolvers<string>();
    await expect(
      createModelCompleter({
        ...base,
        timeoutMs: 20,
        resolveApiKey: async () => lateKey.promise,
      })("JSON"),
    ).rejects.toThrow();
    lateKey.resolve("fixture");
    const abort = new AbortController();
    abort.abort();
    let reads = 0;
    await expect(
      createModelCompleter({
        ...base,
        resolveApiKey: async () => {
          reads++;
          return "fixture";
        },
      })("JSON", abort.signal),
    ).rejects.toThrow();
    expect(reads).toBe(0);
    expect(events).toHaveLength(0);
  });

  test.each(["response", "body"])(
    "timeout and caller cancellation interrupt stalled %s and observe one attempted HTTP call",
    async (boundary) => {
      for (const cancelled of [false, true]) {
        const entered = Promise.withResolvers<void>();
        const never = Promise.withResolvers<Response>();
        let requests = 0;
        const events: ModelCallObservation[] = [];
        const server = Bun.serve({
          port: 0,
          hostname: "127.0.0.1",
          async fetch(request) {
            // Consume the upload before cancelling; otherwise Bun's fixture shutdown stalls.
            await request.text();
            requests++;
            entered.resolve();
            return boundary === "response"
              ? never.promise
              : new Response(
                  new ReadableStream({
                    start(controller) {
                      controller.enqueue(
                        new TextEncoder().encode('{"choices":['),
                      );
                    },
                  }),
                  { headers: { "content-type": "application/json" } },
                );
          },
        });
        try {
          process.env.OPENAI_BASE_URL = server.url.origin;
          const abort = new AbortController();
          const pending = createModelCompleter({
            model: packageModel,
            timeoutMs: cancelled ? 1000 : 40,
            resolveApiKey: async () => "fixture",
            observe: (event) => events.push(event),
          })("JSON", abort.signal);
          const settled = pending.then(
            () => "unexpected success",
            () => "failed",
          );
          await bounded(entered.promise, "entered");
          if (cancelled) abort.abort();
          expect(await bounded(settled, "cancelled completion")).toBe("failed");
          expect(requests).toBe(1);
          expect(events).toHaveLength(1);
          expect(events[0]?.status).toBe(cancelled ? "cancelled" : "timeout");
          expect(events[0]?.usage).toBeNull();
          expect(events[0]!.durationMs).toBeGreaterThanOrEqual(0);
        } finally {
          never.resolve(new Response("{}"));
          await server.stop(true);
        }
      }
    },
  );

  test("the Factory's completion options carry its model and 4,096-token budget to either provider; other callers are unchanged", async () => {
    // Recorded on an OpenAI-compatible gateway: construction sent no output limit, the gateway
    // reserved the model's maximum and answered HTTP 402, reported as MODEL_UNAVAILABLE.
    const bodies: Record<string, unknown>[] = [];
    const server = Bun.serve({
      port: 0,
      hostname: "127.0.0.1",
      async fetch(request) {
        bodies.push(await request.json());
        // Both providers' answer shapes at once; each path reads its own.
        return Response.json({
          choices: [{ message: { content: "{}" } }],
          content: [{ type: "text", text: "{}" }],
        });
      },
    });
    try {
      process.env.OPENAI_BASE_URL = server.url.origin;
      process.env.ANTHROPIC_BASE_URL = server.url.origin;
      const resolveApiKey = async () => "synthetic-fixture";
      const strong = factoryCompletionOptions(packageModel, {
        FACTORY_MODEL: " stronger-model ",
      });
      expect(strong).toEqual({
        model: { provider: "openai", defaultModel: "stronger-model" },
        timeoutMs: 20_000,
        outputTokenBudget: 4096,
      });
      // Unset or blank: construction stays on the runtime model, still bounded.
      for (const environment of [{}, { FACTORY_MODEL: "  " }])
        expect(factoryCompletionOptions(packageModel, environment).model).toBe(
          packageModel,
        );
      await createModelCompleter({ ...strong, resolveApiKey })("JSON");
      await createModelCompleter({
        ...factoryCompletionOptions(packageModel, {}),
        resolveApiKey,
      })("JSON");
      await createModelCompleter({
        ...factoryCompletionOptions(anthropicModel, {}),
        resolveApiKey,
      })("JSON");
      // The intent router and skill selection, built as index.ts builds them.
      await createModelCompleter({ model: packageModel, resolveApiKey })(
        "JSON",
      );
      expect(
        bodies.map((body) => [
          body.model,
          body.max_completion_tokens,
          body.max_tokens,
        ]),
      ).toEqual([
        ["stronger-model", 4096, undefined],
        [packageModel.defaultModel, 4096, undefined],
        [anthropicModel.defaultModel, undefined, 4096],
        [packageModel.defaultModel, undefined, undefined],
      ]);
      expect(bodies[3]).not.toHaveProperty("max_completion_tokens");
      expect(bodies[3]).not.toHaveProperty("max_tokens");
    } finally {
      await server.stop(true);
    }
  });

  test("BOT_MAX_OUTPUT_TOKENS is an opt-in positive integer on the runtime model", () => {
    expect(
      runtimeModelForEnvironment(packageModel, {
        BOT_MAX_OUTPUT_TOKENS: " 2048 ",
      }),
    ).toEqual({ ...packageModel, outputTokenBudget: 2048 });
    for (const value of [undefined, "", "   "])
      expect(
        runtimeModelForEnvironment(packageModel, {
          BOT_MAX_OUTPUT_TOKENS: value,
        }),
      ).not.toHaveProperty("outputTokenBudget");
    for (const value of ["0", "-1", "1.5", "1e3", "many", "2048 tokens"])
      expect(() =>
        runtimeModelForEnvironment(packageModel, {
          BOT_MAX_OUTPUT_TOKENS: value,
        }),
      ).toThrow("BOT_MAX_OUTPUT_TOKENS must be a positive integer.");
  });

  test("invalid completion bounds are refused", () => {
    for (const timeoutMs of [0, -1, Infinity, 90_001])
      expect(() =>
        createModelCompleter({
          model: packageModel,
          resolveApiKey: async () => "fixture",
          timeoutMs,
        }),
      ).toThrow("invalid completion limits");
    for (const outputTokenBudget of [0, -1, Infinity, 16_385])
      expect(() =>
        createModelCompleter({
          model: packageModel,
          resolveApiKey: async () => "fixture",
          outputTokenBudget,
        }),
      ).toThrow("invalid completion limits");
  });
});
