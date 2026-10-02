import type { DeploymentToolCaller } from "../app";
import { isErrorStatus } from "./contracts/envelope";
import {
  createTechnicalToolHost,
  type HostDependencies,
  type HostOptions,
} from "./host";

/**
 * The technical tools as a `DeploymentToolCaller`: the seam `/api/agent-tools/call` already offers
 * to tools the server owns.
 *
 * The route has verified the agent's token and the signed run before this is reached, so `botId`
 * and `actorId` are proven. `null` means the name is not one of ours, and the route goes on to the
 * plugin store as it would have without this. The answer's `text` is the response envelope as JSON,
 * because `{ text, isError }` is all that route carries back to a Bot.
 *
 * Wiring it into `createApp` is the server entrypoint's job, not this module's.
 */
export function createTechnicalToolCaller(
  dependencies: HostDependencies,
  options: HostOptions = {},
): DeploymentToolCaller {
  const host = createTechnicalToolHost(dependencies, options);
  return async ({ name, args, botId, actorId, initiator }) => {
    const tool = host.find(name);
    if (!tool) return null;
    const envelope = await host.call(
      { botId, actorId, ...(initiator ? { initiator } : {}) },
      tool,
      args,
    );
    return {
      text: JSON.stringify(envelope),
      isError: isErrorStatus(envelope.status),
    };
  };
}
