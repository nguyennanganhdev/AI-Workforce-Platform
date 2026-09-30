import { describe, expect, test } from "bun:test";
import { ChatAnthropic } from "@langchain/anthropic";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOpenAI } from "@langchain/openai";
import { createChatModel } from "../../../src/adapters/model/factory";
import type { ReceptionConfig } from "../../../src/config";

const config = (
  modelProvider: ReceptionConfig["modelProvider"],
): ReceptionConfig => ({
  port: 4202,
  host: "127.0.0.1",
  modelProvider,
  model: "test-model",
  modelApiKey: "test-key",
});

describe("createChatModel", () => {
  test("creates the configured LangChain provider without making a network call", () => {
    const openai = createChatModel(config("openai"));
    const anthropic = createChatModel(config("anthropic"));
    const google = createChatModel(config("google"));
    expect(openai).toBeInstanceOf(ChatOpenAI);
    expect(anthropic).toBeInstanceOf(ChatAnthropic);
    expect(google).toBeInstanceOf(ChatGoogleGenerativeAI);
    expect(openai).toMatchObject({ model: "test-model", streaming: true });
    expect(anthropic).toMatchObject({ model: "test-model", streaming: true });
    expect(google).toMatchObject({ model: "test-model", streaming: true });
  });
});
