import { z } from "zod";
import type { TechnicalTool } from "./tool";
import { appendMaintenanceHistoryTool } from "./tools/append-maintenance-history";
import { areaRestrictionRequestTool } from "./tools/area-restriction-request";
import { assetReadTool } from "./tools/asset-read";
import { getActiveOutageTool } from "./tools/get-active-outage";
import { maintenanceHistoryReadTool } from "./tools/maintenance-history-read";
import { recordMeasurementTool } from "./tools/record-measurement";
import { sensorReadTool } from "./tools/sensor-read";
import { sopKbRetrieveTool } from "./tools/sop-kb-retrieve";
import { submitExecutorResultTool } from "./tools/submit-executor-result";
import { utilityIsolationRequestTool } from "./tools/utility-isolation-request";
import { utilityScheduleReadTool } from "./tools/utility-schedule-read";
import { verifyResolutionTool } from "./tools/verify-resolution";

/** Every technical tool this deployment implements. Twelve of the fourteen in tools.md so far. */
export const technicalTools: readonly TechnicalTool[] = [
  getActiveOutageTool,
  utilityScheduleReadTool,
  sopKbRetrieveTool,
  assetReadTool,
  sensorReadTool,
  maintenanceHistoryReadTool,
  recordMeasurementTool,
  submitExecutorResultTool,
  verifyResolutionTool,
  appendMaintenanceHistoryTool,
  utilityIsolationRequestTool,
  areaRestrictionRequestTool,
];

/**
 * The name in tools.md, from whichever spelling a caller arrives with.
 *
 * A model tool name may not contain a dot, so a tool is offered as `technical__get_active_outage`.
 * `/api/agent-tools/call` then rewrites the first `__` to `/` before it asks a deployment tool
 * caller (`parseAgentToolCallInput`), so the same tool reaches this module as
 * `technical/get_active_outage`. Both come back to the one dotted name the catalogue is keyed on.
 */
export function canonicalToolName(name: string): string {
  return name
    .trim()
    .replace(/^mcp__/, "")
    .replace("__", ".")
    .replace("/", ".");
}

export function findTechnicalTool(name: string): TechnicalTool | undefined {
  const canonical = canonicalToolName(name);
  return technicalTools.find((tool) => tool.name === canonical);
}

/**
 * The catalogue as plain data (task Q01): what each tool is called, what it takes and returns, what
 * it may do and what a caller must hold.
 *
 * JSON Schema rather than the Zod objects, so the Python coordination runtime reads the same
 * contract the TypeScript host enforces instead of a copy somebody keeps in step by hand.
 */
export function describeTechnicalTools() {
  return technicalTools.map((tool) => ({
    name: tool.name,
    model_name: tool.modelName,
    version: tool.version,
    description: tool.description,
    side_effect: tool.effect,
    required_capability: tool.capability,
    timeout_ms: tool.timeoutMs,
    retry: tool.effect === "read" ? "transient_errors" : "reconcile_first",
    requires_idempotency_key: tool.effect !== "read",
    input_schema: z.toJSONSchema(tool.inputSchema),
    output_schema: z.toJSONSchema(tool.outputSchema),
  }));
}
