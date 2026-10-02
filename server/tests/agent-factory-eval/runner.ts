// Keep eventsource ESM initialization consistent with the existing Backend evaluator.
import "eventsource";
import type { Message } from "@ag-ui/client";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  createFactoryClient,
  type FactoryConstructionResponse,
  type FactoryObservation,
} from "../../../agent-factory/src/index.js";
import { createFactoryHandler } from "../../../agent-factory/src/http.js";
import { createHttpCompleter } from "../../../agent-factory/src/model.js";
import { readBoundedText } from "../../../agent-factory/src/io.js";
import {
  createAgentFactoryService,
  createFactoryRuntimeReadiness,
} from "../../src/agents/factory.js";
import {
  registeredAgentFromRow,
  resolveRuntimeAgents,
  runtimeModelForEnvironment,
  type RegisteredAgent,
} from "../../src/copilot.js";
import { loadTenantPackage } from "../../src/tenant-package.js";
import { toolNameFor } from "../../src/plugins/store.js";
import {
  behaviors,
  cases,
  catalogue,
  evalTools,
  type ToolCall,
} from "./fixtures.js";
import {
  constructionMetrics,
  scoreBehavior,
  scoreConstruction,
} from "./scoring.js";

const root = resolve(import.meta.dir, "../../..");
const actor = { id: "factory-evaluation-owner", role: "user" as const };
const secrets = () =>
  [
    process.env.FACTORY_SERVICE_TOKEN,
    process.env.FACTORY_MODEL_API_KEY,
    process.env.OPENAI_API_KEY,
    process.env.ANTHROPIC_API_KEY,
  ].filter((s): s is string => !!s && s.length >= 8);

export function modelEvidence(body: string) {
  const tools = new Map<number, { name: string; arguments: string }>();
  let usage: unknown = null;
  const events = !body.trim().startsWith("{")
    ? body
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .filter((line) => line && line !== "[DONE]")
    : [body];
  for (const event of events) {
    const data = JSON.parse(event);
    if (data.usage) usage = data.usage;
    if (data.response?.usage) usage = data.response.usage;
    if (data.item?.type === "function_call") {
      const previous = tools.get(data.output_index) ?? {
        name: "",
        arguments: "",
      };
      tools.set(data.output_index, {
        name: data.item.name,
        arguments: data.item.arguments || previous.arguments,
      });
    }
    if (data.type === "response.function_call_arguments.delta") {
      const previous = tools.get(data.output_index);
      if (previous) previous.arguments += data.delta;
    }
    for (const choice of data.choices ?? []) {
      for (const t of (choice.delta ?? choice.message)?.tool_calls ?? []) {
        const previous = tools.get(t.index ?? tools.size) ?? {
          name: "",
          arguments: "",
        };
        previous.name += t.function?.name ?? "";
        previous.arguments += t.function?.arguments ?? "";
        tools.set(t.index ?? tools.size, previous);
      }
    }
  }
  return { usage, toolAttempts: [...tools.values()] };
}

async function productionHashes() {
  const hashes: Record<string, string> = {};
  for (const directory of [
    "server/src",
    "agent-factory/src",
    "app/src",
    "shared",
    "domain-tools",
  ]) {
    for (const entry of await readdir(join(root, directory), {
      recursive: true,
      withFileTypes: true,
    })) {
      if (!entry.isFile()) continue;
      const path = join(entry.parentPath, entry.name);
      hashes[path.slice(root.length + 1)] = createHash("sha256")
        .update(await readFile(path))
        .digest("hex");
    }
  }
  for (const path of [
    "package.json",
    "bun.lock",
    "server/package.json",
    "agent-factory/package.json",
    ".env",
    ".env.example",
  ]) {
    hashes[path] = createHash("sha256")
      .update(await readFile(join(root, path)))
      .digest("hex");
  }
  return hashes;
}
const asJson = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
async function save(path: string, value: string) {
  if (secrets().some((secret) => value.includes(secret)))
    throw new Error("Evidence refused: a configured secret was detected.");
  await writeFile(path, value);
}
const reportMarkdown = (
  title: string,
  report: {
    counts: { cases: number; passed: number; failed: number; blocked?: number };
    cases: { id: string; pass: boolean }[];
  },
  metrics: unknown,
) =>
  `# ${title}\n\n${asJson(report.counts)}\n\n| Case | Result |\n| --- | --- |\n${report.cases.map((c) => `| ${c.id} | ${c.pass ? "PASS" : "FAIL/BLOCKED"} |`).join("\n")}\n\nMetrics and limitations:\n\n\`\`\`json\n${asJson(metrics)}\`\`\`\n\nFull artifacts, observations and limitations are in the adjacent JSON report.\n`;
