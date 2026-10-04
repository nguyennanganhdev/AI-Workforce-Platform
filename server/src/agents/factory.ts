import { createHash } from "node:crypto";
import type {
  AgentCreationRequest,
  AgentSpec,
  FactoryCatalogue,
  FactoryConfiguration,
  FactoryIssue,
  FactoryReadiness,
  FactoryReadOptions,
  FactoryResult,
  VerificationResult,
} from "../../../agent-factory/src/contracts.js";
import { type AuditStore, recordAuditEvent } from "../audit.js";
import { DEV_ACTOR } from "../auth/dev-actor.js";
import {
  constructAgentSpec,
  type createFactoryClient,
  type FactoryConstructionOptions,
  type FactoryObservation,
  factoryDependencyFailure,
  runFactoryOperation,
} from "../../../agent-factory/src/index.js";
import {
  fingerprintFactoryResource,
  hashAgentSpec,
  parseAgentCreationRequest,
  parseStoredFactoryConfiguration,
  prepareFactoryCatalogue,
  renderCorePrompt,
} from "../../../agent-factory/src/index.js";
import { factoryIssue } from "../../../agent-factory/src/index.js";
import type { PluginStore, SkillActor } from "../plugins/store.js";
import {
  AgentNotFoundError,
  AgentNotManageableError,
  type AgentProfileStore,
  ConstructionConflictError,
  ConstructionDeletedError,
  ProtectedAgentError,
  type StoredConstruction,
} from "./profile-store.js";
import type { AgentActor, AgentProfile } from "./profile-types.js";

type FactoryPluginReader = Pick<
  PluginStore,
  "factoryCatalogue" | "factoryResourceFacts"
>;
type FactoryProfileStore = Pick<
  AgentProfileStore,
  "createConstructed" | "readConstruction" | "setConstructionReadiness"
>;

/** The authenticated actor. Email is used only for the existing audit payload convention. */
export type FactoryActor = AgentActor & { readonly email?: string | null };

export interface FactoryArtifact {
  readonly agent: AgentProfile;
  readonly spec: AgentSpec;
  readonly verification: VerificationResult;
  readonly readiness: FactoryReadiness;
}

export type FactoryUseCaseResult =
  | {
      readonly ok: true;
      readonly outcome: "created" | "replayed" | "read" | "rechecked";
      readonly constructionId: string;
      readonly artifact: FactoryArtifact;
    }
  | {
      readonly ok: false;
      readonly constructionId: string | null;
      readonly issues: readonly FactoryIssue[];
    };

export type AgentFactoryService = ReturnType<typeof createAgentFactoryService>;

/** The outer construction deadline; each model call is separately capped at 20 seconds in core. */
const FACTORY_DEADLINE_MS = 90_000;

const sha256 = (value: string) =>
  createHash("sha256").update(value, "utf8").digest("hex");

/** Server-derived; the unambiguous serialized pair keeps actors' keys from colliding. */
export function factoryConstructionId(actorId: string, idempotencyKey: string) {
  return `agent_factory_${sha256(JSON.stringify([actorId, idempotencyKey]))}`;
}

function factoryRequestHash(request: AgentCreationRequest) {
  return sha256(
    JSON.stringify([request.name, request.role, request.description]),
  );
}

const deadlineIssue = () =>
  factoryIssue(
    "DEADLINE_EXCEEDED",
    "",
    "dependency",
    "Construction deadline exceeded.",
  );

/**
 * Integrity of a persisted artifact: strict spec, hash and the compiler-owned prompt projection.
 * Anything else is refused rather than repaired or trusted. The same pure check guards runtime
 * normalization, so inspection and execution can never disagree about what is intact.
 */
export function readStoredArtifact(
  construction: Pick<StoredConstruction, "type" | "configuration">,
): FactoryResult<FactoryConfiguration & { readonly systemPrompt: string }> {
  return construction.type === "built_in"
    ? parseStoredFactoryConfiguration(construction.configuration)
    : {
        ok: false,
        issues: [
          factoryIssue(
            "ARTIFACT_INVALID",
            "",
            "compiler",
            "Stored generated artifact failed integrity checks.",
          ),
        ],
      };
}

/**
 * The model and limits of the construction completer, kept beside the service so the composition
 * root and the tests name the same values.
 *
 * `FACTORY_MODEL` names a stronger model for construction than the one generated coworkers answer
 * on, reached with the runtime's own provider, key and endpoint; unset, construction uses the
 * runtime model. The output budget is sent on every provider: a gateway that reserves the model's
 * maximum for an unlimited request refuses it on a low balance, which reads as an outage here.
 */
