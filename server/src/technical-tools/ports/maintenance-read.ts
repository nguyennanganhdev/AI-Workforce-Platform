import type { MaintenanceEvent } from "../domain/maintenance";

export type MaintenanceQuery = {
  tenantId: string;
  buildingId: string;
  assetId: string;
  /** Events at or after this instant are not wanted. */
  until: Date;
};

export type MaintenanceReadPort = {
  /**
   * Every recorded event on the asset before `until`, replaced ones included.
   *
   * Not bounded below on purpose: the date of the last maintenance is part of the answer even when
   * it falls before the window asked about, and a port that cut at `from` could not supply it.
   * Which events count, and which were replaced, is `maintenance-rules`' decision.
   */
  listForAsset(query: MaintenanceQuery): Promise<MaintenanceEvent[]>;
};
