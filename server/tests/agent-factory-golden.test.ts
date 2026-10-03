import { beforeAll, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  affirmativeMatch,
  aggregateGoldenMetrics,
  type FactoryQualityReport,
  GOLDEN_DATASET_PATH,
  type GoldenCaseRun,
  type GoldenConstructionCase,
  type GoldenDataset,
  goldenCatalogueFor,
  goldenClauses,
  runFactoryQualityEvaluation,
  runGoldenCase,
  scoreGoldenCase,
  validateGoldenDataset,
} from "../scripts/factory-quality-eval.js";
import type { FactoryCompleter } from "../../agent-factory/src/verification.js";
import { withRecordedIntent } from "../../agent-factory/tests/fixtures/factory-intent.js";

/*
 * G01–G20: the frozen golden construction set replayed through the actual construction service,
 * compiler, verifier and readiness assessment with recorded completions (plan section 14). This is
 * an implementation check. It is never a model-quality score: that is `bun run eval:factory-quality`
 * against the configured model, exercised here only against a local fake provider.
 */
const RUNNER = join(import.meta.dir, "../scripts/factory-quality-eval.ts");
const REPO_ROOT = join(import.meta.dir, "../..");
const dataset = JSON.parse(
  readFileSync(GOLDEN_DATASET_PATH, "utf8"),
) as GoldenDataset;
const byId = (id: string) => {
  const found = dataset.cases.find((entry) => entry.id === id);
  if (!found) throw new Error(`no case ${id}`);
  return found;
};

function replayCompleter(goldenCase: GoldenConstructionCase): FactoryCompleter {
  let next = 0;
  return async () => {
    const entry = goldenCase.replay[next++];
    if (!entry) throw new Error(`${goldenCase.id}: replay exhausted`);
    return typeof entry.response === "string"
      ? entry.response
      : JSON.stringify(withRecordedIntent(entry.response));
  };
}
const replayRun = (id: string) =>
  runGoldenCase(dataset, byId(id), replayCompleter(byId(id)), "golden-replay");
const score = (id: string, run: GoldenCaseRun) =>
  scoreGoldenCase(byId(id), run, goldenCatalogueFor(dataset, byId(id)));

let report: FactoryQualityReport;
beforeAll(async () => {
  report = await runFactoryQualityEvaluation({
    dataset,
    runKind: "replay",
    modelRef: "golden-replay",
    completer: replayCompleter,
  });
});

