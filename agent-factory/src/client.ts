import { z } from "zod";
import type {
  AgentCreationRequest,
  FactoryCatalogue,
  FactoryConstructionResponse,
  FactoryReadOptions,
  FactoryResult,
} from "./contracts.js";
import { readBoundedText } from "./io.js";
import { factoryDependencyFailure, runFactoryOperation } from "./service.js";
import {
  FACTORY_LIMITS,
  parseAgentCreationRequest,
  parseFactoryConstructionResponse,
  storedIssueSchema,
} from "./spec.js";
import { factoryIssue } from "./verification.js";

const errorSchema = z.strictObject({
  error: z.string().max(FACTORY_LIMITS.text),
  code: z.string().max(FACTORY_LIMITS.text),
  issues: z
    .array(storedIssueSchema)
    .min(1)
    .max(FACTORY_LIMITS.items + 1),
  retryable: z.boolean(),
});

/** Deployment-owned URL/token only. No model credentials, redirects, retries or local fallback. */
export function createFactoryClient(
  config: { url: string; token: string },
  send: (url: string, options: RequestInit) => Promise<Response> = fetch,
) {
  let endpoint: string | undefined;
  try {
    const url = new URL(config.url);
    if (
      ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      config.token.length >= 32 &&
      !/\s/.test(config.token)
    )
      endpoint = `${url.href.replace(/\/$/, "")}/v1/constructions`;
  } catch {
    /* Invalid configuration disables construction, not the rest of BE. */
  }

  return async (
    request: AgentCreationRequest,
    catalogue: FactoryCatalogue,
    control: FactoryReadOptions = {},
  ): Promise<FactoryResult<FactoryConstructionResponse>> => {
    const timeout = AbortSignal.timeout(
      Math.max(1, Math.floor(Math.min(control.timeoutMs ?? 90_000, 90_000))),
    );
    const signal = control.signal
      ? AbortSignal.any([control.signal, timeout])
      : timeout;
    const keepDeadline = () => {};
    timeout.addEventListener("abort", keepDeadline);
    try {
      signal.throwIfAborted();
      if (!endpoint)
        throw new Error("Factory service configuration is unavailable.");
      const input = parseAgentCreationRequest(request);
      if (!input.ok) return input;
      return await runFactoryOperation(async () => {
        const response = await send(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${config.token}`,
          },
          body: JSON.stringify({
            request: input.value,
            catalogue: {
              tools: catalogue.tools.map(({ fingerprint: _, ...tool }) => tool),
              defaultToolRefs: catalogue.defaultToolRefs ?? [],
            },
          }),
          signal,
          redirect: "error",
        });
        // Auth/proxy/server failures may carry private diagnostics; never forward them.
        if (![200, 422, 503, 504].includes(response.status)) {
          await response.body?.cancel();
          throw new Error("Factory service unavailable.");
        }
        const body: unknown = JSON.parse(
          await readBoundedText(response, 1024 * 1024),
        );
        signal.throwIfAborted();
        if (response.status === 200)
          return parseFactoryConstructionResponse(body, input.value, catalogue);
        const failure = errorSchema.safeParse(body);
        if (!failure.success)
          throw new Error("Invalid Factory error response.");
        if (
          response.status === 422 &&
          failure.data.issues.every(
            ({ sourceStage }) => sourceStage !== "dependency",
          )
        )
          return { ok: false as const, issues: failure.data.issues };
        if (response.status === 504)
          throw new DOMException("Factory deadline exceeded.", "TimeoutError");
        throw new Error("Factory dependency unavailable.");
      }, signal);
    } catch (error) {
      if (signal.aborted) return factoryDependencyFailure(error, signal);
      return {
        ok: false,
        issues: [
          factoryIssue(
            error instanceof Error && error.name === "TimeoutError"
              ? "DEADLINE_EXCEEDED"
              : "MODEL_UNAVAILABLE",
            "",
            "dependency",
            "Factory service is unavailable or returned an invalid response.",
          ),
        ],
      };
    } finally {
      timeout.removeEventListener("abort", keepDeadline);
    }
  };
}