export function factoryCompletionOptions<M extends { defaultModel: string }>(
  runtimeModel: M,
  environment: Record<string, string | undefined> = process.env,
) {
  const model = environment.FACTORY_MODEL?.trim();
  return {
    model: model ? { ...runtimeModel, defaultModel: model } : runtimeModel,
    timeoutMs: 20_000,
    outputTokenBudget: 4096,
  };
}

/** Why a generated agent may not run on this load; shown to the person instead of a transport error. */
export type FactoryRuntimeVerdict =
  | { readonly ready: true }
  | { readonly ready: false; readonly reason: string };

/**
 * The runtime gate for generated rows, injected into the common agent loader.
 *
 * Deterministic and read-only: no model call, no grant write and no fingerprint update. The stored
 * creator's facts decide, never the requesting actor's accounts; the requester's administrator role
 * counts only when the requester is that creator. A persisted pending state stays pending until an
 * explicit recheck; a changed resource needs reconstruction, not a recheck. `PluginStore.callTool`
 * remains the final authority at call time.
 */
export function createFactoryRuntimeReadiness(
  store: FactoryPluginReader,
  control: FactoryReadOptions = {},
) {
  return async (
    actor: AgentActor,
    row: { id: string; ownerUserId: string | null; configuration: unknown },
  ): Promise<FactoryRuntimeVerdict> => {
    const blocked = (reason: string): FactoryRuntimeVerdict => ({
      ready: false,
      reason,
    });
    const stored = parseStoredFactoryConfiguration(row.configuration);
    if (!stored.ok)
      return blocked(
        "This generated coworker failed its integrity check and cannot run. Recreate it.",
      );
    if (stored.value.state !== "ready")
      return blocked(
        "This generated coworker is waiting for its required resources. Grant or connect them, then recheck it.",
      );
    if (!row.ownerUserId)
      return blocked(
        "The creator of this generated coworker is no longer available, so it cannot run.",
      );
    const readiness = await assessFactoryReadiness(
      store,
      {
        id: row.ownerUserId,
        isAdmin: row.ownerUserId === actor.id && actor.role === "admin",
      },
      row.id,
      stored.value.spec,
      control,
    );
    if (!readiness.ok)
      return blocked(
        "The resources of this generated coworker could not be checked, so it will not run now.",
      );
    if (readiness.value.state === "ready") return { ready: true };
    const codes = new Set(readiness.value.blockers.map(({ code }) => code));
    return blocked(
      codes.has("RESOURCE_CHANGED") || codes.has("RESOURCE_MISSING")
        ? "A resource this generated coworker was built on has changed or been removed. Recreate it."
        : `This generated coworker is missing a required resource (${[...codes].join(", ")}). Grant or connect it, then recheck it.`,
    );
  };
}

/**
 * Construction plus the Step 4 use cases: idempotent persisted creation, owner/admin inspection and
 * readiness recheck. No grant writes anywhere; recheck never calls the model.
 */
