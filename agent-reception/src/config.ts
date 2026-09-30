export type ModelProvider = "openai" | "anthropic" | "google";

export type ReceptionConfig = Readonly<{
  port: number;
  host: string;
  modelProvider: ModelProvider;
  model: string;
  modelApiKey: string;
}>;

const DEFAULT_MODELS: Record<ModelProvider, string> = {
  openai: "gpt-5.5",
  anthropic: "claude-sonnet-4-5",
  google: "gemini-2.5-flash",
};

const API_KEY_VARIABLES: Record<ModelProvider, string> = {
  openai: "OPENAI_API_KEY",
  anthropic: "ANTHROPIC_API_KEY",
  google: "GOOGLE_API_KEY",
};

/** Safe to display at startup: messages contain variable names, never values. */
export class ReceptionConfigError extends Error {
  override name = "ReceptionConfigError";
}

export function loadConfig(
  env: Record<string, string | undefined> = process.env,
): ReceptionConfig {
  const providerValue = (env.RECEPTION_MODEL_PROVIDER ?? "openai")
    .trim()
    .toLowerCase();
  if (!isModelProvider(providerValue)) {
    throw new ReceptionConfigError(
      "RECEPTION_MODEL_PROVIDER must be openai, anthropic or google.",
    );
  }

  const portValue = env.PORT?.trim() || "4202";
  const port = Number(portValue);
  if (
    !/^\d+$/.test(portValue) ||
    !Number.isInteger(port) ||
    port < 1 ||
    port > 65535
  ) {
    throw new ReceptionConfigError(
      "PORT must be an integer between 1 and 65535.",
    );
  }

  const apiKeyVariable = API_KEY_VARIABLES[providerValue];
  const modelApiKey = env[apiKeyVariable]?.trim();
  if (!modelApiKey) {
    throw new ReceptionConfigError(
      `${apiKeyVariable} is required for the selected model provider.`,
    );
  }

  return {
    port,
    host: env.HOST?.trim() || "0.0.0.0",
    modelProvider: providerValue,
    model: env.RECEPTION_MODEL?.trim() || DEFAULT_MODELS[providerValue],
    modelApiKey,
  };
}

function isModelProvider(value: string): value is ModelProvider {
  return value === "openai" || value === "anthropic" || value === "google";
}
