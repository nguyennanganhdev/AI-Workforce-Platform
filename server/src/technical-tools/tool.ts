import { z } from "zod";
import type { ToolContext } from "./contracts/context";
import type { Provenance, ToolError, ToolStatus } from "./contracts/envelope";
import type { AssetReadPort } from "./ports/asset-read";
import type { Clock } from "./ports/clock";
import type { ExecutorResultStore } from "./ports/executor-result-store";
import type { InterruptionReadPort } from "./ports/interruption-read";
import type { MaintenanceReadPort } from "./ports/maintenance-read";
import type { MeasurementStore } from "./ports/measurement-store";
import type { SensorReadPort } from "./ports/sensor-read";
import type { SopProfilePort, SopReadPort } from "./ports/sop-read";
import type { WorkOrderReadPort } from "./ports/work-order-read";

/** What a tool reaches its data through. One field per port, added as tools need them. */
export type ToolDependencies = {
  interruptions: InterruptionReadPort;
  sop: SopReadPort;
  sopProfiles: SopProfilePort;
  assets: AssetReadPort;
  sensors: SensorReadPort;
  maintenance: MaintenanceReadPort;
  workOrders: WorkOrderReadPort;
  measurements: MeasurementStore;
  executorResults: ExecutorResultStore;
  clock: Clock;
};

/** What a tool decided, before the host wraps it in the response envelope. */
export type ToolOutcome<TData> = {
  status: ToolStatus;
  data: TData | null;
  errors?: ToolError[];
  missingFields?: string[];
  provenance?: Provenance[];
  /** How many records came back, for the audit entry. */
  resultCount?: number;
};

/**
 * - `read` changes nothing and may be retried after a transient failure.
 * - `write` records something and needs an idempotency key.
 * - `request` raises something for a person to approve and never acts on it.
 */
export type ToolEffect = "read" | "write" | "request";

type ToolDefinition<TInput extends { building_id: string }, TOutput> = {
  /** The name in docs/teams/quang/tools.md, e.g. `technical.get_active_outage`. */
  name: string;
  version: string;
  description: string;
  effect: ToolEffect;
  /** The grant a caller must hold, checked before the input is even read. */
  capability: string;
  timeoutMs: number;
  inputSchema: z.ZodType<TInput>;
  outputSchema: z.ZodType<TOutput>;
  run(
    context: ToolContext,
    input: TInput,
    dependencies: ToolDependencies,
  ): Promise<ToolOutcome<TOutput>>;
};

/** A tool with its input and output types erased, so tools of different shapes fit in one list. */
export type TechnicalTool = Omit<
  ToolDefinition<{ building_id: string }, unknown>,
  "inputSchema" | "run"
> & {
  /** The name offered to a model, which may not contain a dot. */
  modelName: string;
  inputSchema: z.ZodType<{ building_id: string }>;
  run(
    context: ToolContext,
    input: { building_id: string },
    dependencies: ToolDependencies,
  ): Promise<ToolOutcome<unknown>>;
};

export function modelNameFor(name: string): string {
  return name.replace(".", "__");
}

/**
 * Every tool's input carries `building_id`, and the host checks it against the caller's grant
 * before `run` is reached, which is why the constraint is on the type rather than left to each tool.
 *
 * A tool that writes must also take an `idempotency_key`, and this refuses to define one that does
 * not. Checked here, when the module loads, rather than when a call arrives: a write tool without a
 * key would otherwise pass every test until the first retry wrote twice.
 */
export function defineTool<TInput extends { building_id: string }, TOutput>(
  definition: ToolDefinition<TInput, TOutput>,
): TechnicalTool {
  if (definition.effect !== "read") {
    const shape = z.toJSONSchema(definition.inputSchema) as {
      required?: string[];
    };
    if (!shape.required?.includes("idempotency_key")) {
      throw new Error(
        `${definition.name} writes, so its input must require an idempotency_key.`,
      );
    }
  }
  return {
    ...definition,
    modelName: modelNameFor(definition.name),
    // The host only calls `run` with what `inputSchema` has just parsed.
    run: (context, input, dependencies) =>
      definition.run(context, input as TInput, dependencies),
  };
}
