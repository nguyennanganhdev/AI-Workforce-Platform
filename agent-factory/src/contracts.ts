export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface AgentCreationRequest {
  readonly name: string;
  readonly role: string;
  readonly description: string;
}

export type IntentSource =
  | {
      readonly kind: "request";
      readonly field: keyof AgentCreationRequest;
      readonly quote: string;
    }
  | { readonly kind: "resource"; readonly ref: string };

export interface IntentStatement {
  readonly statement: string;
  readonly source: IntentSource;
}

export interface DraftRequirement {
  readonly need: string;
  readonly fulfillment: "model_on_input" | "tool";
  readonly source: IntentSource;
  readonly proposedRefs: readonly string[];
}

export interface CapabilityRequirement
  extends Omit<DraftRequirement, "proposedRefs"> {
  readonly id: string;
}

export interface ArgumentSource {
  readonly argument: string;
  readonly sourceKind: "user_input" | "runtime_context" | "tool_result";
  readonly sourceRef: string;
  readonly missingBehavior: string;
}

export interface InputFact {
  readonly name: string;
  readonly required: boolean;
  readonly missingBehavior: string;
}

/**
 * The procedural knowledge a generated agent works by: written by construction for one request,
 * never selected from a catalogue. Declarative text only, so it needs no grant and grants nothing:
 * every `toolRef` is a resolved or default tool of the same spec, and calling one still goes
 * through the platform's own authorization.
 */
export interface GeneratedSkill {
  readonly name: string;
  readonly objective: string;
  readonly procedure: readonly string[];
  readonly toolUsageGuidance: readonly {
    readonly toolRef: string;
    readonly whenToUse: string;
    readonly purpose: string;
    readonly guidance: string;
  }[];
  readonly constraints: readonly string[];
  readonly completionCriteria: readonly string[];
}

export interface AgentDraft {
  readonly goal: string;
  readonly responsibilities: readonly IntentStatement[];
  readonly constraints: readonly IntentStatement[];
  readonly generatedSkill: GeneratedSkill;
  readonly requirements: readonly DraftRequirement[];
  readonly toolArguments: readonly (ArgumentSource & {
    readonly ref: string;
  })[];
  readonly inputFacts: readonly InputFact[];
  readonly outputExpectations: readonly string[];
  readonly unresolvedQuestions: readonly string[];
  readonly unsupportedRequirements: readonly {
    readonly kind: "enforced_structured_output" | "runtime_profile";
    readonly source: IntentSource;
  }[];
}

/**
 * How construction read the request before deriving any requirement. It selects no resource.
 * `LOW` stops construction with `missingInformation` instead of a guess; otherwise the reading
 * itself is kept in the spec as {@link SpecIntent}.
 */
export interface IntentNormalizationResult {
  /** The validated request, copied by code; the model cannot restate it. */
  readonly originalInput: AgentCreationRequest;
  readonly normalizedGoal: string;
  /** A free descriptive label in lower_snake_case, not a catalogue ref or a taxonomy entry. */
  readonly taskType: string;
  readonly explicitRequirements: readonly string[];
  readonly inferredRequirements: readonly string[];
  readonly confidence: "HIGH" | "MEDIUM" | "LOW";
  readonly missingInformation: readonly string[];
}

/** The part of the reading a spec keeps: what the agent is for, not how sure construction was. */
export type SpecIntent = Pick<
  IntentNormalizationResult,
  | "normalizedGoal"
  | "taskType"
  | "explicitRequirements"
  | "inferredRequirements"
>;

export interface AgentResource {
  /** `skill` only in a {@link LegacyAgentSpec}; construction binds tools and nothing else. */
  readonly kind: "tool" | "skill";
  readonly ref: string;
  readonly requirementIds: readonly string[];
  readonly fingerprint: string;
  readonly argumentSources: readonly ArgumentSource[];
}

export interface TextContract {
  readonly transport: "ag_ui_messages";
  readonly schema: { readonly type: "string"; readonly minLength: 1 };
}

interface AgentSpecCommon {
  readonly identity: AgentCreationRequest;
  readonly goal: string;
  readonly responsibilities: readonly IntentStatement[];
  readonly constraints: readonly IntentStatement[];
  readonly resources: readonly AgentResource[];
  readonly inputContract: TextContract & {
    readonly inputFacts: readonly InputFact[];
  };
  readonly outputContract: TextContract & {
    readonly expectations: readonly string[];
    readonly enforcement: "prompt_only";
  };
  readonly runtimeProfile: "openbot_builtin_v1";
}

/**
 * An artifact stored before skills were generated: its procedure may come from a selected
 * catalogue skill, bound as a `skill` resource that needs its own grant. Read and run unchanged;
 * construction never produces one.
 */
export interface LegacyAgentSpec extends AgentSpecCommon {
  readonly schemaVersion: 1;
  readonly procedure: readonly string[];
  readonly requirements: readonly (Omit<
    CapabilityRequirement,
    "fulfillment"
  > & {
    readonly fulfillment:
      | CapabilityRequirement["fulfillment"]
      | "skill_instruction";
  })[];
  readonly acceptanceCriteria: readonly string[];
  readonly compilerVersion: 1;
}

