import { FIRST_PARTY_TOOLS } from "./first-party";
import { descriptorsFromMcpTools, type McpRegistryTool } from "./mcp";
import type {
  ToolDescriptor,
  ToolRegistryFilter,
  ToolVisibility,
} from "./types";
import { validateToolDescriptors } from "./validation";

export * from "./first-party";
export * from "./mcp";
export * from "./types";
export * from "./validation";

export type CreateToolRegistryOptions = {
  firstPartyTools?: readonly ToolDescriptor[];
  mcpTools?: readonly McpRegistryTool[];
};

/** Read-only catalogue used by Agent Builder and tool-resolution services. */
export class ToolRegistry {
  readonly #tools: readonly ToolDescriptor[];
  readonly #byRef: ReadonlyMap<string, ToolDescriptor>;

  constructor(descriptors: readonly ToolDescriptor[]) {
    this.#tools = validateToolDescriptors(descriptors);
    this.#byRef = new Map(this.#tools.map((tool) => [tool.ref, tool]));
  }

  get(ref: string): ToolDescriptor | null {
    return this.#byRef.get(ref) ?? null;
  }

  list(filter: ToolRegistryFilter = {}): readonly ToolDescriptor[] {
    return this.#tools.filter((tool) => {
      if (filter.visibility && tool.visibility !== filter.visibility) {
        return false;
      }
      if (filter.source && tool.source !== filter.source) return false;
      if (
        filter.agentType &&
        !tool.allowedAgentTypes.includes("*") &&
        !tool.allowedAgentTypes.includes(filter.agentType)
      ) {
        return false;
      }
      return true;
    });
  }

  /** Tools that may be displayed for a particular Agent Builder template. */
  forBuilder(agentType: string): readonly ToolDescriptor[] {
    return this.list({ visibility: "builder", agentType });
  }

  byVisibility(visibility: ToolVisibility): readonly ToolDescriptor[] {
    return this.list({ visibility });
  }
}

/** Build one catalogue from reviewed first-party tools and discovered MCP rows. */
export function createToolRegistry(
  options: CreateToolRegistryOptions = {},
): ToolRegistry {
  return new ToolRegistry([
    ...(options.firstPartyTools ?? FIRST_PARTY_TOOLS),
    ...descriptorsFromMcpTools(options.mcpTools ?? []),
  ]);
}
