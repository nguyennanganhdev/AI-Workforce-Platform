import { createHash } from "node:crypto";
import { z } from "zod";
import type {
  AgentCreationRequest,
  AgentDraft,
  AgentResource,
  AgentSpec,
  CapabilityRequirement,
  DraftRequirement,
  FactoryCandidateProjection,
  FactoryConfiguration,
  FactoryConstructionResponse,
  FactoryCatalogue,
  FactoryIssue,
  FactoryResult,
  GeneratedSkillAgentSpec,
  IntentNormalizationResult,
  IntentSource,
  SpecIntent,
} from "./contracts.js";

export const FACTORY_LIMITS = {
  name: 80,
  role: 120,
  description: 1000,
  text: 4096,
  items: 32,
  draftBytes: 64 * 1024,
  promptBytes: 16 * 1024,
  tools: 64,
  catalogueBytes: 96 * 1024,
  selectedTools: 8,
  defaultTools: 4,
  // Read only by BE's catalogue projection and readiness of schemaVersion 1 artifacts.
  skills: 32,
  selectedSkills: 4,
} as const;

const text = z.string().trim().min(1).max(FACTORY_LIMITS.text);
const ref = z
  .string()
  .min(1)
  .max(FACTORY_LIMITS.text)
  .refine((value) => !!value.trim());
const requirementId = z
  .string()
  .max(1 + String(FACTORY_LIMITS.items).length)
  .regex(/^r[1-9]\d*$/);
const list = <T extends z.ZodType>(item: T, min = 0) =>
  z.array(item).min(min).max(FACTORY_LIMITS.items);
const requestSchema = z.strictObject({
  name: z.string().trim().min(1).max(FACTORY_LIMITS.name),
  role: z.string().trim().min(1).max(FACTORY_LIMITS.role),
  description: z.string().trim().min(1).max(FACTORY_LIMITS.description),
});
const sourceSchema = z.discriminatedUnion("kind", [
  z.strictObject({
    kind: z.literal("request"),
    field: z.enum(["name", "role", "description"]),
    quote: z
      .string()
      .min(1)
      .max(FACTORY_LIMITS.description)
      .refine((value) => !!value.trim()),
  }),
  z.strictObject({ kind: z.literal("resource"), ref }),
]);
const statementSchema = z.strictObject({
  statement: text,
  source: sourceSchema,
});
const requirementFields = {
  need: text,
  fulfillment: z.enum(["model_on_input", "tool"]),
  source: sourceSchema,
};
const argumentFields = {
  argument: text,
  sourceKind: z.enum(["user_input", "runtime_context", "tool_result"]),
  sourceRef: text,
  missingBehavior: text,
};
const argumentSchema = z.strictObject(argumentFields);
const inputFactSchema = z.strictObject({
  name: text,
  required: z.boolean(),
  missingBehavior: text,
});
const behaviorFields = {
  goal: text,
  responsibilities: list(statementSchema, 1),
  constraints: list(statementSchema),
};
const skillSchema = z.strictObject({
  name: z.string().trim().min(1).max(FACTORY_LIMITS.role),
  objective: text,
  procedure: list(text, 1),
  toolUsageGuidance: list(
    z.strictObject({
      toolRef: ref,
      whenToUse: text,
      purpose: text,
      guidance: text,
    }),
  ),
  constraints: list(text),
  completionCriteria: list(text, 1),
});
const draftSchema = z.strictObject({
  ...behaviorFields,
  generatedSkill: skillSchema,
  requirements: list(
    z.strictObject({ ...requirementFields, proposedRefs: list(ref) }),
  ),
  toolArguments: list(z.strictObject({ ref, ...argumentFields })),
  inputFacts: list(inputFactSchema),
  outputExpectations: list(text, 1),
  unresolvedQuestions: list(text),
  unsupportedRequirements: list(
    z.strictObject({
      kind: z.enum(["enforced_structured_output", "runtime_profile"]),
      source: sourceSchema,
    }),
  ),
});
const readingFields = {
  normalizedGoal: text,
  taskType: z
    .string()
    .trim()
    .max(64)
    .regex(/[\p{L}\p{N}]/u),
  explicitRequirements: list(text),
  inferredRequirements: list(text),
};
const intentSchema = z
  .strictObject({
    ...readingFields,
    confidence: z.enum(["HIGH", "MEDIUM", "LOW"]),
    missingInformation: list(text),
  })
  // The label and the open points must agree: nothing is missing exactly when the reading is
  // HIGH, and a LOW reading without them would give the person nothing to answer.
  .refine(
    ({ confidence, missingInformation }) =>
      (confidence === "HIGH") === (missingInformation.length === 0),
    { path: ["missingInformation"] },
  );
