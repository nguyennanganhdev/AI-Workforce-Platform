import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { client, tryClient } from "@/lib/client";
import type {
  AgentCreationRequest,
  FactoryErrorResponse,
} from "../../../../agent-factory/src/contracts";
import {
  type AgentProfile,
  type AgentVisibility,
  agentApiPath,
  agentKeys,
  type FactoryArtifact,
  factoryApiPath,
} from "./queries";

export type AgentInput = {
  name: string;
  title: string;
  roleDescription: string;
  visibility: AgentVisibility;
  /** Where this coworker runs. Empty means the Bot in the box. */
  endpoint?: string;
  /** Write-only auth value; omitted when the user leaves the key field empty. */
  auth?: { header: string; value: string };
};

/** The sentence for every write here, since they all fail the same way to a reader. */
const FALLBACK = "Coworker operation failed";

/** Server-derived fields are invalidated instead of patched by hand. */
function invalidateAgents(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: agentKeys.all });
}

export function createAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: (input: AgentInput): Promise<AgentProfile> =>
      client("/api/agents", "agent", {
        method: "POST",
        body: input,
        fallback: FALLBACK,
      }),
    onSuccess: () => invalidateAgents(queryClient),
  });
}

/**
 * A factory request that did not produce an artifact. `status` 0 means no answer arrived at all, so
 * the server may or may not have acted; `body` is the server's safe envelope when there was one.
 */
export class FactoryRequestError extends Error {
  constructor(
    readonly status: number,
    readonly body: FactoryErrorResponse | null,
  ) {
    super(body?.error ?? "The server's answer did not arrive.");
  }
}

async function factoryRequest(
  path: string,
  options: Parameters<typeof tryClient>[1],
  success: readonly number[],
) {
  const response = await tryClient(path, options).catch(() => {
    throw new FactoryRequestError(0, null);
  });
  const body = (await response.json().catch(() => null)) as unknown;
  if (!success.includes(response.status) || !body || typeof body !== "object")
    throw new FactoryRequestError(
      response.status,
      body && typeof body === "object" && "error" in body
        ? (body as FactoryErrorResponse)
        : null,
    );
  return { status: response.status, body };
}

/**
 * Build a coworker from name, role and description. 201 is ready, 202 is saved but waiting for
 * access; anything else throws. The caller owns the key: the same one for an unchanged retry, so a
 * lost answer replays instead of building a second coworker.
 */
export function constructAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (variables: {
      request: AgentCreationRequest;
      idempotencyKey: string;
    }) => {
      const { status, body } = await factoryRequest(
        "/api/agent-factory/constructions",
        {
          method: "POST",
          body: variables.request,
          headers: { "Idempotency-Key": variables.idempotencyKey },
        },
        [201, 202],
      );
      return { status: status as 201 | 202, artifact: body as FactoryArtifact };
    },
    // Settled, not success: an answer lost on the way back may still have created the coworker.
    onSettled: () => invalidateAgents(queryClient),
  });
}

/**
 * Re-read the creator's grants and connections for the stored artifact. Never builds or grants
 * anything; a coworker still waiting answers 409 `RESOURCES_PENDING`.
 */
export function recheckFactoryMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (variables: { agentId: string; specHash: string }) =>
      (
        await factoryRequest(
          `${factoryApiPath(variables.agentId)}/recheck`,
          { method: "POST", body: { specHash: variables.specHash } },
          [200],
        )
      ).body as FactoryArtifact,
    onSettled: () => invalidateAgents(queryClient),
  });
}

export function updateAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: (variables: {
      agentId: string;
      input: AgentInput;
    }): Promise<AgentProfile> =>
      client(agentApiPath(variables.agentId), "agent", {
        method: "PATCH",
        body: variables.input,
        fallback: FALLBACK,
      }),
    onSuccess: () => invalidateAgents(queryClient),
  });
}

export function duplicateAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: (agentId: string): Promise<AgentProfile> =>
      client(`${agentApiPath(agentId)}/duplicate`, "agent", {
        method: "POST",
        fallback: FALLBACK,
      }),
    onSuccess: () => invalidateAgents(queryClient),
  });
}

export function setAgentHiddenMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (variables: { agentId: string; hidden: boolean }) => {
      await client(
        `${agentApiPath(variables.agentId)}/${variables.hidden ? "hide" : "unhide"}`,
        { method: "POST", fallback: FALLBACK },
      );
    },
    onSuccess: () => invalidateAgents(queryClient),
  });
}

export function deleteAgentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (agentId: string) => {
      await client(agentApiPath(agentId), {
        method: "DELETE",
        fallback: FALLBACK,
      });
    },
    onSuccess: () => invalidateAgents(queryClient),
  });
}

/**
 * Issue this coworker a credential for calling tools back, and hand it over once.
 *
 * The token is in this response and nowhere else, ever again, so the caller has to show it to the
 * person immediately. Calling this on a coworker that already has one rotates it, which is how a
 * leaked token is retired.
 */
export function issueCallbackTokenMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: (agentId: string): Promise<string> =>
      client(`${agentApiPath(agentId)}/callback-token`, "token", {
        method: "POST",
        fallback: FALLBACK,
      }),
    onSuccess: () => invalidateAgents(queryClient),
  });
}

/** Take the credential away. The coworker may still talk; it may not reach anything outside a chat. */
export function revokeCallbackTokenMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (agentId: string) => {
      await client(`${agentApiPath(agentId)}/callback-token`, {
        method: "DELETE",
        fallback: FALLBACK,
      });
    },
    onSuccess: () => invalidateAgents(queryClient),
  });
}

/**
 * Whether one Bot may hand work to another.
 *
 * The same `plugin_grants` write every other grant makes, with `kind: "bot"`, so the audit row and
 * the refusals are the ones already in place: an administrator only, never a Bot on itself, and
 * never onto a Bot that does not exist.
 *
 * DIRECTIONAL, and the two ids are easy to swap: `agentId` is the Bot doing the asking and `ref` is
 * the Bot it may reach. Granted the other way round it reads as working and hands over nothing.
 */
export function setHandoffGrantMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (variables: {
      /** The Bot doing the asking. */
      agentId: string;
      /** The Bot it may reach. */
      ref: string;
      granted: boolean;
    }) => {
      if (variables.granted) {
        await client("/api/plugins/grants", {
          method: "POST",
          body: { kind: "bot", ref: variables.ref, agentId: variables.agentId },
          fallback: FALLBACK,
        });
        return;
      }
      await client(
        `/api/plugins/grants?kind=bot&ref=${encodeURIComponent(variables.ref)}&agentId=${encodeURIComponent(variables.agentId)}`,
        { method: "DELETE", fallback: FALLBACK },
      );
    },
    onSuccess: () => invalidateAgents(queryClient),
  });
}
