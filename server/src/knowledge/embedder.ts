import {
  EMBEDDING_MODEL,
  type Embedder,
  SUPPORTED_EMBEDDING_MODELS,
  type SupportedEmbeddingModel,
} from "./types";

export class EmbeddingError extends Error {
  constructor(
    message: string,
    readonly code: string,
  ) {
    super(message);
    this.name = "EmbeddingError";
  }
}

export type OpenAIEmbedderOptions = {
  /** Defaults to `EMBEDDING_MODEL` (`text-embedding-3-large`). Always requested at 1536 dimensions. */
  model?: SupportedEmbeddingModel;
  apiKey: string;
  /** Defaults to OpenAI. Any endpoint speaking the same `/embeddings` API works. */
  baseUrl?: string;
  batchSize?: number;
  maxAttempts?: number;
  /** Injected by tests. */
  fetch?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
};

const RETRYABLE = new Set([408, 409, 429, 500, 502, 503, 504]);

/**
 * An OpenAI embedding model at 1536 dimensions, the size the `knowledge_embeddings` column and its
 * trigger require. The dimension is requested explicitly and every response is checked, because a
 * silently different size would fail late, inside an insert.
 */
export function createOpenAIEmbedder(options: OpenAIEmbedderOptions): Embedder {
  if (options.apiKey.trim() === "") {
    throw new EmbeddingError("OPENAI_API_KEY is empty.", "missing_api_key");
  }
  const baseUrl = (
    options.baseUrl?.trim() || "https://api.openai.com/v1"
  ).replace(/\/+$/, "");
  const modelName = options.model ?? EMBEDDING_MODEL.modelName;
  if (!SUPPORTED_EMBEDDING_MODELS.includes(modelName)) {
    throw new EmbeddingError(
      `Unsupported embedding model ${modelName}.`,
      "unsupported_model",
    );
  }
  const batchSize = options.batchSize ?? 96;
  const maxAttempts = options.maxAttempts ?? 4;
  const doFetch = options.fetch ?? fetch;
  const sleep =
    options.sleep ??
    ((ms: number) => new Promise((done) => setTimeout(done, ms)));

  async function embedBatch(input: string[]): Promise<number[][]> {
    for (let attempt = 1; ; attempt++) {
      let response: Response;
      try {
        response = await doFetch(`${baseUrl}/embeddings`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            authorization: `Bearer ${options.apiKey}`,
          },
          body: JSON.stringify({
            model: modelName,
            input,
            dimensions: EMBEDDING_MODEL.dimension,
            encoding_format: "float",
          }),
        });
      } catch (error) {
        if (attempt >= maxAttempts) {
          throw new EmbeddingError(
            `Embedding request failed: ${error instanceof Error ? error.message : String(error)}`,
            "network",
          );
        }
        await sleep(2 ** attempt * 250);
        continue;
      }

      if (!response.ok) {
        if (RETRYABLE.has(response.status) && attempt < maxAttempts) {
          await sleep(2 ** attempt * 250);
          continue;
        }
        // The body can echo input text, so only the status leaves this function.
        throw new EmbeddingError(
          `Embedding provider answered ${response.status}.`,
          `http_${response.status}`,
        );
      }

      const payload = (await response.json()) as {
        data?: { index: number; embedding: number[] }[];
      };
      const rows = [...(payload.data ?? [])].sort((a, b) => a.index - b.index);
      if (rows.length !== input.length) {
        throw new EmbeddingError(
          `Asked for ${input.length} embeddings, got ${rows.length}.`,
          "count_mismatch",
        );
      }
      for (const row of rows) {
        if (row.embedding.length !== EMBEDDING_MODEL.dimension) {
          throw new EmbeddingError(
            `Embedding has ${row.embedding.length} dimensions, the schema requires ${EMBEDDING_MODEL.dimension}.`,
            "dimension_mismatch",
          );
        }
      }
      return rows.map((row) => row.embedding);
    }
  }

  return {
    model: { ...EMBEDDING_MODEL, modelName },
    async embed(texts) {
      const vectors: number[][] = [];
      for (let start = 0; start < texts.length; start += batchSize) {
        vectors.push(
          ...(await embedBatch(texts.slice(start, start + batchSize))),
        );
      }
      return vectors;
    },
  };
}