/** What a generation returns: the draft fields and, beside them, the reading they follow from. */
const generationShape = { ...draftSchema.shape, intent: intentSchema };
/**
 * The validator's own schema for one top-level field of a generation, as JSON Schema. A repair is
 * shown this rather than a description of it, so what the model is told and what `parseAgentDraft`
 * and `parseIntentNormalization` check cannot differ. Unknown fields have none.
 */
export function draftFieldSchema(field: string): unknown {
  if (!Object.hasOwn(generationShape, field)) return undefined;
  const { $schema: _, ...schema } = z.toJSONSchema(
    generationShape[field as keyof typeof generationShape],
  );
  return schema;
}
const contractFields = {
  transport: z.literal("ag_ui_messages"),
  schema: z.strictObject({
    type: z.literal("string"),
    minLength: z.literal(1),
  }),
};
const fingerprintSchema = z.string().regex(/^[a-f0-9]{64}$/);
const resourceFields = {
  ref,
  requirementIds: list(requirementId, 1),
  fingerprint: fingerprintSchema,
  argumentSources: list(argumentSchema),
};
const specFields = {
  ...behaviorFields,
  identity: requestSchema,
  inputContract: z.strictObject({
    ...contractFields,
    inputFacts: list(inputFactSchema),
  }),
  outputContract: z.strictObject({
    ...contractFields,
    expectations: list(text, 1),
    enforcement: z.literal("prompt_only"),
  }),
  runtimeProfile: z.literal("openbot_builtin_v1"),
};
/** Exactly what compilerVersion 1 stored. Kept so those artifacts still pass integrity; frozen. */
const legacySpecSchema = z.strictObject({
  ...specFields,
  schemaVersion: z.literal(1),
  procedure: list(text, 1),
  acceptanceCriteria: list(text, 1),
  requirements: list(
    z.strictObject({
      id: requirementId,
      ...requirementFields,
      fulfillment: z.enum(["model_on_input", "tool", "skill_instruction"]),
    }),
  ),
  resources: list(
    z.strictObject({ kind: z.enum(["tool", "skill"]), ...resourceFields }),
  ),
  compilerVersion: z.literal(1),
});
const specSchema = z.strictObject({
  ...specFields,
  schemaVersion: z.literal(2),
  intent: z.strictObject(readingFields),
  requirements: list(
    z.strictObject({ id: requirementId, ...requirementFields }),
  ),
  resources: list(
    z.strictObject({ kind: z.literal("tool"), ...resourceFields }),
  ),
  defaultTools: z
    .array(z.strictObject({ ref, fingerprint: fingerprintSchema }))
    .max(FACTORY_LIMITS.defaultTools),
  generatedSkill: skillSchema,
  compilerVersion: z.literal(2),
});

function issue(
  code: string,
  path: string,
  sourceStage: FactoryIssue["sourceStage"],
  message: string,
  evidenceRefs: readonly string[] = [],
): FactoryIssue {
  return { code, path, sourceStage, message, evidenceRefs };
}

function parse<T>(
  schema: z.ZodType<T>,
  value: unknown,
  stage: FactoryIssue["sourceStage"],
): FactoryResult<T> {
  const result = schema.safeParse(value);
  return result.success
    ? { ok: true, value: result.data }
    : {
        ok: false,
        issues: result.error.issues
          .slice(0, FACTORY_LIMITS.items)
          .map((error) =>
            issue(
              "INVALID_SCHEMA",
              error.path.join("."),
              stage,
              "Invalid or unexpected field.",
            ),
          ),
      };
}

export function parseAgentCreationRequest(
  value: unknown,
): FactoryResult<AgentCreationRequest> {
  return parse(requestSchema, value, "request");
}

function sourceIssues(
  source: IntentSource,
  path: string,
  request: AgentCreationRequest,
  refs: readonly string[],
): FactoryIssue[] {
  const valid =
    source.kind === "request"
      ? request[source.field].includes(source.quote)
      : refs.includes(source.ref);
  return valid
    ? []
    : [
        issue(
          "INVALID_PROVENANCE",
          path,
          "draft",
          "Source quote or reference does not exist.",
          [source.kind === "request" ? `request.${source.field}` : source.ref],
        ),
      ];
}

/**
 * The `intent` block of a generation, checked before any draft field is trusted. It is a reading
 * of the request, not a resource selection: refs still come only from `requirements` and the exact
 * resolver. The request is attached by code and the label is canonicalized, so equivalent
 * readings compare equal whatever casing or separators the model used.
 */
