import { type TechnicalToolName, toolSchemas } from "./schemas";

export interface ToolDefinition {
  name: TechnicalToolName;
  version: "1.0";
  capability: string;
  effect: "read" | "append";
  idempotency: "none" | "required";
  /** Host policy may override this with a tighter limit. */
  timeoutMs: number;
}

export const technicalToolCatalog = {
  "sop_kb.retrieve": {
    name: "sop_kb.retrieve",
    version: "1.0",
    capability: "sop:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "asset.read": {
    name: "asset.read",
    version: "1.0",
    capability: "asset:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "sensor.read": {
    name: "sensor.read",
    version: "1.0",
    capability: "sensor:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "maintenance_history.read": {
    name: "maintenance_history.read",
    version: "1.0",
    capability: "maintenance:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "technical.get_active_outage": {
    name: "technical.get_active_outage",
    version: "1.0",
    capability: "interruption:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "utility_schedule.read": {
    name: "utility_schedule.read",
    version: "1.0",
    capability: "interruption:read",
    effect: "read",
    idempotency: "none",
    timeoutMs: 5000,
  },
  "maintenance_history.append": {
    name: "maintenance_history.append",
    version: "1.0",
    capability: "maintenance:append",
    effect: "append",
    idempotency: "required",
    timeoutMs: 10000,
  },
} as const satisfies Record<TechnicalToolName, ToolDefinition>;

/** Runtime validation is kept alongside the catalog, independent of TS callers. */
export function parseToolInput(
  name: TechnicalToolName,
  input: unknown,
): unknown {
  return toolSchemas[name].input.parse(input);
}

export function parseToolOutput(
  name: TechnicalToolName,
  output: unknown,
): unknown {
  return toolSchemas[name].output.parse(output);
}
