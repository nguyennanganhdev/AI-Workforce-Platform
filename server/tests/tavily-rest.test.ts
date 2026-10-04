import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { accessFor } from "../src/plugins/access";
import {
  catalogueEntry,
  classifyTool,
  resolveServerUrl,
} from "../src/plugins/catalogue";
import { MAX_RESULT_CHARS } from "../src/plugins/mcp";
import { callTool, listTools } from "../src/plugins/tavily-rest";
import { transportFor } from "../src/plugins/transport";

/**
 * The Tavily adapter, asserted without Tavily.
 *
 * `fetch` is replaced rather than a server started, for the reason the Drive adapter's tests give:
 * what is under test is the translation — which request a search becomes, what a refusal reads as,
 * and that the deployment's key reaches the vendor's header and nothing else.
 */

const connection = { url: "https://api.tavily.com/search" };
// Shaped like a key and unmistakable in an assertion; never a real one.
const KEY = "tvly-TEST-KEY-never-real";

const realFetch = globalThis.fetch;
const realKey = process.env.TAVILY_API_KEY;

// Anything a test did not stub is an escape, and an escape fails the test that let it out.
let escapedToNetwork: string[] = [];

beforeEach(() => {
  escapedToNetwork = [];
  process.env.TAVILY_API_KEY = KEY;
  globalThis.fetch = (async (input: string | URL): Promise<Response> => {
    escapedToNetwork.push(String(input));
    throw new Error(`unstubbed fetch escaped to the network: ${String(input)}`);
  }) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = realFetch;
  if (realKey === undefined) delete process.env.TAVILY_API_KEY;
  else process.env.TAVILY_API_KEY = realKey;
  expect(escapedToNetwork).toEqual([]);
});

type Recorded = { url: string; init: RequestInit };