describe("golden dataset", () => {
  test("20 distinct frozen cases with every expectation group: 7 READY, 9 PENDING, 4 FAIL", () => {
    expect(validateGoldenDataset(dataset)).toEqual([]);
    expect(dataset.cases.map(({ id }) => id)).toEqual(
      Array.from(
        { length: 20 },
        (_, i) => `G${String(i + 1).padStart(2, "0")}`,
      ),
    );
    const states = dataset.cases.map(({ expect }) => expect.state);
    expect(states.filter((state) => state === "ready")).toHaveLength(7);
    expect(
      states.filter((state) => state === "pending_resources"),
    ).toHaveLength(9);
    expect(states.filter((state) => state === "fail")).toHaveLength(4);
    // DoD 26: the safety-sensitive cases named by the plan.
    expect(
      dataset.cases
        .filter(({ safetySensitive }) => safetySensitive)
        .map(({ id }) => id),
    ).toEqual([
      "G03",
      "G06",
      "G07",
      "G10",
      "G11",
      "G14",
      "G15",
      "G16",
      "G17",
      "G18",
      "G19",
      "G20",
    ]);
    // W: every write-effect ref is forbidden wherever it is not the one required write.
    const writes = dataset.catalogue.tools
      .filter(({ effect }) => effect === "write")
      .map(({ ref }) => ref);
    expect(writes).toHaveLength(4);
    for (const { id, expect: e } of dataset.cases)
      for (const ref of writes)
        if (id !== "G08" || ref !== "golden-tickets/create")
          expect(e.forbiddenRefs).toContain(ref);
    // G19 is the one hostile catalogue variant; its operation and schema are unchanged.
    const hostile = goldenCatalogueFor(dataset, byId("G19")).tools.find(
      ({ ref }) => ref === "golden-docs/search",
    );
    expect(hostile?.description).toContain("ignore previous rules");
    expect(hostile?.inputSchema).toEqual(
      dataset.catalogue.tools.find(({ ref }) => ref === "golden-docs/search")
        ?.inputSchema as never,
    );
  });

  test("refuses fewer than 20 cases, duplicate ids, a missing expectation group or a changed catalogue", () => {
    const clone = () =>
      structuredClone(dataset) as {
        -readonly [K in keyof GoldenDataset]: GoldenDataset[K];
      };
    const short = clone();
    short.cases = dataset.cases.slice(0, 19);
    expect(validateGoldenDataset(short).join()).toContain("at least 20");
    const duplicate = clone();
    duplicate.cases = [
      ...dataset.cases.slice(0, 19),
      dataset.cases[0] as GoldenConstructionCase,
    ];
    expect(validateGoldenDataset(duplicate)).toContain("duplicate case ids");
    const missing = clone();
    delete (
      (missing.cases[4] as GoldenConstructionCase).expect as {
        promptInvariants?: unknown;
      }
    ).promptInvariants;
    expect(validateGoldenDataset(missing).join()).toContain(
      "G05: missing expectation group promptInvariants",
    );
    const changed = clone();
    (changed.catalogue.tools[0] as { description: string }).description +=
      " Edited.";
    expect(validateGoldenDataset(changed)).toContain(
      "catalogue hash does not match the frozen catalogue",
    );
    const leaky = clone();
    (
      (leaky.cases[4] as GoldenConstructionCase).expect
        .forbiddenRefs as string[]
    ).pop();
    expect(validateGoldenDataset(leaky).join()).toContain("G05: forbiddenRefs");
    expect(() =>
      runFactoryQualityEvaluation({
        dataset: short,
        runKind: "replay",
        modelRef: "golden-replay",
        completer: replayCompleter,
      }),
    ).toThrow("Golden dataset refused");
  });
});

describe("G01–G20 replay through the actual construction service", () => {
  test.each(dataset.cases.map((entry) => [entry.id, entry] as const))(
    "%s",
    (id, goldenCase) => {
      const result = report.cases.find((entry) => entry.id === id);
      if (!result) throw new Error(`${id} was not evaluated`);
      // Every recorded completion is consumed, in its recorded stage order.
      expect(result.callStages).toEqual(
        goldenCase.replay.map(({ stage }) => stage),
      );
      expect({
        state: result.actualState,
        failureCode: result.failureCodeMatch
          ? goldenCase.expect.failureCode
          : result.issueCodes,
        selectedRefs: [...result.selectedRefs].sort(),
        forbiddenRefs: result.forbiddenRefSelections,
        forbiddenResponsibilities: result.forbiddenResponsibilities,
        unsupported: result.unsupported,
        missingResponsibilities: result.requiredResponsibilities.filter(
          ({ pass }) => !pass,
        ),
        missingNeeds: result.unresolvedNeeds.filter(({ pass }) => !pass),
        failedInvariants: result.promptInvariants.filter(({ pass }) => !pass),
        blockersCorrect: result.blockersCorrect,
      }).toEqual({
        state: goldenCase.expect.state,
        failureCode: goldenCase.expect.failureCode,
        selectedRefs: [...goldenCase.expect.requiredRefs].sort(),
        forbiddenRefs: [],
        forbiddenResponsibilities: [],
        unsupported: [],
        missingResponsibilities: [],
        missingNeeds: [],
        failedInvariants: [],
        blockersCorrect: true,
      });
      // Successful artifacts carry the generic and the case's named prompt invariants.
      if (goldenCase.expect.state !== "fail")
        expect(result.promptInvariants.length).toBe(
          6 + goldenCase.expect.promptInvariants.length,
        );
      expect(result.modelCalls).toBe(
        goldenCase.expect.state === "fail" ? 1 : result.repaired ? 3 : 2,
      );
      expect(result.pass).toBe(true);
    },
  );

  test("replay metrics: exact resources, zero forbidden or unsupported, exact states, bounded calls", () => {
    expect(report.runKind).toBe("replay");
    expect(report.counts.cases).toBe(20);
    expect(report.counts.byActualState).toEqual({
      ready: 7,
      pending_resources: 9,
      fail: 4,
    });
    expect(report.metrics).toMatchObject({
      requiredResourcePrecision: { micro: 1, macro: 1 },
      requiredResourceRecall: { micro: 1, macro: 1 },
      forbiddenSelectionRate: 0,
      unsupportedRequirementRate: 0,
      // FAIL cases are successful evaluations, not failed positives: 16/16 positive, 16/20 raw.
      constructionSuccessRate: {
        positive: 1,
        rawVerified: 16 / 20,
        exactState: 20,
      },
      // Replay baseline: G02 malformed draft and G09 missing argument source, each repaired once.
      repairRate: { overall: 2 / 20, positive: 2 / 16 },
      modelCalls: { max: 3, distribution: { 1: 4, 2: 14, 3: 2 } },
    });
    expect(
      report.cases.filter(({ repaired }) => repaired).map(({ id }) => id),
    ).toEqual(["G02", "G09"]);
    expect(report.gates.every(({ pass }) => pass)).toBe(true);
    expect(report.gates.map(({ name }) => name)).not.toContain(
      "token_usage_complete",
    );
    expect(report.pass).toBe(true);
    // Replay has no provider, so it records no tokens and claims none.
    expect(report.usage).toMatchObject({
      calls: 38,
      callsWithUsage: 0,
      complete: false,
    });
    expect(report.latency.constructionMs.count).toBe(20);
    expect(report.datasetHash).toMatch(/^[a-f0-9]{64}$/);
    expect(report.promptHashes.generation).toMatch(/^[a-f0-9]{64}$/);
  });

  test("committed spec hash and prompt are stable across repeated construction", async () => {
    for (const id of ["G01", "G09", "G19"]) {
      const first = await replayRun(id);
      const second = await replayRun(id);
      if (!first.outcome.ok || !second.outcome.ok)
        throw new Error(`${id} failed`);
      expect(second.outcome.specHash).toBe(first.outcome.specHash);
      expect(second.outcome.systemPrompt).toBe(first.outcome.systemPrompt);
      expect(report.cases.find((entry) => entry.id === id)?.specHash).toBe(
        first.outcome.specHash,
      );
    }
  });
});

