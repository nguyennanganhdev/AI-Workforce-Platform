import type { Measurement } from "../domain/measurement";

/** Where recorded measurements are kept. Append-only: there is no update and no delete. */
export type MeasurementStore = {
  append(measurement: Measurement): Promise<void>;
  /** The tenant's measurements among `ids`; ids it does not hold are absent from the answer. */
  findByIds(tenantId: string, ids: readonly string[]): Promise<Measurement[]>;
};
