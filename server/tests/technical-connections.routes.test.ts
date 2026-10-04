import { afterAll, beforeAll, expect, test } from "bun:test";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { z } from "zod";
import { createConnectionRoutes } from "../src/technical-api/connection-routes";

const TOKEN = "t".repeat(40);
const KEY = Buffer.from(new Uint8Array(32).fill(7)).toString("base64");
const headers = {
  authorization: `Bearer ${TOKEN}`,
  "content-type": "application/json",
};

// A real MCP server on this machine: one tool that reads, one it marks destructive, behind a bearer token.
let vendor: ReturnType<typeof Bun.serve>;
let origin = "";
beforeAll(() => {
  vendor = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      if (request.headers.get("authorization") !== "Bearer vendor-secret")
        return new Response("Unauthorized", { status: 401 });
      const mcp = new McpServer({ name: "handbook", version: "1.0.0" });
      mcp.registerTool(
        "lookup",
        { description: "Look a topic up.", inputSchema: { topic: z.string() } },
        async ({ topic }) => ({ content: [{ type: "text", text: `About ${topic}` }] }),
      );
      mcp.registerTool(
        "wipe",
        { description: "Delete it all.", annotations: { destructiveHint: true } },
        async () => ({ content: [{ type: "text", text: "no" }], isError: true }),
      );
      const transport = new WebStandardStreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
      });
      await mcp.connect(transport);
      return transport.handleRequest(request);
    },
  });
  origin = `http://127.0.0.1:${vendor.port}`;
});
afterAll(() => vendor.stop(true));

const post = (app: ReturnType<typeof createConnectionRoutes>, path: string, body: unknown, auth = headers) =>
  app.request(path, { method: "POST", headers: auth, body: JSON.stringify(body) });

test("only the business API reaches these routes, and nothing works without the sealing key", async () => {
  const app = createConnectionRoutes(TOKEN, KEY);
  expect((await post(app, "/seal", { token: "x" }, { ...headers, authorization: "Bearer wrong" })).status).toBe(401);
  expect((await post(createConnectionRoutes(TOKEN, ""), "/seal", { token: "x" })).status).toBe(503);
});

test("an address is refused unless it is a public https host or an origin named for testing", async () => {
  const app = createConnectionRoutes(TOKEN, KEY);
  for (const url of [origin + "/mcp", "https://10.0.0.5/mcp", "https://tools/mcp", "https://user:pw@mcp.example.com/mcp", "not a url"])
    expect((await post(app, "/check", { url })).status).toBe(422);
  expect((await post(app, "/check", { url: "https://mcp.example.com/mcp" })).status).toBe(200);
  expect((await post(createConnectionRoutes(TOKEN, KEY, [origin]), "/check", { url: origin + "/mcp" })).status).toBe(200);
});

test("a sealed token lists and calls the server's tools; the clear token never comes back", async () => {
  const app = createConnectionRoutes(TOKEN, KEY, [origin]);
  const sealed = ((await (await post(app, "/seal", { token: "vendor-secret" })).json()) as { sealed: string }).sealed;
  expect(sealed).not.toContain("vendor-secret");
  const listed = (await (await post(app, "/tools", { url: origin + "/mcp", sealed })).json()) as { tools: { name: string; destructive?: boolean }[] };
  expect(listed.tools.map((t) => [t.name, t.destructive ?? false])).toEqual([["lookup", false], ["wipe", true]]);
  const called = await post(app, "/call", { url: origin + "/mcp", sealed, tool: "lookup", arguments: { topic: "lifts" } });
  expect(await called.json()).toEqual({ text: "About lifts", isError: false, truncated: false });
  // Arguments that carry a credential stay here: the answer says where, never what.
  const leaking = await post(app, "/call", { url: origin + "/mcp", sealed, tool: "lookup", arguments: { topic: "lifts", api_key: "sk-live-0123456789abcdefghij" } });
  expect(leaking.status).toBe(400);
  const sentence = ((await leaking.json()) as { error: string }).error;
  expect(sentence).toContain("credential_field at $.api_key");
  expect(sentence).not.toContain("0123456789");
  // Without the token the vendor refuses, and the refusal arrives as one sentence, not as a crash.
  const refused = await post(app, "/tools", { url: origin + "/mcp" });
  expect(refused.status).toBe(502);
  expect(((await refused.json()) as { error: string }).error).toContain("401");
});
