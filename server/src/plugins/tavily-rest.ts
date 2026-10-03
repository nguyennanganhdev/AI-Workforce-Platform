import type { ListedTool, McpCallResult } from "./mcp";

/**
 * Tavily web search, reached over its ordinary REST API.
 *
 * WHY THIS IS AN ADAPTER AND NOT TAVILY'S MCP SERVER. The contract a Bot is offered here is one
 * tool with two arguments and one answer shape, and it is this deployment's to keep stable: a grant
 * is stored as `tavily/tavily_search`, a skill declares that ref, and a generated coworker's spec
 * fingerprints its schema. A vendor's hosted tool list changes when the vendor ships, and every
 * change there would block those coworkers until they were rebuilt.
 *
 * Same seam as {@link ./google-drive-rest}: `listTools` and `callTool`, MCP's own shapes, chosen
 * per catalogue entry by {@link ./access} and looked up in {@link ./transport}. Whether a call is
 * permitted is not decided here — the grant, the policy and the audit row are the store's.
 *
 * THE KEY IS THE DEPLOYMENT'S ENVIRONMENT AND GOES NOWHERE ELSE. `TAVILY_API_KEY` is read when a
 * call is made and sent as one header to the address the catalogue pins. It is never an argument,
 * never part of the URL, never in a result and never in a failure sentence, so nothing that is
 * stored, audited or shown to a model can carry it.
 */

/** Long enough for a slow search, short enough that a Bot's turn is not held open on it. */
const REQUEST_TIMEOUT_MS = 30_000;

const DEFAULT_RESULTS = 5;
const MAX_RESULTS = 10;

/**
 * How much of one page's extract a result keeps.
 *
 * ponytail: a per-result cap, so ten results stay under `MAX_RESULT_CHARS` and the answer is always
 * whole JSON rather than JSON cut mid-string. Raise it together with a real truncation rule if
 * Bots need longer extracts; deep reading is what the browser tools are for.
 */
const MAX_CONTENT_CHARS = 1_500;

const TOOL = "tavily_search";

/**
 * Static, like Drive's: there is no remote list to discover, so `refreshTools` records what this
 * code can do. `effect` is stated because a search changes nothing anywhere.
 */
const TOOLS: readonly ListedTool[] = Object.freeze([
  {
    name: TOOL,
    description:
      "Search the public web. Returns JSON {results:[{title,url,content}]}: for each matching page its title, its address and a short extract of what it says. Use the url to cite a source.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "What to search the web for.",
        },
        max_results: {
          type: "integer",
          minimum: 1,
          maximum: MAX_RESULTS,
          description: `How many results to return. Defaults to ${DEFAULT_RESULTS}.`,
        },
      },
      required: ["query"],
    },
    effect: "read",
  },
]);

/** The list is this file, so no credential is needed to know it — a missing key still lists. */
export const listNeedsCredential = false;

export async function listTools(): Promise<ListedTool[]> {
  return [...TOOLS];
}

const failure = (message: string): McpCallResult => ({
  text: message,
  isError: true,
  truncated: false,
});

const text = (value: unknown): string =>
  typeof value === "string" ? value.trim() : "";

/**
 * Search, and answer in one shape whatever Tavily sent.
 *
 * Every failure is an `isError` result with a sentence written here. The vendor's own body is never
 * relayed: it is somebody else's text on its way into a model's context and an audit row, and a
 * status code says everything an operator can act on.
 */
export async function callTool(
  connection: { url: string },
  toolName: string,
  args: Record<string, unknown>,
): Promise<McpCallResult> {
  if (toolName !== TOOL)
    return failure(`Tavily has no tool named ${toolName}.`);

  const query = text(args.query);
  if (!query) return failure("tavily_search needs a query to search for.");

  const requested = Number(args.max_results);
  const maxResults = Number.isFinite(requested)
    ? Math.min(MAX_RESULTS, Math.max(1, Math.trunc(requested)))
    : DEFAULT_RESULTS;

  const apiKey = process.env.TAVILY_API_KEY?.trim();
  if (!apiKey) {
    return failure(
      "Web search is not configured for this deployment: TAVILY_API_KEY is not set, so nothing was searched.",
    );
  }

  let response: Response;
  try {
    response = await fetch(connection.url, {
      method: "POST",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ query, max_results: maxResults }),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    return failure(
      error instanceof Error && error.name === "TimeoutError"
        ? "Tavily did not answer in time, so nothing was searched."
        : "Tavily could not be reached, so nothing was searched.",
    );
  }

  if (!response.ok) {
    return failure(
      response.status === 401 || response.status === 403
        ? `Tavily refused this deployment's key (HTTP ${response.status}). An administrator has to check TAVILY_API_KEY.`
        : `Tavily refused the search (HTTP ${response.status}).`,
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return failure("Tavily answered with something that is not JSON.");
  }

  const rows =
    body && typeof body === "object"
      ? (body as { results?: unknown }).results
      : undefined;
  if (!Array.isArray(rows)) {
    return failure("Tavily answered without a list of results.");
  }

  // A row with no address cannot be cited, so it is not a result.
  const results = rows.flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const { title, url, content } = row as Record<string, unknown>;
    return text(url)
      ? [
          {
            title: text(title),
            url: text(url),
            content: text(content).slice(0, MAX_CONTENT_CHARS),
          },
        ]
      : [];
  });
  if (rows.length > 0 && results.length === 0) {
    return failure("Tavily answered with results that carry no address.");
  }

  return {
    text: JSON.stringify({ results }),
    isError: false,
    truncated: false,
  };
}