export function createAgentFactoryService(
  deps: {
    store: FactoryPluginReader;
    /** Required for create/read/recheck; construction alone needs no persistence. */
    profiles?: FactoryProfileStore;
    auditStore?: AuditStore;
  } & Pick<FactoryConstructionOptions, "now" | "observe"> &
    (
      | { constructSpec: ReturnType<typeof createFactoryClient> }
      | Omit<FactoryConstructionOptions, "signal" | "timeoutMs">
    ),
) {
  const now = deps.now ?? (() => performance.now());

  async function construct(
    actor: SkillActor,
    request: AgentCreationRequest,
    control: FactoryReadOptions = {},
    observe = deps.observe,
  ) {
    const started = now();
    const timeoutMs = Math.max(
      1,
      Math.floor(
        Math.min(control.timeoutMs ?? FACTORY_DEADLINE_MS, FACTORY_DEADLINE_MS),
      ),
    );
    const deadline = AbortSignal.timeout(timeoutMs);
    const keepDeadline = () => {};
    deadline.addEventListener("abort", keepDeadline);
    const signal = control.signal
      ? AbortSignal.any([control.signal, deadline])
      : deadline;
    try {
      const snapshot = await runFactoryOperation(
        () => readFactoryCatalogue(deps.store, actor, { signal, timeoutMs }),
        signal,
      );
      if (!snapshot.ok) return snapshot;
      signal.throwIfAborted();
      const remaining = timeoutMs - (now() - started);
      if (remaining <= 0)
        return {
          ok: false as const,
          issues: [
            factoryIssue(
              "DEADLINE_EXCEEDED",
              "",
              "dependency",
              "Construction deadline exceeded during catalogue read.",
            ),
          ],
        };
      if ("constructSpec" in deps)
        return await runFactoryOperation(
          () =>
            deps.constructSpec(request, snapshot.value, {
              signal,
              timeoutMs: remaining,
            }),
          signal,
        );
      // Explicit local injection is retained for offline tests and the quality evaluator.
      return await constructAgentSpec(request, snapshot.value, {
        complete: deps.complete,
        modelRef: deps.modelRef,
        ...(deps.now ? { now: deps.now } : {}),
        ...(observe ? { observe } : {}),
        signal,
        timeoutMs: remaining,
      });
    } catch (error) {
      return factoryDependencyFailure(error, signal);
    } finally {
      deadline.removeEventListener("abort", keepDeadline);
    }
  }

  function bounds(control: FactoryReadOptions) {
    const started = now();
    const timeoutMs = Math.max(
      1,
      Math.floor(
        Math.min(control.timeoutMs ?? FACTORY_DEADLINE_MS, FACTORY_DEADLINE_MS),
      ),
    );
    const deadline = AbortSignal.timeout(timeoutMs);
    // Keep the outer deadline alive across reads, model calls and readiness on Bun 1.3.14.
    const keepDeadline = () => {};
    deadline.addEventListener("abort", keepDeadline);
    const signal = control.signal
      ? AbortSignal.any([control.signal, deadline])
      : deadline;
    const remaining = () => Math.max(1, timeoutMs - (now() - started));
    const expired = () =>
      deadline.aborted || timeoutMs - (now() - started) <= 0;
    const dispose = () => deadline.removeEventListener("abort", keepDeadline);
    return { signal, remaining, expired, dispose };
  }
  type Bounds = ReturnType<typeof bounds>;

  const failure = (
    constructionId: string | null,
    issues: readonly FactoryIssue[],
  ): FactoryUseCaseResult => ({ ok: false, constructionId, issues });

  const dependencyFailure = (
    constructionId: string | null,
    error: unknown,
    bound: Bounds,
  ) => {
    if (bound.expired()) return failure(constructionId, [deadlineIssue()]);
    const cancelled = factoryDependencyFailure(error, bound.signal);
    return failure(
      constructionId,
      bound.signal.aborted && !cancelled.ok
        ? cancelled.issues
        : [
            factoryIssue(
              "STORAGE_FAILURE",
              "",
              "dependency",
              "Construction storage is unavailable.",
            ),
          ],
    );
  };

  function requireProfiles(): FactoryProfileStore {
    if (!deps.profiles)
      throw new Error("Agent factory persistence is not configured.");
    return deps.profiles;
  }

  /** The stored creator's facts; an administrator's own accounts never stand in for the owner's. */
  async function readinessFor(
    actor: FactoryActor,
    construction: StoredConstruction,
    spec: AgentSpec,
    bound: Bounds,
  ): Promise<FactoryResult<FactoryReadiness>> {
    const owner = construction.profile.ownerUserId;
    if (!owner)
      return {
        ok: true,
        value: {
          state: "pending_resources",
          blockers: [
            {
              code: "OWNER_UNAVAILABLE",
              path: "",
              sourceStage: "access",
              evidenceRefs: [],
              message: "The creator of this agent is no longer available.",
            },
          ],
        },
      };
    return runFactoryOperation(
      () =>
        assessFactoryReadiness(
          deps.store,
          { id: owner, isAdmin: owner === actor.id && actor.role === "admin" },
          construction.profile.id,
          spec,
          { signal: bound.signal, timeoutMs: bound.remaining() },
        ),
      bound.signal,
    );
  }

  async function audit(
    actor: FactoryActor,
    eventType: "configuration.changed" | "bot.created",
    targetType: string,
    targetId: string,
    payload: Record<string, unknown>,
  ) {
    if (!deps.auditStore) return;
    try {
      await recordAuditEvent(deps.auditStore, {
        eventType,
        targetType,
        targetId,
        ...(actor.email !== DEV_ACTOR.email ? { actorUserId: actor.id } : {}),
        payload,
      });
    } catch (error) {
      console.error(
        JSON.stringify({
          type: "agent-factory-audit-write-failed",
          eventType,
          targetId,
          error: String(error),
        }),
      );
    }
  }

  /** Metadata only: no request text, completions, drafts, prompts or secrets. */
  async function auditConstruction(
    actor: FactoryActor,
    constructionId: string,
    observations: readonly FactoryObservation[],
    result: FactoryUseCaseResult,
  ) {
    for (const { stage, attempt, durationMs, status } of observations)
      await audit(
        actor,
        "configuration.changed",
        "agent_construction",
        constructionId,
        {
          constructionId,
          stage,
          attempt,
          durationMs: Math.round(durationMs),
          status,
        },
      );
    await audit(
      actor,
      "configuration.changed",
      "agent_construction",
      constructionId,
      {
        constructionId,
        stage: "outcome",
        outcome: result.ok ? result.outcome : "failed",
        ...(result.ok
          ? {
              state: result.artifact.readiness.state,
              specHash: result.artifact.verification.specHash,
              attempts: result.artifact.verification.attempts,
              resources: result.artifact.spec.resources.map(
                ({ kind, ref, fingerprint }) => ({ kind, ref, fingerprint }),
              ),
            }
          : {
              issueCodes: result.issues.map(({ code }) => code),
              issuePaths: result.issues.map(({ path }) => path),
            }),
      },
    );
    if (result.ok && result.outcome === "created")
      await audit(actor, "bot.created", "agent", constructionId, {
        bot: constructionId,
        actor: actor.email ?? "unknown",
        name: result.artifact.agent.name,
        visibility: "private",
        generated: true,
      });
  }

  async function replay(
    actor: FactoryActor,
    construction: StoredConstruction,
    requestHash: string,
    bound: Bounds,
  ): Promise<FactoryUseCaseResult> {
    const id = construction.profile.id;
    if (construction.profile.deletedAt)
      return failure(id, [
        factoryIssue(
          "CONSTRUCTION_DELETED",
          "",
          "request",
          "The agent created with this idempotency key was deleted.",
        ),
      ]);
    const stored = readStoredArtifact(construction);
    if (!stored.ok) return failure(id, stored.issues);
    if (stored.value.requestHash !== requestHash)
      return failure(id, [conflictIssue()]);
    const readiness = await readinessFor(
      actor,
      construction,
      stored.value.spec,
      bound,
    );
    if (!readiness.ok)
      return failure(
        id,
        bound.expired() ? [deadlineIssue()] : readiness.issues,
      );
    return {
      ok: true,
      outcome: "replayed",
      constructionId: id,
      artifact: {
        agent: construction.profile,
        spec: stored.value.spec,
        verification: stored.value.verification,
        readiness: readiness.value,
      },
    };
  }

  const conflictIssue = () =>
    factoryIssue(
      "IDEMPOTENCY_CONFLICT",
      "",
      "request",
      "This idempotency key was already used for a different request.",
    );
  const notFoundIssue = () =>
    factoryIssue("NOT_FOUND", "", "access", "Generated agent not found.");

  /** Owner/admin read plus integrity; shared by inspection and recheck. */
  async function stored(actor: FactoryActor, id: string, bound: Bounds) {
    const construction = await runFactoryOperation(
      () => requireProfiles().readConstruction(actor, id),
      bound.signal,
    );
    if (!construction) return failure(id, [notFoundIssue()]);
    const artifact = readStoredArtifact(construction);
    return artifact.ok
      ? { construction, artifact: artifact.value }
      : failure(id, artifact.issues);
  }

  return {
    construct(
      actor: SkillActor,
      request: AgentCreationRequest,
      control: FactoryReadOptions = {},
    ) {
      return construct(actor, request, control);
    },

    async create(
      actor: FactoryActor,
      input: unknown,
      idempotencyKey: string,
      control: FactoryReadOptions = {},
    ): Promise<FactoryUseCaseResult> {
      const parsed = parseAgentCreationRequest(input);
      if (!parsed.ok) return failure(null, parsed.issues);
      const profiles = requireProfiles();
      const request = parsed.value;
      const creationKeyHash = sha256(
        JSON.stringify([actor.id, idempotencyKey]),
      );
      const id = `agent_factory_${creationKeyHash}`;
      const requestHash = factoryRequestHash(request);
      const bound = bounds(control);
      const skillActor = { id: actor.id, isAdmin: actor.role === "admin" };
      const observations: FactoryObservation[] = [];
      const result = await (async (): Promise<FactoryUseCaseResult> => {
        try {
          // Before any model work: an identical retry replays, a changed body conflicts.
          const existing = await runFactoryOperation(
            () =>
              profiles.readConstruction(actor, id, { includeDeleted: true }),
            bound.signal,
          );
          if (existing)
            return await replay(actor, existing, requestHash, bound);
          const constructed = await construct(
            skillActor,
            request,
            { signal: bound.signal, timeoutMs: bound.remaining() },
            (event) => {
              observations.push(event);
              deps.observe?.(event);
            },
          );
          if (!constructed.ok)
            return failure(
              id,
              bound.expired() ? [deadlineIssue()] : constructed.issues,
            );
          const { spec, systemPrompt, specHash, verification } =
            constructed.value;
          if (
            specHash !== hashAgentSpec(spec) ||
            verification.specHash !== specHash ||
            systemPrompt !== renderCorePrompt(spec)
          )
            return failure(id, [
              factoryIssue(
                "ARTIFACT_INVALID",
                "",
                "compiler",
                "Artifact hash or prompt changed before save.",
              ),
            ]);
          // Revalidates resource identity/fingerprints immediately before save. A new id has no
          // grants, so any bound resource makes this a pending artifact; nothing is granted here.
          const readiness = await runFactoryOperation(
            () =>
              assessFactoryReadiness(deps.store, skillActor, id, spec, {
                signal: bound.signal,
                timeoutMs: bound.remaining(),
              }),
            bound.signal,
          );
          if (!readiness.ok)
            return failure(
              id,
              bound.expired() ? [deadlineIssue()] : readiness.issues,
            );
          const stale = readiness.value.blockers.filter(
            ({ code }) =>
              code === "RESOURCE_MISSING" || code === "RESOURCE_CHANGED",
          );
          if (stale.length) return failure(id, stale);
          if (bound.expired()) return failure(id, [deadlineIssue()]);
          bound.signal.throwIfAborted();
          // Deliberately not raced against the deadline. The transaction bounds itself and checks
          // cancellation before commit, so a timeout is only ever reported for a rollback: no late
          // save can follow a 504.
          const saved = await profiles.createConstructed(
            actor,
            {
              id,
              name: request.name,
              title: request.role,
              roleDescription: request.description,
              systemPrompt,
              factory: {
                spec,
                verification,
                state: readiness.value.state,
                requestHash,
                creationKeyHash,
              },
            },
            { signal: bound.signal, timeoutMs: bound.remaining() },
          );
          if (!saved.created)
            return await replay(actor, saved.construction, requestHash, bound);
          return {
            ok: true,
            outcome: "created",
            constructionId: id,
            artifact: {
              agent: saved.construction.profile,
              spec,
              verification,
              readiness: readiness.value,
            },
          };
        } catch (error) {
          if (error instanceof ConstructionConflictError)
            return failure(id, [conflictIssue()]);
          if (error instanceof ConstructionDeletedError)
            return failure(id, [
              factoryIssue(
                "CONSTRUCTION_DELETED",
                "",
                "request",
                "The agent created with this idempotency key was deleted.",
              ),
            ]);
          return dependencyFailure(id, error, bound);
        } finally {
          bound.dispose();
        }
      })();
      await auditConstruction(actor, id, observations, result);
      return result;
    },

    /** Canonical artifact and fresh readiness for the owner or an administrator. */
    async read(
      actor: FactoryActor,
      id: string,
      control: FactoryReadOptions = {},
    ): Promise<FactoryUseCaseResult> {
      const bound = bounds(control);
      try {
        const found = await stored(actor, id, bound);
        if ("ok" in found) return found;
        const readiness = await readinessFor(
          actor,
          found.construction,
          found.artifact.spec,
          bound,
        );
        if (!readiness.ok)
          return failure(
            id,
            bound.expired() ? [deadlineIssue()] : readiness.issues,
          );
        return {
          ok: true,
          outcome: "read",
          constructionId: id,
          artifact: {
            agent: found.construction.profile,
            spec: found.artifact.spec,
            verification: found.artifact.verification,
            readiness: readiness.value,
          },
        };
      } catch (error) {
        return dependencyFailure(id, error, bound);
      } finally {
        bound.dispose();
      }
    },

    /**
     * Re-read the stored creator's grant/configuration/connection facts for the exact stored
     * artifact. No LLM call, no regeneration and no grant write; only the persisted state changes.
     */
    async recheck(
      actor: FactoryActor,
      id: string,
      specHash: string,
      control: FactoryReadOptions = {},
    ): Promise<FactoryUseCaseResult> {
      const bound = bounds(control);
      const changed = () =>
        failure(id, [
          factoryIssue(
            "SPEC_CHANGED",
            "",
            "request",
            "The stored artifact no longer matches the expected specHash.",
          ),
        ]);
      try {
        const found = await stored(actor, id, bound);
        if ("ok" in found) return found;
        if (found.artifact.verification.specHash !== specHash) return changed();
        const readiness = await readinessFor(
          actor,
          found.construction,
          found.artifact.spec,
          bound,
        );
        if (!readiness.ok)
          return failure(
            id,
            bound.expired() ? [deadlineIssue()] : readiness.issues,
          );
        if (
          !(await requireProfiles().setConstructionReadiness(
            actor,
            id,
            specHash,
            readiness.value.state,
          ))
        )
          return changed();
        await audit(actor, "configuration.changed", "agent_construction", id, {
          constructionId: id,
          stage: "recheck",
          state: readiness.value.state,
          specHash,
          blockerCodes: readiness.value.blockers.map(({ code }) => code),
        });
        return {
          ok: true,
          outcome: "rechecked",
          constructionId: id,
          artifact: {
            agent: {
              ...found.construction.profile,
              generated: { state: readiness.value.state, specHash },
            },
            spec: found.artifact.spec,
            verification: found.artifact.verification,
            readiness: readiness.value,
          },
        };
      } catch (error) {
        if (error instanceof AgentNotFoundError)
          return failure(id, [notFoundIssue()]);
        if (
          error instanceof AgentNotManageableError ||
          error instanceof ProtectedAgentError
        )
          return failure(id, [
            factoryIssue(
              "FORBIDDEN",
              "",
              "access",
              "You do not have permission to manage this agent.",
            ),
          ]);
        return dependencyFailure(id, error, bound);
      } finally {
        bound.dispose();
      }
    },
  };
}

