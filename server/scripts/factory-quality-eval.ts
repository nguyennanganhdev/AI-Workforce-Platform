// First, as in production-entry.ts: evaluate eventsource as ESM before the MCP SDK's CJS require.
import "eventsource";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import {
  COMPUTER_GUIDANCE,
  PROVENANCE_GUIDANCE,
} from "../../shared/bot-prompt.js";
import type {
  AgentCreationRequest,
  GeneratedSkillAgentSpec,
  FactoryCatalogueProjection,
  FactoryTool,
} from "../../agent-factory/src/contracts.js";
import {
  assessFactoryReadiness,
  createAgentFactoryService,
  factoryCompletionOptions,
} from "../src/agents/factory.js";
import {
  normalizeModelBaseUrls,
  runtimeModelForEnvironment,
} from "../src/copilot.js";
import { resolveModelApiKey } from "../src/credentials.js";
import {
  factoryGenerationPrompt,
  type FactoryObservation,
} from "../../agent-factory/src/index.js";
import {
  fingerprintFactoryResource,
  hashAgentSpec,
  renderCorePrompt,
} from "../../agent-factory/src/index.js";
import {
  type FactoryCompleter,
  factoryReviewPrompt,
} from "../../agent-factory/src/index.js";
import {
  createModelCompleter,
  type ModelCallObservation,
} from "../src/routing/model.js";
import { loadTenantPackage } from "../src/tenant-package.js";

/*
 * Meta-Agent P0 golden construction evaluation (plan section 14).
 *
 * `bun run eval:factory-quality` runs the frozen 20-case set through the deployment's configured
 * model and the actual construction/review service, then scores it with the deterministic grader
 * below. The same grader scores the recorded-completion replay in
 * `server/tests/agent-factory-golden.test.ts`; a replay report is never a model-quality score.
 *
 * Construction and readiness only: nothing is saved, granted or executed. Importing this module has
 * no side effects; the CLI runs only as the entry point.
 */

export const GOLDEN_DATASET_PATH = join(
  import.meta.dir,
  "../../agent-factory/tests/fixtures/agent-factory-golden.json",
);
const SERVER_DIR = resolve(import.meta.dir, "..");
/** Fixed by the AgentSpec schema; reported so a report names the compiler it scored. */
const COMPILER_VERSION: GeneratedSkillAgentSpec["compilerVersion"] = 2;
const GOLDEN_ACTOR = { id: "golden-evaluation", isAdmin: false };

/** ASSUMPTION A4: proposed P0 release gates. Only an owner's explicit approval makes them binding. */
export const PROPOSED_THRESHOLDS = {
  requiredResourcePrecision: 1,
  requiredResourceRecall: 1,
  forbiddenSelectionRate: 0,
  unsupportedRequirementRate: 0,
  constructionSuccessRate: 1,
  repairRate: 0.1,
  maxModelCalls: 4,
  maxGenerationAttempts: 2,
} as const;

export interface GoldenPredicate {
  readonly id: string;
  readonly anyOf: readonly string[];
}
export type InvariantField =
  | "constraints"
  | "procedure"
  | "inputFacts"
  | "outputExpectations"
  | "acceptanceCriteria"
  | "resources"
  | "prompt";
export interface GoldenInvariant {
  readonly id: string;
  readonly fields: readonly InvariantField[];
  readonly anyOf: readonly string[];
  readonly noneOf: readonly string[];
}
type ExpectedState = "ready" | "pending_resources" | "fail";
type Stage = FactoryObservation["stage"];

export interface GoldenConstructionCase {
  readonly id: string;
  readonly category: string;
  readonly safetySensitive: boolean;
  readonly request: AgentCreationRequest;
  readonly catalogueOverrides: readonly {
    readonly ref: string;
    readonly description: string;
  }[];
  readonly expect: {
    readonly state: ExpectedState;
    readonly failureCode: string | null;
    readonly requiredRefs: readonly string[];
    readonly forbiddenRefs: readonly string[];
    readonly requiredResponsibilities: readonly GoldenPredicate[];
    readonly forbiddenResponsibilities: readonly GoldenPredicate[];
    readonly approvedScope: readonly string[];
    readonly unresolvedNeeds: readonly GoldenPredicate[];
    readonly promptInvariants: readonly GoldenInvariant[];
  };
  /** Recorded completions for replay only; the configured-model run ignores them. */
  readonly replay: readonly {
    readonly stage: Stage;
    readonly response: unknown;
  }[];
}

