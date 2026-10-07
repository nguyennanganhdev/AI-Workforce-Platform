import type { DeploymentToolCaller } from "../app";
import { isErrorStatus } from "../technical-tools/contracts/envelope";
import type { HostOptions } from "../technical-tools/host";
import { createCleaningToolHost, type CleaningHostDependencies } from "./host";
/** Exported seam only: mounting the caller and granting its tools belong to the integration owner. */
export function createCleaningToolCaller(
  deps: CleaningHostDependencies,
  options: HostOptions = {},
): DeploymentToolCaller {
  const host = createCleaningToolHost(deps, options);
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
