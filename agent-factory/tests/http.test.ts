import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type {
  AgentCreationRequest,
  FactoryConstructionResponse,
} from "../src/contracts.js";
import { createFactoryHandler, MAX_REQUEST_BYTES } from "../src/http.js";
import { readBoundedText } from "../src/io.js";
import { createHttpCompleter } from "../src/model.js";
import { hashAgentSpec, renderCorePrompt } from "../src/spec.js";
import { withRecordedIntent } from "./fixtures/factory-intent.js";

const token = "test-only-service-token-0123456789";
const dataset = JSON.parse(
  readFileSync(
    new URL("./fixtures/agent-factory-golden.json", import.meta.url),
    "utf8",
  ),
) as {
  cases: { request: AgentCreationRequest; replay: { response: unknown }[] }[];
};
const golden = dataset.cases[0]!;
const body = { request: golden.request, catalogue: { tools: [] } };
const generation = JSON.stringify(
  withRecordedIntent(golden.replay[0]!.response),
);
const review = JSON.stringify(golden.replay[1]!.response);
const successfulCompletion = async (prompt: string) =>
  prompt.startsWith("FACTORY_GENERATE:") ? generation : review;
const call = (value: unknown = body, headers: Record<string, string> = {}) =>
  new Request("http://factory/v1/constructions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...headers,
    },
    body: JSON.stringify(value),
  });

describe("standalone construction HTTP API", () => {
  test("health, unknown route and method; refuses an empty service secret", async () => {
    expect(() =>
      createFactoryHandler({
        token: "",
        modelRef: "fixture",
        complete: successfulCompletion,
      }),
    ).toThrow();
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: successfulCompletion,
    });
    expect((await handler(new Request("http://factory/health"))).status).toBe(
      200,
    );
    expect((await handler(new Request("http://factory/missing"))).status).toBe(
      404,
    );
    const response = await handler(
      new Request("http://factory/v1/constructions"),
    );
    expect(response.status).toBe(405);
    expect(response.headers.get("Allow")).toBe("POST");
  });

  test("unauthenticated and forged bodies make zero model calls", async () => {
    let calls = 0;
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: async (prompt) => {
        calls++;
        return successfulCompletion(prompt);
      },
    });
    expect((await handler(call(body, { Authorization: "" }))).status).toBe(401);
    expect(
      (await handler(call(body, { Authorization: "Bearer incorrect-token" })))
        .status,
    ).toBe(401);
    expect(
      (await handler(call(body, { "Content-Type": "text/plain" }))).status,
    ).toBe(415);
    expect(
      (await handler(call({ ...body, model: "attacker-model" }))).status,
    ).toBe(400);
    expect(
      (
        await handler(
          call({ ...body, request: { ...golden.request, grants: ["all"] } }),
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await handler(
          call({
            ...body,
            catalogue: { ...body.catalogue, credentials: { key: "forged" } },
          }),
        )
      ).status,
    ).toBe(422);
    expect(calls).toBe(0);
  });

  test("malformed JSON and streamed oversized bodies are refused before generation", async () => {
    let calls = 0;
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: async () => {
        calls++;
        return generation;
      },
    });
    const request = call();
    expect(
      (
        await handler(
          new Request(request.url, {
            method: "POST",
            headers: request.headers,
            body: "{",
          }),
        )
      ).status,
    ).toBe(400);
    const oversized = new Request(request.url, {
      method: "POST",
      headers: request.headers,
      body: "x".repeat(MAX_REQUEST_BYTES + 1),
    });
    expect(oversized.headers.has("content-length")).toBe(false);
    expect((await handler(oversized)).status).toBe(413);
    expect(calls).toBe(0);
  });

  test("real HTTP to a fake model performs generation + review and returns an intact artifact", async () => {
    const requests: {
      model: string;
      max_completion_tokens: number;
      messages: { content: string }[];
    }[] = [];
    const upstream = Bun.serve({
      port: 0,
      fetch: async (request) => {
        expect(request.headers.get("authorization")).toBe(
          "Bearer test-model-key",
        );
        const sent = (await request.json()) as (typeof requests)[number];
        requests.push(sent);
        return Response.json({
          choices: [
            {
              message: {
                content: await successfulCompletion(sent.messages[0]!.content),
              },
            },
          ],
        });
      },
    });
    try {
      const complete = createHttpCompleter({
        url: upstream.url.href,
        apiKey: "test-model-key",
        model: "configured-model",
      });
      const handler = createFactoryHandler({
        token,
        modelRef: "openai/configured-model",
        complete,
      });
      const response = await handler(call());
      expect(response.status).toBe(200);
      const artifact = (await response.json()) as FactoryConstructionResponse;
      expect(artifact.spec.identity).toEqual(golden.request);
      expect(artifact.specHash).toBe(hashAgentSpec(artifact.spec));
      expect(artifact.verification.specHash).toBe(artifact.specHash);
      expect(artifact.systemPrompt).toBe(renderCorePrompt(artifact.spec));
      expect(artifact.verification.construction).toBe("PASS");
      expect(requests).toHaveLength(2);
      expect(
        requests.every(
          (request) =>
            request.model === "configured-model" &&
            request.max_completion_tokens === 4096,
        ),
      ).toBe(true);
      expect(artifact).not.toHaveProperty("agent");
      expect(artifact).not.toHaveProperty("readiness");
    } finally {
      upstream.stop(true);
    }
  });

  test("invalid generation repairs once then refuses the artifact", async () => {
    let calls = 0;
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: async () => {
        calls++;
        return "{}";
      },
    });
    const response = await handler(call());
    expect(response.status).toBe(422);
    expect(calls).toBe(2);
    expect(
      (await response.json()).issues.some(
        (issue: { code: string }) => issue.code === "ATTEMPTS_EXHAUSTED",
      ),
    ).toBe(true);
  });

  test("deadline covers a stalled review; provider details never reach the caller", async () => {
    let calls = 0;
    const stalled = createFactoryHandler({
      token,
      modelRef: "fixture",
      timeoutMs: 50,
      complete: async () => {
        calls++;
        return calls === 1 ? generation : new Promise<string>(() => {});
      },
    });
    expect((await stalled(call())).status).toBe(504);
    expect(calls).toBe(2);
    const unavailable = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: async () => {
        throw new Error("provider-secret-key-and-payload");
      },
    });
    const response = await unavailable(call());
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("provider-secret");
  });

  test("client cancellation prevents model work", async () => {
    let calls = 0;
    const handler = createFactoryHandler({
      token,
      modelRef: "fixture",
      complete: async () => {
        calls++;
        return generation;
      },
    });
    const controller = new AbortController();
    const request = call();
    const cancelled = new Request(request, { signal: controller.signal });
    controller.abort();
    expect((await handler(cancelled)).status).toBe(503);
    expect(calls).toBe(0);
  });
});

