import { createHash, timingSafeEqual } from "node:crypto";
import { z } from "zod";
import type { FactoryIssue } from "./contracts.js";
import { readBoundedText } from "./io.js";
import { createHttpCompleter } from "./model.js";
import {
  constructAgentSpec,
  type FactoryConstructionOptions,
} from "./service.js";
import { parseAgentCreationRequest, prepareFactoryCatalogue, parseFactoryConstructionResponse } from "./spec.js";

export const MAX_REQUEST_BYTES = 128 * 1024;
const bodySchema = z.strictObject({
  request: z.unknown(),
  catalogue: z.unknown(),
  model_config: z.object({ model_name: z.string().min(1), api_key: z.string().min(1), base_url: z.url(), provider: z.string() }).optional(),
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
  options: FactoryConstructionOptions & { token: string; reasoningEffort?: 'none' | 'low' | 'medium' | 'high' | 'xhigh'; maxCompletionTokens?: number },
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
    if (path !== "/v1/constructions" && path !== "/v1/verify")
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
    if (path === "/v1/verify") {
      const verifiedBody = z.strictObject({ request: z.unknown(), catalogue: z.unknown(), artifact: z.unknown() }).safeParse(value);
      if (!verifiedBody.success) return failure(400, "INVALID_BODY", "Request, catalogue and artifact are required.");
      const input = parseAgentCreationRequest(verifiedBody.data.request);
      const catalogue = prepareFactoryCatalogue(verifiedBody.data.catalogue);
      if (!input.ok || !catalogue.ok) return failure(422, "INVALID_INPUT", "Invalid request or catalogue.");
      const parsed = parseFactoryConstructionResponse(verifiedBody.data.artifact, input.value, catalogue.value);
      return parsed.ok ? Response.json(parsed.value) : failure(422, "INVALID_ARTIFACT", "Artifact integrity check failed.", parsed.issues);
    }
    const body = bodySchema.safeParse(value);
    if (!body.success)
      return failure(
        400,
        "INVALID_BODY",
        "Send request and catalogue with optional service-owned model configuration.",
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
      const chosen = body.data.model_config;
      const complete = chosen ? createHttpCompleter({
        model: chosen.model_name, apiKey: chosen.api_key,
        url: chosen.base_url.replace(/\/$/, "") + "/chat/completions",
        provider: chosen.provider === "openai" ? "openai" : "openai-compatible",
        maxCompletionTokens: options.maxCompletionTokens ?? 8192,
        ...(chosen.model_name === 'gpt-6-luna' ? {reasoningEffort: 'none' as const} : options.reasoningEffort ? {reasoningEffort: options.reasoningEffort} : {}),
      }) : options.complete;
      const result = await constructAgentSpec(input.value, catalogue.value, {
        ...options,
        complete,
        ...(chosen ? { modelRef: `${chosen.provider}/${chosen.model_name}` } : {}),
        signal: request.signal,
      });
      if (result.ok) return Response.json(result.value);
      console.warn(JSON.stringify({event: 'factory.refused', issues: result.issues.map(i => ({code: i.code, path: i.path, message: i.message, sourceStage: i.sourceStage}))}));
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
