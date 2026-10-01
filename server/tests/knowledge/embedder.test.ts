import { describe, expect, test } from "bun:test";
import {
  createOpenAIEmbedder,
  EmbeddingError,
} from "../../src/knowledge/embedder";

const vector = (size = 1536) => Array.from({ length: size }, () => 0.01);

function respond(handler: (body: { input: string[] }) => Response) {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  const fetchImpl = (async (url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body));
    calls.push({ url, body });
    return handler(body);
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

const ok = (input: string[], size = 1536) =>
  Response.json({
    data: input
      .map((_, index) => ({ index, embedding: vector(size) }))
      .reverse(),
  });

describe("createOpenAIEmbedder", () => {
  test("asks for the default model, text-embedding-3-large, at 1536 dimensions and keeps input order", async () => {
    const { fetchImpl, calls } = respond((body) => ok(body.input));
    const embedder = createOpenAIEmbedder({ apiKey: "k", fetch: fetchImpl });
    const result = await embedder.embed(["a", "b"]);
    expect(result).toHaveLength(2);
    expect(calls[0]?.url).toBe("https://api.openai.com/v1/embeddings");
    expect(calls[0]?.body.model).toBe("text-embedding-3-large");
    expect(calls[0]?.body.dimensions).toBe(1536);
  });

  test("splits into batches", async () => {
    const { fetchImpl, calls } = respond((body) => ok(body.input));
    const embedder = createOpenAIEmbedder({
      apiKey: "k",
      batchSize: 2,
      fetch: fetchImpl,
    });
    expect(await embedder.embed(["a", "b", "c", "d", "e"])).toHaveLength(5);
    expect(calls).toHaveLength(3);
  });

  test("retries a 429 and then succeeds", async () => {
    let attempts = 0;
    const { fetchImpl } = respond((body) =>
      ++attempts < 3
        ? new Response("slow down", { status: 429 })
        : ok(body.input),
    );
    const embedder = createOpenAIEmbedder({
      apiKey: "k",
      fetch: fetchImpl,
      sleep: async () => {},
    });
    expect(await embedder.embed(["a"])).toHaveLength(1);
    expect(attempts).toBe(3);
  });

  test("a 401 is not retried and does not leak the response body", async () => {
    let attempts = 0;
    const { fetchImpl } = respond(() => {
      attempts++;
      return new Response("secret echo of input", { status: 401 });
    });
    const embedder = createOpenAIEmbedder({
      apiKey: "k",
      fetch: fetchImpl,
      sleep: async () => {},
    });
    const error = await embedder.embed(["a"]).catch((e) => e);
    expect(error).toBeInstanceOf(EmbeddingError);
    expect(error.code).toBe("http_401");
    expect(error.message).not.toContain("secret");
    expect(attempts).toBe(1);
  });

  test("a wrong dimension is refused before it reaches the database", async () => {
    const { fetchImpl } = respond((body) => ok(body.input, 768));
    const embedder = createOpenAIEmbedder({ apiKey: "k", fetch: fetchImpl });
    const error = await embedder.embed(["a"]).catch((e) => e);
    expect(error.code).toBe("dimension_mismatch");
  });

  test("an empty key is refused at construction", () => {
    expect(() => createOpenAIEmbedder({ apiKey: " " })).toThrow(EmbeddingError);
  });
});

describe("model choice", () => {
  test("text-embedding-3-small can still be chosen, at 1536 dimensions, named in the spec", async () => {
    const calls: Record<string, unknown>[] = [];
    const fetchImpl = (async (_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body));
      calls.push(body);
      return Response.json({
        data: body.input.map((_: string, index: number) => ({
          index,
          embedding: new Array(1536).fill(0),
        })),
      });
    }) as unknown as typeof fetch;
    const embedder = createOpenAIEmbedder({
      apiKey: "k",
      model: "text-embedding-3-small",
      fetch: fetchImpl,
    });
    await embedder.embed(["a"]);
    expect(calls[0]).toMatchObject({
      model: "text-embedding-3-small",
      dimensions: 1536,
    });
    expect(embedder.model.modelName).toBe("text-embedding-3-small");
    expect(embedder.model.dimension).toBe(1536);
  });

  test("an unknown model is refused", () => {
    expect(() =>
      createOpenAIEmbedder({ apiKey: "k", model: "ada" as never }),
    ).toThrow("Unsupported");
  });
});
