import { timingSafeEqual } from "node:crypto";
import { Hono } from "hono";
import {
  cleaningNames,
  describeCleaningTools,
  findCleaningTool,
  type CleaningTool,
} from "../cleaning-tools";
import type { ResponseEnvelope } from "../technical-tools";
import { describeTechnicalTools, findTechnicalTool } from "../technical-tools";
import type { TechnicalTool } from "../technical-tools/tool";
import {
  httpStatusOf,
  technicalEnvelope,
  type VerifiedTechnicalCaller,
} from "./routes";

export type SessionToolDependencies = {
  /** The specialist turn this run is, or null when the business database no longer allows it. */
  sessionCaller(runId: string): Promise<VerifiedTechnicalCaller | null>;
  call(
    caller: VerifiedTechnicalCaller,
    tool: TechnicalTool | CleaningTool,
    args: Record<string, unknown>,
  ): Promise<ResponseEnvelope>;
};

/**
 * Team Hoàng's cleaning counterparts of the technical tools. Their five work-order entries are
 * not served here: they need a bridge to the business API that sessions do not have yet.
 */
const cleaningCounterparts = new Set(Object.values(cleaningNames));

function findSessionTool(name: string): TechnicalTool | CleaningTool | undefined {
  const cleaning = findCleaningTool(name);
  return (
    findTechnicalTool(name) ??
    (cleaning && cleaningCounterparts.has(cleaning.name) ? cleaning : undefined)
  );
}

export function sameToken(expected: string, offered: string): boolean {
  const a = Buffer.from(expected);
  const b = Buffer.from(offered);
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * The technical tools for a Supervisor session's specialists.
 *
 * The service token only proves the caller is the Coordination runtime. What a call may do is
 * decided from the agent run it names (see session.ts), and then by the tool host exactly as for
 * every other caller: capability, input shape, building inside the grant, audit.
 *
 * Tools that write or raise a request stay closed here until the runtime reconciles an unknown
 * outcome by the call's own id; a read can simply be asked again.
 */
export function createSessionToolRoutes(
  deps: SessionToolDependencies,
  serviceToken: string,
) {
  if (serviceToken.length < 32)
    throw new Error("The session tool service token needs 32+ characters");
  const app = new Hono();
  app.use("*", async (c, next) => {
    c.header("Cache-Control", "no-store");
    const offered = c.req.header("authorization") ?? "";
    if (
      !offered.startsWith("Bearer ") ||
      !sameToken(serviceToken, offered.slice(7))
    )
      return c.json(
        technicalEnvelope("FORBIDDEN", "Invalid service credential."),
        401,
      );
    await next();
  });
  app.get("/tools", (c) =>
    c.json({
      tools: [
        ...describeTechnicalTools(),
        ...describeCleaningTools().filter((tool) =>
          cleaningCounterparts.has(tool.name),
        ),
      ],
    }),
  );
  app.post("/call", async (c) => {
    let body: unknown;
    try {
      body = await c.req.json();
    } catch {
      body = null;
    }
    const request = body as {
      run_id?: unknown;
      tool?: unknown;
      arguments?: unknown;
    } | null;
    const args = request?.arguments;
    if (
      !request ||
      typeof request.run_id !== "string" ||
      typeof request.tool !== "string" ||
      !args ||
      typeof args !== "object" ||
      Array.isArray(args)
    )
      return c.json(
        technicalEnvelope(
          "INVALID_INPUT",
          "run_id, tool and an arguments object are required.",
        ),
        400,
      );
    const tool = findSessionTool(request.tool);
    if (!tool)
      return c.json(technicalEnvelope("NOT_FOUND", "No such tool."), 404);
    if (tool.effect !== "read")
      return c.json(
        technicalEnvelope(
          "FORBIDDEN",
          "Only read tools are open to a Supervisor session.",
        ),
        403,
      );
    const caller = await deps.sessionCaller(request.run_id);
    if (!caller)
      return c.json(
        technicalEnvelope(
          "FORBIDDEN",
          "This run is not a current specialist turn with a granted tool.",
        ),
        403,
      );
    const envelope = await deps.call(caller, tool, {
      ...(args as Record<string, unknown>),
    });
    return c.json(envelope, httpStatusOf(envelope.status));
  });
  return app;
}