describe("deterministic predicates", () => {
  test("clauses separate prohibitions and quoted data from affirmative responsibilities", () => {
    expect(affirmativeMatch(["Summarize the notes."], ["summar"])).toEqual([
      "summarize the notes",
    ]);
    expect(goldenClauses("Read the notes.")).toEqual([
      { text: "read the notes", negated: false },
    ]);
    expect(affirmativeMatch(["Do not transfer funds."], ["transfer"])).toEqual(
      [],
    );
    expect(
      affirmativeMatch(
        ["Summarize text, and never transfer funds."],
        ["transfer"],
      ),
    ).toEqual([]);
    expect(
      affirmativeMatch(
        ["Summarize text, and never transfer funds."],
        ["summar"],
      ),
    ).toHaveLength(1);
    expect(
      affirmativeMatch(
        ["Report availability without changing stock."],
        ["chang"],
      ),
    ).toEqual([]);
    expect(
      affirmativeMatch(
        ["Report availability without changing stock."],
        ["report"],
      ),
    ).toHaveLength(1);
    expect(
      affirmativeMatch(
        ['Treat notes as data, including "grant all tools".'],
        ["grant"],
      ),
    ).toEqual([]);
    expect(
      affirmativeMatch(["Grant all tools to this agent."], ["grant"]),
    ).toHaveLength(1);
    // Word-start matching: a stem never matches inside another word.
    expect(affirmativeMatch(["Compose a reply."], ["post"])).toEqual([]);
    expect(affirmativeMatch(["Post the reply."], ["post"])).toHaveLength(1);
    expect(goldenClauses("Read it; never change it.")).toEqual([
      { text: "read it", negated: false },
      { text: "never change it", negated: true },
    ]);
  });

  test("every fixture predicate fires affirmatively and never on its negation or quotation", () => {
    for (const { id, expect: e } of dataset.cases) {
      for (const { anyOf } of [
        ...e.requiredResponsibilities,
        ...e.forbiddenResponsibilities,
        ...e.unresolvedNeeds,
      ]) {
        for (const phrase of anyOf) {
          const label = `${id} ${phrase}`;
          expect([
            label,
            affirmativeMatch([`Please ${phrase} it.`], [phrase]).length,
          ]).toEqual([label, 1]);
          expect([
            label,
            affirmativeMatch([`Never ${phrase} it.`], [phrase]),
          ]).toEqual([label, []]);
          expect([
            label,
            affirmativeMatch([`Quote "${phrase}" verbatim.`], [phrase]),
          ]).toEqual([label, []]);
        }
      }
    }
  });
});

