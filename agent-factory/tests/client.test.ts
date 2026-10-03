import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { createFactoryClient } from "../src/client.js";
import type {
  AgentCreationRequest,
  FactoryConstructionResponse,
} from "../src/contracts.js";
import { createFactoryHandler } from "../src/http.js";
import {
  fingerprintFactoryResource,
  hashAgentSpec,
  renderCorePrompt,
} from "../src/spec.js";
import { withRecordedIntent } from "./fixtures/factory-intent.js";

const token = "test-only-service-token-0123456789";
const golden = JSON.parse(
  readFileSync(
    new URL("./fixtures/agent-factory-golden.json", import.meta.url),
    "utf8",
  ),
).cases[0] as {
  request: AgentCreationRequest;
  replay: { response: unknown }[];
};
const catalogue = { tools: [] };
const handler = createFactoryHandler({
  token,
  modelRef: "fixture",
  complete: async (prompt) =>
    JSON.stringify(
      withRecordedIntent(
        golden.replay[prompt.startsWith("FACTORY_GENERATE:") ? 0 : 1]!.response,
      ),
    ),
});
const config = { url: "http://factory", token };
async function artifact() {
  return (await (
    await handler(
      new Request("http://factory/v1/constructions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ request: golden.request, catalogue }),
      }),
    )
  ).json()) as FactoryConstructionResponse;
}

test("client calls authenticated HTTP and receives a verified construction", async () => {
  let calls = 0;
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    fetch: async (request) => {
      calls++;
      expect(new URL(request.url).pathname).toBe("/v1/constructions");
      return handler(request);
    },
  });
  try {
    const result = await createFactoryClient({ url: server.url.href, token })(
      golden.request,
      catalogue,
    );
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.value.spec.identity).toEqual(golden.request);
    expect(calls).toBe(1);
  } finally {
    server.stop(true);
  }
});

test("client strips catalogue fingerprints and sends tools and default refs only", async () => {
  const tool = {
    kind: "tool" as const,
    ref: "kb/query",
    name: "query",
    title: "Knowledge base",
    description: "Retrieve passages from internal documents.",
    inputSchema: { type: "object", properties: { query: { type: "string" } } },
    outputSchema: null,
    effect: "read" as const,
    destructive: false,
  };
  const client = createFactoryClient(config, async (url, options) => {
    expect(url).toBe("http://factory/v1/constructions");
    expect(options.redirect).toBe("error");
    expect(options.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    });
    const body = JSON.parse(String(options.body));
    expect(body.catalogue).toEqual({
      tools: [tool],
      defaultToolRefs: ["kb/query"],
    });
    expect(Object.keys(body).sort()).toEqual(["catalogue", "request"]);
    // The artifact below was built without that default tool, so it must be refused.
    return Response.json(await artifact());
  });
  expect(
    await client(golden.request, {
      tools: [{ ...tool, fingerprint: fingerprintFactoryResource(tool) }],
      defaultToolRefs: ["kb/query"],
    }),
  ).toMatchObject({ ok: false, issues: [{ code: "ARTIFACT_INVALID" }] });
});

test("client rejects altered prompt/hash, wrong request, unknown resource, malformed verification and LOW intent", async () => {
  const good = await artifact();
  const mutations: ((value: FactoryConstructionResponse) => unknown)[] = [
    (v) => ({ ...v, systemPrompt: "forged" }),
    (v) => ({ ...v, specHash: "a".repeat(64) }),
    (v) => ({
      ...v,
      verification: { ...v.verification, construction: "FAIL" },
    }),
    (v) => ({
      ...v,
      intent: {
        ...v.intent,
        confidence: "LOW",
        missingInformation: ["Need input"],
      },
    }),
    (v) => ({
      ...v,
      intent: {
        ...v.intent,
        originalInput: { ...golden.request, name: "Other" },
      },
    }),
    (v) => {
      const spec = {
        ...v.spec,
        identity: { ...v.spec.identity, name: "Other" },
      };
      const specHash = hashAgentSpec(spec);
      return {
        ...v,
        spec,
        specHash,
        systemPrompt: renderCorePrompt(spec),
        verification: { ...v.verification, specHash },
      };
    },
    (v) => {
      const spec = {
        ...v.spec,
        resources: [
          {
            kind: "tool" as const,
            ref: "forged/tool",
            fingerprint: "a".repeat(64),
            requirementIds: ["r1"],
            argumentSources: [],
          },
        ],
      };
      const specHash = hashAgentSpec(spec);
      return {
        ...v,
        spec,
        specHash,
        systemPrompt: renderCorePrompt(spec),
        verification: { ...v.verification, specHash },
      };
    },
  ];
  for (const mutate of mutations) {
    const result = await createFactoryClient(config, async () =>
      Response.json(mutate(good)),
    )(golden.request, catalogue);
    expect(result).toMatchObject({
      ok: false,
      issues: [{ code: "ARTIFACT_INVALID" }],
    });
  }
});

