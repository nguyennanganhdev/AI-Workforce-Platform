import type { RuntimeModel } from "../copilot";

export interface ModelCallObservation {
  readonly durationMs: number;
  readonly status: "success" | "http_error" | "error" | "timeout" | "cancelled";
  readonly httpStatus: number | null;
  readonly usage: {
    readonly inputTokens: number | null;
    readonly outputTokens: number | null;
    readonly totalTokens: number | null;
    readonly details: Readonly<
      Record<string, number | Readonly<Record<string, number>>>
    >;
  } | null;
}

/**
 * The one model call the router makes, kept apart from the routing logic so that logic stays a pure
 * function the tests drive without a network. This reuses the deployment's own model and key — the
 * same ones the built-in coworkers answer on — so a router is never a second thing to configure.
 *
 * It throws on a missing key or a bad response on purpose: the router treats a throw as "not sure"
 * and lands on the default, so failure here is a soft landing, not an error a person sees.
 */
export function createModelCompleter(deps: {
  model: RuntimeModel;
  resolveApiKey: () => Promise<string | null>;
  timeoutMs?: number;
  outputTokenBudget?: number;
  observe?: (event: ModelCallObservation) => void;
}): (prompt: string, signal?: AbortSignal) => Promise<string> {
  const timeoutMs = deps.timeoutMs ?? 10_000;
  const outputTokenBudget = deps.outputTokenBudget;
  if (
    !Number.isInteger(timeoutMs) ||
    timeoutMs < 1 ||
    timeoutMs > 90_000 ||
    (outputTokenBudget !== undefined &&
      (!Number.isInteger(outputTokenBudget) ||
        outputTokenBudget < 1 ||
        outputTokenBudget > 16_384))
  )
    throw new Error("invalid completion limits");
  return async (prompt: string, signal?: AbortSignal) => {
    const timeout = AbortSignal.timeout(timeoutMs);
    const activeSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
    // Keep one listener through key/fetch/body: Bun 1.3.14 cancels the timeout when
    // its last listener is removed, even if another stage subsequently adds one.
    let abort: () => void = () => {};
    const aborted = new Promise<never>((_, reject) => {
      abort = () => reject(activeSignal.reason);
      activeSignal.addEventListener("abort", abort, { once: true });
    });
    const bounded = async <T>(operation: () => Promise<T>): Promise<T> => {
      activeSignal.throwIfAborted();
      return Promise.race([
        aborted,
        Promise.resolve().then(() => {
          activeSignal.throwIfAborted();
          return operation();
        }),
      ]);
    };
    const anthropic = deps.model.provider === "anthropic";
    let started: number | null = null;
    let status: ModelCallObservation["status"] = "error";
    let httpStatus: number | null = null;
    let usage: ModelCallObservation["usage"] = null;
    try {
      const key = await bounded(deps.resolveApiKey);
      activeSignal.throwIfAborted();
      if (!key) throw new Error("no model key");
      started = performance.now();
      const response = await bounded(() =>
        fetch(
          anthropic
            ? anthropicMessagesUrl(process.env)
            : chatCompletionsUrl(process.env),
          {
            method: "POST",
            headers: {
              "content-type": "application/json",
              ...(anthropic
                ? { "x-api-key": key, "anthropic-version": "2023-06-01" }
                : { authorization: `Bearer ${key}` }),
            },
            body: JSON.stringify({
              model: deps.model.defaultModel,
              /*
               * No temperature.
               *
               * It was zero, for a router that answers the same way twice. Reasoning models refuse the
               * setting outright — "Unsupported value: 'temperature' does not support 0 with this model.
               * Only the default (1) value is supported" — and this call treats a throw as "not sure", so
               * every routing decision quietly became the default coworker and the roster was never
               * consulted. A question naming Google Drive went to a Bot holding no Drive tools, which is
               * the exact failure the roster exists to prevent, and nothing said so.
               *
               * Omitted rather than set per model, because a list of which models accept it is a list that
               * goes stale. `response_format` and a prompt that asks for one object keep the answer tight,
               * and the confidence floor still sends an unsure match to the default.
               */
              ...(anthropic
                ? { max_tokens: outputTokenBudget ?? 1024 }
                : {
                    response_format: { type: "json_object" },
                    ...(outputTokenBudget === undefined
                      ? {}
                      : { max_completion_tokens: outputTokenBudget }),
                  }),
              messages: [{ role: "user", content: prompt }],
            }),
            signal: activeSignal,
          },
        ),
      );
      httpStatus = response.status;
      if (!response.ok) {
        status = "http_error";
        throw new Error(`router model answered ${response.status}`);
      }
      const body = (await bounded(() => response.json())) as {
        choices?: { message?: { content?: unknown } }[];
        content?: { type?: string; text?: unknown }[];
        usage?: unknown;
      };
      if (
        body.usage &&
        typeof body.usage === "object" &&
        !Array.isArray(body.usage)
      ) {
        const reported = body.usage as Record<string, unknown>;
        const count = (field: string) =>
          typeof reported[field] === "number" &&
          Number.isFinite(reported[field]) &&
          reported[field] >= 0
            ? (reported[field] as number)
            : null;
        const details: Record<string, number | Record<string, number>> = {};
        for (const field of [
          "prompt_tokens_details",
          "completion_tokens_details",
          "cache_creation_input_tokens",
          "cache_read_input_tokens",
          "cache_creation",
          "input_tokens_details",
          "output_tokens_details",
        ]) {
          const value = reported[field];
          if (typeof value === "number" && Number.isFinite(value) && value >= 0)
            details[field] = value;
          else if (value && typeof value === "object" && !Array.isArray(value))
            details[field] = Object.fromEntries(
              Object.entries(value).filter(
                ([, v]) =>
                  typeof v === "number" && Number.isFinite(v) && v >= 0,
              ),
            ) as Record<string, number>;
        }
        usage = {
          inputTokens: count(anthropic ? "input_tokens" : "prompt_tokens"),
          outputTokens: count(
            anthropic ? "output_tokens" : "completion_tokens",
          ),
          totalTokens: count("total_tokens"),
          details,
        };
      }
      const content = anthropic
        ? body.content
            ?.filter(
              (block) =>
                block.type === "text" && typeof block.text === "string",
            )
            .map((block) => block.text)
            .join("") || undefined
        : body.choices?.[0]?.message?.content;
      if (typeof content !== "string")
        throw new Error("router model returned no text");
      activeSignal.throwIfAborted();
      status = "success";
      return content;
    } catch (error) {
      if (activeSignal.aborted)
        status =
          activeSignal.reason?.name === "TimeoutError"
            ? "timeout"
            : "cancelled";
      throw error;
    } finally {
      activeSignal.removeEventListener("abort", abort);
      if (started !== null)
        deps.observe?.({
          durationMs: performance.now() - started,
          status,
          httpStatus,
          usage,
        });
    }
  };
}

