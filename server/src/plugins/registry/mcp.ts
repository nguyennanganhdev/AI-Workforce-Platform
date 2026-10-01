import type { ToolDescriptor, ToolJsonSchema } from "./types";
import { validateToolDescriptor } from "./validation";

/** The database/MCP fields needed to publish one tool in the common registry. */
export type McpRegistryTool = {
  serverId: string;
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  version?: string | null;
  effect?: "read" | "write";
  destructive?: boolean;
};

const MCP_RESULT_SCHEMA: ToolJsonSchema = Object.freeze({
  type: "object",
  properties: {
    text: { type: "string" },
    isError: { type: "boolean" },
    truncated: { type: "boolean" },
  },
  required: ["text", "isError", "truncated"],
  additionalProperties: false,
});

/** Convert a discovered `mcp_tools` row into the platform-wide descriptor. */
export function descriptorFromMcpTool(tool: McpRegistryTool): ToolDescriptor {
  const effect = tool.effect ?? "write";
  const destructive = tool.destructive ?? false;

  return validateToolDescriptor({
    ref: `${tool.serverId}/${tool.name}`,
    name: tool.name,
    version: tool.version?.trim() || "unversioned",
    displayName: tool.name,
    description: tool.description,
    category: "mcp",
    source: "mcp",
    inputSchema: tool.inputSchema,
    outputSchema: MCP_RESULT_SCHEMA,
    visibility: "builder",
    allowedAgentTypes: ["*"],
    // The existing plugin grant remains the authority for this MCP ref.
    requiredPermissions: [],
    effect,
    destructive,
    timeoutMs: 30_000,
    retry: {
      // Retrying a write without an idempotency contract could repeat its effect.
      maxRetries: effect === "read" ? 2 : 0,
      backoffMs: effect === "read" ? 500 : 0,
    },
    requiresIdempotencyKey: false,
    execution: {
      kind: "mcp",
      serverId: tool.serverId,
      toolName: tool.name,
    },
  });
}

export function descriptorsFromMcpTools(
  tools: readonly McpRegistryTool[],
): readonly ToolDescriptor[] {
  return Object.freeze(tools.map(descriptorFromMcpTool));
}
