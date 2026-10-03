import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chmod, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readBoundedText } from "../src/io.js";
import { createHttpCompleter } from "../src/model.js";
import { factoryGenerationPrompt, generateDraft } from "../src/service.js";

const root = fileURLToPath(new URL("../", import.meta.url));
const cases = {
  document: {
    name: "Document Summarizer",
    role: "Document Summarization Agent",
    description:
      "Tóm tắt nội dung người dùng cung cấp, giữ lại các ý chính và thông tin quan trọng.",
  },
  web: {
    name: "Web Researcher",
    role: "Internet Research Agent",
    description:
      "Nghiên cứu một chủ đề và tổng hợp thành báo cáo có dẫn nguồn.",
  },
  security: {
    name: "Security Incident Assistant",
    role: "Security Incident Support Agent",
    description:
      "Hỗ trợ phân tích thông tin incident và tổng hợp trạng thái xử lý cho người vận hành.",
  },
} as const;
const catalogue = { tools: [], defaultToolRefs: [] };
const sha256 = (text: string) =>
  createHash("sha256").update(text).digest("hex");
async function sourceHashes() {
  const directory = join(root, "src");
  return Object.fromEntries(
    await Promise.all(
      (await readdir(directory))
        .filter((name) => name.endsWith(".ts"))
        .sort()
        .map(async (name) => [
          name,
          sha256(await readFile(join(directory, name), "utf8")),
        ]),
    ),
  );
}
async function freeze(path: string, text: string) {
  await writeFile(path, text, { flag: "wx", mode: 0o600 });
  await chmod(path, 0o444);
}

async function run(key: keyof typeof cases, directory: string) {
  const request = cases[key];
  const provider = process.env.FACTORY_MODEL_PROVIDER;
  const model = process.env.FACTORY_MODEL;
  const apiKey = process.env.FACTORY_MODEL_API_KEY;
  const url = process.env.FACTORY_MODEL_API_URL;
  assert(provider === "deepseek" && model === "deepseek-v4-pro");
  assert(apiKey && url);
  const hashes = await sourceHashes();
  await mkdir(directory, { recursive: true });
  const prefix = join(
    directory,
    `${key}-${new Date().toISOString().replace(/[:.]/g, "-")}`,
  );
  let calls = 0;
  let raw: string | null = null;
  let wireRequest: unknown;
  let metadata: unknown;
  const complete = createHttpCompleter(
    { provider, model, apiKey, url },
    async (target, options) => {
      calls++;
      assert.equal(calls, 1, "No retries or repairs in this smoke.");
      wireRequest = JSON.parse(String(options.body));
      const response = await fetch(target, options);
      // Never persist the provider envelope or reasoning_content. Select final content and counters.
      if (response.ok) {
        const body = JSON.parse(
          await readBoundedText(response.clone(), 256 * 1024),
        );
        const choice = body.choices?.[0];
        raw =
          typeof choice?.message?.content === "string"
            ? choice.message.content
            : null;
        metadata = {
          status: response.status,
          finishReason: choice?.finish_reason ?? null,
          promptTokens: body.usage?.prompt_tokens ?? null,
          completionTokens: body.usage?.completion_tokens ?? null,
          reasoningTokens:
            body.usage?.completion_tokens_details?.reasoning_tokens ?? null,
          contentType: typeof choice?.message?.content,
        };
        if (raw !== null) await freeze(`${prefix}.content.txt`, raw);
      } else metadata = { status: response.status };
      return response;
    },
  );
  let result:
    | Awaited<ReturnType<typeof generateDraft>>
    | { ok: false; dependencyFailure: string };
  const started = performance.now();
  try {
    result = await generateDraft(
      request,
      catalogue,
      complete,
      // Diagnostic only: allow a complete token-usage observation; production caps are unchanged.
      AbortSignal.timeout(120_000),
    );
  } catch (error) {
    result = {
      ok: false,
      dependencyFailure: error instanceof Error ? error.name : "ModelError",
    };
  }
  const durationMs = Math.round(performance.now() - started);
  assert.deepEqual(await sourceHashes(), hashes);
  const captured = {
    case: key,
    request,
    catalogue,
    modelRef: `${provider}/${model}`,
    wireRequest,
    metadata,
    durationMs,
    contentBytes: raw === null ? null : Buffer.byteLength(raw, "utf8"),
    calls,
    rawFile: raw === null ? null : `${prefix}.content.txt`,
    rawSha256: raw === null ? null : sha256(raw),
    result,
    productionHashes: hashes,
    stopStage:
      "AgentDraft; no resource resolution, compilation, review, repair or runtime",
  };
  await freeze(`${prefix}.json`, `${JSON.stringify(captured, null, 2)}\n`);
  console.log(
    JSON.stringify({
      capture: `${prefix}.json`,
      metadata,
      durationMs,
      contentBytes: captured.contentBytes,
      valid: result.ok,
      issues: "issues" in result ? result.issues : [],
    }),
  );
  if (!result.ok) process.exitCode = 1;
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
  assert.equal(captured.calls, 1);
  assert.deepEqual(captured.catalogue, catalogue);
  assert.deepEqual(captured.wireRequest.messages, [
    {
      role: "user",
      content: factoryGenerationPrompt(captured.request, catalogue),
    },
  ]);
  if (captured.rawFile !== null) {
    assert.equal(dirname(captured.rawFile), dirname(path));
    const raw = await readFile(captured.rawFile, "utf8");
    assert.equal(sha256(raw), captured.rawSha256);
    // Replay the adapter as well: empty content fails its response schema before JSON parsing.
    const complete = createHttpCompleter(
      {
        provider: "deepseek",
        model: "deepseek-v4-pro",
        apiKey: "offline",
        url: "http://offline/chat/completions",
      },
      async () => Response.json({ choices: [{ message: { content: raw } }] }),
    );
    let replay: unknown;
    try {
      replay = await generateDraft(captured.request, catalogue, complete);
    } catch (error) {
      replay = {
        ok: false,
        dependencyFailure: error instanceof Error ? error.name : "ModelError",
      };
    }
    assert.deepEqual(replay, captured.result);
  }
  // Parsing code must remain frozen; the adapter may change between diagnostic attempts.
  const current = await sourceHashes();
  for (const [name, hash] of Object.entries(captured.productionHashes)) {
    if (name !== "model.ts") assert.equal(current[name], hash, name);
  }
  console.log(
    `PASS: ${path}; exact content hash, input/prompt integrity and production-parser replay.`,
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
    "Use --run document|web|security <directory> or --verify <capture.json>.",
  );