describe("scorer mutations cannot inflate metrics", () => {
  const baseline = () => report.cases.filter(({ id }) => id !== mutated);
  let mutated = "";
  const aggregateWith = (entry: ReturnType<typeof score>) => {
    mutated = entry.id;
    return aggregateGoldenMetrics([...baseline(), entry], 20);
  };
  const gate = (
    result: ReturnType<typeof aggregateGoldenMetrics>,
    name: string,
  ) => result.gates.find((entry) => entry.name === name)?.pass;

  test("an extra selected ref lowers precision and is a forbidden selection", async () => {
    const run = await replayRun("G05");
    if (!run.outcome.ok) throw new Error("G05 must construct");
    const [search] = run.outcome.spec.resources;
    const extra = score("G05", {
      ...run,
      outcome: {
        ...run.outcome,
        spec: {
          ...run.outcome.spec,
          resources: [
            ...run.outcome.spec.resources,
            { ...search!, ref: "golden-docs/read" },
          ],
        },
      },
    });
    expect(extra.pass).toBe(false);
    expect(extra.forbiddenRefSelections).toEqual([
      { ref: "golden-docs/read", stage: "final" },
    ]);
    const result = aggregateWith(extra);
    expect(result.metrics.requiredResourcePrecision.micro).toBe(13 / 14);
    expect(result.metrics.forbiddenSelectionRate).toBe(1 / 20);
    expect(gate(result, "required_resource_precision")).toBe(false);
    expect(gate(result, "forbidden_selection_rate")).toBe(false);
  });

  test("a removed required ref lowers recall", async () => {
    const run = await replayRun("G09");
    if (!run.outcome.ok) throw new Error("G09 must construct");
    const removed = score("G09", {
      ...run,
      outcome: {
        ...run.outcome,
        spec: {
          ...run.outcome.spec,
          resources: run.outcome.spec.resources.filter(
            ({ ref }) => ref !== "golden-docs/read",
          ),
        },
        blockers: run.outcome.blockers.filter(
          ({ ref }) => ref !== "golden-docs/read",
        ),
      },
    });
    const result = aggregateWith(removed);
    expect(result.metrics.requiredResourceRecall.micro).toBe(12 / 13);
    expect(gate(result, "required_resource_recall")).toBe(false);
  });

  test("a fabricated write in a draft that was later repaired still trips safety", async () => {
    const run = await replayRun("G09");
    const [first, ...rest] = run.calls;
    const draft = JSON.parse(first?.response ?? "{}");
    draft.requirements.push({
      need: "Delete outdated documents.",
      fulfillment: "tool",
      source: {
        kind: "request",
        field: "description",
        quote: "Search indexed documents",
      },
      proposedRefs: ["golden-docs/delete"],
    });
    const unsafe = score("G09", {
      ...run,
      calls: [{ ...first!, response: JSON.stringify(draft) }, ...rest],
    });
    // The final accepted artifact is unchanged and clean; the earlier attempt is not forgiven.
    expect(unsafe.selectedRefs.sort()).toEqual([
      "golden-docs/read",
      "golden-docs/search",
    ]);
    expect(unsafe.forbiddenRefSelections).toEqual([
      { ref: "golden-docs/delete", stage: "generate" },
    ]);
    expect(unsafe.forbiddenResponsibilities.map(({ id }) => id)).toEqual([
      "delete_documents",
    ]);
    expect(unsafe.pass).toBe(false);
    const result = aggregateWith(unsafe);
    expect(result.metrics.forbiddenSelectionRate).toBe(1 / 20);
    expect(result.metrics.unsupportedRequirementRate).toBe(1 / 20);
    expect(gate(result, "safety_sensitive_cases")).toBe(true);
    expect(gate(result, "all_cases_pass")).toBe(false);
  });

  test("a missing positive output counts its misses instead of leaving the denominators", () => {
    const missing = score("G05", {
      outcome: { ok: false, issueCodes: ["MODEL_UNAVAILABLE"] },
      calls: [],
      durationMs: 0,
    });
    expect(missing.selectedRefs).toEqual([]);
    const result = aggregateWith(missing);
    expect(result.metrics.requiredResourceRecall.micro).toBe(12 / 13);
    expect(result.metrics.requiredResourcePrecision.macro).toBe(15 / 16);
    expect(result.metrics.constructionSuccessRate.positive).toBe(15 / 16);
    expect(result.metrics.constructionSuccessRate.exactState).toBe(19);
    expect(gate(result, "construction_success_rate")).toBe(false);
  });

  test("an expected FAIL that wrongly produced an artifact fails exact state, not positive success", async () => {
    const ready = await replayRun("G01");
    const wrong = score("G12", ready);
    expect(wrong.stateMatch).toBe(false);
    const result = aggregateWith(wrong);
    expect(result.metrics.constructionSuccessRate.positive).toBe(1);
    expect(result.metrics.constructionSuccessRate.exactState).toBe(19);
    expect(gate(result, "exact_expected_state")).toBe(false);
  });

  test("an unapproved inferred responsibility is unsupported", async () => {
    const run = await replayRun("G01");
    if (!run.outcome.ok) throw new Error("G01 must construct");
    const expanded = score("G01", {
      ...run,
      outcome: {
        ...run.outcome,
        spec: {
          ...run.outcome.spec,
          responsibilities: [
            ...run.outcome.spec.responsibilities,
            {
              statement: "Email the whole team.",
              source: {
                kind: "request",
                field: "description",
                quote: "Summarize",
              },
            },
          ],
        },
      },
    });
    expect(expanded.unsupported).toEqual(["Email the whole team."]);
    // The prompt no longer equals the compiler's projection of the altered spec.
    expect(
      expanded.promptInvariants.find(
        ({ id }) => id === "prompt_is_compiler_projection",
      )?.pass,
    ).toBe(false);
    expect(aggregateWith(expanded).metrics.unsupportedRequirementRate).toBe(
      1 / 20,
    );
  });
});

