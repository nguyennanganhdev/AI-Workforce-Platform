import { z } from "zod";
import { createFactoryHandler, MAX_REQUEST_BYTES } from "./http.js";
import { createHttpCompleter } from "./model.js";

const environment = z
  .object({
    FACTORY_SERVICE_TOKEN: z.string().min(32),
    FACTORY_PORT: z.coerce.number().int().min(0).max(65535).default(4010),
    FACTORY_HOST: z.string().min(1).default("127.0.0.1"),
    FACTORY_MODEL_PROVIDER: z
      .enum(["openai", "openai-compatible", "deepseek"])
      .default("openai"),
    FACTORY_MODEL_API_URL: z
      .url()
      .default("https://api.openai.com/v1/chat/completions"),
    FACTORY_MODEL_API_KEY: z.string().trim().min(1),
    FACTORY_MODEL: z.string().trim().min(1),
  })
  .safeParse(process.env);
if (!environment.success) {
  // Names only: do not print environment values, URLs containing credentials or provider errors.
  console.error(
    `Invalid Factory configuration: ${environment.error.issues.map((issue) => issue.path.join(".")).join(", ")}`,
  );
  process.exit(1);
}
const config = environment.data;
const server = Bun.serve({
  port: config.FACTORY_PORT,
  hostname: config.FACTORY_HOST,
  maxRequestBodySize: MAX_REQUEST_BYTES,
  idleTimeout: 120,
  fetch: createFactoryHandler({
    token: config.FACTORY_SERVICE_TOKEN,
    modelRef: `${config.FACTORY_MODEL_PROVIDER}/${config.FACTORY_MODEL}`,
    complete: createHttpCompleter({
      provider: config.FACTORY_MODEL_PROVIDER,
      url: config.FACTORY_MODEL_API_URL,
      apiKey: config.FACTORY_MODEL_API_KEY,
      model: config.FACTORY_MODEL,
    }),
  }),
});
console.log(`Agent Factory listening at ${server.url}`);
