/**
 * A piece of equipment or fabric, as the technical tools read it.
 *
 * No table holds this yet, so `ownership` and `warrantyUntil` are the fields tools.md §3.2 asks
 * for rather than columns anybody has committed to. `etag` is whatever the source system uses to
 * say which revision this is, reported as provenance so an agent's answer can be traced back.
 */
export type Asset = {
  assetId: string;
  tenantId: string;
  buildingId: string;
  /** e.g. `air_conditioner`, `breaker_panel`, `water_heater`. */
  type: string;
  model: string | null;
  /** Free text as the source system holds it, e.g. `A1-1205/phòng khách`. */
  location: string;
  /** Who owns it, e.g. `resident` or `management`. */
  ownership: string | null;
  warrantyUntil: string | null;
  status: string;
  updatedAt: Date;
  etag: string | null;
};