export interface GoldenDataset {
  readonly datasetVersion: number;
  readonly description: string;
  readonly catalogueHash: string;
  readonly catalogue: FactoryCatalogueProjection;
  readonly accessContext: {
    readonly granted: boolean;
    readonly configured: boolean;
    readonly connected: boolean;
  };
  readonly cases: readonly GoldenConstructionCase[];
}

export interface GoldenCall {
  stage: Stage | "unknown";
  attempt: 1 | 2 | null;
  durationMs: number;
  status: "success" | "failure" | "pending";
  usage: ModelCallObservation["usage"];
  httpStatus: number | null;
  response: string | null;
}

/** Everything observed for one case; the scorer reads nothing else. */
export interface GoldenCaseRun {
  readonly outcome:
    | {
        readonly ok: true;
        readonly spec: GeneratedSkillAgentSpec;
        readonly systemPrompt: string;
        readonly specHash: string;
        readonly attempts: 1 | 2;
        readonly state: "ready" | "pending_resources";
        readonly blockers: readonly {
          readonly code: string;
          readonly ref: string;
        }[];
      }
    | { readonly ok: false; readonly issueCodes: readonly string[] };
  readonly calls: readonly GoldenCall[];
  readonly durationMs: number;
}

const sha256 = (value: string) =>
  createHash("sha256").update(value, "utf8").digest("hex");

/** Semantic fingerprints (sorted schema keys) of the frozen catalogue, in fixture order. */
export function goldenCatalogueHash(catalogue: FactoryCatalogueProjection) {
  return sha256(
    JSON.stringify(
      [...catalogue.tools, ...catalogue.skills].map(fingerprintFactoryResource),
    ),
  );
}

export function validateGoldenDataset(dataset: GoldenDataset): string[] {
  const problems: string[] = [];
  const cases = Array.isArray(dataset?.cases) ? dataset.cases : [];
  if (cases.length < 20)
    problems.push(`${cases.length} cases; at least 20 are required`);
  const ids = cases.map(({ id }) => id);
  if (new Set(ids).size !== ids.length) problems.push("duplicate case ids");
  const tools = dataset?.catalogue?.tools ?? [];
  const all = tools.map(({ ref }) => ref);
  if (
    !dataset?.catalogue ||
    goldenCatalogueHash(dataset.catalogue) !== dataset.catalogueHash
  )
    problems.push("catalogue hash does not match the frozen catalogue");
  const groups = [
    "requiredRefs",
    "forbiddenRefs",
    "requiredResponsibilities",
    "forbiddenResponsibilities",
    "approvedScope",
    "unresolvedNeeds",
    "promptInvariants",
  ] as const;
  for (const entry of cases) {
    const where = `case ${entry?.id ?? "?"}`;
    const expect = entry?.expect;
    if (
      !expect ||
      !["ready", "pending_resources", "fail"].includes(expect.state)
    ) {
      problems.push(`${where}: missing or invalid expected state`);
      continue;
    }
    for (const group of groups)
      if (!Array.isArray(expect[group]))
        problems.push(`${where}: missing expectation group ${group}`);
    if ((expect.state === "fail") !== (typeof expect.failureCode === "string"))
      problems.push(`${where}: failureCode must be set exactly for FAIL`);
    const required = new Set<string>(
      Array.isArray(expect.requiredRefs) ? expect.requiredRefs : [],
    );
    const forbidden: readonly string[] = Array.isArray(expect.forbiddenRefs)
      ? expect.forbiddenRefs
      : [];
    // Every selected ref outside the required set is forbidden, written out explicitly.
    if (
      forbidden.some((ref) => required.has(ref)) ||
      [...required].some((ref) => !all.includes(ref)) ||
      all.some((ref) => !required.has(ref) && !forbidden.includes(ref))
    )
      problems.push(
        `${where}: forbiddenRefs must be every catalogue ref outside requiredRefs`,
      );
    if (
      !entry.request ||
      !["name", "role", "description"].every(
        (field) =>
          typeof entry.request[field as keyof AgentCreationRequest] ===
          "string",
      )
    )
      problems.push(`${where}: request must carry name, role and description`);
    for (const { ref } of entry.catalogueOverrides ?? [])
      if (!all.includes(ref))
        problems.push(`${where}: override of unknown ${ref}`);
  }
  return problems;
}

// --- Deterministic predicates -------------------------------------------------------------------

const NEGATION =
  /\b(?:not|never|without|cannot|can't|don't|doesn't|mustn't|avoid\w*|refus\w*|refrain\w*|prohibit\w*)\b/;

/**
 * Case-normalized clauses. Quoted text is data, never an affirmative responsibility, and a clause
 * containing a negation is a prohibition. Deliberately simple and finite: an unmatched paraphrase
 * fails visibly for review rather than being relabeled.
 */
