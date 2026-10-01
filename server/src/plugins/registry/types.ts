/** A JSON Schema stored as plain JSON and handed to an agent runtime. */
export type ToolJsonSchema = Readonly<Record<string, unknown>>;

export type ToolVisibility = "builder" | "system" | "internal";
export type ToolEffect = "read" | "write";

export type ToolRetryPolicy = {
  /** Number of retries after the first failed attempt. */
  maxRetries: number;
  backoffMs: number;
};

export type ToolExecution =
  | {
      kind: "first-party";
      /** Stable handler key resolved by the internal tool gateway. */
      handler: string;
    }
  | {
      kind: "mcp";
      serverId: string;
      toolName: string;
    };

/**
 * Metadata used by Agent Builder and the runtime tool gateway.
 *
 * A descriptor advertises a capability. It never grants that capability: the
 * existing plugin grant and policy checks remain authoritative at call time.
 */
export type ToolDescriptor = {
  /** Globally unique, stable reference, for example `reporting/revenue-summary`. */
  ref: string;
  /** Tool name exposed to the agent runtime. */
  name: string;
  version: string;
  displayName: string;
  description: string;
  category: string;
  source: "first-party" | "mcp";

  inputSchema: ToolJsonSchema;
  outputSchema: ToolJsonSchema;

  visibility: ToolVisibility;
  /** `*` means every agent type. */
  allowedAgentTypes: readonly string[];
  requiredPermissions: readonly string[];

  effect: ToolEffect;
  destructive: boolean;
  timeoutMs: number;
  retry: ToolRetryPolicy;
  requiresIdempotencyKey: boolean;

  execution: ToolExecution;
};

export type ToolRegistryFilter = {
  visibility?: ToolVisibility;
  source?: ToolDescriptor["source"];
  agentType?: string;
};
