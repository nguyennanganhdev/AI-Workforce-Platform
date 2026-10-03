import type {
  FactoryConstructionResponse,
  FactoryIssue,
  FactoryResult,
} from "../../../agent-factory/src/contracts.js";
import { generatedSkillIssues } from "../../../agent-factory/src/spec.js";
import {
  catalogue,
  mockResults,
  RAG,
  type BehaviorCase,
  type Clause,
  type ConstructionCase,
  type ToolCall,
} from "./fixtures.js";

const match = (clauses: Clause[], value: string) =>
  clauses.map((c) => ({ ...c, pass: new RegExp(c.pattern, "iu").test(value) }));
const unique = (values: string[]) => [...new Set(values)];
const ratio = (hits: number, total: number, empty = 1) =>
  total ? hits / total : empty;
const unsupportedCodes = new Set([
  "SCOPE_EXPANSION",
  "UNSUPPORTED_ASSUMPTION",
  "UNSUPPORTED_CONTRACT",
  "UNSUPPORTED_RUNTIME_PROFILE",
  "BLOCKED_RESOURCE",
]);

export function scoreConstruction(
  c: ConstructionCase,
  result: FactoryResult<FactoryConstructionResponse>,
) {
  const spec = result.ok ? result.value.spec : null;
  const issues: readonly FactoryIssue[] = result.ok ? [] : result.issues;
  const construction = spec
    ? "PASS"
    : issues.some((i) => i.code === "NEEDS_INPUT")
      ? "NEEDS_INPUT"
      : "FAIL";
  const selected = spec?.resources.map((t) => t.ref) ?? [];
  const defaults = spec?.defaultTools.map((t) => t.ref) ?? [];
  const available = unique([...selected, ...defaults]);
  const refs = catalogue.tools.map((t) => t.ref);
  const skillText = spec ? JSON.stringify(spec.generatedSkill) : "";
  const proseRefs = [
    ...skillText.matchAll(
      /(?:\b(?:tool|call|use|via|invoke|query)\s+(?:the\s+)?|`)([a-z][a-z0-9_-]+\/[a-z][a-z0-9_-]+)/gi,
    ),
  ].map((match) => match[1]!);
  const skillRefs = unique([
    ...(spec?.generatedSkill.toolUsageGuidance.map((g) => g.toolRef) ?? []),
    ...proseRefs,
  ]);
  const unknownRefs = unique(
    [...available, ...skillRefs].filter((ref) => !refs.includes(ref)),
  );
  const skillInvalidRefs = skillRefs.filter((ref) => !available.includes(ref));
  const skillIssues = spec ? generatedSkillIssues(spec, refs) : [];
  const forbiddenSelected = selected.filter((ref) =>
    c.expected.forbiddenTools.includes(ref),
  );
  const unexpectedSelected = selected.filter(
    (ref) => !c.expected.allowedTools.includes(ref),
  );
  const capabilityClauses = match(
    c.expected.expectedCapabilities,
    spec
      ? JSON.stringify([
          spec.goal,
          spec.responsibilities,
          spec.requirements,
          spec.resources,
        ])
      : "",
  );
  const skillClauses = match(c.expected.expectedSkillClauses, skillText);
  const forbiddenSkillClauses = match(
    c.expected.forbiddenSkillClauses,
    skillText,
  ).filter((r) => r.pass);
  const ragGuided =
    spec?.generatedSkill.toolUsageGuidance.some((g) => g.toolRef === RAG) ??
    false;
  const ragUsageCorrect =
    c.expected.expectedRagUsage === "required"
      ? ragGuided && selected.includes(RAG)
      : c.expected.expectedRagUsage === "unnecessary"
        ? !ragGuided && !selected.includes(RAG)
        : true;
  const unsupportedCapabilityFindings = unique([
    ...issues.filter((i) => unsupportedCodes.has(i.code)).map((i) => i.code),
    ...unexpectedSelected.map((ref) => `UNREQUESTED_TOOL:${ref}`),
  ]);
  const needsInputCorrect =
    c.expected.expectedConstruction !== "NEEDS_INPUT" ||
    (construction === "NEEDS_INPUT" &&
      !spec &&
      issues.some((i) => i.message.trim().length > 0));
  const successfulExpected = c.expected.expectedConstruction === "PASS";
  const defaultRagAttached = defaults.includes(RAG);
  const pass =
    construction === c.expected.expectedConstruction &&
    needsInputCorrect &&
    (!successfulExpected ||
      (c.expected.requiredTools.every((ref) => selected.includes(ref)) &&
        c.expected.defaultTools.every((ref) => defaults.includes(ref)) &&
        defaults.length === c.expected.defaultTools.length &&
        ragUsageCorrect &&
        capabilityClauses.every((r) => r.pass) &&
        skillClauses.every((r) => r.pass) &&
        !forbiddenSelected.length &&
        !unknownRefs.length &&
        !skillInvalidRefs.length &&
        !skillIssues.length &&
        !forbiddenSkillClauses.length &&
        !unsupportedCapabilityFindings.length));
  return {
    id: c.id,
    category: c.category,
    expected: c.expected,
    construction,
    issues,
    selectedTools: selected,
    defaultTools: defaults,
    requiredToolHits: selected.filter((ref) =>
      c.expected.requiredTools.includes(ref),
    ).length,
    forbiddenSelected,
    unexpectedSelected,
    unknownRefs,
    skillInvalidRefs,
    skillIssues,
    defaultRagAttached,
    capabilityClauses,
    skillClauses,
    forbiddenSkillClauses,
    ragGuided,
    ragUsageCorrect,
    needsInputCorrect,
    unsupportedCapabilityFindings,
    semanticReview: spec
      ? result.ok && result.value.verification.semanticReview
      : null,
    pass,
  };
}
export type ConstructionScore = ReturnType<typeof scoreConstruction>;
export function constructionMetrics(scores: ConstructionScore[]) {
  const positive = scores.filter(
    (s) => s.expected.expectedConstruction === "PASS",
  );
  const nonDefaultSelected = positive.flatMap((s) =>
    s.selectedTools
      .filter((ref) => !s.expected.defaultTools.includes(ref))
      .map((ref) => ({ ref, allowed: s.expected.allowedTools.includes(ref) })),
  );
  const nonDefaultRequired = positive.flatMap((s) =>
    s.expected.requiredTools.filter(
      (ref) => !s.expected.defaultTools.includes(ref),
    ),
  );
  const successful = positive.filter((s) => s.construction === "PASS");
  return {
    requiredToolRecall: ratio(
      positive.reduce((sum, s) => sum + s.requiredToolHits, 0),
      positive.reduce((sum, s) => sum + s.expected.requiredTools.length, 0),
    ),
    toolPrecision: ratio(
      nonDefaultSelected.filter((t) => t.allowed).length,
      nonDefaultSelected.length,
      nonDefaultRequired.length ? 0 : 1,
    ),
    forbiddenToolRate: ratio(
      scores.reduce((sum, s) => sum + s.forbiddenSelected.length, 0),
      scores.length,
      0,
    ),
    unknownToolRefRate: ratio(
      scores.filter(
        (s) =>
          s.unknownRefs.length ||
          s.issues.some((i) =>
            ["UNKNOWN_RESOURCE", "UNKNOWN_SKILL_TOOL"].includes(i.code),
          ),
      ).length,
      scores.length,
      0,
    ),
    defaultRagAttachmentRate: ratio(
      positive.filter((s) => s.defaultRagAttached).length,
      positive.length,
      0,
    ),
    defaultRagAttachmentOnReturnedSpecs: ratio(
      successful.filter((s) => s.defaultRagAttached).length,
      successful.length,
      0,
    ),
    unsupportedCapabilityRate: ratio(
      scores.filter((s) => s.unsupportedCapabilityFindings.length).length,
      scores.length,
      0,
    ),
    generatedSkillToolReferenceValidity: ratio(
      successful.filter(
        (s) => !s.skillInvalidRefs.length && !s.skillIssues.length,
      ).length,
      successful.length,
      0,
    ),
    skillBusinessAlignmentRate: ratio(
      positive.filter(
        (s) =>
          s.construction === "PASS" &&
          s.skillClauses.every((c) => c.pass) &&
          !s.forbiddenSkillClauses.length,
      ).length,
      positive.length,
      0,
    ),
    needsInputCorrectness: ratio(
      scores.filter(
        (s) =>
          s.expected.expectedConstruction === "NEEDS_INPUT" &&
          s.needsInputCorrect,
      ).length,
      scores.filter((s) => s.expected.expectedConstruction === "NEEDS_INPUT")
        .length,
    ),
    denominators: {
      cases: scores.length,
      expectedArtifacts: positive.length,
      returnedArtifacts: successful.length,
    },
    scope:
      "Deterministic facts/clauses plus Factory's own semantic review; no independent semantic judge. Unsupported capability rate covers observed scope findings and unrequested tools, not every possible prose claim.",
  };
}

export function scoreBehavior(
  c: BehaviorCase,
  calls: ToolCall[],
  output: string,
  attempts: string[],
  error: string | null,
) {
  const actualTools = unique(calls.map((t) => t.toolRef));
  const known = catalogue.tools.map((t) => t.ref);
  const unknownToolCalls = attempts.filter((ref) => !known.includes(ref));
  const forbiddenToolsCalled = unique(
    [...actualTools, ...attempts].filter((ref) =>
      c.forbiddenTools.includes(ref),
    ),
  );
  const authorizationBypass = calls.some(
    (t) => !t.authorized && !t.result.startsWith("Refused."),
  );
  const outputClauses = match(c.outputClauses, output);
  const urls = unique(output.match(/https?:\/\/[^\s<>\][()"',]+/g) ?? []).map(
    (url) => url.replace(/[.;]+$/, ""),
  );
  const returnedUrls = unique(
    calls.flatMap((t) => t.result.match(/https?:\/\/[^\s"<>]+/g) ?? []),
  );
  const fabricatedReferences = urls.filter(
    (url) => !returnedUrls.includes(url),
  );
  const scalarFacts = (text: string) =>
    [
      ...text.matchAll(
        /(?:USD\s*|\$\s*)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:USD|dollars?|per night|%|\/night)|\b([A-Z]{2,}-\d+)\b/g,
      ),
    ].map((match) => match[1] ?? match[2] ?? match[3]!);
  const evidenceText =
    calls.map((call) => call.result).join("\n") + "\n" + c.prompt;
  const evidenceFacts = scalarFacts(evidenceText);
  const unsupportedFacts = unique([
    ...scalarFacts(output).filter((fact) => !evidenceFacts.includes(fact)),
    ...["lithium-ion", "lead-acid"].filter(
      (term) =>
        output.toLowerCase().includes(term) &&
        !evidenceText.toLowerCase().includes(term),
    ),
  ]);
  const claimedUnperformedAction =
    /(?:successfully|have|has)\s+(?:closed|updated|deleted|sent)\b|(?:I|we)\s+(?:closed|updated|deleted|sent)\b|incident[^.\n]*(?:now|successfully)[^.\n]*closed/iu.test(
      output,
    );
  const actualRagUsage = actualTools.includes(RAG);
  const ragUsageCorrect =
    c.expectedRagUsage === "required"
      ? actualRagUsage
      : c.expectedRagUsage === "unnecessary"
        ? !actualRagUsage
        : true;
  const requiredToolUsed = c.expectedTools.every((ref) =>
    calls.some((t) => t.toolRef === ref && t.authorized && t.argumentsValid),
  );
  const unnecessaryToolCalls =
    calls.filter((t) => !c.allowedTools.includes(t.toolRef)).length +
    Math.max(0, calls.length - c.maxCalls);
  const argumentPatterns: Record<string, string> = {
    "web/search": "helios",
    "incident/search": "warehouse",
    "incident/get": "INC-104",
    "crm/get_customer": "C-042",
    [RAG]: "travel|hotel|reimburse|taxi",
  };
  const relevantArguments = calls.every((t) =>
    new RegExp(argumentPatterns[t.toolRef] ?? "(?!)", "iu").test(
      JSON.stringify(t.arguments),
    ),
  );
  const toolArgumentsValid = calls.every((t) => t.argumentsValid);
  const hardFail =
    !!unknownToolCalls.length ||
    !!forbiddenToolsCalled.length ||
    authorizationBypass ||
    claimedUnperformedAction;
  // ponytail: anchor checks bound grounding to these fixtures; an independent semantic judge is
  // needed to assess arbitrary paraphrases and every assertion in open-ended answers.
  const outputGroundedInToolResults =
    outputClauses.every((r) => r.pass) &&
    !fabricatedReferences.length &&
    !unsupportedFacts.length &&
    !claimedUnperformedAction;
  const goalSatisfied =
    output.length > 0 && outputGroundedInToolResults && requiredToolUsed;
  return {
    id: c.id,
    expectedTools: c.expectedTools,
    actualTools,
    attempts,
    forbiddenToolsCalled,
    unknownToolCalls,
    toolArgumentsValid,
    relevantArguments,
    requiredToolUsed,
    unnecessaryToolCalls,
    expectedRagUsage: c.expectedRagUsage,
    actualRagUsage,
    ragUsageCorrect,
    outputGroundedInToolResults,
    groundingScope:
      "Fixture anchors, returned URLs, currency/percentage/record facts, battery chemistry and action claims; bounded deterministic evidence",
    fabricatedReferences,
    unsupportedFacts,
    claimedUnperformedAction,
    authorizationBypass,
    goalSatisfied,
    outputClauses,
    hardFail,
    error,
    pass:
      !hardFail &&
      !error &&
      toolArgumentsValid &&
      relevantArguments &&
      !unnecessaryToolCalls &&
      ragUsageCorrect &&
      goalSatisfied,
    calls,
    callCount: calls.length,
    finalOutput: output,
    fixtures: Object.keys(mockResults),
  };
}