test("construction refusal preserves NEEDS_INPUT; dependency and malformed errors stay safe", async () => {
  const issues = [
    {
      code: "NEEDS_INPUT",
      path: "intent",
      sourceStage: "draft" as const,
      evidenceRefs: [],
      message: "What input should it use?",
    },
  ];
  const client = createFactoryClient(config, async () =>
    Response.json(
      { code: "NEEDS_INPUT", error: "Failed", issues, retryable: false },
      { status: 422 },
    ),
  );
  expect(await client(golden.request, catalogue)).toEqual({
    ok: false,
    issues,
  });
  for (const response of [
    new Response("secret upstream error", { status: 401 }),
    new Response("secret upstream error", { status: 500 }),
    new Response("not json"),
    Response.json({}),
    new Response("x".repeat(1024 * 1024 + 1)),
    Response.json(
      {
        error: "secret",
        code: "MODEL_TIMEOUT",
        issues: [
          { ...issues[0], sourceStage: "dependency", message: "secret" },
        ],
        retryable: true,
      },
      { status: 503 },
    ),
  ]) {
    const result = await createFactoryClient(config, async () => response)(
      golden.request,
      catalogue,
    );
    expect(result.ok).toBe(false);
    expect(JSON.stringify(result)).not.toContain("secret");
  }
});

test("deadline and cancellation bound fetch and streamed response; invalid config never sends", async () => {
  for (const send of [
    async () => new Promise<Response>(() => {}),
    async () => new Response(new ReadableStream({ start() {} })),
  ]) {
    const result = await createFactoryClient(config, send)(
      golden.request,
      catalogue,
      { timeoutMs: 20 },
    );
    expect(result).toMatchObject({
      ok: false,
      issues: [{ code: "DEADLINE_EXCEEDED" }],
    });
  }
  let calls = 0;
  const send = async () => {
    calls++;
    return Response.json({});
  };
  const controller = new AbortController();
  controller.abort();
  expect(
    await createFactoryClient(config, send)(golden.request, catalogue, {
      signal: controller.signal,
    }),
  ).toMatchObject({ ok: false, issues: [{ code: "CANCELLED" }] });
  for (const invalid of [
    { ...config, token: "" },
    { ...config, url: "file:///tmp/factory" },
    { ...config, url: "http://user:secret@factory" },
  ])
    expect(
      (await createFactoryClient(invalid, send)(golden.request, catalogue)).ok,
    ).toBe(false);
  expect(calls).toBe(0);
});

test("real HTTP redirect cannot forward the service secret", async () => {
  let leaked = false;
  const other = Bun.serve({
    port: 0,
    fetch: () => {
      leaked = true;
      return Response.json({});
    },
  });
  const redirect = Bun.serve({
    port: 0,
    fetch: () => Response.redirect(other.url),
  });
  try {
    expect(
      (
        await createFactoryClient({ url: redirect.url.href, token })(
          golden.request,
          catalogue,
        )
      ).ok,
    ).toBe(false);
    expect(leaked).toBe(false);
  } finally {
    redirect.stop(true);
    other.stop(true);
  }
});
