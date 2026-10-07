import {
  createTechnicalToolHost,
  type HostDependencies,
  type HostOptions,
} from "../technical-tools/host";
import type { ToolCaller } from "../technical-tools/ports/context-resolver";
import type { TechnicalTool } from "../technical-tools/tool";
import { findCleaningTool } from "./catalog";
import type { CleaningDependencies, CleaningTool } from "./tool";

export type CleaningHostDependencies = CleaningDependencies &
  Pick<
    HostDependencies,
    "contextResolver" | "audit" | "idempotency" | "buildingAccess"
  >;

/** Reuse the existing technical host unchanged; bind only the cleaning catalogue/dependencies. */
export function createCleaningToolHost(
  dependencies: CleaningHostDependencies,
  options: HostOptions = {},
) {
  const host = createTechnicalToolHost(dependencies, options);
  return {
    find: findCleaningTool,
    call(
      caller: ToolCaller,
      tool: CleaningTool,
      args: Record<string, unknown>,
    ) {
      const delegated: TechnicalTool = {
        ...tool,
        run: (context, input) => tool.run(context, input, dependencies),
      };
      return host.call(caller, delegated, args);
    },
  };
}