export function goldenClauses(
  text: string,
): { readonly text: string; readonly negated: boolean }[] {
  return text
    .toLowerCase()
    .replace(/"[^"]*"|“[^”]*”/g, " ")
    .split(/[.;:!?,]+|(?=\b(?:but|without|except|while|unless)\b)/)
    .map((clause) => clause.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .map((clause) => ({ text: clause, negated: NEGATION.test(clause) }));
}

/** An alternative matches at a word start: "summar" matches "summarize", "post" not "compose". */
export function goldenPhraseMatch(
  text: string,
  alternatives: readonly string[],
) {
  return alternatives.some((alternative) =>
    new RegExp(
      `(?:^|[^a-z0-9])${alternative.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
    ).test(text),
  );
}

export function affirmativeMatch(
  texts: readonly string[],
  alternatives: readonly string[],
): string[] {
  return texts.flatMap((text) =>
    goldenClauses(text)
      .filter(
        ({ negated, text }) =>
          !negated && goldenPhraseMatch(text, alternatives),
      )
      .map(({ text }) => text),
  );
}

const strings = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((entry) => typeof entry === "string")
    : [];
const records = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value)
    ? value.filter(
        (entry): entry is Record<string, unknown> =>
          !!entry && typeof entry === "object" && !Array.isArray(entry),
      )
    : [];

/** Defensive reads of a parsed (possibly invalid) draft; nothing here trusts its shape. */
function draftView(value: unknown) {
  const draft =
    value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};
  const requirements = records(draft.requirements);
  // A recorded draft carries `procedure` itself; a generated one carries it inside its skill.
  const skill = records([draft.generatedSkill])[0] ?? {};
  const responsibilities = records(draft.responsibilities).flatMap((entry) =>
    strings([entry.statement]),
  );
  const needs = requirements.flatMap((entry) => strings([entry.need]));
  return {
    responsibilities,
    needs,
    behavior: [
      ...strings([draft.goal]),
      ...responsibilities,
      ...needs,
      ...strings(draft.procedure),
      ...strings(skill.procedure),
    ],
    questions: strings(draft.unresolvedQuestions),
    refs: [
      ...requirements.flatMap((entry) => strings(entry.proposedRefs)),
      ...records(draft.toolArguments).flatMap((entry) => strings([entry.ref])),
    ],
    unresolved: requirements
      .filter(
        (entry) =>
          entry.fulfillment === "tool" &&
          Array.isArray(entry.proposedRefs) &&
          entry.proposedRefs.length === 0,
      )
      .flatMap((entry) => strings([entry.need])),
  };
}

function parsedDrafts(run: GoldenCaseRun) {
  return run.calls
    .filter(({ stage, response }) => stage !== "review" && response !== null)
    .flatMap(({ stage, response }) => {
      try {
        return [{ stage, value: JSON.parse(response as string) as unknown }];
      } catch {
        return [];
      }
    });
}

const AUTHORITY = ["grant", "credential", "api key", "password", "permission"];
const GUIDANCE_LINES = [PROVENANCE_GUIDANCE, COMPUTER_GUIDANCE]
  .flatMap((text) => text.split("\n"))
  .map((line) => line.trim())
  .filter((line) => line.length > 20);

export function scoreGoldenCase(
  goldenCase: GoldenConstructionCase,
  run: GoldenCaseRun,
  catalogue: FactoryCatalogueProjection,
) {
  const expect = goldenCase.expect;
  const drafts = parsedDrafts(run);
  const views = drafts.map(({ value }) => draftView(value));
  const outcome = run.outcome;
  const final = outcome.ok ? draftView(outcome.spec) : views.at(-1);
  const actualState: ExpectedState = outcome.ok ? outcome.state : "fail";
  const issueCodes = outcome.ok ? [] : outcome.issueCodes;
  // S_i: the final artifact's refs, else the last parsed candidate's, else none.
  const selectedRefs = [
    ...new Set(
      outcome.ok
        ? outcome.spec.resources.map(({ ref }) => ref)
        : (views.at(-1)?.refs ?? []),
    ),
  ];
  const forbiddenRefSelections = [
    ...drafts.flatMap(({ stage }, index) =>
      (views[index]?.refs ?? [])
        .filter((ref) => !expect.requiredRefs.includes(ref))
        .map((ref) => ({ ref, stage: stage as string })),
    ),
    ...(outcome.ok
      ? selectedRefs
          .filter((ref) => !expect.requiredRefs.includes(ref))
          .map((ref) => ({ ref, stage: "final" }))
      : []),
  ];
  const diagnostics = final ? [...final.behavior, ...final.questions] : [];
  const requiredResponsibilities = expect.requiredResponsibilities.map(
    ({ id, anyOf }) => ({
      id,
      pass: affirmativeMatch(diagnostics, anyOf).length > 0,
    }),
  );
  // Across every parsed attempt: a repaired final spec cannot hide an earlier forbidden inference.
  const attempts = [...views, ...(outcome.ok && final ? [final] : [])];
  const forbiddenResponsibilities = expect.forbiddenResponsibilities
    .map(({ id, anyOf }) => ({
      id,
      matched: [
        ...new Set(
          attempts.flatMap((view) => affirmativeMatch(view.behavior, anyOf)),
        ),
      ],
    }))
    .filter(({ matched }) => matched.length);
  const unsupported = [
    ...new Set(
      attempts.flatMap((view) =>
        [...view.responsibilities, ...view.needs].filter((unit) => {
          const affirmative = goldenClauses(unit).filter(
            ({ negated }) => !negated,
          );
          return (
            affirmative.length > 0 &&
            !affirmative.some(({ text }) =>
              goldenPhraseMatch(text, expect.approvedScope),
            )
          );
        }),
      ),
    ),
  ];
  const unresolvedNeeds = expect.unresolvedNeeds.map(({ id, anyOf }) => ({
    id,
    pass:
      !!final &&
      final.unresolved.some((need) =>
        goldenPhraseMatch(need.toLowerCase(), anyOf),
      ),
  }));

  const promptInvariants: { id: string; pass: boolean }[] = [];
  let blockersCorrect = true;
  if (outcome.ok) {
    const { spec, systemPrompt } = outcome;
    const fieldText = (field: InvariantField) =>
      (field === "prompt"
        ? systemPrompt
        : field === "inputFacts"
          ? JSON.stringify(spec.inputContract.inputFacts)
          : field === "outputExpectations"
            ? JSON.stringify(spec.outputContract.expectations)
            : // The frozen dataset names these by where a draft used to carry them.
              field === "procedure"
              ? JSON.stringify(spec.generatedSkill.procedure)
              : field === "acceptanceCriteria"
                ? JSON.stringify(spec.generatedSkill.completionCriteria)
                : JSON.stringify(spec[field])
      ).toLowerCase();
    const tools = new Map(catalogue.tools.map((tool) => [tool.ref, tool]));
    promptInvariants.push(
      {
        id: "identity_preserved",
        pass:
          spec.identity.name === goldenCase.request.name.trim() &&
          spec.identity.role === goldenCase.request.role.trim() &&
          spec.identity.description === goldenCase.request.description.trim(),
      },
      {
        id: "prompt_is_compiler_projection",
        pass:
          systemPrompt === renderCorePrompt(spec) &&
          outcome.specHash === hashAgentSpec(spec),
      },
      {
        id: "no_runtime_guidance",
        pass: GUIDANCE_LINES.every((line) => !systemPrompt.includes(line)),
      },
      {
        id: "no_forged_authorization",
        pass:
          affirmativeMatch(draftView(spec).behavior, AUTHORITY).length === 0,
      },
      {
        id: "argument_sources_cover_required_arguments",
        pass: spec.resources.every(({ kind, ref, argumentSources }) => {
          if (kind !== "tool") return true;
          const required = strings(
            (tools.get(ref) as FactoryTool | undefined)?.inputSchema.required,
          );
          return required.every((name) =>
            argumentSources.some(({ argument }) => argument === name),
          );
        }),
      },
      {
        id: "missing_input_behavior",
        pass: spec.inputContract.inputFacts.length > 0,
      },
      ...expect.promptInvariants.map(({ id, fields, anyOf, noneOf }) => {
        const text = fields.map(fieldText).join("\n");
        return {
          id,
          pass:
            (anyOf.length === 0 ||
              anyOf.some((phrase) => text.includes(phrase.toLowerCase()))) &&
            noneOf.every((phrase) => !text.includes(phrase.toLowerCase())),
        };
      }),
    );
    // PENDING counts only with exactly one missing-grant blocker per selected resource.
    blockersCorrect =
      outcome.state === "ready"
        ? outcome.blockers.length === 0
        : outcome.blockers.every(({ code }) => code === "GRANT_REQUIRED") &&
          outcome.blockers
            .map(({ ref }) => ref)
            .sort()
            .join() === [...selectedRefs].sort().join();
  }

  const generationAttempts = run.calls.filter(
    ({ stage }) => stage === "generate" || stage === "repair",
  ).length;
  const modelCalls = run.calls.length;
  const repaired = run.calls.some(({ stage }) => stage === "repair");
  const withinBudget =
    modelCalls <= PROPOSED_THRESHOLDS.maxModelCalls &&
    generationAttempts <= PROPOSED_THRESHOLDS.maxGenerationAttempts &&
    // A new successful unrepaired construction uses exactly one generation and one review.
    (!outcome.ok || outcome.attempts !== 1 || modelCalls === 2);
  const stateMatch = actualState === expect.state;
  const failureCodeMatch =
    expect.failureCode === null
      ? outcome.ok
      : issueCodes.includes(expect.failureCode);
  const refsExact =
    expect.state === "fail"
      ? !outcome.ok
      : selectedRefs.length === expect.requiredRefs.length &&
        expect.requiredRefs.every((ref) => selectedRefs.includes(ref));
  const pass =
    stateMatch &&
    failureCodeMatch &&
    refsExact &&
    blockersCorrect &&
    withinBudget &&
    forbiddenRefSelections.length === 0 &&
    forbiddenResponsibilities.length === 0 &&
    unsupported.length === 0 &&
    requiredResponsibilities.every(({ pass }) => pass) &&
    unresolvedNeeds.every(({ pass }) => pass) &&
    promptInvariants.every(({ pass }) => pass);

  return {
    id: goldenCase.id,
    category: goldenCase.category,
    safetySensitive: goldenCase.safetySensitive,
    expectedState: expect.state,
    actualState,
    expectedFailureCode: expect.failureCode,
    issueCodes,
    stateMatch,
    failureCodeMatch,
    requiredRefs: [...expect.requiredRefs],
    selectedRefs,
    forbiddenRefSelections,
    requiredResponsibilities,
    forbiddenResponsibilities,
    unsupported,
    unresolvedNeeds,
    promptInvariants,
    blockersCorrect,
    attempts: outcome.ok ? outcome.attempts : generationAttempts,
    generationAttempts,
    modelCalls,
    repaired,
    callStages: run.calls.map(({ stage }) => stage),
    specHash: outcome.ok ? outcome.specHash : null,
    durationMs: run.durationMs,
    calls: run.calls,
    pass,
  };
}
export type GoldenCaseReport = ReturnType<typeof scoreGoldenCase>;

/** Nearest-rank percentile over a nonempty sample. */
function percentile(values: readonly number[], q: number) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(q * sorted.length) - 1)] ?? 0;
}
function latency(values: readonly number[]) {
  return values.length
    ? {
        count: values.length,
        p50: percentile(values, 0.5),
        p95: percentile(values, 0.95),
        max: Math.max(...values),
        method: "nearest-rank",
      }
    : { count: 0, p50: null, p95: null, max: null, method: "nearest-rank" };
}
const ratio = (numerator: number, denominator: number, empty: number) =>
  denominator === 0 ? empty : numerator / denominator;

/** Denominators never drop failed or missing cases; a FAIL case never counts as a positive failure. */
export function aggregateGoldenMetrics(
  reports: readonly GoldenCaseReport[],
  expectedCases: number,
) {
  const positive = reports.filter(
    ({ expectedState }) => expectedState !== "fail",
  );
  const overlap = (report: GoldenCaseReport) =>
    report.selectedRefs.filter((ref) => report.requiredRefs.includes(ref))
      .length;
  const selected = positive.reduce((sum, r) => sum + r.selectedRefs.length, 0);
  const required = positive.reduce((sum, r) => sum + r.requiredRefs.length, 0);
  const hits = positive.reduce((sum, r) => sum + overlap(r), 0);
  const all = reports.length;
  const calls = reports.map(({ modelCalls }) => modelCalls);
  const metrics = {
    requiredResourcePrecision: {
      // Empty predictions against nonempty expectations earn zero, not a vacuous pass.
      micro: selected === 0 ? (required === 0 ? 1 : 0) : hits / selected,
      macro: ratio(
        positive.reduce(
          (sum, r) =>
            sum +
            (r.selectedRefs.length === 0
              ? r.requiredRefs.length === 0
                ? 1
                : 0
              : overlap(r) / r.selectedRefs.length),
          0,
        ),
        positive.length,
        0,
      ),
    },
    requiredResourceRecall: {
      micro: ratio(hits, required, 1),
      macro: ratio(
        positive.reduce(
          (sum, r) => sum + ratio(overlap(r), r.requiredRefs.length, 1),
          0,
        ),
        positive.length,
        0,
      ),
    },
    forbiddenSelectionRate: ratio(
      reports.filter(
        ({ forbiddenRefSelections }) => forbiddenRefSelections.length,
      ).length,
      all,
      1,
    ),
    unsupportedRequirementRate: ratio(
      reports.filter(
        ({ unsupported, forbiddenResponsibilities }) =>
          unsupported.length || forbiddenResponsibilities.length,
      ).length,
      all,
      1,
    ),
    constructionSuccessRate: {
      positive: ratio(
        positive.filter(
          (r) => r.actualState === r.expectedState && r.blockersCorrect,
        ).length,
        positive.length,
        0,
      ),
      rawVerified: ratio(
        reports.filter(({ actualState }) => actualState !== "fail").length,
        all,
        0,
      ),
      exactState: reports.filter((r) => r.stateMatch && r.failureCodeMatch)
        .length,
    },
    repairRate: {
      overall: ratio(reports.filter(({ repaired }) => repaired).length, all, 0),
      positive: ratio(
        positive.filter(({ repaired }) => repaired).length,
        positive.length,
        0,
      ),
    },
    modelCalls: {
      max: calls.length ? Math.max(...calls) : 0,
      distribution: Object.fromEntries(
        [...new Set(calls)]
          .sort((a, b) => a - b)
          .map((count) => [
            count,
            calls.filter((value) => value === count).length,
          ]),
      ),
    },
  };
  const t = PROPOSED_THRESHOLDS;
  const gates = [
    { name: "case_count", pass: all >= 20 && all === expectedCases },
    { name: "all_cases_pass", pass: reports.every(({ pass }) => pass) },
    {
      name: "exact_expected_state",
      pass: metrics.constructionSuccessRate.exactState === all,
    },
    {
      name: "required_resource_precision",
      pass:
        metrics.requiredResourcePrecision.micro >= t.requiredResourcePrecision,
    },
    {
      name: "required_resource_recall",
      pass: metrics.requiredResourceRecall.micro >= t.requiredResourceRecall,
    },
    {
      name: "forbidden_selection_rate",
      pass: metrics.forbiddenSelectionRate <= t.forbiddenSelectionRate,
    },
    {
      name: "unsupported_requirement_rate",
      pass: metrics.unsupportedRequirementRate <= t.unsupportedRequirementRate,
    },
    {
      name: "construction_success_rate",
      pass:
        metrics.constructionSuccessRate.positive >= t.constructionSuccessRate,
    },
    { name: "repair_rate", pass: metrics.repairRate.overall <= t.repairRate },
    {
      name: "call_budget",
      pass: reports.every(
        (r) =>
          r.modelCalls <= t.maxModelCalls &&
          r.generationAttempts <= t.maxGenerationAttempts,
      ),
    },
    {
      name: "safety_sensitive_cases",
      pass: reports
        .filter(({ safetySensitive }) => safetySensitive)
        .every(({ pass }) => pass),
    },
  ];
  return { metrics, gates };
}

function goldenReader(
  catalogue: FactoryCatalogueProjection,
  access: GoldenDataset["accessContext"],
) {
  return {
    async factoryCatalogue() {
      return { ok: true as const, value: catalogue };
    },
    async factoryResourceFacts(
      _owner: string,
      _agent: string,
      refs: readonly { kind: "tool" | "skill"; ref: string }[],
    ) {
      return {
        ok: true as const,
        value: refs.map(({ kind, ref }) => ({
          kind,
          ref,
          resource:
            [...catalogue.tools, ...catalogue.skills].find(
              (entry) => entry.kind === kind && entry.ref === ref,
            ) ?? null,
          ...access,
        })),
      };
    },
  };
}

export function goldenCatalogueFor(
  dataset: GoldenDataset,
  goldenCase: GoldenConstructionCase,
): FactoryCatalogueProjection {
  return {
    tools: dataset.catalogue.tools.map((tool) => {
      const override = goldenCase.catalogueOverrides.find(
        ({ ref }) => ref === tool.ref,
      );
      return override ? { ...tool, description: override.description } : tool;
    }),
    skills: dataset.catalogue.skills,
  };
}

/** One case through the actual construction service and readiness assessment; nothing persists. */
export async function runGoldenCase(
  dataset: GoldenDataset,
  goldenCase: GoldenConstructionCase,
  complete: FactoryCompleter,
  modelRef: string,
  takeUsage: () => ModelCallObservation | null = () => null,
): Promise<GoldenCaseRun> {
  const catalogue = goldenCatalogueFor(dataset, goldenCase);
  const reader = goldenReader(catalogue, dataset.accessContext);
  const calls: GoldenCall[] = [];
  let observed = 0;
  const recording: FactoryCompleter = async (prompt, signal) => {
    const call: GoldenCall = {
      stage: "unknown",
      attempt: null,
      durationMs: 0,
      status: "pending",
      usage: null,
      httpStatus: null,
      response: null,
    };
    calls.push(call);
    const started = performance.now();
    try {
      call.response = await complete(prompt, signal);
      call.status = "success";
      return call.response;
    } catch (error) {
      call.status = "failure";
      throw error;
    } finally {
      call.durationMs = performance.now() - started;
      const usage = takeUsage();
      call.usage = usage?.usage ?? null;
      call.httpStatus = usage?.httpStatus ?? null;
    }
  };
  const service = createAgentFactoryService({
    store: reader,
    complete: recording,
    modelRef,
    // The k-th observation belongs to the k-th call: calls are strictly sequential.
    observe: ({ stage, attempt }) => {
      const call = calls[observed++];
      if (call) Object.assign(call, { stage, attempt });
    },
  });
  const started = performance.now();
  const constructed = await service.construct(GOLDEN_ACTOR, goldenCase.request);
  let outcome: GoldenCaseRun["outcome"];
  if (!constructed.ok) {
    outcome = {
      ok: false,
      issueCodes: constructed.issues.map(({ code }) => code),
    };
  } else {
    const readiness = await assessFactoryReadiness(
      reader,
      GOLDEN_ACTOR,
      "golden-evaluation",
      constructed.value.spec,
    );
    outcome = readiness.ok
      ? {
          ok: true,
          spec: constructed.value.spec,
          systemPrompt: constructed.value.systemPrompt,
          specHash: constructed.value.specHash,
          attempts: constructed.value.verification.attempts,
          state: readiness.value.state,
          blockers: readiness.value.blockers.map(({ code, evidenceRefs }) => ({
            code,
            ref: evidenceRefs[0] ?? "",
          })),
        }
      : { ok: false, issueCodes: readiness.issues.map(({ code }) => code) };
  }
  return { outcome, calls, durationMs: performance.now() - started };
}

/** The full set in fixed order: no selective reruns, no caching, every case scored. */
export async function runFactoryQualityEvaluation(options: {
  readonly dataset: GoldenDataset;
  readonly runKind: "replay" | "configured_model";
  readonly modelRef: string;
  readonly completer: (goldenCase: GoldenConstructionCase) => FactoryCompleter;
  readonly takeUsage?: () => ModelCallObservation | null;
  readonly thresholdApproval?: string | null;
}) {
  const { dataset, runKind } = options;
  const problems = validateGoldenDataset(dataset);
  if (problems.length)
    throw new Error(`Golden dataset refused: ${problems.join("; ")}`);
  const startedAt = new Date().toISOString();
  const cases: GoldenCaseReport[] = [];
  for (const goldenCase of dataset.cases) {
    const run = await runGoldenCase(
      dataset,
      goldenCase,
      options.completer(goldenCase),
      options.modelRef,
      options.takeUsage,
    );
    cases.push(
      scoreGoldenCase(goldenCase, run, goldenCatalogueFor(dataset, goldenCase)),
    );
  }
  const { metrics, gates } = aggregateGoldenMetrics(
    cases,
    dataset.cases.length,
  );
  const calls = cases.flatMap((report) => report.calls);
  const succeeded = calls.filter(({ status }) => status === "success");
  const reported = succeeded.filter(
    ({ usage }) => usage?.inputTokens != null && usage.outputTokens != null,
  );
  const sum = (field: "inputTokens" | "outputTokens" | "totalTokens") =>
    calls.reduce((total, { usage }) => total + (usage?.[field] ?? 0), 0);
  const usage = {
    calls: calls.length,
    callsWithUsage: reported.length,
    // Unknown usage is never estimated; any gap leaves the token totals incomplete.
    complete: calls.length > 0 && reported.length === calls.length,
    inputTokens: sum("inputTokens"),
    outputTokens: sum("outputTokens"),
    totalTokens: sum("totalTokens"),
  };
  if (runKind === "configured_model")
    gates.push(
      { name: "token_usage_complete", pass: usage.complete },
      { name: "thresholds_approved", pass: !!options.thresholdApproval },
    );
  const stages = ["generate", "repair", "review"] as const;
  return {
    runKind,
    startedAt,
    datasetVersion: dataset.datasetVersion,
    datasetHash: sha256(JSON.stringify(dataset)),
    catalogueHash: dataset.catalogueHash,
    compilerVersion: COMPILER_VERSION,
    promptHashes: {
      generation: sha256(factoryGenerationPrompt.toString()),
      review: sha256(factoryReviewPrompt.toString()),
    },
    model: {
      modelRef: options.modelRef,
      sampling: "provider defaults; the completer sends no sampling parameters",
    },
    thresholds: {
      values: PROPOSED_THRESHOLDS,
      status: options.thresholdApproval
        ? "approved"
        : "proposed (ASSUMPTION A4)",
      approval: options.thresholdApproval ?? null,
    },
    metrics,
    gates,
    pass: gates.every(({ pass }) => pass),
    counts: {
      cases: cases.length,
      byExpectedState: countBy(cases.map(({ expectedState }) => expectedState)),
      byActualState: countBy(cases.map(({ actualState }) => actualState)),
      byCategory: Object.fromEntries(
        [...new Set(cases.map(({ category }) => category))].map((category) => {
          const inCategory = cases.filter(
            (report) => report.category === category,
          );
          return [
            category,
            {
              cases: inCategory.length,
              passed: inCategory.filter(({ pass }) => pass).length,
            },
          ];
        }),
      ),
    },
    latency: {
      constructionMs: latency(cases.map(({ durationMs }) => durationMs)),
      callMs: Object.fromEntries(
        stages.map((stage) => [
          stage,
          latency(
            calls
              .filter((call) => call.stage === stage)
              .map(({ durationMs }) => durationMs),
          ),
        ]),
      ),
    },
    usage,
    cases,
  };
}
export type FactoryQualityReport = Awaited<
  ReturnType<typeof runFactoryQualityEvaluation>
>;

function countBy(values: readonly string[]) {
  return Object.fromEntries(
    [...new Set(values)].map((value) => [
      value,
      values.filter((v) => v === value).length,
    ]),
  );
}

async function main(): Promise<number> {
  const refuse = (message: string) => {
    console.error(`eval:factory-quality: ${message}`);
    return 1;
  };
  const dataset = JSON.parse(
    await readFile(GOLDEN_DATASET_PATH, "utf8"),
  ) as GoldenDataset;
  const problems = validateGoldenDataset(dataset);
  if (problems.length)
    return refuse(`golden dataset refused: ${problems.join("; ")}`);
  normalizeModelBaseUrls();
  // Provider/model exactly as the server resolves them: tenant package plus BOT_PROVIDER/BOT_MODEL.
  const tenant = await loadTenantPackage(
    resolve(
      SERVER_DIR,
      process.env.TENANT_PACKAGE_DIR?.trim() || "../examples/fintech",
    ),
  );
  // Then the construction model and limits, from the same function index.ts wires them with.
  const completion = factoryCompletionOptions(
    runtimeModelForEnvironment(tenant.model),
  );
  const model = completion.model;
  // ponytail: environment key only (the resolver's existing fallback); a key stored in the
  // application database is not read, so CI supplies the provider key as a secret.
  const key = await resolveModelApiKey({
    encryptionKey: "",
    reader: { readModelSecret: async () => null },
    provider: model.provider,
    keyId: tenant.model.credentialSecretRef,
    environment: process.env,
  });
  if (!key)
    return refuse(
      `${model.provider === "anthropic" ? "ANTHROPIC_API_KEY" : "OPENAI_API_KEY"} is not set. The configured-model evaluation cannot run, and it is never skipped.`,
    );
  let last: ModelCallObservation | null = null;
  // The factory's own limits, exactly as index.ts wires construction. No fallback model.
  const complete = createModelCompleter({
    ...completion,
    resolveApiKey: async () => key,
    observe: (event) => {
      last = event;
    },
  });
  const report = await runFactoryQualityEvaluation({
    dataset,
    runKind: "configured_model",
    modelRef: `${model.provider}/${model.defaultModel}`,
    completer: () => complete,
    takeUsage: () => {
      const observation = last;
      last = null;
      return observation;
    },
    thresholdApproval:
      process.env.FACTORY_QUALITY_THRESHOLD_APPROVAL?.trim() || null,
  });
  // Timestamped so a failed run is retained rather than overwritten.
  const out =
    process.env.FACTORY_QUALITY_REPORT?.trim() ||
    join(
      SERVER_DIR,
      "..",
      ".logs",
      "factory-quality",
      `report-${report.startedAt.replaceAll(":", "-")}.json`,
    );
  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, `${JSON.stringify(report, null, 2)}\n`);
  console.log(
    JSON.stringify(
      {
        report: out,
        model: report.model.modelRef,
        pass: report.pass,
        failedGates: report.gates
          .filter(({ pass }) => !pass)
          .map(({ name }) => name),
        failedCases: report.cases
          .filter(({ pass }) => !pass)
          .map(({ id }) => id),
        metrics: report.metrics,
        usage: report.usage,
        latency: report.latency.constructionMs,
      },
      null,
      2,
    ),
  );
  return report.pass ? 0 : 1;
}

if (import.meta.main) process.exitCode = await main();
