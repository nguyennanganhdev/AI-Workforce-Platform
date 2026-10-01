import type { z } from "zod";
import type { ExecutionContext } from "./context";
import type { Provenance } from "./response";
import type {
  assetReadInput,
  assetReadOutput,
  maintenanceAppendInput,
  maintenanceAppendOutput,
  maintenanceReadInput,
  maintenanceReadOutput,
  outageInput,
  outageOutput,
  scheduleInput,
  scheduleOutput,
  sensorReadInput,
  sensorReadOutput,
  sopRetrieveInput,
  sopRetrieveOutput,
} from "./schemas";

export interface PortResult<T> {
  data: T;
  provenance: readonly Provenance[];
  /** Keep safe candidate/readings data when the caller needs clarification or data is stale. */
  notice?: {
    code: "NEEDS_INPUT" | "STALE_DATA";
    message: string;
    missingFields?: readonly string[];
  };
}

export interface SopPort {
  retrieve(
    context: ExecutionContext,
    input: z.output<typeof sopRetrieveInput>,
  ): Promise<PortResult<z.output<typeof sopRetrieveOutput>>>;
}

export interface AssetPort {
  read(
    context: ExecutionContext,
    input: z.output<typeof assetReadInput>,
  ): Promise<PortResult<z.output<typeof assetReadOutput>>>;
}

export interface SensorPort {
  read(
    context: ExecutionContext,
    input: z.output<typeof sensorReadInput>,
  ): Promise<PortResult<z.output<typeof sensorReadOutput>>>;
}

export interface MaintenancePort {
  read(
    context: ExecutionContext,
    input: z.output<typeof maintenanceReadInput>,
  ): Promise<PortResult<z.output<typeof maintenanceReadOutput>>>;

  /** Check the result, work order, asset, actor and building before any write. */
  appendVerified(
    context: ExecutionContext,
    input: z.output<typeof maintenanceAppendInput>,
  ): Promise<PortResult<z.output<typeof maintenanceAppendOutput>>>;
}

export interface InterruptionPort {
  getActiveOutages(
    context: ExecutionContext,
    input: z.output<typeof outageInput>,
  ): Promise<PortResult<z.output<typeof outageOutput>>>;

  readSchedule(
    context: ExecutionContext,
    input: z.output<typeof scheduleInput>,
  ): Promise<PortResult<z.output<typeof scheduleOutput>>>;
}