/**
 * Where this deployment's `/chat/completions` actually is.
 *
 * `/v1` USED TO BE APPENDED UNCONDITIONALLY, and that was wrong for every deployment that set the
 * variable. `.env.example` and `docs/configuration.md` both document it with the version in it
 * (`https://gateway.internal/v1`), because that is the shape the AI SDK wants: it takes `baseURL`
 * verbatim and asks for `/chat/completions` under it, which is how the built-in Bots reach the same
 * endpoint. Appending here produced `/v1/v1/chat/completions`, so on a gateway — the entire reason
 * the variable exists — every call from this function 404'd.
 *
 * That failure was invisible, which is the worst part. The router treats a throw as "not sure" and
 * lands on the default coworker, so a deployment behind a gateway silently stopped routing and
 * nothing anywhere said why. Tool selection reads through the same function and would have failed
 * the same way, offering the whole catalogue on the deployments most likely to have a big one.
 *
 * So the version segment is added only when the configured URL does not already end in one, and the
 * unset case keeps the public API's own `https://api.openai.com/v1`.
 */
export function chatCompletionsUrl(
  environment: Record<string, string | undefined>,
): string {
  const base = (environment.OPENAI_BASE_URL?.trim() || "https://api.openai.com")
    // A trailing slash is the difference between `/v1` and `/v1/`, and no more than that.
    .replace(/\/+$/, "");
  return /\/v\d+$/.test(base)
    ? `${base}/chat/completions`
    : `${base}/v1/chat/completions`;
}

/** Native Anthropic endpoint, accepting the same versioned base URL as the runtime. */
export function anthropicMessagesUrl(
  environment: Record<string, string | undefined>,
): string {
  const base = (
    environment.ANTHROPIC_BASE_URL?.trim() || "https://api.anthropic.com"
  ).replace(/\/+$/, "");
  return /\/v\d+$/.test(base) ? `${base}/messages` : `${base}/v1/messages`;
}
