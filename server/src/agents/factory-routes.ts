import type { Context, MiddlewareHandler } from "hono";
import { Hono } from "hono";
import type {
  FactoryArtifactResponse,
  FactoryErrorResponse,
  FactoryIssue,
} from "../../../agent-factory/src/contracts.js";
import type { AppVariables } from "../auth/guards";
import type { AgentFactoryService, FactoryUseCaseResult } from "./factory";
import { agentDto } from "./routes";

/** Larger than any valid three-field body (see FACTORY_LIMITS), small enough to refuse early. */
const MAX_BODY_BYTES = 32 * 1024;
const MAX_KEY_LENGTH = 128;
const MAX_ID_LENGTH = 256;

/** Codes that are an HTTP answer of their own; everything else is decided by the issue's stage. */
const STATUS_BY_CODE: Readonly<Record<string, number>> = {
  DEADLINE_EXCEEDED: 504,
  UNAUTHENTICATED: 401,
  AUTHORIZATION_DENIED: 403,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONSTRUCTION_DELETED: 410,
  IDEMPOTENCY_CONFLICT: 409,
  SPEC_CHANGED: 409,
  RESOURCE_CHANGED: 409,
  RESOURCE_MISSING: 409,
  ARTIFACT_INVALID: 409,
  RESOURCES_PENDING: 409,
};
const MESSAGES: Readonly<Record<number, string>> = {
  400: "The construction request is invalid.",
  401: "Authentication required.",
  403: "You do not have permission to do that.",
  404: "Generated agent not found.",
  409: "The construction conflicts with its current state.",
  410: "The agent created with this idempotency key was deleted.",
  422: "An agent could not be constructed from this request.",
  503: "Construction is temporarily unavailable.",
  504: "Construction did not finish before its deadline.",
};

export function factoryStatusFor(issues: readonly FactoryIssue[]): number {
  const statuses = issues
    .map(({ code }) => STATUS_BY_CODE[code])
    .filter((status): status is number => status !== undefined);
  // The deadline outranks everything: whatever else went wrong, nothing was saved in time.
  if (statuses.includes(504)) return 504;
  if (statuses[0] !== undefined) return statuses[0];
  if (issues.some(({ sourceStage }) => sourceStage === "dependency"))
    return 503;
  if (
    issues.length &&
    issues.every(({ sourceStage }) => sourceStage === "request")
  )
    return 400;
  return 422;
}

/**
 * Three authenticated endpoints under `/api/agent-factory`. Parsing, actor and serialization only;
 * construction, persistence and readiness live in the shell service. Never returns provider or
 * database error text.
 */