/** Records what was requested and answers with a fixed response. */
function stubFetch(respond: () => Response | Promise<Response>): Recorded[] {
  const requests: Recorded[] = [];
  globalThis.fetch = (async (input: string | URL, init?: RequestInit) => {
    requests.push({ url: String(input), init: init ?? {} });
    return respond();
  }) as typeof fetch;
  return requests;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("discovery", () => {
  test("offers one stable tool, with no credential needed to list it", async () => {
    delete process.env.TAVILY_API_KEY;
    const tools = await listTools();
    expect(tools.map(({ name }) => name)).toEqual(["tavily_search"]);
    expect(tools[0]).toMatchObject({
      effect: "read",
      inputSchema: {
        type: "object",
        required: ["query"],
        properties: {
          query: { type: "string" },
          max_results: { type: "integer", minimum: 1, maximum: 10 },
        },
      },
    });
    // The schema is what a model, a spec fingerprint and the catalogue all see.
    expect(JSON.stringify(tools)).not.toMatch(
      /key|token|secret|authorization/i,
    );
  });

  test("the catalogue entry routes to this adapter at Tavily's pinned address", () => {
    const entry = catalogueEntry("tavily");
    expect(entry?.transport).toBe("tavily-rest");
    expect(entry?.auth.kind).toBe("none");
    expect(resolveServerUrl("tavily")?.url).toBe(connection.url);
    // The address is the catalogue's whatever a caller offers.
    expect(resolveServerUrl("tavily", "https://evil.test")?.url).toBe(
      connection.url,
    );
    if (!entry) throw new Error("tavily must be a catalogue entry");
    const access = accessFor(
      { provenance: "first-party", url: connection.url, authScheme: null },
      entry,
    );
    expect(access).toEqual({
      transport: "tavily-rest",
      credential: "none",
      reachedAs: "deployment",
      toolkit: null,
    });
    expect(transportFor(access.transport).callTool).toBe(callTool);
    expect(transportFor(access.transport).listNeedsCredential).toBe(false);
    expect(classifyTool(entry, "tavily_search", true, "read")).toBe("read");
    // A name the server never listed came from a model, and stays a write.
    expect(classifyTool(entry, "tavily_delete", false)).toBe("write");
  });
});

describe("a successful search", () => {
  test("sends the query and the key to Tavily and answers in one normalized shape", async () => {
    const requests = stubFetch(() =>
      json({
        query: "temporal architecture",
        answer: null,
        response_time: 1.2,
        results: [
          {
            title: " Temporal docs ",
            url: "https://docs.temporal.io/temporal",
            content: "Temporal is a durable execution platform.",
            score: 0.98,
            raw_content: "IGNORED",
          },
          {
            title: "Workflows",
            url: "https://docs.temporal.io/workflows",
            content: "x".repeat(5_000),
          },
        ],
      }),
    );

    const result = await callTool(connection, "tavily_search", {
      query: "  temporal architecture ",
      max_results: 3,
    });

    expect(requests).toHaveLength(1);
    expect(requests[0]?.url).toBe(connection.url);
    expect(requests[0]?.init.method).toBe("POST");
    expect(requests[0]?.init.headers).toEqual({
      authorization: `Bearer ${KEY}`,
      "content-type": "application/json",
    });
    // The key travels in the header only: not in the address, not in the body.
    expect(JSON.parse(String(requests[0]?.init.body))).toEqual({
      query: "temporal architecture",
      max_results: 3,
    });
    expect(requests[0]?.init.signal).toBeInstanceOf(AbortSignal);

    expect(result.isError).toBe(false);
    expect(result.truncated).toBe(false);
    const parsed = JSON.parse(result.text);
    expect(Object.keys(parsed)).toEqual(["results"]);
    expect(parsed.results[0]).toEqual({
      title: "Temporal docs",
      url: "https://docs.temporal.io/temporal",
      content: "Temporal is a durable execution platform.",
    });
    expect(parsed.results[1].content).toHaveLength(1_500);
    expect(result.text).not.toContain(KEY);
  });

  test("max_results defaults to five and is clamped to what the schema allows", async () => {
    const requests = stubFetch(() => json({ results: [] }));
    await callTool(connection, "tavily_search", { query: "q" });
    await callTool(connection, "tavily_search", {
      query: "q",
      max_results: 99,
    });
    await callTool(connection, "tavily_search", { query: "q", max_results: 0 });
    await callTool(connection, "tavily_search", {
      query: "q",
      max_results: "many",
    });
    expect(
      requests.map(({ init }) => JSON.parse(String(init.body)).max_results),
    ).toEqual([5, 10, 1, 5]);
  });

  test("ten full results are still whole JSON under the result ceiling", async () => {
    stubFetch(() =>
      json({
        results: Array.from({ length: 10 }, (_, index) => ({
          title: `Source ${index}`,
          url: `https://example.test/${index}`,
          content: "y".repeat(9_000),
        })),
      }),
    );
    const result = await callTool(connection, "tavily_search", {
      query: "q",
      max_results: 10,
    });
    expect(result.text.length).toBeLessThanOrEqual(MAX_RESULT_CHARS);
    expect(JSON.parse(result.text).results).toHaveLength(10);
  });

  test("a search that finds nothing is an empty list, not an error", async () => {
    stubFetch(() => json({ results: [] }));
    const result = await callTool(connection, "tavily_search", { query: "q" });
    expect(result).toEqual({
      text: '{"results":[]}',
      isError: false,
      truncated: false,
    });
  });
});

describe("refusals before anything is sent", () => {
  test("a missing TAVILY_API_KEY is said plainly and nothing is requested", async () => {
    for (const value of [undefined, "", "   "]) {
      if (value === undefined) delete process.env.TAVILY_API_KEY;
      else process.env.TAVILY_API_KEY = value;
      const result = await callTool(connection, "tavily_search", {
        query: "q",
      });
      expect(result.isError).toBe(true);
      expect(result.text).toContain("TAVILY_API_KEY is not set");
    }
    // The escape ledger in afterEach proves no request left for any of the three.
  });

  test("a missing query and an unknown tool are refused without a request", async () => {
    for (const args of [{}, { query: "" }, { query: 7 }]) {
      const result = await callTool(connection, "tavily_search", args);
      expect(result.isError).toBe(true);
      expect(result.text).toContain("needs a query");
    }
    const unknown = await callTool(connection, "tavily_extract", {
      query: "q",
    });
    expect(unknown).toMatchObject({
      isError: true,
      text: "Tavily has no tool named tavily_extract.",
    });
  });
});

describe("provider errors", () => {
  test("an HTTP refusal reports the status and never relays the vendor's body or the key", async () => {
    for (const [status, sentence] of [
      [401, "refused this deployment's key (HTTP 401)"],
      [403, "refused this deployment's key (HTTP 403)"],
      [429, "refused the search (HTTP 429)"],
      [432, "refused the search (HTTP 432)"],
      [500, "refused the search (HTTP 500)"],
    ] as const) {
      stubFetch(() =>
        json({ detail: { error: `VENDOR_BODY echoing ${KEY}` } }, status),
      );
      const result = await callTool(connection, "tavily_search", {
        query: "q",
      });
      expect(result.isError).toBe(true);
      expect(result.text).toContain(sentence);
      expect(result.text).not.toContain("VENDOR_BODY");
      expect(result.text).not.toContain(KEY);
    }
  });

  test("an unreachable vendor is a sentence, and the thrown message is not relayed", async () => {
    stubFetch(() => {
      throw new Error(`connect ECONNREFUSED with ${KEY}`);
    });
    const result = await callTool(connection, "tavily_search", { query: "q" });
    expect(result).toEqual({
      text: "Tavily could not be reached, so nothing was searched.",
      isError: true,
      truncated: false,
    });
  });

  test("a timeout is reported as one", async () => {
    stubFetch(() => {
      throw new DOMException("The operation timed out.", "TimeoutError");
    });
    const result = await callTool(connection, "tavily_search", { query: "q" });
    expect(result).toEqual({
      text: "Tavily did not answer in time, so nothing was searched.",
      isError: true,
      truncated: false,
    });
  });
});

describe("malformed responses", () => {
  test("a body that is not JSON is an error", async () => {
    stubFetch(() => new Response("<html>gateway</html>", { status: 200 }));
    const result = await callTool(connection, "tavily_search", { query: "q" });
    expect(result).toMatchObject({
      isError: true,
      text: "Tavily answered with something that is not JSON.",
    });
  });

  test("JSON without a results list is an error", async () => {
    for (const body of [null, [], "text", {}, { results: "none" }]) {
      stubFetch(() => json(body));
      const result = await callTool(connection, "tavily_search", {
        query: "q",
      });
      expect(result).toMatchObject({
        isError: true,
        text: "Tavily answered without a list of results.",
      });
    }
  });

  test("rows that cannot be cited are dropped, and a list of only those is an error", async () => {
    stubFetch(() =>
      json({
        results: [
          null,
          "row",
          { title: "No address", content: "c" },
          { title: 7, url: "https://example.test/kept", content: null },
        ],
      }),
    );
    const mixed = await callTool(connection, "tavily_search", { query: "q" });
    expect(mixed.isError).toBe(false);
    expect(JSON.parse(mixed.text)).toEqual({
      results: [{ title: "", url: "https://example.test/kept", content: "" }],
    });

    stubFetch(() => json({ results: [{ title: "No address" }, { url: 3 }] }));
    const unusable = await callTool(connection, "tavily_search", {
      query: "q",
    });
    expect(unusable).toMatchObject({
      isError: true,
      text: "Tavily answered with results that carry no address.",
    });
  });
});
