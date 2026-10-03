import { randomUUID } from "node:crypto";
import { Hono } from "hono";
import type { Context } from "hono";
import type { CallVerdict, RunAssertion } from "../agents/callback-token";
import { describeTechnicalTools, findTechnicalTool } from "../technical-tools";
import type { ResponseEnvelope, ToolStatus } from "../technical-tools";
import type { TechnicalTool } from "../technical-tools/tool";

export type VerifiedTechnicalCaller = Extract<CallVerdict, { ok: true }> & {
  assertion: RunAssertion;
};
export type TechnicalApiDependencies = {
  authorise(c: Context): Promise<VerifiedTechnicalCaller | null>;
  call(
    caller: VerifiedTechnicalCaller,
    tool: TechnicalTool,
    args: Record<string, unknown>,
  ): Promise<ResponseEnvelope>;
  refusal(status: ToolStatus, endpoint: string): Promise<void>;
};

export function technicalEnvelope(
  status: ToolStatus,
  message: string,
): ResponseEnvelope {
  return {
    status,
    trace_id: randomUUID(),
    server_time: new Date().toISOString(),
    data: null,
    errors: [
      {
        code: status === "OK" ? "INTERNAL_ERROR" : status,
        message,
        retryable: false,
      },
    ],
    missing_fields: [],
    provenance: [],
  };
}

export function httpStatusOf(status: ToolStatus, create = false) {
  switch (status) {
    case "OK":
      return create ? 201 : 200;
    case "STALE_DATA":
    case "NEEDS_INPUT":
      return 200;
    case "PENDING_APPROVAL":
      return 202;
    case "INVALID_INPUT":
      return 400;
    case "FORBIDDEN":
      return 403;
    case "NOT_FOUND":
      return 404;
    case "CONFLICT":
      return 409;
    case "INTERNAL_ERROR":
      return 500;
  }
}

const endpoints = [
  [
    "GET",
    "/buildings/:building_id/outages/active",
    "technical.get_active_outage",
  ],
  ["GET", "/buildings/:building_id/utility-schedules", "utility_schedule.read"],
  ["GET", "/buildings/:building_id/sops", "sop_kb.retrieve"],
  ["GET", "/buildings/:building_id/assets", "asset.read"],
  ["GET", "/buildings/:building_id/sensor-readings", "sensor.read"],
  [
    "GET",
    "/buildings/:building_id/assets/:asset_id/maintenance-history",
    "maintenance_history.read",
  ],
  [
    "POST",
    "/buildings/:building_id/work-orders/:workorder_id/measurements",
    "technical.record_measurement",
  ],
  [
    "POST",
    "/buildings/:building_id/work-orders/:workorder_id/executor-results",
    "technical.submit_executor_result",
  ],
  [
    "POST",
    "/buildings/:building_id/work-orders/:workorder_id/executor-results/:result_id/verification",
    "technical.verify_resolution",
  ],
  [
    "POST",
    "/buildings/:building_id/assets/:asset_id/maintenance-events",
    "maintenance_history.append",
  ],
  [
    "POST",
    "/buildings/:building_id/utility-isolation-requests",
    "utility_isolation.request",
  ],
  [
    "POST",
    "/buildings/:building_id/area-restriction-requests",
    "area_restriction.request",
  ],
  [
    "POST",
    "/buildings/:building_id/apartment-entry-requests",
    "apartment_entry.request",
  ],
  [
    "POST",
    "/buildings/:building_id/vendor-dispatch-requests",
    "vendor_dispatch.request",
  ],
] as const;