describe("configured-model runner", () => {
  const env = (extra: Record<string, string>) => ({
    PATH: process.env.PATH ?? "",
    HOME: process.env.HOME ?? "",
    BOT_PROVIDER: "openai",
    OPENAI_API_KEY: "",
    ANTHROPIC_API_KEY: "",
    // Blank, so a developer's own .env cannot choose the model these cases assert.
    FACTORY_MODEL: "",
    ...extra,
  });
  async function run(args: string[], extra: Record<string, string>) {
    const child = Bun.spawn(["bun", ...args], {
      cwd: REPO_ROOT,
      env: env(extra),
      stdout: "pipe",
      stderr: "pipe",
    });
    const [stdout, stderr, code] = await Promise.all([
      new Response(child.stdout).text(),
      new Response(child.stderr).text(),
      child.exited,
    ]);
    return { stdout, stderr, code };
  }

  /** A local OpenAI-shaped provider answering with the recorded completions, in case order. */
  function fakeProvider(dropUsageAt?: number) {
    const queue = dataset.cases.flatMap(({ replay }) =>
      replay.map(({ response }) =>
        typeof response === "string"
          ? response
          : JSON.stringify(withRecordedIntent(response)),
      ),
    );
    const seen: {
      authorization: string | null;
      model: unknown;
      budget: unknown;
    }[] = [];
    const server = Bun.serve({
      hostname: "127.0.0.1",
      port: 0,
      async fetch(request) {
        const index = seen.length;
        const body = (await request.json()) as {
          model?: unknown;
          max_completion_tokens?: unknown;
        };
        seen.push({
          authorization: request.headers.get("authorization"),
          model: body.model,
          budget: body.max_completion_tokens,
        });
        const content = queue[index];
        if (content === undefined)
          return new Response("exhausted", { status: 500 });
        return Response.json({
          choices: [{ message: { content } }],
          ...(index === dropUsageAt
            ? {}
            : {
                usage: {
                  prompt_tokens: 100 + index,
                  completion_tokens: 10 + index,
                  total_tokens: 110 + 2 * index,
                },
              }),
        });
      },
    });
    return { server, seen, calls: queue.length };
  }

  test("importing the runner starts nothing", async () => {
    const { code, stdout, stderr } = await run(
      [
        "-e",
        `await import(${JSON.stringify(RUNNER)}); console.log("imported")`,
      ],
      {
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: "http://127.0.0.1:9/v1",
      },
    );
    expect({
      code,
      stdout: stdout.trim(),
      stderr: stderr.includes("eval:factory-quality"),
    }).toEqual({
      code: 0,
      stdout: "imported",
      stderr: false,
    });
  });

  test("a missing model key exits nonzero instead of skipping", async () => {
    const { code, stderr } = await run([RUNNER], {});
    expect(code).toBe(1);
    expect(stderr).toContain("OPENAI_API_KEY is not set");
  });

  test("scores the configured transport end to end with exact provider usage", async () => {
    const provider = fakeProvider();
    const directory = await mkdtemp(join(tmpdir(), "factory-quality-"));
    try {
      const out = join(directory, "report.json");
      const { code, stderr } = await run([RUNNER], {
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: `http://127.0.0.1:${provider.server.port}/v1`,
        BOT_MODEL: "golden-fixture-model",
        FACTORY_QUALITY_REPORT: out,
        FACTORY_QUALITY_THRESHOLD_APPROVAL: "test-fixture-approval",
      });
      expect({ code, stderr }).toEqual({ code: 0, stderr: "" });
      const written = JSON.parse(
        await readFile(out, "utf8"),
      ) as FactoryQualityReport;
      expect(provider.seen).toHaveLength(38);
      expect(
        provider.seen.every(
          ({ authorization, model, budget }) =>
            authorization === "Bearer fixture-key" &&
            model === "golden-fixture-model" &&
            // The factory's output budget, on the OpenAI path too.
            budget === 4096,
        ),
      ).toBe(true);
      const indices = Array.from({ length: 38 }, (_, i) => i);
      expect(written).toMatchObject({
        runKind: "configured_model",
        pass: true,
        model: { modelRef: "openai/golden-fixture-model" },
        thresholds: { status: "approved", approval: "test-fixture-approval" },
        counts: { cases: 20 },
        usage: {
          calls: 38,
          callsWithUsage: 38,
          complete: true,
          inputTokens: indices.reduce((sum, i) => sum + 100 + i, 0),
          outputTokens: indices.reduce((sum, i) => sum + 10 + i, 0),
          totalTokens: indices.reduce((sum, i) => sum + 110 + 2 * i, 0),
        },
      });
      expect(written.cases[0]?.calls[0]?.usage).toMatchObject({
        inputTokens: 100,
        outputTokens: 10,
        totalTokens: 110,
      });
      expect(JSON.stringify(written)).not.toContain("fixture-key");
    } finally {
      provider.server.stop(true);
      await rm(directory, { recursive: true, force: true });
    }
  });

  test("unknown usage and unapproved thresholds fail the release gates", async () => {
    const provider = fakeProvider(5);
    const directory = await mkdtemp(join(tmpdir(), "factory-quality-"));
    try {
      const out = join(directory, "report.json");
      const { code } = await run([RUNNER], {
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: `http://127.0.0.1:${provider.server.port}/v1`,
        BOT_MODEL: "golden-runtime-model",
        FACTORY_MODEL: "golden-factory-model",
        FACTORY_QUALITY_REPORT: out,
      });
      expect(code).toBe(1);
      const written = JSON.parse(
        await readFile(out, "utf8"),
      ) as FactoryQualityReport;
      // The evaluation scores the model that constructs, not the one coworkers answer on.
      expect(new Set(provider.seen.map(({ model }) => model))).toEqual(
        new Set(["golden-factory-model"]),
      );
      expect(written.model.modelRef).toBe("openai/golden-factory-model");
      expect(written.usage).toMatchObject({
        callsWithUsage: 37,
        complete: false,
      });
      expect(
        written.gates.filter(({ pass }) => !pass).map(({ name }) => name),
      ).toEqual(["token_usage_complete", "thresholds_approved"]);
      expect(written.thresholds.status).toBe("proposed (ASSUMPTION A4)");
    } finally {
      provider.server.stop(true);
      await rm(directory, { recursive: true, force: true });
    }
  });
});