const counts = (reports: { pass: boolean; blocked?: boolean }[]) => ({
  cases: reports.length,
  passed: reports.filter((c) => c.pass).length,
  failed: reports.filter((c) => !c.pass && !c.blocked).length,
  blocked: reports.filter((c) => c.blocked).length,
});

/** Temporary script composition only; normal Backend startup never imports this module. */
export async function runEvaluation() {
  const startedAt = new Date().toISOString();
  const out = join(
    root,
    ".logs",
    `agent-factory-eval-${startedAt.replaceAll(":", "-")}`,
  );
  await mkdir(out, { recursive: true });
  const baseline = await productionHashes();
  const token = randomUUID().replaceAll("-", "");
  const factoryCalls: {
    stage?: FactoryObservation["stage"];
    attempt?: number;
    durationMs?: number;
    status?: string;
    httpStatus: number;
    usage: unknown;
  }[] = [];
  const runtimeCalls: {
    model: string;
    httpStatus: number;
    durationMs: number;
    evidence: Awaited<ReturnType<typeof modelEvidence>> | null;
  }[] = [];
  let factoryServer: ReturnType<typeof Bun.serve> | undefined;
  let runtimeProxy: ReturnType<typeof Bun.serve> | undefined;
  const previousBase = process.env.OPENAI_BASE_URL;
  const previousError = console.error;
  const blockers: string[] = [];
  const artifacts = new Map<string, FactoryConstructionResponse>();
  const level1: (ReturnType<typeof scoreConstruction> & {
    latencyMs: number;
    factoryModelCalls: unknown[];
    artifact: FactoryConstructionResponse | null;
  })[] = [];
  const level2: (Partial<ReturnType<typeof scoreBehavior>> & {
    id: string;
    pass: boolean;
    blocked: boolean;
    latencyMs: number;
    runtimeModelCalls: unknown[];
    blocker?: string;
  })[] = [];
  let runtimeModelName: string | null = null;
  try {
    const provider = process.env.FACTORY_MODEL_PROVIDER ?? "openai";
    if (!["openai", "openai-compatible"].includes(provider))
      throw new Error("Unsupported configured Factory provider.");
    const model = process.env.FACTORY_MODEL?.trim();
    const apiKey = process.env.FACTORY_MODEL_API_KEY?.trim();
    if (!model || !apiKey)
      throw new Error(
        "FACTORY_MODEL and FACTORY_MODEL_API_KEY must be configured.",
      );
    const complete = createHttpCompleter(
      {
        provider: provider as "openai" | "openai-compatible",
        model,
        apiKey,
        url:
          process.env.FACTORY_MODEL_API_URL ||
          "https://api.openai.com/v1/chat/completions",
      },
      async (url, options) => {
        const response = await fetch(url, options);
        let usage: unknown = null;
        if (response.ok) {
          const body = JSON.parse(
            await readBoundedText(response.clone(), 256 * 1024),
          );
          usage = body.usage ?? null;
        }
        factoryCalls.push({ httpStatus: response.status, usage });
        return response;
      },
    );
    factoryServer = Bun.serve({
      hostname: "127.0.0.1",
      port: 0,
      idleTimeout: 120,
      fetch: createFactoryHandler({
        token,
        complete,
        modelRef: `${provider}/${model}`,
        observe: (event) => {
          const call = factoryCalls.at(-1);
          if (call && !call.stage) Object.assign(call, event);
          else factoryCalls.push({ ...event, httpStatus: 0, usage: null });
        },
      }),
    });
    const grants = new Set<string>();
    const reader = {
      factoryCatalogue: async () => ({ ok: true as const, value: catalogue }),
      factoryResourceFacts: async (
        owner: string,
        _agent: string,
        refs: readonly { kind: "tool" | "skill"; ref: string }[],
      ) => ({
        ok: true as const,
        value: refs.map((t) => ({
          ...t,
          resource:
            catalogue.tools.find((entry) => entry.ref === t.ref) ?? null,
          granted: owner === actor.id && grants.has(t.ref),
          configured: true,
          connected: true,
        })),
      }),
    };
    const service = createAgentFactoryService({
      store: reader,
      constructSpec: createFactoryClient({
        url: factoryServer.url.toString(),
        token,
      }),
    });
    for (const c of cases) {
      // Script-only pacing prevents this dataset from exhausting a low-TPM model quota.
      if (level1.length)
        await new Promise((resolve) => setTimeout(resolve, 20_000));
      const start = performance.now();
      const beforeCalls = factoryCalls.length;
      const result = await service.construct(
        { id: actor.id, isAdmin: false },
        c.input,
      );
      if (result.ok) artifacts.set(c.id, result.value);
      const scored = {
        ...scoreConstruction(c, result),
        latencyMs: performance.now() - start,
        factoryModelCalls: factoryCalls.slice(beforeCalls),
        artifact: result.ok ? result.value : null,
      };
      level1.push(scored);
      await save(join(out, "level-1-progress.json"), asJson(level1));
      console.log(
        `${c.id}: ${scored.pass ? "PASS" : "FAIL"} (${scored.construction}, ${scored.selectedTools.join(", ") || "no special tools"})`,
      );
    }

    const tenant = await loadTenantPackage(
      resolve(
        root,
        "server",
        process.env.TENANT_PACKAGE_DIR?.trim() || "../examples/fintech",
      ),
    );
    const runtimeModel = runtimeModelForEnvironment(tenant.model);
    runtimeModelName = `${runtimeModel.provider}/${runtimeModel.defaultModel}`;
    if (
      runtimeModel.provider !== "openai" ||
      !process.env.OPENAI_API_KEY?.trim()
    )
      throw new Error(
        "Level 2 needs the configured OpenAI runtime credential/provider.",
      );
    const upstream = new URL(previousBase || "https://api.openai.com");
    if (
      upstream.username ||
      upstream.password ||
      upstream.search ||
      upstream.hash ||
      !["http:", "https:"].includes(upstream.protocol)
    )
      throw new Error("Invalid runtime model endpoint.");
    const upstreamBase = upstream.pathname.replace(/\/(?:v1)?\/?$/, "");
    let pending: Promise<void>[] = [];
    let runCalls = 0;
    runtimeProxy = Bun.serve({
      hostname: "127.0.0.1",
      port: 0,
      idleTimeout: 120,
      fetch: async (request) => {
        const path = new URL(request.url).pathname;
        const api = path.endsWith("/responses")
          ? "responses"
          : path.endsWith("/chat/completions")
            ? "chat/completions"
            : null;
        if (!api) return new Response("Not found", { status: 404 });
        if (++runCalls > 8)
          return new Response("Eval call limit", { status: 429 });
        const start = performance.now();
        const body = await request.text();
        const target = new URL(upstream);
        target.pathname = `${upstreamBase}/v1/${api}`;
        const response = await fetch(target, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            authorization: request.headers.get("authorization") ?? "",
          },
          body,
          signal: AbortSignal.any([
            request.signal,
            AbortSignal.timeout(60_000),
          ]),
          redirect: "error",
        });
        const call = {
          model: JSON.parse(body).model as string,
          httpStatus: response.status,
          durationMs: 0,
          evidence: null as ReturnType<typeof modelEvidence> | null,
        };
        runtimeCalls.push(call);
        if (!response.ok) {
          await response.body?.cancel();
          call.durationMs = performance.now() - start;
          return Response.json(
            {
              error: {
                message: "Eval model request failed.",
                type: "eval_model_error",
                code: "eval_model_error",
              },
            },
            { status: response.status },
          );
        }
        // Observe the actual response without replacing the runtime's streaming behavior.
        pending.push(
          (async () => {
            try {
              if (response.ok)
                call.evidence = modelEvidence(
                  await readBoundedText(response.clone(), 1024 * 1024),
                );
            } finally {
              call.durationMs = performance.now() - start;
            }
          })(),
        );
        return response;
      },
    });
    process.env.OPENAI_BASE_URL = runtimeProxy.url
      .toString()
      .replace(/\/$/, "");
    console.error = () =>
      previousError(
        "Runtime diagnostic omitted; inspect sanitized eval evidence.",
      );
    const gate = createFactoryRuntimeReadiness(reader);
    async function build(
      id: string,
      artifact: FactoryConstructionResponse,
      calls: ToolCall[],
    ) {
      const row = {
        id,
        name: artifact.spec.identity.name,
        title: artifact.spec.identity.role,
        roleDescription: artifact.spec.identity.description,
        ownerUserId: actor.id,
        type: "built_in" as const,
        configuration: {
          systemPrompt: artifact.systemPrompt,
          factory: {
            spec: artifact.spec,
            verification: artifact.verification,
            state: "ready",
            requestHash: "a".repeat(64),
            creationKeyHash: "b".repeat(64),
          },
        },
      };
      const normalized = registeredAgentFromRow(row);
      const verdict = await gate(actor, row);
      const registered: RegisteredAgent =
        normalized && verdict.ready
          ? normalized
          : {
              id,
              name: row.name,
              type: "unavailable",
              reason: !verdict.ready ? verdict.reason : "Invalid artifact",
            };
      const refs = [
        ...artifact.spec.resources.map((t) => t.ref),
        ...artifact.spec.defaultTools.map((t) => t.ref),
      ];
      const roster = await resolveRuntimeAgents(
        async () => [registered],
        runtimeModel,
        async () => process.env.OPENAI_API_KEY ?? null,
        undefined,
        async () => evalTools(refs, grants, calls),
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        id,
      );
      const agent = roster[id]?.clone();
      if (!agent) throw new Error("Eval agent was not built.");
      return agent;
    }
    for (const c of behaviors) {
      const artifact = artifacts.get(c.constructionId);
      if (!artifact) {
        level2.push({
          id: c.id,
          pass: false,
          blocked: true,
          latencyMs: 0,
          runtimeModelCalls: [],
          blocker: "Factory returned no usable artifact.",
        });
        continue;
      }
      grants.clear();
      for (const ref of [
        ...artifact.spec.resources.map((t) => t.ref),
        ...artifact.spec.defaultTools.map((t) => t.ref),
      ]) {
        if (catalogue.tools.some((t) => t.ref === ref && t.effect === "read"))
          grants.add(ref);
      }
      const calls: ToolCall[] = [];
      const start = performance.now();
      const beforeCalls = runtimeCalls.length;
      runCalls = 0;
      pending = [];
      const agent = await build(c.id, artifact, calls);
      agent.addMessage({ id: randomUUID(), role: "user", content: c.prompt });
      let error: string | null = null;
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        await Promise.race([
          agent.runAgent(),
          new Promise<never>((_, reject) => {
            timer = setTimeout(() => {
              agent.abortRun();
              reject(new Error("deadline"));
            }, 90_000);
            timer.unref();
          }),
        ]);
      } catch {
        error =
          "Runtime failed or exceeded the eval deadline; provider diagnostics omitted.";
      } finally {
        clearTimeout(timer);
      }
      if (
        (await Promise.allSettled(pending)).some(
          (result) => result.status === "rejected",
        )
      )
        error = "Runtime response evidence could not be parsed completely.";
      const observed = runtimeCalls.slice(beforeCalls);
      const attempts = observed.flatMap(
        (call) =>
          call.evidence?.toolAttempts.map(
            (t) =>
              catalogue.tools.find((tool) => toolNameFor(tool.ref) === t.name)
                ?.ref ?? t.name,
          ) ?? [],
      );
      const last = agent.messages.findLast(
        (m: Message) =>
          m.role === "assistant" &&
          typeof m.content === "string" &&
          m.content.length > 0,
      );
      const scored = {
        ...scoreBehavior(
          c,
          calls,
          typeof last?.content === "string" ? last.content : "",
          attempts,
          error,
        ),
        blocked: false,
        latencyMs: performance.now() - start,
        runtimeModelCalls: observed,
      };
      level2.push(scored);
      console.log(
        `${c.id}: ${scored.pass ? "PASS" : "FAIL"} (${calls.map((t) => t.toolRef).join(", ") || "no tool calls"})`,
      );
      await save(join(out, "level-2-progress.json"), asJson(level2));
    }
    // Selected != granted: same production readiness gate, no model call and no execution.
    const artifact = artifacts.get("L06");
    if (artifact) {
      grants.clear();
      const calls: ToolCall[] = [];
      const beforeCalls = runtimeCalls.length;
      const agent = await build("B06", artifact, calls);
      agent.addMessage({
        id: randomUUID(),
        role: "user",
        content: "Research Helios.",
      });
      let blocked = false;
      try {
        await agent.runAgent();
      } catch {
        blocked = true;
      }
      grants.add("web/search");
      const stale = evalTools(["web/search"], grants, calls)[0]!;
      grants.delete("web/search");
      const refusal = await stale.execute({ query: "Helios" });
      level2.push({
        id: "B06-authorization",
        pass:
          blocked &&
          runtimeCalls.length === beforeCalls &&
          refusal.startsWith("Refused.") &&
          calls.every((t) => !t.authorized),
        blocked: false,
        latencyMs: 0,
        runtimeModelCalls: [],
        calls,
        blocker:
          "Expected missing-grant refusal plus stale-offer revocation refusal.",
      });
    } else
      level2.push({
        id: "B06-authorization",
        pass: false,
        blocked: true,
        latencyMs: 0,
        runtimeModelCalls: [],
        blocker: "No selected-tool artifact for the authorization test.",
      });
  } catch (error) {
    blockers.push(
      error instanceof Error &&
        /^(FACTORY_MODEL|Unsupported configured|Level 2 needs|Invalid runtime)/.test(
          error.message,
        )
        ? error.message
        : "Eval infrastructure failed; private diagnostics omitted.",
    );
  } finally {
    factoryServer?.stop(true);
    runtimeProxy?.stop(true);
    console.error = previousError;
    if (previousBase === undefined) delete process.env.OPENAI_BASE_URL;
    else process.env.OPENAI_BASE_URL = previousBase;
  }
  for (const c of behaviors)
    if (!level2.some((r) => r.id === c.id))
      level2.push({
        id: c.id,
        pass: false,
        blocked: true,
        latencyMs: 0,
        runtimeModelCalls: [],
        blocker: "Runtime evaluation unavailable.",
      });
  const after = await productionHashes();
  const changedProductionFiles = [
    ...new Set([...Object.keys(baseline), ...Object.keys(after)]),
  ].filter((path) => baseline[path] !== after[path]);
  const entry = await readFile(join(root, "server/src/index.ts"), "utf8");
  const cleanup = {
    temporaryFactoryServerStopped:
      !factoryServer ||
      (await fetch(factoryServer.url, {
        signal: AbortSignal.timeout(1000),
      }).then(
        () => false,
        () => true,
      )),
    temporaryRuntimeProxyStopped:
      !runtimeProxy ||
      (await fetch(runtimeProxy.url, {
        signal: AbortSignal.timeout(1000),
      }).then(
        () => false,
        () => true,
      )),
    runtimeEnvironmentRestored: process.env.OPENAI_BASE_URL === previousBase,
    changedProductionFiles,
    productionFactoryInjectionAbsent:
      !/createAgentFactoryService|createFactoryClient/.test(entry),
    productionEvalImportsAbsent:
      !/factory-eval|agent-factory-eval|FACTORY_EVAL_MODE/.test(entry),
    databaseUsed: false,
  };
  const l1 = {
    startedAt,
    completedAt: new Date().toISOString(),
    model: `${process.env.FACTORY_MODEL_PROVIDER ?? "openai"}/${process.env.FACTORY_MODEL ?? "unconfigured"}`,
    caseCountExpected: cases.length,
    counts: counts(level1),
    metrics: constructionMetrics(level1),
    factoryModelCallCount: factoryCalls.length,
    runtimeModelCallCount: 0,
    modelCalls: factoryCalls,
    cases: level1,
    blockers: level1.length === cases.length ? [] : blockers,
  };
  const l2 = {
    startedAt,
    completedAt: new Date().toISOString(),
    model: runtimeModelName,
    counts: counts(level2),
    caseCountExpected: behaviors.length,
    factoryModelCallCount: 0,
    runtimeModelCallCount: runtimeCalls.length,
    modelCalls: runtimeCalls,
    cases: level2,
    blockers,
  };
  await save(join(out, "level-1-report.json"), asJson(l1));
  await save(
    join(out, "level-1-report.md"),
    reportMarkdown("Level 1 construction", l1, {
      model: l1.model,
      metrics: l1.metrics,
      factoryModelCallCount: l1.factoryModelCallCount,
      tokenUsage: factoryCalls.map((c) => c.usage),
      blockers: l1.blockers,
    }),
  );
  await save(join(out, "level-2-report.json"), asJson(l2));
  await save(
    join(out, "level-2-report.md"),
    reportMarkdown("Level 2 behavior", l2, {
      model: l2.model,
      runtimeModelCallCount: l2.runtimeModelCallCount,
      tokenUsage: runtimeCalls.map((c) => c.evidence?.usage ?? null),
      blockers,
      groundingScope:
        "Bounded fixture anchors and source URLs; no independent semantic judge",
    }),
  );
  await save(join(out, "cleanup.json"), asJson(cleanup));
  await save(
    join(out, "summary.md"),
    `# Agent Factory evaluation\n\nFactory: ${l1.model}; runtime: ${runtimeModelName ?? "unavailable"}.\n\nLevel 1: ${l1.counts.passed}/${cases.length} passed. Level 2: ${l2.counts.passed}/${level2.length} passed, ${l2.counts.blocked} blocked.\n\nNo persistence or production wiring. Both loopback servers stopped; runtime environment restored.\n\n\`\`\`json\n${asJson({ cleanup, metrics: l1.metrics, blockers })}\`\`\`\n\nRegression verification is recorded separately after cleanup. Model-quality failures are retained; no selective reruns or Factory repairs.\n`,
  );
  console.log(`Evidence: ${out}`);
  return {
    out,
    level1: l1,
    level2: l2,
    cleanup,
    pass:
      level1.length === cases.length &&
      level1.every((c) => c.pass) &&
      level2.every((c) => c.pass) &&
      !changedProductionFiles.length &&
      !blockers.length,
  };
}

if (import.meta.main) process.exitCode = (await runEvaluation()).pass ? 0 : 1;
