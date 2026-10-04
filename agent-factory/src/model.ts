import { z } from "zod";
import { readBoundedText } from "./io.js";
import type { FactoryCompleter } from "./verification.js";

const configSchema = z
  .strictObject({
    url: z.url().refine((value) => /^https?:/i.test(value)),
    apiKey: z.string().trim().min(1),
    model: z.string().trim().min(1),
    provider: z.enum(["openai", "openai-compatible"]).default("openai"),
    reasoningEffort: z.enum(["none", "low", "medium", "high", "xhigh"]).optional(),
    maxCompletionTokens: z.number().int().min(1024).max(16384).default(4096),
  })
  .superRefine((config, context) => {
    if (!URL.canParse(config.url)) return;
    const url = new URL(config.url);
    const openaiKey = /^sk-(proj-|svcacct-)/.test(config.apiKey);
    const openrouterKey = config.apiKey.startsWith("sk-or-");
    if (
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      (openaiKey &&
        (config.provider !== "openai" ||
          url.origin !== "https://api.openai.com" ||
          url.pathname !== "/v1/chat/completions")) ||
      (openrouterKey &&
        (config.provider !== "openai-compatible" ||
          url.origin !== "https://openrouter.ai" ||
          url.pathname !== "/api/v1/chat/completions")) ||
      (url.hostname === "openrouter.ai" &&
        config.provider !== "openai-compatible")
    )
      context.addIssue({
        code: "custom",
        path: ["url"],
        message: "Model provider, endpoint and credential must match.",
      });
  });
const responseSchema = z.object({
  choices: z
    .array(
      z.object({
        message: z.object({ content: z.string().min(1) }),
      }),
    )
    .min(1),
});

/** The endpoint/model/key are deployment configuration, never request fields. No fallback/retry. */
export function createHttpCompleter(
  input: z.input<typeof configSchema>,
  send: (url: string, options: RequestInit) => Promise<Response> = fetch,
): FactoryCompleter {
  const parsed = configSchema.safeParse(input);
  if (!parsed.success) throw new Error("Invalid Factory model configuration.");
  const config = parsed.data;
  return async (prompt, signal) => {
    const response = await send(config.url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        model: config.model,
        messages: [{ role: "user", content: prompt }],
        ...(config.reasoningEffort ? { reasoning_effort: config.reasoningEffort } : {}),
        [config.provider === "openai" ? "max_completion_tokens" : "max_tokens"]:
          config.maxCompletionTokens,
      }),
      ...(signal ? { signal } : {}),
      redirect: "error",
    });
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error("Model request failed.");
    }
    const body = responseSchema.parse(
      JSON.parse(await readBoundedText(response, 256 * 1024)),
    );
    const content = body.choices[0]?.message.content;
    if (!content) throw new Error("Model returned no text.");
    return content;
  };
}
