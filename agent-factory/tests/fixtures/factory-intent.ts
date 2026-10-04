import type { AgentCreationRequest, AgentDraft } from "../../src/contracts.js";
import { compileAgentSpec } from "../../src/spec.js";

/**
 * Generations written or recorded before the intent block existed carry draft fields only. They are
 * replayed under this one clear reading so they keep exercising what they were written for; the
 * frozen golden dataset is not edited. Tests about intent script their own block.
 */
export const recordedIntent = {
  normalizedGoal: "Do the task the recorded draft describes.",
  taskType: "recorded_fixture",
  explicitRequirements: ["the capabilities the recorded draft lists"],
  inferredRequirements: [],
  confidence: "HIGH",
  missingInformation: [],
} as const;

/**
 * Compile a draft written in the recorded shape, as construction would once it had accepted the
 * recorded reading. For fixtures that need a stored artifact rather than a construction run.
 */
export function compileRecorded(
  request: AgentCreationRequest,
  draft: unknown,
  bindings: Parameters<typeof compileAgentSpec>[3] = {},
) {
  const {
    confidence: _confidence,
    missingInformation: _missingInformation,
    ...reading
  } = recordedIntent;
  return compileAgentSpec(
    request,
    withRecordedSkill(draft) as AgentDraft,
    reading,
    bindings,
  );
}

const isRecordedDraft = (
  completion: unknown,
): completion is Record<string, unknown> =>
  completion !== null &&
  typeof completion === "object" &&
  !Array.isArray(completion) &&
  !(completion instanceof Error) &&
  !("verdict" in completion);

/**
 * Generations recorded before skills were generated carry their method as top-level `procedure`
 * and `acceptanceCriteria`. The same content is moved into `generatedSkill`, with one guidance
 * entry per proposed tool, so a recording keeps exercising what it was written for. Nothing is
 * repaired on the way: a recording that was malformed stays malformed.
 */
export function withRecordedSkill(completion: unknown): unknown {
  if (
    !isRecordedDraft(completion) ||
    "generatedSkill" in completion ||
    !("procedure" in completion || "acceptanceCriteria" in completion)
  )
    return completion;
  const { procedure, acceptanceCriteria, ...draft } = completion;
  const requirements = Array.isArray(draft.requirements)
    ? (draft.requirements as { proposedRefs?: unknown }[])
    : [];
  return {
    ...draft,
    generatedSkill: {
      name: "Recorded procedure",
      objective: draft.goal,
      procedure,
      toolUsageGuidance: [
        ...new Set(
          requirements.flatMap((entry) =>
            Array.isArray(entry?.proposedRefs) ? entry.proposedRefs : [],
          ),
        ),
      ].map((toolRef) => ({
        toolRef,
        whenToUse:
          "When the recorded procedure reaches the step that needs it.",
        purpose: "Fulfil the recorded requirement that proposes it.",
        guidance:
          "Call it as the recorded procedure says and use what it returns.",
      })),
      constraints: [],
      completionCriteria: acceptanceCriteria,
    },
  };
}

/** Reviews, raw strings, errors and completions that script their own intent pass through. */
export function withRecordedIntent(completion: unknown): unknown {
  const upgraded = withRecordedSkill(completion);
  return isRecordedDraft(upgraded) && !("intent" in upgraded)
    ? { intent: recordedIntent, ...upgraded }
    : upgraded;
}