/** HTTP transport only; the existing host validates the business contract. */
export function createTechnicalApiRoutes(deps: TechnicalApiDependencies) {
  const app = new Hono<{ Variables: { caller: VerifiedTechnicalCaller } }>();
  app.onError(async (_error, c) => {
    try {
      await deps.refusal("INTERNAL_ERROR", c.req.path);
    } catch {
      /* no successful result */
    }
    return c.json(
      technicalEnvelope(
        "INTERNAL_ERROR",
        "The request could not be completed.",
      ),
      500,
    );
  });
  app.use("*", async (c, next) => {
    c.header("Cache-Control", "no-store");
    const caller = await deps.authorise(c);
    if (!caller) {
      await deps.refusal("FORBIDDEN", c.req.path);
      return c.json(
        technicalEnvelope(
          "FORBIDDEN",
          "This call is not permitted for the current identity and scope.",
        ),
        403,
      );
    }
    c.set("caller", caller);
    await next();
  });
  app.get("/tools", (c) => c.json({ tools: describeTechnicalTools() }));
  for (const [method, path, name] of endpoints) {
    app.on(method, path, async (c) => {
      let args: Record<string, unknown>;
      if (method === "POST") {
        if (
          !/^application\/json(?:;|$)/i.test(c.req.header("content-type") ?? "")
        ) {
          await deps.refusal("INVALID_INPUT", c.req.path);
          return c.json(
            technicalEnvelope(
              "INVALID_INPUT",
              "Content-Type must be application/json.",
            ),
            400,
          );
        }
        const reader = c.req.raw.body?.getReader();
        const chunks: Uint8Array[] = [];
        let size = 0;
        if (reader) {
          try {
            for (;;) {
              const chunk = await reader.read();
              if (chunk.done) break;
              size += chunk.value.byteLength;
              if (size > 128 * 1024) {
                await reader.cancel();
                break;
              }
              chunks.push(chunk.value);
            }
          } finally {
            reader.releaseLock();
          }
        }
        if (size > 128 * 1024) {
          await deps.refusal("INVALID_INPUT", c.req.path);
          return c.json(
            technicalEnvelope("INVALID_INPUT", "Request body exceeds 128 KiB."),
            400,
          );
        }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) {
          bytes.set(chunk, offset);
          offset += chunk.length;
        }
        let value: unknown;
        try {
          value = JSON.parse(new TextDecoder().decode(bytes));
        } catch {
          value = null;
        }
        if (!value || typeof value !== "object" || Array.isArray(value)) {
          await deps.refusal("INVALID_INPUT", c.req.path);
          return c.json(
            technicalEnvelope("INVALID_INPUT", "A JSON object is required."),
            400,
          );
        }
        args = { ...value };
        if (
          Object.keys(c.req.queries()).length ||
          Object.keys(c.req.param()).some((key) => key in args) ||
          "idempotency_key" in args
        ) {
          await deps.refusal("INVALID_INPUT", c.req.path);
          return c.json(
            technicalEnvelope(
              "INVALID_INPUT",
              "Path and idempotency fields cannot be supplied in the body; POST query is not supported.",
            ),
            400,
          );
        }
        if (name !== "technical.verify_resolution")
          args.idempotency_key = c.req.header("Idempotency-Key");
      } else {
        const queries = c.req.queries();
        if (
          Object.values(queries).some((values) => values.length !== 1) ||
          Object.keys(c.req.param()).some((key) => key in queries)
        ) {
          await deps.refusal("INVALID_INPUT", c.req.path);
          return c.json(
            technicalEnvelope(
              "INVALID_INPUT",
              "Duplicate or conflicting query parameters.",
            ),
            400,
          );
        }
        args = c.req.query();
        if (
          [
            "utility_schedule.read",
            "sensor.read",
            "maintenance_history.read",
          ].includes(name)
        ) {
          args.time_range = { from: args.from, to: args.to };
          delete args.from;
          delete args.to;
        }
        for (const key of ["limit", "max_age_seconds"])
          if (key in args) args[key] = Number(args[key]);
      }
      Object.assign(args, c.req.param());
      const tool = findTechnicalTool(name);
      if (!tool) throw new Error("Technical tool is not registered");
      const result = await deps.call(
        c.get("caller") as VerifiedTechnicalCaller,
        tool,
        args,
      );
      return c.json(
        result,
        httpStatusOf(
          result.status,
          [
            "technical.record_measurement",
            "technical.submit_executor_result",
            "maintenance_history.append",
          ].includes(name),
        ),
      );
    });
  }
  app.notFound((c) =>
    c.json(technicalEnvelope("NOT_FOUND", "Endpoint not found."), 404),
  );
  return app;
}