export function parseIntentNormalization(
  value: unknown,
  request: AgentCreationRequest,
): FactoryResult<IntentNormalizationResult> {
  const parsed = parse(intentSchema, value, "draft");
  if (!parsed.ok)
    return {
      ok: false,
      issues: parsed.issues.map((entry) => ({
        ...entry,
        path: entry.path ? `intent.${entry.path}` : "intent",
      })),
    };
  return {
    ok: true,
    value: {
      originalInput: request,
      ...parsed.value,
      taskType: parsed.value.taskType
        .toLowerCase()
        .replace(/[^\p{L}\p{N}]+/gu, "_")
        .replace(/^_|_$/g, ""),
    },
  };
}

export function parseAgentDraft(
  value: unknown,
  request: AgentCreationRequest,
  sourceRefs: readonly string[] = [],
): FactoryResult<AgentDraft> {
  try {
    if (
      Buffer.byteLength(JSON.stringify(value) ?? "", "utf8") >
      FACTORY_LIMITS.draftBytes
    ) {
      return {
        ok: false,
        issues: [
          issue(
            "DRAFT_TOO_LARGE",
            "",
            "draft",
            "Draft exceeds the UTF-8 byte limit.",
          ),
        ],
      };
    }
  } catch {
    return {
      ok: false,
      issues: [
        issue("INVALID_SCHEMA", "", "draft", "Draft must be JSON data."),
      ],
    };
  }
  const parsed = parse(draftSchema, value, "draft");
  if (!parsed.ok) return parsed;
  const issues = (
    [
      "responsibilities",
      "constraints",
      "requirements",
      "unsupportedRequirements",
    ] as const
  ).flatMap((field) =>
    parsed.value[field].flatMap((entry, index) =>
      sourceIssues(
        entry.source,
        `${field}.${index}.source`,
        request,
        sourceRefs,
      ),
    ),
  );
  return issues.length ? { ok: false, issues } : parsed;
}

export function normalizeRequirements(
  requirements: readonly DraftRequirement[],
): readonly CapabilityRequirement[] {
  return requirements.map(({ need, fulfillment, source }, index) => ({
    id: `r${index + 1}`,
    need,
    fulfillment,
    source,
  }));
}

/** Either stored version. Construction itself only ever compiles schemaVersion 2. */
export function parseAgentSpec(value: unknown): FactoryResult<AgentSpec> {
  return parse(
    z.discriminatedUnion("schemaVersion", [legacySpecSchema, specSchema]),
    value,
    "compiler",
  );
}

// ponytail: a pattern list, not a parser. The schema has no code field, so this only refuses the
// obvious; whether prose smuggles a procedure-as-program is the reviewer's call.
const EXECUTABLE =
  /```|<script\b|^#!|\bfunction\s*\w*\s*\([^)]*\)\s*\{|=>\s*\{|\bdef\s+\w+\s*\([^)]*\)\s*:|\bimport\s+[\w*{}\s,]+\s+from\s+["']|\b(?:require|eval|exec)\s*\(\s*["'`]|\bsubprocess\.|\bos\.system\b|\bcurl\s+-|\bsudo\s+\w/m;