export function createAgentFactoryRoutes(
  service: AgentFactoryService,
  requireUser: MiddlewareHandler<{ Variables: AppVariables }>,
) {
  const routes = new Hono<{ Variables: AppVariables }>();

  const errorResponse = (
    context: Context<{ Variables: AppVariables }>,
    constructionId: string | null,
    issues: readonly FactoryIssue[],
    status = factoryStatusFor(issues),
    code = issues[0]?.code ?? "INVALID_REQUEST",
  ) => {
    const body: FactoryErrorResponse = {
      error: MESSAGES[status] ?? "The construction failed.",
      code,
      constructionId,
      issues,
      // A pending recheck is answered by granting or connecting, not by resubmitting.
      retryable:
        status === 503 ||
        status === 504 ||
        (code !== "RESOURCES_PENDING" &&
          issues.some(
            ({ code }) =>
              code === "RESOURCE_CHANGED" || code === "RESOURCE_MISSING",
          )),
    };
    return context.json(body, status as 400);
  };
  const invalid = (
    context: Context<{ Variables: AppVariables }>,
    code: string,
    message: string,
  ) =>
    errorResponse(
      context,
      null,
      [{ code, path: "", sourceStage: "request", evidenceRefs: [], message }],
      400,
    );
  const artifactResponse = (
    context: Context<{ Variables: AppVariables }>,
    result: Extract<FactoryUseCaseResult, { ok: true }>,
    status: 200 | 201 | 202,
  ) => {
    const { agent, spec, verification, readiness } = result.artifact;
    const body: FactoryArtifactResponse<ReturnType<typeof agentDto>> = {
      // Generated agents always run in-process, whatever endpoint the deployment manages.
      agent: {
        ...agentDto(context.var.actor, agent),
        builtIn: true,
      } as ReturnType<typeof agentDto>,
      spec,
      verification,
      readiness,
    };
    return context.json(body, status);
  };
  const agentId = (context: Context<{ Variables: AppVariables }>) => {
    const id = context.req.param("agentId") ?? "";
    return id.trim() && id.length <= MAX_ID_LENGTH ? id : null;
  };
  const jsonBody = async (context: Context<{ Variables: AppVariables }>) => {
    const declared = Number(context.req.header("content-length") ?? 0);
    if (declared > MAX_BODY_BYTES) return { ok: false as const };
    const text = await context.req.text().catch(() => null);
    if (text === null || Buffer.byteLength(text, "utf8") > MAX_BODY_BYTES)
      return { ok: false as const };
    try {
      return { ok: true as const, value: JSON.parse(text) as unknown };
    } catch {
      return { ok: false as const };
    }
  };

  routes.post("/constructions", requireUser, async (context) => {
    const key = context.req.header("idempotency-key");
    // Opaque, bounded and printable; the server derives the agent id from it and the actor.
    if (!key || key.length > MAX_KEY_LENGTH || !/^[\x21-\x7e]+$/.test(key))
      return invalid(
        context,
        "IDEMPOTENCY_KEY_INVALID",
        "A printable Idempotency-Key of at most 128 characters is required.",
      );
    const body = await jsonBody(context);
    if (!body.ok)
      return invalid(
        context,
        "INVALID_BODY",
        "The body must be a small JSON object.",
      );
    const result = await service.create(context.var.actor, body.value, key, {
      signal: context.req.raw.signal,
    });
    if (!result.ok)
      return errorResponse(context, result.constructionId, result.issues);
    // Pending is persisted but not runnable, so it is never reported as a plain success.
    return artifactResponse(
      context,
      result,
      result.artifact.readiness.state === "ready" ? 201 : 202,
    );
  });

  routes.get("/:agentId", requireUser, async (context) => {
    const id = agentId(context);
    if (!id)
      return invalid(context, "INVALID_AGENT_ID", "An agent id is required.");
    const result = await service.read(context.var.actor, id, {
      signal: context.req.raw.signal,
    });
    return result.ok
      ? artifactResponse(context, result, 200)
      : errorResponse(context, result.constructionId, result.issues);
  });

  routes.post("/:agentId/recheck", requireUser, async (context) => {
    const id = agentId(context);
    if (!id)
      return invalid(context, "INVALID_AGENT_ID", "An agent id is required.");
    const body = await jsonBody(context);
    const value = body.ok ? body.value : null;
    // Exactly the expected hash: recheck never takes a spec, a grant or an owner from the client.
    if (
      !value ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      Object.keys(value).join() !== "specHash" ||
      typeof (value as { specHash?: unknown }).specHash !== "string" ||
      !/^[a-f0-9]{64}$/.test((value as { specHash: string }).specHash)
    )
      return invalid(
        context,
        "INVALID_BODY",
        "The body must be exactly {specHash}.",
      );
    const result = await service.recheck(
      context.var.actor,
      id,
      (value as { specHash: string }).specHash,
      { signal: context.req.raw.signal },
    );
    if (!result.ok)
      return errorResponse(context, result.constructionId, result.issues);
    if (result.artifact.readiness.state === "ready")
      return artifactResponse(context, result, 200);
    return errorResponse(
      context,
      result.constructionId,
      result.artifact.readiness.blockers,
      409,
      "RESOURCES_PENDING",
    );
  });

  return routes;
}
