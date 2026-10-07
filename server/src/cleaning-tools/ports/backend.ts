import type { ToolContext } from "../../technical-tools/contracts/context";

export type BackendRequest = {
  method: "GET" | "POST" | "PATCH";
  path: string;
  query?: Record<string, string | number>;
  body?: Record<string, unknown>;
  idempotencyKey?: string;
};

/**
 * Supplied by the deployment: resolve the verified context to existing V3 handlers.
 * No tool manufactures a cookie, actor or admin flag. The existing host's idempotency port
 * handles retries; backend handlers retain their version, lock and authority checks.
 */
export type CleaningBackend = {
  request(context: ToolContext, request: BackendRequest): Promise<unknown>;
};

export class CleaningBackendError extends Error {
  constructor(public readonly status: 400 | 401 | 403 | 404 | 409 | 422 | 500) {
    super(`Cleaning backend rejected the operation (${status}).`);
  }
}