test("bounded reader handles split UTF-8 and refuses declared overflow", async () => {
  const bytes = new TextEncoder().encode("Tiếng Việt");
  const response = new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(bytes.slice(0, 3));
        controller.enqueue(bytes.slice(3));
        controller.close();
      },
    }),
  );
  expect(await readBoundedText(response, bytes.length)).toBe("Tiếng Việt");
  await expect(
    readBoundedText(
      new Response("x", { headers: { "Content-Length": "100" } }),
      10,
    ),
  ).rejects.toBeInstanceOf(RangeError);
});

test("compatible model protocol, cancellation, malformed and oversized provider responses", async () => {
  const controller = new AbortController();
  const complete = createHttpCompleter(
    {
      url: "http://model/chat/completions",
      apiKey: "key",
      model: "local",
      provider: "openai-compatible",
    },
    async (_url, options) => {
      expect(options.signal).toBe(controller.signal);
      expect(JSON.parse(String(options.body)).max_tokens).toBe(4096);
      return Response.json({ choices: [{ message: { content: "{}" } }] });
    },
  );
  expect(await complete("prompt", controller.signal)).toBe("{}");
  for (const response of [
    Response.json({ error: "private-provider-payload" }, { status: 401 }),
    Response.json({ choices: [] }),
    new Response("x".repeat(256 * 1024 + 1)),
  ]) {
    const unavailable = createHttpCompleter(
      { url: "http://model", apiKey: "key", model: "local" },
      async () => response,
    );
    await expect(unavailable("prompt")).rejects.toThrow();
  }
  expect(() =>
    createHttpCompleter({
      url: "file:///tmp/key",
      apiKey: "key",
      model: "local",
    }),
  ).toThrow();
});

test("DeepSeek reuses compatible requests and parses only final content", async () => {
  const content = '{"ok":true}';
  const complete = createHttpCompleter(
    {
      provider: "deepseek",
      url: "https://api.deepseek.com/chat/completions",
      model: "deepseek-v4-pro",
      apiKey: "synthetic-deepseek-key",
    },
    async (url, options) => {
      expect(url).toBe("https://api.deepseek.com/chat/completions");
      expect(options.method).toBe("POST");
      expect(options.redirect).toBe("error");
      expect(new Headers(options.headers).get("authorization")).toBe(
        "Bearer synthetic-deepseek-key",
      );
      expect(JSON.parse(String(options.body))).toEqual({
        model: "deepseek-v4-pro",
        messages: [{ role: "user", content: "Return JSON only." }],
        max_tokens: 4096,
      });
      return Response.json({
        choices: [{ message: { content, reasoning_content: "ignored" } }],
      });
    },
  );
  expect(await complete("Return JSON only.")).toBe(content);
});