export interface GeneratedSkillAgentSpec extends AgentSpecCommon {
  readonly schemaVersion: 2;
  readonly intent: SpecIntent;
  readonly requirements: readonly CapabilityRequirement[];
  /**
   * Tools the catalogue attaches to every agent. Available, not required: one blocks readiness
   * only when a requirement binds it, and then it is also an entry of `resources`.
   */
  readonly defaultTools: readonly Pick<AgentResource, "ref" | "fingerprint">[];
  readonly generatedSkill: GeneratedSkill;
  readonly compilerVersion: 2;
}

export type AgentSpec = LegacyAgentSpec | GeneratedSkillAgentSpec;

export interface FactoryIssue {
  readonly code: string;
  readonly path: string;
  readonly sourceStage:
    | "request"
    | "draft"
    | "resources"
    | "compiler"
    | "access"
    | "dependency";
  readonly evidenceRefs: readonly string[];
  readonly message: string;
}

export type FactoryResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly issues: readonly FactoryIssue[] };

export interface VerificationResult {
  readonly specHash: string;
  readonly construction: "PASS" | "FAIL";
  readonly issues: readonly FactoryIssue[];
  readonly warnings: readonly {
    readonly code: string;
    readonly message: string;
  }[];
  readonly attempts: 1 | 2;
  readonly semanticReview: {
    readonly verdict: "PASS" | "FAIL";
    readonly modelRef: string;
    readonly criterionFindings: readonly FactoryIssue[];
  };
}

export interface FactoryReadiness {
  readonly state: "ready" | "pending_resources";
  readonly blockers: readonly FactoryIssue[];
}

export interface FactoryConfiguration {
  readonly spec: AgentSpec;
  readonly verification: VerificationResult;
  readonly state: FactoryReadiness["state"];
  readonly requestHash: string;
  readonly creationKeyHash: string;
}

/** Compact roster facts; the full artifact is served only by the factory endpoint. */
export interface GeneratedAgentSummary {
  /** `invalid` is a read-side projection of a corrupt marker, never a persisted state. */
  readonly state: FactoryReadiness["state"] | "invalid";
  readonly specHash: string | null;
}

export interface FactoryArtifactResponse<Agent> {
  readonly agent: Agent;
  readonly spec: AgentSpec;
  readonly verification: VerificationResult;
  readonly readiness: FactoryReadiness;
}

export interface FactoryErrorResponse {
  readonly error: string;
  readonly code: string;
  readonly constructionId: string | null;
  readonly issues: readonly FactoryIssue[];
  readonly retryable: boolean;
}

export interface FactoryTool {
  readonly kind: "tool";
  readonly ref: string;
  readonly name: string;
  readonly title: string;
  readonly description: string;
  readonly inputSchema: Readonly<Record<string, JsonValue>>;
  /** The existing MCP cache does not record output schemas. */
  readonly outputSchema: null;
  readonly effect: "read" | "write";
  readonly destructive: boolean;
  readonly fingerprint: string;
}

/** A catalogue skill. Read only by BE readiness of a {@link LegacyAgentSpec}; never by construction. */
export interface FactorySkill {
  readonly kind: "skill";
  readonly ref: string;
  readonly title: string;
  readonly description: string;
  readonly instructions: string;
  readonly toolRefs: readonly string[];
  readonly fingerprint: string;
}

export type FactoryCandidate = FactoryTool | FactorySkill;
export type FactoryCandidateProjection =
  | Omit<FactoryTool, "fingerprint">
  | Omit<FactorySkill, "fingerprint">;

export interface FactoryCatalogueProjection {
  readonly tools: readonly Omit<FactoryTool, "fingerprint">[];
  /** Still projected by BE for legacy readiness. Construction accepts and ignores it unread. */
  readonly skills: readonly Omit<FactorySkill, "fingerprint">[];
  /**
   * Refs in `tools` that BE attaches to every generated agent, such as its knowledge-retrieval
   * tool. The Factory names none itself.
   */
  readonly defaultToolRefs?: readonly string[];
}

/** BE supplies an actor-scoped catalogue; credentials and grants never cross this API. */
export interface FactoryConstructionRequest {
  readonly request: AgentCreationRequest;
  readonly catalogue: Pick<
    FactoryCatalogueProjection,
    "tools" | "defaultToolRefs"
  >;
}

/** Construction only. Persistence and runtime readiness are BE responsibilities. */
export interface FactoryConstructionResponse {
  readonly spec: GeneratedSkillAgentSpec;
  readonly systemPrompt: string;
  readonly specHash: string;
  readonly intent: IntentNormalizationResult;
  readonly verification: VerificationResult;
}

/** What construction resolves against: tools only. */
export interface FactoryCatalogue {
  readonly tools: readonly FactoryTool[];
  readonly defaultToolRefs?: readonly string[];
}

export type FactoryResourceRef = Pick<AgentResource, "kind" | "ref">;

export interface FactoryResourceFact extends FactoryResourceRef {
  readonly resource: FactoryCandidateProjection | null;
  readonly granted: boolean;
  readonly configured: boolean;
  readonly connected: boolean;
}

export interface FactoryReadOptions {
  readonly signal?: AbortSignal;
  readonly timeoutMs?: number;
}
