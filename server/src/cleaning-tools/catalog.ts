import { z } from "zod";
import { canonicalToolName } from "../technical-tools/catalog";
import { cleaningTechnicalTools } from "./tools/technical-counterparts";
import {
  listStaffTool,
  readWorkTool,
  createWorkTool,
  dispatchTool,
  updateStatusTool,
} from "./tools/operations";
export const cleaningTools = [
  ...cleaningTechnicalTools,
  listStaffTool,
  readWorkTool,
  createWorkTool,
  dispatchTool,
  updateStatusTool,
] as const;
export const findCleaningTool = (name: string) =>
  cleaningTools.find((t) => t.name === canonicalToolName(name));
export const describeCleaningTools = () =>
  cleaningTools.map((t) => ({
    name: t.name,
    model_name: t.modelName,
    version: t.version,
    description: t.description,
    side_effect: t.effect,
    required_capability: t.capability,
    timeout_ms: t.timeoutMs,
    retry: t.effect === "read" ? "transient_errors" : "reconcile_first",
    requires_idempotency_key: t.effect !== "read",
    input_schema: z.toJSONSchema(t.inputSchema),
    output_schema: z.toJSONSchema(t.outputSchema),
  }));
