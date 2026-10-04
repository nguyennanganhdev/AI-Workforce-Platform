import { createHash, timingSafeEqual } from "node:crypto";
import { z } from "zod";
import type { FactoryIssue } from "./contracts.js";
import { readBoundedText } from "./io.js";
import {
  constructAgentSpec,
  type FactoryConstructionOptions,
} from "./service.js";
import { parseAgentCreationRequest, prepareFactoryCatalogue } from "./spec.js";

export const MAX_REQUEST_BYTES = 128 * 1024;
const bodySchema = z.strictObject({
  request: z.unknown(),
  catalogue: z.unknown(),
});
const digest = (value: string) => createHash("sha256").update(value).digest();

const failure = (
  status: number,
  code: string,
  error: string,
  issues: readonly FactoryIssue[] = [],
) =>
  Response.json({ error, code, issues, retryable: status >= 500 }, { status });

/** The bearer belongs to BE/service callers; the original user never supplies a catalogue. */
export function createFactoryHandler(
  options: FactoryConstructionOptions & { token: string },
) {
  if (options.token.length < 32)
    throw new Error(
      "FACTORY_SERVICE_TOKEN must contain at least 32 characters.",
    );
  const authorization = digest(`Bearer ${options.token}`);
  return async (request: Request): Promise<Response> => {
    const path = new URL(request.url).pathname;
    if (path === "/health" && request.method === "GET")
      return Response.json({ status: "ok", service: "agent-factory" });
    if (path !== "/v1/constructions")
      return failure(404, "NOT_FOUND", "Endpoint not found.");
    if (request.method !== "POST") {
      const response = failure(405, "METHOD_NOT_ALLOWED", "Use POST.");
      response.headers.set("Allow", "POST");
      return response;
    }
    if (
      !timingSafeEqual(
        authorization,
        digest(request.headers.get("authorization") ?? ""),
      )
    ) {
      const response = failure(
        401,
        "UNAUTHENTICATED",
        "Service authentication required.",
      );
      response.headers.set("WWW-Authenticate", "Bearer");
      return response;
    }
    if (
      request.headers.get("content-type")?.split(";")[0]?.trim() !==
      "application/json"
    )
      return failure(415, "UNSUPPORTED_MEDIA_TYPE", "Use application/json.");
    let value: unknown;
    try {
      value = JSON.parse(await readBoundedText(request, MAX_REQUEST_BYTES));
    } catch (error) {
      return error instanceof RangeError
        ? failure(413, "BODY_TOO_LARGE", "Construction request is too large.")
        : failure(400, "INVALID_BODY", "A valid JSON body is required.");
    }
    const body = bodySchema.safeParse(value);
    if (!body.success)
      return failure(
        400,
        "INVALID_BODY",
        "Send exactly request and catalogue.",
      );
    const input = parseAgentCreationRequest(body.data.request);
    if (!input.ok)
      return failure(
        400,
        "INVALID_REQUEST",
        "Invalid agent request.",
        input.issues,
      );
    const catalogue = prepareFactoryCatalogue(body.data.catalogue);
    if (!catalogue.ok)
      return failure(
        422,
        "INVALID_CATALOGUE",
        "Invalid construction catalogue.",
        catalogue.issues,
      );
    try {
      const result = await constructAgentSpec(input.value, catalogue.value, {
        ...options,
        signal: request.signal,
      });
      if (result.ok) return Response.json(result.value);
      const status = result.issues.some(
        ({ code }) => code === "DEADLINE_EXCEEDED",
      )
        ? 504
        : result.issues.some(({ sourceStage }) => sourceStage === "dependency")
          ? 503
          : 422;
      return failure(
        status,
        result.issues[0]?.code ?? "CONSTRUCTION_FAILED",
        "Agent construction failed.",
        result.issues,
      );
    } catch {
      return failure(500, "INTERNAL_ERROR", "Agent construction failed.");
    }
  };
}
