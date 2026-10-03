/**
 * Explicit live smoke of full construction through the production HTTP handler:
 *   bun --env-file=.env agent-factory/tests/construction-smoke.ts --run web|document|security <directory>
 *   bun agent-factory/tests/construction-smoke.ts --verify <capture.json>
 * The request is exactly name, role and description. The catalogue is one fixed deployment snapshot
 * for every case: the Tavily tool as BE projects it (server/src/plugins/tavily-rest.ts, server title
 * "Tavily") and no default tool. Only final content and counters are kept, never reasoning text.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { createFactoryHandler } from "../src/http.js";
import { readBoundedText } from "../src/io.js";
import { createHttpCompleter } from "../src/model.js";
import type { FactoryObservation } from "../src/service.js";
import { hashAgentSpec } from "../src/spec.js";

const cases = {
  web: {
    name: "Web Researcher",
    role: "Internet Research Agent",
    description:
      "Nghiên cứu một chủ đề và tổng hợp thành báo cáo có dẫn nguồn.",
  },
  document: {
    name: "Document Summarizer",
    role: "Document Summarization Agent",
    description:
      "Tóm tắt nội dung người dùng cung cấp, giữ lại các ý chính và thông tin quan trọng.",
  },
  security: {
    name: "Security Incident Assistant",
    role: "Security Incident Support Agent",
    description:
      "Hỗ trợ phân tích thông tin incident và tổng hợp trạng thái xử lý cho người vận hành.",
  },
} as const;
const catalogue = {
  tools: [
    {
      kind: "tool",
      ref: "tavily/tavily_search",
      name: "tavily_search",
      title: "Tavily",
      description:
        "Search the public web. Returns JSON {results:[{title,url,content}]}: for each matching page its title, its address and a short extract of what it says. Use the url to cite a source.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "What to search the web for." },
          max_results: {
            type: "integer",
            minimum: 1,
            maximum: 10,
            description: "How many results to return. Defaults to 5.",
          },
        },
        required: ["query"],
      },
      outputSchema: null,
      effect: "read",
      destructive: false,
    },
  ],
  defaultToolRefs: [],
};
const token = "construction-smoke-local-token-0123456789";
const sha256 = (text: string) =>
  createHash("sha256").update(text).digest("hex");
async function freeze(path: string, text: string) {
  await writeFile(path, text, { flag: "wx", mode: 0o600 });
  await chmod(path, 0o444);
}

async function run(key: keyof typeof cases, directory: string) {
  const provider = process.env.FACTORY_MODEL_PROVIDER;
  const model = process.env.FACTORY_MODEL;
  const apiKey = process.env.FACTORY_MODEL_API_KEY;
  const url = process.env.FACTORY_MODEL_API_URL;
  assert(provider === "deepseek" && model === "deepseek-v4-pro");
  assert(apiKey && url);
  await mkdir(directory, { recursive: true });
  const prefix = join(
    directory,
    `${key}-${new Date().toISOString().replace(/[:.]/g, "-")}`,
  );
  const calls: Record<string, unknown>[] = [];
  const stages: FactoryObservation[] = [];
  const handler = createFactoryHandler({
    token,
    modelRef: `${provider}/${model}`,
    observe: (event) => stages.push(event),
    complete: createHttpCompleter(
      { provider, model, apiKey, url },
      async (target, options) => {
        const wire = JSON.parse(String(options.body));
        const content: string = wire.messages[0].content;
        const call: Record<string, unknown> = {
          prefix: content.slice(0, content.indexOf(":")),
          repair: content.includes("\nFACTORY_REPAIR:"),
          promptSha256: sha256(content),
          wire: { ...wire, messages: undefined },
        };
        calls.push(call);
        const started = performance.now();
        try {
          const response = await fetch(target, options);
          call.status = response.status;
          if (response.ok) {
            const body = JSON.parse(
              await readBoundedText(response.clone(), 256 * 1024),
            );
            const choice = body.choices?.[0];
            const final = choice?.message?.content;
            Object.assign(call, {
              finishReason: choice?.finish_reason ?? null,
              promptTokens: body.usage?.prompt_tokens ?? null,
              completionTokens: body.usage?.completion_tokens ?? null,
              reasoningTokens:
                body.usage?.completion_tokens_details?.reasoning_tokens ?? null,
              contentBytes:
                typeof final === "string" ? Buffer.byteLength(final) : null,
              content: typeof final === "string" ? final : null,
            });
          }
          return response;
        } catch (error) {
          call.error = error instanceof Error ? error.name : "FetchError";
          throw error;
        } finally {
          call.durationMs = Math.round(performance.now() - started);
        }
      },
    ),
  });
  const started = performance.now();
  const response = await handler(
    new Request("http://factory/v1/constructions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ request: cases[key], catalogue }),
    }),
  );
  const result = await response.json();
  const captured = {
    case: key,
    request: cases[key],
    catalogue,
    modelRef: `${provider}/${model}`,
    httpStatus: response.status,
    durationMs: Math.round(performance.now() - started),
    stages,
    calls,
    result,
  };
  await freeze(`${prefix}.json`, `${JSON.stringify(captured, null, 2)}\n`);
  console.log(
    JSON.stringify({
      capture: `${prefix}.json`,
      httpStatus: response.status,
      durationMs: captured.durationMs,
      construction: result.verification?.construction ?? null,
      attempts: result.verification?.attempts ?? null,
      code: result.code ?? null,
      issues: result.issues ?? result.verification?.semanticReview?.findings,
      calls: calls.map(
        ({ content: _, wire: __, promptSha256: ___, ...rest }) => rest,
      ),
    }),
  );
  if (result.verification?.construction !== "PASS") process.exitCode = 1;
}

async function verify(path: string) {
  const captured = JSON.parse(await readFile(path, "utf8"));
  assert(Object.hasOwn(cases, captured.case));
  assert.deepEqual(
    captured.request,
    cases[captured.case as keyof typeof cases],
  );
  assert.deepEqual(Object.keys(captured.request).sort(), [
    "description",
    "name",
    "role",
  ]);
  assert.deepEqual(captured.catalogue, catalogue);
  assert.equal(captured.httpStatus, 200);
  const { spec, specHash, verification } = captured.result;
  assert.equal(verification.construction, "PASS");
  assert.equal(verification.semanticReview.verdict, "PASS");
  assert.equal(specHash, hashAgentSpec(spec));
  assert.equal(verification.specHash, specHash);
  console.log(
    `PASS: ${path}; exact request, catalogue, PASS verdict and spec hash.`,
  );
}

if (process.argv[2] === "--run" && process.argv.length === 5) {
  const key = process.argv[3];
  assert(key && Object.hasOwn(cases, key));
  await run(key as keyof typeof cases, resolve(process.argv[4]!));
} else if (process.argv[2] === "--verify" && process.argv.length === 4) {
  await verify(resolve(process.argv[3]!));
} else
  throw new Error(
    "Use --run web|document|security <directory> or --verify <capture.json>.",
  );
