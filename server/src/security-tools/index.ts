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
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { serve } from "bun";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { createLocalJWKSet, type JSONWebKeySet } from "jose";
import { CoreClient } from "./client";
import { readBodyText } from "./common/body";
import {
  type AccessTokenVerifier,
  AuthenticationError,
  correlationIdFrom,
  createAccessTokenVerifier,
  HEADERS,
  type IssuerKeys,
  rawWriteHeaders,
  type RequestIdentity,
} from "./common/context";
import { createWriteGuard } from "./common/execution-grant";
import { parseStrictJson, StrictJsonError } from "./common/strict-json";
import { loadFixtureScope, MockSecurityProvider } from "./providers/mock-provider";
import { createWriteHandlers } from "./providers/mock-write";
import { RealSecurityProvider } from "./providers/real-provider";
import { registerSecurityTools, type SecurityToolsOptions } from "./tools";

/** Profile MCP được pin cho tích hợp; không tuyên bố đây là bản mới nhất. */
export const MCP_PROTOCOL_VERSION = "2025-11-25";
export const SERVER_INFO = { name: "security-mcp", version: "0.3.0" } as const;
const MAX_BODY_BYTES = 1024 * 1024;

export type SecurityMcpOptions = SecurityToolsOptions & {
  verifyAccessToken: AccessTokenVerifier;
  maxBodyBytes?: number;
  /**
   * Origin được phép gửi request (dạng `https://host[:port]`). Request có header Origin ngoài danh
   * sách bị 403; mặc định rỗng vì caller là service, không phải trình duyệt.
   */
  allowedOrigins?: readonly string[];
};

/** Handler Web Standard: gắn vào Bun.serve, Hono `app.all(path, (c) => handler(c.req.raw))`... */
export function createSecurityMcpHandler(options: SecurityMcpOptions): (request: Request) => Promise<Response> {
  const allowedOrigins = new Set((options.allowedOrigins ?? []).map((origin) => new URL(origin).origin));
  return async (request) => {
    const correlationId = correlationIdFrom(request.headers);
    const reply = (status: number, body: unknown, headers: Record<string, string> = {}) =>
      Response.json(body, { status, headers: { [HEADERS.correlationId]: correlationId, ...headers } });

    // Chống DNS rebinding (MCP Streamable HTTP): có Origin thì phải nằm trong allowlist. Caller
    // service-to-service không gửi Origin nên không bị ảnh hưởng.
    const origin = request.headers.get("origin");
    if (origin !== null && !allowedOrigins.has(origin)) return reply(403, rpcError(-32000, "Origin không được phép"));

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
      const read = await readBodyText(request, options.maxBodyBytes ?? MAX_BODY_BYTES);
      if (!read.ok && read.reason === "too_large") return reply(413, rpcError(-32600, "Request quá lớn"));
      if (!read.ok) return reply(400, rpcError(-32700, "Parse error"));
      body = parseStrictJson(read.text);
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
 * - SECURITY_MCP_ACCESS_ISSUERS: JSON `{"<issuer>": "<jwks>"}`, mỗi issuer một JWKS; SECURITY_MCP_ACCESS_AUDIENCE
 * - SECURITY_MCP_GRANT_ISSUERS: JSON cùng dạng cho execution grant. Không đặt thì không bật WRITE
 *   (tools/list ẩn WRITE, tools/call từ chối).
 * - SECURITY_MCP_ALLOWED_ORIGINS (phân tách dấu phẩy, tùy chọn)
 * - SECURITY_MCP_PROVIDER = core | mock; với core: SECURITY_CORE_API_URL, SECURITY_CORE_API_TOKEN
 *
 * `<jwks>` là URL HTTPS, hoặc đường dẫn tới file jwks.json cục bộ (chỉ khi NODE_ENV khác production,
 * để test/dev ký token và grant bằng key local). Provider mock bị từ chối khi NODE_ENV=production.
 */
export function configFromEnv(env: Record<string, string | undefined> = process.env) {
  const required = (name: string) => {
    const value = env[name]?.trim();
    if (!value) throw new Error(`Thiếu biến môi trường ${name}`);
    return value;
  };
  const production = env.NODE_ENV === "production";
  const providerKind = env.SECURITY_MCP_PROVIDER?.trim() || "core";
  if (providerKind === "mock" && production) throw new Error("Không dùng provider mock ở production");
  const grantIssuers = env.SECURITY_MCP_GRANT_ISSUERS?.trim();
  const provider =
    providerKind === "mock"
      ? new MockSecurityProvider({ scopes: [loadFixtureScope()], writeHandlers: createWriteHandlers() })
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
        issuers: issuerKeysFromEnv("SECURITY_MCP_ACCESS_ISSUERS", required("SECURITY_MCP_ACCESS_ISSUERS"), production),
        audience: required("SECURITY_MCP_ACCESS_AUDIENCE"),
      }),
      writeGuard: grantIssuers
        ? createWriteGuard({ issuers: issuerKeysFromEnv("SECURITY_MCP_GRANT_ISSUERS", grantIssuers, production) })
        : undefined,
      allowedOrigins: (env.SECURITY_MCP_ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean),
    } satisfies SecurityMcpOptions,
  };
}

/** Parse map issuer → JWKS. URL giữ nguyên (HTTPS do verifier kiểm); giá trị khác là file jwks.json cục bộ. */
function issuerKeysFromEnv(name: string, value: string, production: boolean): Record<string, IssuerKeys> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    parsed = null;
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed) || Object.keys(parsed).length === 0) {
    throw new Error(`${name} phải là JSON {"<issuer>": "<jwks>"} có ít nhất một issuer`);
  }
  const issuers: Record<string, IssuerKeys> = {};
  for (const [issuer, source] of Object.entries(parsed)) {
    if (typeof source !== "string" || source.trim() === "") throw new Error(`${name}: JWKS của ${issuer} không hợp lệ`);
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(source)) {
      issuers[issuer] = new URL(source);
      continue;
    }
    if (production) throw new Error(`${name}: JWKS cục bộ chỉ dùng ngoài production (${issuer})`);
    issuers[issuer] = createLocalJWKSet(JSON.parse(readFileSync(resolve(source), "utf8")) as JSONWebKeySet);
  }
  return issuers;
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