test("only DeepSeek Factory generation and review turn thinking off, ask for JSON Output and use temperature 0", async () => {
  for (const provider of ["openai", "openai-compatible", "deepseek"] as const) {
    const requests: Record<string, unknown>[] = [];
    const complete = createHttpCompleter(
      {
        provider,
        url: "http://model/chat/completions",
        apiKey: "key",
        model: "fixture",
      },
      async (_url, options) => {
        requests.push(JSON.parse(String(options.body)));
        return Response.json({ choices: [{ message: { content: "{}" } }] });
      },
    );
    const prompts = [
      "FACTORY_GENERATE: draft",
      "FACTORY_REVIEW: artifact",
      "Reply with OK.",
    ];
    for (const prompt of prompts) expect(await complete(prompt)).toBe("{}");
    const deepseekFactory = provider === "deepseek" ? [true, true, false] : [];
    for (const [index, request] of requests.entries()) {
      expect(request).toEqual({
        model: "fixture",
        messages: [{ role: "user", content: prompts[index] }],
        [provider === "openai" ? "max_completion_tokens" : "max_tokens"]: 4096,
        ...(deepseekFactory[index]
          ? {
              reasoning_effort: "none",
              response_format: { type: "json_object" },
              temperature: 0,
            }
          : {}),
      });
    }
  }
});

test("DeepSeek reasoning that leaves no final content is still refused", async () => {
  const complete = createHttpCompleter(
    {
      provider: "deepseek",
      url: "https://api.deepseek.com/chat/completions",
      model: "deepseek-v4-pro",
      apiKey: "synthetic-deepseek-key",
    },
    async () =>
      Response.json({
        choices: [
          {
            finish_reason: "length",
            message: { content: "", reasoning_content: "spent the budget" },
          },
        ],
      }),
  );
  await expect(complete("FACTORY_GENERATE: draft")).rejects.toThrow();
});

test("model configuration rejects provider credential misrouting before HTTP and hides values", () => {
  const openai = {
    provider: "openai" as const,
    model: "gpt-4.1",
    apiKey: "sk-proj-placeholder",
    url: "https://api.openai.com/v1/chat/completions",
  };
  const openrouter = {
    provider: "openai-compatible" as const,
    model: "openai/gpt-4.1",
    apiKey: "sk-or-placeholder",
    url: "https://openrouter.ai/api/v1/chat/completions",
  };
  let calls = 0;
  const send = async () => {
    calls++;
    return new Response();
  };
  for (const config of [openai, openrouter])
    expect(() => createHttpCompleter(config, send)).not.toThrow();
  for (const config of [
    { ...openai, url: openrouter.url },
    { ...openai, provider: "openai-compatible" as const, url: openrouter.url },
    {
      ...openai,
      provider: "deepseek" as const,
      url: "https://api.deepseek.com/chat/completions",
    },
    { ...openai, url: "https://another-provider.test/v1/chat/completions" },
    { ...openai, url: "http://api.openai.com/v1/chat/completions" },
    { ...openai, url: "https://api.openai.com/other" },
    { ...openrouter, url: openai.url },
    { ...openrouter, provider: "openai" as const },
    {
      ...openrouter,
      provider: "deepseek" as const,
      url: "https://api.deepseek.com/chat/completions",
    },
    {
      ...openai,
      url: "https://secret:password@api.openai.com/v1/chat/completions",
    },
    { ...openai, url: `${openai.url}?key=placeholder` },
    { ...openai, url: `${openai.url}#placeholder` },
    { ...openai, url: "https://sk-proj-placeholder@" },
  ])
    expect(() => createHttpCompleter(config, send)).toThrow(
      "Invalid Factory model configuration.",
    );
  expect(calls).toBe(0);
});

test.each(["openai", "deepseek"] as const)(
  "standalone entry starts without BE and serves a complete HTTP construction with %s",
  async (provider) => {
    let calls = 0;
    const model = Bun.serve({
      port: 0,
      fetch: async (request) => {
        calls++;
        const input = (await request.json()) as {
          messages: { content: string }[];
        };
        return Response.json({
          choices: [
            {
              message: {
                content: await successfulCompletion(input.messages[0]!.content),
              },
            },
          ],
        });
      },
    });
    const child = Bun.spawn({
      cmd: [process.execPath, "src/server.ts"],
      cwd: fileURLToPath(new URL("..", import.meta.url)),
      env: {
        ...process.env,
        FACTORY_SERVICE_TOKEN: token,
        FACTORY_HOST: "127.0.0.1",
        FACTORY_PORT: "0",
        FACTORY_MODEL_PROVIDER: provider,
        FACTORY_MODEL_API_URL: model.url.href,
        FACTORY_MODEL_API_KEY: "offline-test-key",
        FACTORY_MODEL: "fixture",
      },
      stdout: "pipe",
      stderr: "pipe",
    });
    try {
      const reader = child.stdout.getReader();
      const output = await reader.read();
      reader.releaseLock();
      const url = new TextDecoder()
        .decode(output.value)
        .match(/http:\/\/[^\s]+/)?.[0];
      expect(url).toBeDefined();
      if (!url) throw new Error("Factory did not start.");
      expect((await fetch(new URL("/health", url))).status).toBe(200);
      const request = call();
      const response = await fetch(new URL("/v1/constructions", url), {
        method: "POST",
        headers: request.headers,
        body: JSON.stringify(body),
      });
      expect(response.status).toBe(200);
      const artifact = (await response.json()) as FactoryConstructionResponse;
      expect(artifact.specHash).toBe(hashAgentSpec(artifact.spec));
      expect(calls).toBe(2);
    } finally {
      child.kill();
      await child.exited;
      model.stop(true);
    }
  },
);