const SECRET =
  /\bsk-[\w-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|\btvly-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[\w.~+/-]{20,}|\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*["']?[\w.~+/-]{12,}/i;

/**
 * What code can say about a generated skill: it guides the tools the spec holds and no other, and
 * it is text. A skill is not an authorization, so naming a tool here never makes it callable; this
 * only refuses a skill that tells the agent to use something it was not given. `catalogueRefs` is
 * absent for a stored artifact, whose catalogue is gone.
 *
 * ponytail: a tool that is in no catalogue can only be spotted by the reviewer; code checks refs.
 */
export function generatedSkillIssues(
  spec: Pick<
    GeneratedSkillAgentSpec,
    "generatedSkill" | "resources" | "defaultTools"
  >,
  catalogueRefs: readonly string[] = [],
): FactoryIssue[] {
  const skill = spec.generatedSkill;
  const required = spec.resources.map(({ ref }) => ref);
  const allowed = new Set([
    ...required,
    ...spec.defaultTools.map(({ ref }) => ref),
  ]);
  const guided = skill.toolUsageGuidance.map(({ toolRef }) => toolRef);
  const issues: FactoryIssue[] = [];
  const fail = (
    code: string,
    path: string,
    message: string,
    refs: readonly string[] = [],
  ) =>
    issues.push(issue(code, `generatedSkill${path}`, "draft", message, refs));
  guided.forEach((toolRef, index) => {
    if (!allowed.has(toolRef))
      fail(
        "UNKNOWN_SKILL_TOOL",
        `.toolUsageGuidance.${index}`,
        "Skill guidance names a tool that is neither resolved nor a default tool.",
        [toolRef],
      );
    else if (guided.indexOf(toolRef) !== index)
      fail(
        "INVALID_SCHEMA",
        `.toolUsageGuidance.${index}`,
        "Each tool has exactly one guidance entry.",
        [toolRef],
      );
  });
  for (const toolRef of required)
    if (!guided.includes(toolRef))
      fail(
        "SKILL_TOOL_UNGUIDED",
        ".toolUsageGuidance",
        "A resolved tool has no usage guidance in the skill.",
        [toolRef],
      );
  const prose = canonical(skill);
  // Whole refs only: `drive/search` is not named by a skill that uses `google-drive/search`.
  const named = catalogueRefs.filter(
    (candidate) =>
      !allowed.has(candidate) &&
      new RegExp(
        `(?<![\\w./-])${candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w/-])`,
      ).test(prose),
  );
  if (named.length)
    fail(
      "UNKNOWN_SKILL_TOOL",
      "",
      "Skill text names a catalogue tool the agent was not given.",
      named,
    );
  const texts = [
    skill.name,
    skill.objective,
    ...skill.procedure,
    ...skill.toolUsageGuidance.flatMap(({ whenToUse, purpose, guidance }) => [
      whenToUse,
      purpose,
      guidance,
    ]),
    ...skill.constraints,
    ...skill.completionCriteria,
  ];
  if (texts.some((entry) => EXECUTABLE.test(entry)))
    fail(
      "SKILL_EXECUTABLE_CONTENT",
      "",
      "A generated skill is declarative text and carries no code or commands.",
    );
  if (texts.some((entry) => SECRET.test(entry)))
    fail(
      "SKILL_SECRET",
      "",
      "A generated skill carries no credential, key or token.",
    );
  return issues;
}

/** Resources are supplied by the exact resolver. No discovery here. */
export function compileAgentSpec(
  request: AgentCreationRequest,
  draft: AgentDraft,
  intent: SpecIntent,
  bindings: {
    readonly resources?: readonly AgentResource[];
    readonly defaultTools?: GeneratedSkillAgentSpec["defaultTools"];
    /** Every ref of the catalogue this construction ran against. */
    readonly catalogueRefs?: readonly string[];
  } = {},
): FactoryResult<{
  readonly spec: GeneratedSkillAgentSpec;
  readonly systemPrompt: string;
  readonly specHash: string;
}> {
  const normalized = parseAgentCreationRequest(request);
  if (!normalized.ok) return normalized;
  const parsed = parseAgentDraft(
    draft,
    normalized.value,
    bindings.catalogueRefs,
  );
  if (!parsed.ok) return parsed;
  const value = parsed.value;
  if (value.unsupportedRequirements.length) {
    return {
      ok: false,
      issues: value.unsupportedRequirements.map((entry, index) =>
        issue(
          entry.kind === "enforced_structured_output"
            ? "UNSUPPORTED_CONTRACT"
            : "UNSUPPORTED_RUNTIME_PROFILE",
          `unsupportedRequirements.${index}`,
          "draft",
          "The built-in runtime does not support this requirement.",
        ),
      ),
    };
  }
  if (value.unresolvedQuestions.length) {
    return {
      ok: false,
      issues: [
        issue(
          "NEEDS_INPUT",
          "unresolvedQuestions",
          "draft",
          "Clarification is required before compilation.",
        ),
      ],
    };
  }
  const spec = parse(
    specSchema,
    {
      schemaVersion: 2,
      identity: normalized.value,
      intent: {
        normalizedGoal: intent.normalizedGoal,
        taskType: intent.taskType,
        explicitRequirements: intent.explicitRequirements,
        inferredRequirements: intent.inferredRequirements,
      },
      goal: value.goal,
      responsibilities: value.responsibilities,
      constraints: value.constraints,
      requirements: normalizeRequirements(value.requirements),
      resources: bindings.resources ?? [],
      defaultTools: bindings.defaultTools ?? [],
      generatedSkill: value.generatedSkill,
      inputContract: {
        transport: "ag_ui_messages",
        schema: { type: "string", minLength: 1 },
        inputFacts: value.inputFacts,
      },
      outputContract: {
        transport: "ag_ui_messages",
        schema: { type: "string", minLength: 1 },
        expectations: value.outputExpectations,
        enforcement: "prompt_only",
      },
      runtimeProfile: "openbot_builtin_v1",
      compilerVersion: 2,
    },
    "compiler",
  );
  if (!spec.ok) return spec;
  const skillIssues = generatedSkillIssues(spec.value, bindings.catalogueRefs);
  if (skillIssues.length) return { ok: false, issues: skillIssues };
  const systemPrompt = renderCorePrompt(spec.value);
  if (Buffer.byteLength(systemPrompt, "utf8") > FACTORY_LIMITS.promptBytes) {
    return {
      ok: false,
      issues: [
        issue(
          "PROMPT_TOO_LARGE",
          "",
          "compiler",
          "Core prompt exceeds the UTF-8 byte limit.",
        ),
      ],
    };
  }
  return {
    ok: true,
    value: {
      spec: spec.value,
      systemPrompt,
      specHash: hashAgentSpec(spec.value),
    },
  };
}

/**
 * The stored prompt is this projection of the spec, byte for byte: integrity compares them. So the
 * schemaVersion 1 sections are frozen, and a new section is a new compiler version.
 */
export function renderCorePrompt(spec: AgentSpec): string {
  const needs = spec.requirements.map(({ id, need, fulfillment }) => ({
    id,
    need,
    fulfillment,
  }));
  const responsibilities = spec.responsibilities.map(
    ({ statement }) => statement,
  );
  const constraints = spec.constraints.map(({ statement }) => statement);
  const sections: readonly [string, unknown][] =
    spec.schemaVersion === 1
      ? [
          ["Identity", spec.identity],
          ["Goal", spec.goal],
          ["Responsibilities", responsibilities],
          ["Constraints", constraints],
          ["Procedure", spec.procedure],
          ["Resource needs", needs],
          ["Resource usage", spec.resources],
          ["Input and missing-input behavior", spec.inputContract],
          ["Output expectations", spec.outputContract],
          ["Acceptance criteria", spec.acceptanceCriteria],
        ]
      : [
          ["Identity", spec.identity],
          ["Intent", spec.intent],
          ["Goal", spec.goal],
          ["Responsibilities", responsibilities],
          ["Constraints", constraints],
          [
            "Skill",
            {
              name: spec.generatedSkill.name,
              objective: spec.generatedSkill.objective,
            },
          ],
          ["Procedure", spec.generatedSkill.procedure],
          ["Tool usage guidance", spec.generatedSkill.toolUsageGuidance],
          ["Skill constraints", spec.generatedSkill.constraints],
          ["Completion criteria", spec.generatedSkill.completionCriteria],
          ["Resource needs", needs],
          ["Resource usage", spec.resources],
          [
            "Default tools (available; use one only when the task needs it)",
            spec.defaultTools.map(({ ref }) => ref),
          ],
          ["Input and missing-input behavior", spec.inputContract],
          ["Output expectations", spec.outputContract],
        ];
  return sections
    .map(([title, value]) => `## ${title}\n${canonical(value)}`)
    .join("\n\n");
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`,
      )
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

export function hashAgentSpec(spec: AgentSpec): string {
  return createHash("sha256").update(canonical(spec), "utf8").digest("hex");
}

const toolProjectionSchema = z.strictObject({
  kind: z.literal("tool"),
  ref,
  name: ref,
  title: ref,
  description: z.string(),
  inputSchema: z.record(z.string(), z.json()),
  outputSchema: z.null(),
  effect: z.enum(["read", "write"]),
  destructive: z.boolean(),
});
const defaultToolRefsSchema = z.array(ref).max(FACTORY_LIMITS.defaultTools);

export function fingerprintFactoryResource(
  resource: FactoryCandidateProjection,
): string {
  const semantic =
    resource.kind === "tool"
      ? {
          kind: resource.kind,
          ref: resource.ref,
          name: resource.name,
          title: resource.title,
          description: resource.description,
          inputSchema: resource.inputSchema,
          outputSchema: resource.outputSchema,
          effect: resource.effect,
          destructive: resource.destructive,
        }
      : {
          kind: resource.kind,
          ref: resource.ref,
          title: resource.title,
          description: resource.description,
          instructions: resource.instructions,
          toolRefs: [...resource.toolRefs].sort(),
        };
  return createHash("sha256").update(canonical(semantic), "utf8").digest("hex");
}

function catalogueBounds(value: {
  tools: readonly unknown[];
  defaultToolRefs?: unknown;
}): FactoryIssue[] {
  try {
    return value.tools.length > FACTORY_LIMITS.tools ||
      Buffer.byteLength(JSON.stringify(value), "utf8") >
        FACTORY_LIMITS.catalogueBytes
      ? [
          issue(
            "CATALOGUE_TOO_LARGE",
            "",
            "resources",
            "Catalogue exceeds construction limits.",
          ),
        ]
      : [];
  } catch {
    return [
      issue("INVALID_SCHEMA", "", "resources", "Catalogue must be JSON data."),
    ];
  }
}

/**
 * The tools construction may resolve against, fingerprinted. A supplied `skills` key is dropped
 * before anything is measured or validated: construction reads no skill, so a skill catalogue of
 * any size or shape can neither feed nor fail it.
 */
export function prepareFactoryCatalogue(
  value: unknown,
): FactoryResult<FactoryCatalogue> {
  if (
    !value ||
    typeof value !== "object" ||
    !("tools" in value) ||
    !Array.isArray(value.tools)
  ) {
    return {
      ok: false,
      issues: [
        issue(
          "INVALID_SCHEMA",
          "",
          "resources",
          "Catalogue must contain a tool array.",
        ),
      ],
    };
  }
  const { skills: _, ...supplied } = value as {
    tools: unknown[];
    skills?: unknown;
  };
  const inputBounds = catalogueBounds(supplied);
  if (inputBounds.length) return { ok: false, issues: inputBounds };
  const projection = parse(
    z.strictObject({
      tools: z.array(toolProjectionSchema),
      defaultToolRefs: defaultToolRefsSchema.optional(),
    }),
    supplied,
    "resources",
  );
  if (!projection.ok) return projection;
  const catalogue = {
    tools: projection.value.tools.map((tool) => ({
      ...tool,
      fingerprint: fingerprintFactoryResource(tool),
    })),
    defaultToolRefs: projection.value.defaultToolRefs ?? [],
  };
  const finalBounds = catalogueBounds(catalogue);
  if (finalBounds.length) return { ok: false, issues: finalBounds };
  const refs = catalogue.tools.map(({ ref }) => ref);
  if (
    new Set(refs).size !== refs.length ||
    new Set(catalogue.defaultToolRefs).size !==
      catalogue.defaultToolRefs.length ||
    catalogue.defaultToolRefs.some((ref) => !refs.includes(ref))
  ) {
    return {
      ok: false,
      issues: [
        issue(
          "INVALID_CATALOGUE",
          "",
          "resources",
          "Catalogue contains duplicate references or a default tool it does not list.",
        ),
      ],
    };
  }
  return { ok: true, value: catalogue };
}

/** The catalogue's default tools as a spec records them. Attached by code, never by the model. */
export function defaultToolsOf(
  snapshot: FactoryCatalogue,
): GeneratedSkillAgentSpec["defaultTools"] {
  return (snapshot.defaultToolRefs ?? []).flatMap((ref) => {
    const tool = snapshot.tools.find((entry) => entry.ref === ref);
    return tool ? [{ ref, fingerprint: tool.fingerprint }] : [];
  });
}

/** Exact matching only. Operation/effect adequacy against prose belongs to independent review. */
export function resolveDraftResources(
  request: AgentCreationRequest,
  draft: AgentDraft,
  snapshot: FactoryCatalogue,
  runtimeContextFields: readonly string[] = [],
): FactoryResult<readonly AgentResource[]> {
  // Re-derived from the facts themselves, so a snapshot cannot vouch for its own fingerprints.
  const refreshed = prepareFactoryCatalogue(
    Array.isArray(snapshot?.tools)
      ? {
          tools: snapshot.tools.map(({ fingerprint: _, ...tool }) => tool),
          defaultToolRefs: snapshot.defaultToolRefs ?? [],
        }
      : snapshot,
  );
  if (!refreshed.ok) return refreshed;
  if (
    snapshot.tools.some(
      (entry, index) =>
        entry.fingerprint !== refreshed.value.tools[index]?.fingerprint,
    )
  ) {
    return {
      ok: false,
      issues: [
        issue(
          "RESOURCE_CHANGED",
          "",
          "resources",
          "Resource fingerprint does not match its evidence.",
        ),
      ],
    };
  }
  const parsed = parseAgentDraft(
    draft,
    request,
    snapshot.tools.map(({ ref }) => ref),
  );
  if (!parsed.ok) return parsed;
  const value = parsed.value;
  const resources = new Map<string, AgentResource>();
  const issues: FactoryIssue[] = [];
  const fail = (
    code: string,
    path: string,
    message: string,
    refs: string[] = [],
  ) => issues.push(issue(code, path, "resources", message, refs));
  value.requirements.forEach((requirement, index) => {
    const path = `requirements.${index}`;
    if (requirement.fulfillment === "model_on_input") {
      if (requirement.proposedRefs.length)
        fail(
          "UNUSED_RESOURCE",
          path,
          "Model-on-input needs must not bind resources.",
        );
      return;
    }
    if (!requirement.proposedRefs.length)
      fail(
        "BLOCKED_RESOURCE",
        path,
        "A required resource has no proposed reference.",
      );
    for (const ref of requirement.proposedRefs) {
      const candidate = snapshot.tools.find((entry) => entry.ref === ref);
      if (!candidate) {
        fail(
          "UNKNOWN_RESOURCE",
          path,
          "Required reference does not exist in the supplied catalogue.",
          [ref],
        );
        continue;
      }
      if (
        requirement.source.kind === "resource" &&
        requirement.source.ref !== ref
      ) {
        fail(
          "RESOURCE_SOURCE_MISMATCH",
          path,
          "Selected resource differs from the requirement evidence.",
          [ref],
        );
      }
      const existing = resources.get(ref);
      const id = `r${index + 1}`;
      resources.set(ref, {
        kind: "tool",
        ref,
        fingerprint: candidate.fingerprint,
        requirementIds: [...new Set([...(existing?.requirementIds ?? []), id])],
        argumentSources: [],
      });
    }
  });
  const selected = [...resources.values()];
  if (selected.length > FACTORY_LIMITS.selectedTools) {
    fail(
      "TOO_MANY_RESOURCES",
      "requirements",
      "Selected resource count exceeds construction limits.",
    );
  }
  for (const entry of selected) {
    const tool = snapshot.tools.find(({ ref }) => ref === entry.ref);
    if (!tool) continue;
    let converted: z.ZodObject;
    try {
      const schema = z.fromJSONSchema(tool.inputSchema as never);
      if (!(schema instanceof z.ZodObject))
        throw new Error("object schema required");
      converted = schema;
    } catch {
      fail(
        "INVALID_TOOL_SCHEMA",
        "resources",
        "Required tool must have a supported object input schema.",
        [entry.ref],
      );
      continue;
    }
    const required = tool.inputSchema.required ?? [];
    if (
      !Array.isArray(required) ||
      required.some(
        (name) => typeof name !== "string" || !(name in converted.shape),
      )
    ) {
      fail(
        "INVALID_TOOL_SCHEMA",
        "resources",
        "Required arguments must name schema properties.",
        [entry.ref],
      );
      continue;
    }
    const sources = value.toolArguments.filter(({ ref }) => ref === entry.ref);
    if (
      new Set(sources.map(({ argument }) => argument)).size !==
        sources.length ||
      sources.some(({ argument }) => !required.includes(argument))
    ) {
      fail(
        "UNUSED_ARGUMENT_SOURCE",
        "toolArguments",
        "Argument declarations must cover required arguments exactly.",
        [entry.ref],
      );
    }
    for (const argument of required) {
      const source = sources.find((entry) => entry.argument === argument);
      if (!source) {
        fail(
          "MISSING_ARGUMENT_SOURCE",
          "toolArguments",
          "Required argument has no declared source.",
          [entry.ref],
        );
        continue;
      }
      const valid =
        source.sourceKind === "user_input"
          ? value.inputFacts.some(({ name }) => name === source.sourceRef)
          : source.sourceKind === "runtime_context" &&
            runtimeContextFields.includes(source.sourceRef);
      if (!valid)
        fail(
          "INVALID_ARGUMENT_SOURCE",
          "toolArguments",
          "Argument source lacks input or documented runtime evidence; tool output schemas are unknown.",
          [entry.ref],
        );
    }
    resources.set(entry.ref, {
      ...entry,
      argumentSources: sources.map(({ ref: _, ...source }) => source),
    });
  }
  if (value.toolArguments.some(({ ref }) => !resources.has(ref))) {
    fail(
      "UNUSED_RESOURCE",
      "toolArguments",
      "Argument declarations name an unselected tool.",
    );
  }
  return issues.length
    ? { ok: false, issues: issues.slice(0, FACTORY_LIMITS.items) }
    : { ok: true, value: [...resources.values()] };
}

export const storedIssueSchema = z.strictObject({
  code: z.string().min(1).max(FACTORY_LIMITS.text),
  path: z.string().max(FACTORY_LIMITS.text),
  sourceStage: z.enum([
    "request",
    "draft",
    "resources",
    "compiler",
    "access",
    "dependency",
  ]),
  evidenceRefs: z
    .array(z.string().max(FACTORY_LIMITS.text))
    .max(FACTORY_LIMITS.items),
  message: z.string().max(FACTORY_LIMITS.text),
});
const storedFactorySchema = z.strictObject({
  spec: z.unknown(),
  verification: z.strictObject({
    specHash: fingerprintSchema,
    construction: z.literal("PASS"),
    issues: z.array(storedIssueSchema).max(FACTORY_LIMITS.items),
    warnings: z
      .array(
        z.strictObject({
          code: z.string().max(FACTORY_LIMITS.text),
          message: z.string().max(FACTORY_LIMITS.text),
        }),
      )
      .max(FACTORY_LIMITS.items),
    attempts: z.union([z.literal(1), z.literal(2)]),
    semanticReview: z.strictObject({
      verdict: z.literal("PASS"),
      modelRef: z.string().min(1).max(FACTORY_LIMITS.text),
      criterionFindings: z.array(storedIssueSchema).max(FACTORY_LIMITS.items),
    }),
  }),
  state: z.enum(["ready", "pending_resources"]),
  requestHash: fingerprintSchema,
  creationKeyHash: fingerprintSchema,
});

/**
 * Integrity of a persisted generated configuration `{ systemPrompt, factory }`: strict artifact,
 * canonical hash and the exact compiler-owned prompt projection. Pure and deterministic, so the
 * runtime normalizer and the shell can both refuse anything else without querying or repairing.
 * It says nothing about current access; readiness is checked separately.
 */
export function parseStoredFactoryConfiguration(
  configuration: unknown,
): FactoryResult<FactoryConfiguration & { readonly systemPrompt: string }> {
  const invalid = {
    ok: false as const,
    issues: [
      issue(
        "ARTIFACT_INVALID",
        "",
        "compiler",
        "Stored generated artifact failed integrity checks.",
      ),
    ],
  };
  if (
    !configuration ||
    typeof configuration !== "object" ||
    Array.isArray(configuration) ||
    Object.keys(configuration).sort().join() !== "factory,systemPrompt"
  )
    return invalid;
  const { systemPrompt, factory } = configuration as {
    systemPrompt: unknown;
    factory: unknown;
  };
  const stored = storedFactorySchema.safeParse(factory);
  if (!stored.success || typeof systemPrompt !== "string") return invalid;
  const spec = parseAgentSpec(stored.data.spec);
  if (
    !spec.ok ||
    stored.data.verification.specHash !== hashAgentSpec(spec.value) ||
    systemPrompt !== renderCorePrompt(spec.value) ||
    (spec.value.schemaVersion === 2 && generatedSkillIssues(spec.value).length)
  )
    return invalid;
  return {
    ok: true,
    value: { ...stored.data, spec: spec.value, systemPrompt },
  };
}

const constructionResponseSchema = z.strictObject({
  spec: specSchema,
  systemPrompt: z.string().max(FACTORY_LIMITS.promptBytes),
  specHash: fingerprintSchema,
  verification: storedFactorySchema.shape.verification,
  intent: intentSchema.safeExtend({ originalInput: requestSchema }),
});

/** Validate the remote artifact before BE can persist it; reuse the core's schemas. */
export function parseFactoryConstructionResponse(
  value: unknown,
  request: AgentCreationRequest,
  catalogue: FactoryCatalogue,
): FactoryResult<FactoryConstructionResponse> {
  const parsed = constructionResponseSchema.safeParse(value);
  if (parsed.success) {
    const artifact = parsed.data;
    const sameRequest = (other: AgentCreationRequest) =>
      other.name === request.name &&
      other.role === request.role &&
      other.description === request.description;
    if (
      sameRequest(artifact.spec.identity) &&
      sameRequest(artifact.intent.originalInput) &&
      artifact.intent.confidence !== "LOW" &&
      // The reading the spec keeps is the reading construction reported, not a second one.
      (Object.keys(artifact.spec.intent) as (keyof SpecIntent)[]).every(
        (key) =>
          canonical(artifact.spec.intent[key]) ===
          canonical(artifact.intent[key]),
      ) &&
      artifact.specHash === hashAgentSpec(artifact.spec) &&
      artifact.verification.specHash === artifact.specHash &&
      artifact.systemPrompt === renderCorePrompt(artifact.spec) &&
      artifact.verification.issues.length === 0 &&
      artifact.verification.semanticReview.criterionFindings.length === 0 &&
      artifact.spec.resources.every((resource) =>
        catalogue.tools.some(
          (candidate) =>
            candidate.ref === resource.ref &&
            candidate.fingerprint === resource.fingerprint,
        ),
      ) &&
      // Exactly the default tools BE declared: a response can neither add nor drop one.
      canonical(artifact.spec.defaultTools) ===
        canonical(defaultToolsOf(catalogue)) &&
      !generatedSkillIssues(
        artifact.spec,
        catalogue.tools.map(({ ref }) => ref),
      ).length
    )
      return { ok: true, value: artifact };
  }
  return {
    ok: false,
    issues: [
      issue(
        "ARTIFACT_INVALID",
        "",
        "compiler",
        "Factory returned an invalid construction artifact.",
      ),
    ],
  };
}
