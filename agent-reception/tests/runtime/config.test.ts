import { describe, expect, test } from "bun:test";
import { loadConfig, ReceptionConfigError } from "../../src/config";

describe("loadConfig", () => {
  test("loads defaults for a configured provider", () => {
    expect(loadConfig({ OPENAI_API_KEY: "test-key" })).toEqual({
      port: 4202,
      host: "0.0.0.0",
      modelProvider: "openai",
      model: "gpt-5.5",
      modelApiKey: "test-key",
    });
  });

  test("rejects invalid ports and missing provider credentials", () => {
    expect(() => loadConfig({ PORT: "0", OPENAI_API_KEY: "test-key" })).toThrow(
      "PORT must be an integer",
    );
    expect(() => loadConfig({})).toThrow("OPENAI_API_KEY is required");
  });

  test("rejects unknown model providers", () => {
    expect(() =>
      loadConfig({ RECEPTION_MODEL_PROVIDER: "unknown", OPENAI_API_KEY: "x" }),
    ).toThrow("RECEPTION_MODEL_PROVIDER must be");
  });

  test.each([
    ["anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-4-5"],
    ["google", "GOOGLE_API_KEY", "gemini-2.5-flash"],
  ])(
    "selects the correct credentials and default for %s",
    (provider, variable, model) => {
      const result = loadConfig({
        RECEPTION_MODEL_PROVIDER: ` ${provider.toUpperCase()} `,
        [variable]: " provider-key ",
        OPENAI_API_KEY: "unrelated-key",
        RECEPTION_MODEL: " ",
        PORT: " 65535 ",
        HOST: " 127.0.0.1 ",
      });
      expect(result).toMatchObject({
        modelProvider: provider,
        modelApiKey: "provider-key",
        model,
        port: 65535,
        host: "127.0.0.1",
      });
      expect(() =>
        loadConfig({ RECEPTION_MODEL_PROVIDER: provider, OPENAI_API_KEY: "x" }),
      ).toThrow(`${variable} is required`);
    },
  );

  test.each([
    "-1",
    "65536",
    "1.5",
    "NaN",
    "Infinity",
    "0x106a",
    "4e3",
    "secret-port",
  ])("rejects invalid port %s without echoing input", (port) => {
    expect(() =>
      loadConfig({ PORT: port, OPENAI_API_KEY: "secret-key" }),
    ).toThrow(
      new ReceptionConfigError("PORT must be an integer between 1 and 65535."),
    );
  });

  test("honors an explicit model and rejects blank credentials", () => {
    expect(
      loadConfig({ OPENAI_API_KEY: "x", RECEPTION_MODEL: " custom-model " })
        .model,
    ).toBe("custom-model");
    expect(() => loadConfig({ OPENAI_API_KEY: "  " })).toThrow(
      ReceptionConfigError,
    );
  });
});
