/**
 * Security MCP server (spec v0.3 §3): Streamable HTTP, profile MCP 2025-11-25, stateless.
 *
 * Mỗi HTTP request: verify access token (401/403 trước khi chạm tool) → parse body chặt → dựng một
 * MCP Server + transport riêng cho đúng caller đó → trả JSON → đóng. Không giữ session giữa request
 * nên không có chuyện request của caller này chạy trên context của caller khác. TLS kết thúc ở
 * ingress; endpoint này không nhận HTTP thô từ ngoài cluster.
 *
 * Chạy riêng: `bun server/src/security-tools/index.ts` với biến môi trường trong `configFromEnv`.
 */
import { serve } from "bun";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { CoreClient } from "./client";
import {
  type AccessTokenVerifier,
  AuthenticationError,
  correlationIdFrom,
  createAccessTokenVerifier,
  HEADERS,
  rawWriteHeaders,
  type RequestIdentity,
} from "./common/context";
import { parseStrictJson, StrictJsonError } from "./common/strict-json";
import { loadFixtureScope, MockSecurityProvider } from "./providers/mock-provider";
import { RealSecurityProvider } from "./providers/real-provider";
import { registerSecurityTools, type SecurityToolsOptions } from "./tools";

/** Profile MCP được pin cho tích hợp; không tuyên bố đây là bản mới nhất. */
export const MCP_PROTOCOL_VERSION = "2025-11-25";
export const SERVER_INFO = { name: "security-mcp", version: "0.3.0" } as const;
const MAX_BODY_BYTES = 1024 * 1024;

export type SecurityMcpOptions = SecurityToolsOptions & {
  verifyAccessToken: AccessTokenVerifier;
  maxBodyBytes?: number;
};

/** Handler Web Standard: gắn vào Bun.serve, Hono `app.all(path, (c) => handler(c.req.raw))`... */
export function createSecurityMcpHandler(options: SecurityMcpOptions): (request: Request) => Promise<Response> {
  return async (request) => {
    const correlationId = correlationIdFrom(request.headers);
    const reply = (status: number, body: unknown, headers: Record<string, string> = {}) =>
      Response.json(body, { status, headers: { [HEADERS.correlationId]: correlationId, ...headers } });

    // Stateless, JSON response: không có SSE stream (GET) hay session để xóa (DELETE).
    if (request.method !== "POST") return reply(405, rpcError(-32000, "Method not allowed"), { allow: "POST" });

    let identity: RequestIdentity;
    try {
      const caller = await options.verifyAccessToken(request.headers.get("authorization"));
      identity = { caller, correlation_id: correlationId, write_headers: rawWriteHeaders(request.headers) };
    } catch (error) {
      if (!(error instanceof AuthenticationError)) throw error;
      const challenge = error.status === 401 ? 'Bearer error="invalid_token"' : 'Bearer error="insufficient_scope"';
      return reply(error.status, rpcError(-32001, error.message), { "www-authenticate": challenge });
    }

    const version = request.headers.get("mcp-protocol-version");
    if (version !== null && version !== MCP_PROTOCOL_VERSION) {
      return reply(400, rpcError(-32000, `Chỉ hỗ trợ MCP-Protocol-Version ${MCP_PROTOCOL_VERSION}`));
    }

    let body: unknown;
    try {
      const text = await request.text();
      if (text.length > (options.maxBodyBytes ?? MAX_BODY_BYTES)) return reply(413, rpcError(-32600, "Request quá lớn"));
      body = parseStrictJson(text);
    } catch (error) {
      if (!(error instanceof StrictJsonError)) throw error;
      return reply(400, rpcError(-32700, "Parse error"));
    }
    pinProtocolVersion(body);

    const server = new Server(SERVER_INFO, { capabilities: { tools: { listChanged: false } } });
    registerSecurityTools(server, identity, options);
    const transport = new WebStandardStreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    try {
      await server.connect(transport);
      const response = await transport.handleRequest(request, { parsedBody: body });
      response.headers.set(HEADERS.correlationId, correlationId);
      return response;
    } finally {
      await server.close();
    }
  };
}

/**
 * Server luôn trả profile đã pin trong initialize: client không hỗ trợ 2025-11-25 sẽ tự ngắt theo
 * quy tắc negotiate của MCP, thay vì server âm thầm chạy profile khác.
 */
function pinProtocolVersion(body: unknown): void {
  const message = body as { method?: unknown; params?: { protocolVersion?: unknown } } | null;
  if (message && typeof message === "object" && message.method === "initialize" && message.params && typeof message.params === "object") {
    message.params.protocolVersion = MCP_PROTOCOL_VERSION;
  }
}

function rpcError(code: number, message: string) {
  return { jsonrpc: "2.0", id: null, error: { code, message } };
}

// ---------------------------------------------------------------------------------------------
// Chạy độc lập
// ---------------------------------------------------------------------------------------------

/**
 * Cấu hình từ môi trường:
 * - SECURITY_MCP_PORT (mặc định 8790), SECURITY_MCP_PATH (mặc định /mcp)
 * - SECURITY_MCP_ACCESS_ISSUERS (phân tách dấu phẩy), SECURITY_MCP_ACCESS_AUDIENCE, SECURITY_MCP_ACCESS_JWKS_URL
 * - SECURITY_MCP_PROVIDER = core | mock; với core: SECURITY_CORE_API_URL, SECURITY_CORE_API_TOKEN
 * Provider mock bị từ chối khi NODE_ENV=production.
 */
export function configFromEnv(env: Record<string, string | undefined> = process.env) {
  const required = (name: string) => {
    const value = env[name]?.trim();
    if (!value) throw new Error(`Thiếu biến môi trường ${name}`);
    return value;
  };
  const providerKind = env.SECURITY_MCP_PROVIDER?.trim() || "core";
  if (providerKind === "mock" && env.NODE_ENV === "production") throw new Error("Không dùng provider mock ở production");
  const provider =
    providerKind === "mock"
      ? new MockSecurityProvider({ scopes: [loadFixtureScope()] })
      : providerKind === "core"
        ? new RealSecurityProvider(
            new CoreClient({
              baseUrl: new URL(required("SECURITY_CORE_API_URL")),
              credential: () => required("SECURITY_CORE_API_TOKEN"),
            }),
          )
        : (() => {
            throw new Error(`SECURITY_MCP_PROVIDER không hợp lệ: ${providerKind}`);
          })();
  return {
    port: Number.parseInt(env.SECURITY_MCP_PORT?.trim() || "8790", 10),
    path: env.SECURITY_MCP_PATH?.trim() || "/mcp",
    options: {
      provider,
      verifyAccessToken: createAccessTokenVerifier({
        issuers: required("SECURITY_MCP_ACCESS_ISSUERS").split(",").map((s) => s.trim()).filter(Boolean),
        audience: required("SECURITY_MCP_ACCESS_AUDIENCE"),
        keys: new URL(required("SECURITY_MCP_ACCESS_JWKS_URL")),
      }),
    } satisfies SecurityMcpOptions,
  };
}

export function startSecurityMcpServer(config = configFromEnv()) {
  if (!Number.isInteger(config.port) || config.port <= 0) throw new Error("SECURITY_MCP_PORT không hợp lệ");
  const handle = createSecurityMcpHandler(config.options);
  return serve({
    port: config.port,
    fetch: (request) =>
      new URL(request.url).pathname === config.path ? handle(request) : new Response("Not found", { status: 404 }),
  });
}

if (import.meta.main) {
  const server = startSecurityMcpServer();
  console.log(`[security-mcp] listening on ${server.url}`);
}
