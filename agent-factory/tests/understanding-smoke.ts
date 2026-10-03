/**
 * Explicit live smoke: bun --env-file=.env agent-factory/tests/understanding-smoke.ts --run
 * Integrity check: bun agent-factory/tests/understanding-smoke.ts --verify <output-directory>
 * Stops at the existing AgentDraft seam. No resolver, compiler, production reviewer or repair.
 * Evaluate only after frozen/manifest.json exists; never feed observations back into generation.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { chmod, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { FactoryCatalogue } from "../src/contracts.js";
import { createHttpCompleter } from "../src/model.js";
import { factoryGenerationPrompt, generateDraft } from "../src/service.js";
import { parseAgentCreationRequest } from "../src/spec.js";

const root = fileURLToPath(new URL("../", import.meta.url));
const cases = [
  {
    name: "Web Researcher",
    role: "Internet Research Agent",
    description:
      "Nghiên cứu một chủ đề và tổng hợp thành báo cáo có dẫn nguồn.",
  },
  {
    name: "Document Summarizer",
    role: "Document Summarization Agent",
    description:
      "Tóm tắt nội dung người dùng cung cấp, giữ lại các ý chính và thông tin quan trọng.",
  },
  {
    name: "Security Incident Assistant",
    role: "Security Incident Support Agent",
    description:
      "Hỗ trợ phân tích thông tin incident và tổng hợp trạng thái xử lý cho người vận hành.",
  },
] as const;
const catalogue: FactoryCatalogue = { tools: [], defaultToolRefs: [] };
const sha256 = (text: string) =>
  createHash("sha256").update(text).digest("hex");
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;

async function productionHashes() {
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

async function freeze(path: string, value: unknown) {
  const text = json(value);
  await writeFile(path, text, { flag: "wx", mode: 0o600 });
  await chmod(path, 0o444);
  return sha256(text);
}

async function verify(directory: string) {
  const frozen = join(directory, "frozen");
  const manifest = JSON.parse(
    await readFile(join(frozen, "manifest.json"), "utf8"),
  );
  assert.equal(manifest.cases.length, 3);
  assert.deepEqual(await productionHashes(), manifest.productionHashes);
  let replayed = 0;
  for (const [index, entry] of manifest.cases.entries()) {
    const text = await readFile(join(frozen, entry.file), "utf8");
    assert.equal(sha256(text), entry.sha256);
    const captured = JSON.parse(text);
    assert.deepEqual(captured.request, cases[index]);
    assert.deepEqual(Object.keys(captured.request).sort(), [
      "description",
      "name",
      "role",
    ]);
    assert.equal(captured.calls.length, 1);
    assert.equal(
      captured.calls[0].prompt,
      factoryGenerationPrompt(captured.request, catalogue),
    );
    assert.equal(captured.repairAttempt, null);
    // Re-parse the exact captured response offline; no model request and no expected business answer.
    if (typeof captured.calls[0].raw === "string") {
      const replay = await generateDraft(
        captured.request,
        catalogue,
        async () => captured.calls[0].raw,
      );
      assert.deepEqual(replay, captured.generationResult);
      replayed++;
    }
  }
  console.log(
    `PASS: input/prompt/source/hash integrity; ${replayed} raw responses replayed. This is not a semantic verdict.`,
  );
}

async function run() {
  const model = process.env.FACTORY_MODEL;
  const apiKey = process.env.FACTORY_MODEL_API_KEY;
  const provider = process.env.FACTORY_MODEL_PROVIDER ?? "openai";
  assert(
    model && apiKey,
    "FACTORY_MODEL and FACTORY_MODEL_API_KEY are required.",
  );
  assert(
    provider === "openai" ||
      provider === "openai-compatible" ||
      provider === "deepseek",
  );
  const complete = createHttpCompleter({
    model,
    apiKey,
    provider,
    url:
      process.env.FACTORY_MODEL_API_URL ??
      "https://api.openai.com/v1/chat/completions",
  });
  const startedAt = new Date().toISOString();
  const directory = resolve(
    root,
    "../.logs",
    `agent-factory-understanding-smoke-${startedAt.replace(/[:.]/g, "-")}`,
  );
  const frozen = join(directory, "frozen");
  await mkdir(frozen, { recursive: true });
  const sourceHashes = await productionHashes();
  const entries: { file: string; sha256: string }[] = [];
  let generated = 0;
  for (const [index, request] of cases.entries()) {
    const parsed = parseAgentCreationRequest(request);
    assert(parsed.ok);
    const calls: { prompt: string; raw?: string; error?: string }[] = [];
    const started = performance.now();
    let generationResult;
    try {
      generationResult = await generateDraft(
        parsed.value,
        catalogue,
        async (prompt, signal) => {
          const call: (typeof calls)[number] = { prompt };
          calls.push(call);
          try {
            call.raw = await complete(prompt, signal);
            return call.raw;
          } catch (error) {
            call.error = error instanceof Error ? error.name : "ModelError";
            throw error;
          }
        },
        AbortSignal.timeout(60_000),
      );
    } catch {
      generationResult = { ok: false as const, dependencyFailure: true };
    }
    if (generationResult.ok) generated++;
    const file = `case-${String(index + 1).padStart(2, "0")}-${request.name.toLowerCase().replaceAll(" ", "-")}.json`;
    const sha = await freeze(join(frozen, file), {
      request,
      modelRef: `${provider}/${model}`,
      capturedAt: new Date().toISOString(),
      durationMs: performance.now() - started,
      calls,
      generationResult,
      staticVerification: {
        stage:
          "parseAgentCreationRequest + parseIntentNormalization + parseAgentDraft",
        verdict:
          "dependencyFailure" in generationResult
            ? "NOT_RUN"
            : generationResult.ok
              ? "PASS"
              : "FAIL",
        issues: "issues" in generationResult ? generationResult.issues : [],
        scope:
          "Draft schema, size, intent confidence consistency and request provenance only. Resource/spec verification not run.",
      },
      productionSemanticReview: {
        status: "NOT_RUN",
        reason:
          "reviewSpec requires a compiled resource-bound artifact; generic semantic assessment follows freezing.",
      },
      repairAttempt: null,
      stopStage: "AgentDraft before verifyStaticSpec/resolveDraftResources",
    });
    entries.push({ file, sha256: sha });
    console.log(`Saved ${file}; no semantic evaluation performed.`);
  }
  await freeze(join(frozen, "manifest.json"), {
    startedAt,
    frozenAt: new Date().toISOString(),
    productionHashes: sourceHashes,
    cases: entries,
    resourceSnapshot: catalogue,
    modelCalls: 3,
    generationPrompt:
      "Unmodified factoryGenerationPrompt; no smoke prompt or case-specific expectations.",
  });
  await verify(directory);
  console.log(directory);
  console.log(`${generated}/3 valid AgentDrafts captured.`);
  if (generated !== 3) process.exitCode = 1;
}

if (process.argv[2] === "--run" && process.argv.length === 3) await run();
else if (
  process.argv[2] === "--verify" &&
  process.argv[3] &&
  process.argv.length === 4
)
  await verify(resolve(process.argv[3]));
else
  throw new Error(
    "Use --run for exactly three live generations, or --verify <output-directory> offline.",
  );
