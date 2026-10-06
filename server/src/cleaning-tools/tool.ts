import { z } from "zod";
import type { ToolContext } from "../technical-tools/contracts/context";
import {
  modelNameFor,
  type ToolEffect,
  type ToolOutcome,
  type ToolDependencies,
} from "../technical-tools/tool";
import type { CleaningOperations } from "./ports/operations";

export type CleaningDependencies = ToolDependencies & {
  operations: CleaningOperations;
  /** Resolves category from trusted catalogue, never from model-supplied metadata. */
  isCleaningWorkOrder(
    tenantId: string,
    buildingId: string,
    workOrderId: string,
  ): Promise<boolean>;
  /** Trusted mapping of vendor specialty codes to cleaning, supplied by the deployment. */
  isCleaningSpecialty(
    tenantId: string,
    specialtyCode: string,
  ): Promise<boolean>;
};

type CleaningToolDefinition<I extends { building_id: string }, O> = {
  name: string;
  version: string;
  description: string;
  effect: ToolEffect;
  capability: string;
  timeoutMs: number;
  inputSchema: z.ZodType<I>;
  outputSchema: z.ZodType<O>;
  run(
    context: ToolContext,
    input: I,
    dependencies: CleaningDependencies,
  ): Promise<ToolOutcome<O>>;
};
export type CleaningTool = CleaningToolDefinition<
  { building_id: string },
  unknown
> & { modelName: string };

/** Same descriptor checks as the technical module, kept local to avoid changing that module. */
export function defineCleaningTool<I extends { building_id: string }, O>(
  definition: CleaningToolDefinition<I, O>,
): CleaningTool {
  if (definition.effect !== "read") {
    const schema = z.toJSONSchema(definition.inputSchema) as {
      required?: string[];
    };
    if (!schema.required?.includes("idempotency_key"))
      throw new Error(
        `${definition.name} writes, so its input must require an idempotency_key.`,
      );
  }
  return {
    ...definition,
    modelName: modelNameFor(definition.name),
    run: (context, input, dependencies) =>
      definition.run(context, input as I, dependencies),
  };
}
