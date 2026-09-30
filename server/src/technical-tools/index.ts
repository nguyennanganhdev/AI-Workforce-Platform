/**
 * Technical Agent A2's tools (docs/teams/quang/tools.md).
 *
 * What the rest of the server needs in order to mount them: the caller for `/api/agent-tools/call`,
 * the ports behind it, and the catalogue.
 */
export {
  createDbInterruptionReadPort,
  type TechnicalToolsDatabase,
  technicalToolsDatabase,
} from "./adapters/db/interruption-read";
export { createDbSopReadPort } from "./adapters/db/sop-read";
export { createInMemoryAssetReadPort } from "./adapters/poc/asset-read";
export { createInMemoryMaintenanceReadPort } from "./adapters/poc/maintenance-read";
export { createInMemorySensorReadPort } from "./adapters/poc/sensor-read";
export { createInMemorySopProfilePort } from "./adapters/poc/sop-profiles";
export {
  canonicalToolName,
  describeTechnicalTools,
  findTechnicalTool,
  technicalTools,
} from "./catalog";
export type { ResolvedIdentity, RuntimeContext } from "./contracts/context";
export {
  type ResponseEnvelope,
  responseEnvelopeSchema,
  type ToolStatus,
} from "./contracts/envelope";
export type { Asset } from "./domain/asset";
export type { MaintenanceEvent } from "./domain/maintenance";
export type {
  ReadingQuality,
  Sensor,
  SensorReading,
} from "./domain/sensor";
export type {
  AcceptanceCriterion,
  DocumentAclEntry,
  SopDocumentRecord,
  SopProfile,
} from "./domain/sop";
export { createTechnicalToolCaller } from "./entry";
export {
  createTechnicalToolHost,
  type HostDependencies,
  type HostOptions,
} from "./host";
export type { AssetQuery, AssetReadPort } from "./ports/asset-read";
export type { AuditSink, ToolAuditEntry } from "./ports/audit-sink";
export { type Clock, systemClock } from "./ports/clock";
export type { ContextResolver, ToolCaller } from "./ports/context-resolver";
export type {
  InterruptionQuery,
  InterruptionReadPort,
} from "./ports/interruption-read";
export type {
  MaintenanceQuery,
  MaintenanceReadPort,
} from "./ports/maintenance-read";
export type { SensorQuery, SensorReadPort } from "./ports/sensor-read";
export type {
  SopProfilePort,
  SopQuery,
  SopReadPort,
} from "./ports/sop-read";
export { defineTool, type ToolDependencies } from "./tool";
export {
  ISSUE_CODES,
  type IssueCode,
  type IssueLevel,
  issueCode,
} from "./reference/issue-codes";
export {
  METRICS,
  type MetricDefinition,
  unitAccepted,
} from "./reference/metrics";
