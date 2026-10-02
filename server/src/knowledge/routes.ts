import { Hono } from "hono";
import {
  type SearchKnowledgeError,
  searchKnowledgeDto,
  searchKnowledgeRequest,
} from "./contract";
import { EmbeddingError } from "./embedder";
import { type RetrieveDeps, retrieve } from "./retrieve";
import type { AuthorizedContext } from "./types";

/**
 * What the backend's authorization answers for one search. Implemented by Chiến's authz service:
 * it reads the caller's credential from the request (agent runtime token, session binding), works
 * out whose behalf the agent acts on, and turns that into scopes. Nothing in the request body is
 * trusted as authority; `scopeId` is only a choice among scopes the caller already has.
 */
export type KnowledgeAuthorization =
  | { ok: true; context: AuthorizedContext; knowledgeBaseId: string }
  | {
      ok: false;
      status: 401;
      code: "unauthenticated";
      message: string;
    }
  | { ok: false; status: 403; code: "forbidden"; message: string }
  | {
      ok: false;
      status: 409;
      code: "scope_required";
      message: string;
      /** The caller's scopes, for the agent to ask the resident which one they mean. */
      choices: { scopeId: string; label: string }[];
    };

export type AuthorizeKnowledgeSearch = (
  request: Request,
  ask: { scopeId?: string },
) => Promise<KnowledgeAuthorization>;

export type KnowledgeRouteDeps = {
  authorize: AuthorizeKnowledgeSearch;
  retrieval: RetrieveDeps;
  /** Where unexpected failures are reported; the response never carries their detail. */
  onError?: (error: unknown) => void;
};

function failure(
  code: SearchKnowledgeError["error"]["code"],
  message: string,
  choices?: { scopeId: string; label: string }[],
): SearchKnowledgeError {
  return { error: { code, message, ...(choices ? { choices } : {}) } };
}

/**
 * `POST /search` for agent runtimes, mounted by the server at `/internal/knowledge`.
 *
 * Authorization happens before anything is embedded or read, and its answer is the only authority
 * retrieval sees. A caller with several scopes and no choice gets 409 `scope_required` with the
 * choices, so Reception asks the resident instead of answering for the wrong building.
 */
export function createKnowledgeRoutes(deps: KnowledgeRouteDeps) {
  const routes = new Hono();

  routes.post("/search", async (context) => {
    const body = await context.req.json().catch(() => undefined);
    const parsed = searchKnowledgeRequest.safeParse(body);
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      const where = issue?.path.join(".") || "body";
      return context.json(
        failure("invalid_request", `${where}: ${issue?.message ?? "invalid"}`),
        400,
      );
    }

    let authorization: KnowledgeAuthorization;
    try {
      authorization = await deps.authorize(context.req.raw, {
        scopeId: parsed.data.scopeId,
      });
    } catch (error) {
      deps.onError?.(error);
      return context.json(failure("internal", "Authorization failed."), 500);
    }
    if (!authorization.ok) {
      return context.json(
        failure(
          authorization.code,
          authorization.message,
          authorization.code === "scope_required"
            ? authorization.choices
            : undefined,
        ),
        authorization.status,
      );
    }

    try {
      const result = await retrieve(deps.retrieval, {
        context: authorization.context,
        knowledgeBaseId: authorization.knowledgeBaseId,
        query: parsed.data.query,
        topK: parsed.data.topK,
      });
      return context.json(searchKnowledgeDto(result), 200);
    } catch (error) {
      deps.onError?.(error);
      if (error instanceof EmbeddingError) {
        return context.json(
          failure(
            "embedding_unavailable",
            "The embedding provider did not answer. Retry once.",
          ),
          502,
        );
      }
      return context.json(failure("internal", "Search failed."), 500);
    }
  });

  return routes;
}
