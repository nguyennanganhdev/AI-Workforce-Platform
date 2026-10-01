import { ZodError, type z } from "zod";
import {
  parseToolInput,
  parseToolOutput,
  technicalToolCatalog,
} from "./catalog";
import {
  type BuildingAccessPort,
  type ExecutionContext,
  requireBuildingAccess,
} from "./context";
import { ToolError } from "./errors";
import type { PortResult } from "./ports";
import {
  errorEnvelope,
  noticeEnvelope,
  successEnvelope,
  type ToolEnvelope,
} from "./response";
import type { TechnicalToolName, toolSchemas } from "./schemas";

type InputFor<N extends TechnicalToolName> = z.output<
  (typeof toolSchemas)[N]["input"]
>;
type OutputFor<N extends TechnicalToolName> = z.output<
  (typeof toolSchemas)[N]["output"]
>;

/** Shared boundary for the seven tools. The host supplies authenticated context and a service port. */
export async function runTechnicalTool<N extends TechnicalToolName>(
  name: N,
  rawInput: unknown,
  context: ExecutionContext,
  access: BuildingAccessPort,
  invoke: (
    input: InputFor<N>,
    context: ExecutionContext,
  ) => Promise<PortResult<OutputFor<N>>>,
): Promise<ToolEnvelope> {
  let input: InputFor<N>;
  try {
    input = parseToolInput(name, rawInput) as InputFor<N>;
  } catch (error) {
    if (error instanceof ZodError) {
      return errorEnvelope(
        context,
        new ToolError("INVALID_INPUT", "Invalid tool input."),
      );
    }
    return errorEnvelope(context, error);
  }
  try {
    await requireBuildingAccess(
      context,
      name,
      technicalToolCatalog[name].capability,
      input.building_id,
      access,
    );
    const result = await invoke(input, context);
    const data = parseToolOutput(name, result.data) as Record<string, unknown>;
    if (result.notice) {
      return noticeEnvelope(context, data, result.provenance, result.notice);
    }
    return successEnvelope(context, data, result.provenance);
  } catch (error) {
    if (error instanceof ZodError) {
      // A malformed adapter result is an internal fault, never a request validation error.
      return errorEnvelope(
        context,
        new ToolError("INTERNAL_ERROR", "The tool returned invalid data."),
      );
    }
    return errorEnvelope(context, error);
  }
}
