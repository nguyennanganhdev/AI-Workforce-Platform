import { Hono } from "hono";
import { decryptSecret, encryptSecret } from "../credentials";
import { customUrlRefusal } from "../plugins/catalogue";
import { inspectToolArguments } from "../plugins/content-governance";
import { callTool, listTools, McpServerError } from "../plugins/mcp";
import { sameToken } from "./session-routes";

/**
 * External MCP connections of a management unit's agents.
 *
 * The business API decides who may call what: the agent run, the pinned version, the grant, the
 * unit the connection belongs to, and the audit row. This host does the two things the API does not:
 * it holds the key that seals a connection's token, and it speaks MCP through the platform's one
 * client (plugins/mcp.ts: timeouts, result cap, a vendor's failure as one sentence).
 *
 * A token arrives here in clear once, when an administrator saves it, and leaves sealed. After that
 * the API only ever holds and sends back the sealed form.
 *
 * Arguments an agent wrote are checked before they leave (plugins/content-governance.ts): a call that
 * carries a credential is answered 400 and never reaches the vendor. The answer names where it was
 * found, never what was found.
 */
export function createConnectionRoutes(
  serviceToken: string,
  /** Base64 of 32 bytes. Without it no connection can be saved or used. */
  encryptionKey: string,
  /** Origins reachable over plain http, for a test server on the same machine. Empty in a deployment. */
  httpOrigins: string[] = [],
) {
  const app = new Hono();
  app.use("*", async (c, next) => {
    c.header("Cache-Control", "no-store");
    const offered = c.req.header("authorization") ?? "";
    if (
      !offered.startsWith("Bearer ") ||
      !sameToken(serviceToken, offered.slice(7))
    )
      return c.json({ error: "Invalid service credential." }, 401);
    if (!encryptionKey)
      return c.json({ error: "External connections are not configured on this host." }, 503);
    await next();
  });

  const refusal = (url: string) => {
    try {
      if (httpOrigins.includes(new URL(url).origin)) return null;
    } catch {
      // Not a URL: the rule below says so.
    }
    return customUrlRefusal(url);
  };
  const connection = async (body: { url?: unknown; sealed?: unknown }) => {
    if (typeof body.url !== "string") throw new Refused("That is not a URL.");
    const refused = refusal(body.url);
    if (refused) throw new Refused(refused);
    return {
      url: body.url,
      token:
        typeof body.sealed === "string" && body.sealed
          ? await decryptSecret(encryptionKey, body.sealed)
          : undefined,
    };
  };
  class Refused extends Error {}
  const answer = async (work: () => Promise<Response>) => {
    try {
      return await work();
    } catch (error) {
      if (error instanceof Refused)
        return Response.json({ error: error.message }, { status: 422 });
      if (error instanceof McpServerError)
        return Response.json({ error: error.message }, { status: 502 });
      throw error;
    }
  };

  app.post("/seal", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (typeof body.token !== "string" || !body.token.trim())
      return c.json({ error: "A token is required." }, 422);
    return c.json({ sealed: await encryptSecret(encryptionKey, body.token.trim()) });
  });
  app.post("/check", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    const refused = typeof body.url === "string" ? refusal(body.url) : "That is not a URL.";
    return refused ? c.json({ error: refused }, 422) : c.json({ ok: true });
  });
  app.post("/tools", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    return answer(async () =>
      Response.json({ tools: await listTools(await connection(body)) }),
    );
  });
  app.post("/call", async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (typeof body.tool !== "string" || !body.tool)
      return c.json({ error: "A tool name is required." }, 422);
    const inspection = inspectToolArguments(body.arguments ?? {});
    if (!inspection.safe)
      return c.json(
        {
          error:
            inspection.reason === "sensitive_content"
              ? `These arguments were not sent: they carry a credential (${inspection.findings
                  .map((finding) => `${finding.category} at ${finding.path}`)
                  .join(", ")}). Call again without it.`
              : "These arguments were not sent: they are too large or too deeply nested to check.",
        },
        400,
      );
    return answer(async () =>
      Response.json(
        await callTool(await connection(body), body.tool, body.arguments ?? {}),
      ),
    );
  });
  return app;
}