export async function readFactoryCatalogue(
  store: FactoryPluginReader,
  actor: SkillActor,
  control: FactoryReadOptions = {},
): Promise<FactoryResult<FactoryCatalogue>> {
  const result = await store.factoryCatalogue(actor, control);
  return result.ok ? prepareFactoryCatalogue(result.value) : result;
}

/** Required bindings are scope; only separate grant/configuration/connection facts establish readiness. */
export async function assessFactoryReadiness(
  store: FactoryPluginReader,
  owner: SkillActor,
  agentId: string,
  spec: AgentSpec,
  control: FactoryReadOptions = {},
): Promise<FactoryResult<FactoryReadiness>> {
  const result = await store.factoryResourceFacts(
    owner.id,
    agentId,
    spec.resources.map(({ kind, ref }) => ({ kind, ref })),
    control,
    owner.isAdmin,
  );
  if (!result.ok) return result;
  const blockers: FactoryIssue[] = [];
  const block = (code: string, index: number, ref: string, message: string) =>
    blockers.push({
      code,
      path: `resources.${index}`,
      sourceStage: "access",
      evidenceRefs: [ref],
      message,
    });
  spec.resources.forEach((resource, index) => {
    const fact = result.value.find(
      (fact) => fact.kind === resource.kind && fact.ref === resource.ref,
    );
    if (!fact?.resource) {
      block(
        "RESOURCE_MISSING",
        index,
        resource.ref,
        "Required resource is unavailable.",
      );
      return;
    }
    if (fingerprintFactoryResource(fact.resource) !== resource.fingerprint)
      block(
        "RESOURCE_CHANGED",
        index,
        resource.ref,
        "Required resource evidence has changed.",
      );
    if (!fact.granted)
      block(
        "GRANT_REQUIRED",
        index,
        resource.ref,
        "Required resource has not been granted to this agent.",
      );
    if (!fact.configured)
      block(
        "CONFIGURATION_REQUIRED",
        index,
        resource.ref,
        "Required resource is not configured.",
      );
    if (!fact.connected)
      block(
        "CONNECTION_REQUIRED",
        index,
        resource.ref,
        "The creator has not connected this resource.",
      );
  });
  return {
    ok: true,
    value: { state: blockers.length ? "pending_resources" : "ready", blockers },
  };
}
