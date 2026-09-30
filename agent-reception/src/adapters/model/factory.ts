import { ChatAnthropic } from "@langchain/anthropic";
import type { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { ChatOpenAI } from "@langchain/openai";
import type { ReceptionConfig } from "../../config";

export function createChatModel(config: ReceptionConfig): BaseChatModel {
  switch (config.modelProvider) {
    case "anthropic":
      return new ChatAnthropic({
        model: config.model,
        apiKey: config.modelApiKey,
        streaming: true,
      });
    case "google":
      return new ChatGoogleGenerativeAI({
        model: config.model,
        apiKey: config.modelApiKey,
        streaming: true,
      });
    case "openai":
      return new ChatOpenAI({
        model: config.model,
        apiKey: config.modelApiKey,
        streaming: true,
      });
  }
}
