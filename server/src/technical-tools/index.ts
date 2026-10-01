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
export {
  createDbIsolationWriter,
  createDbScopeReadPort,
} from "./adapters/db/isolation-writer";
export { createDbSopReadPort } from "./adapters/db/sop-read";
export { createDbWorkOrderReadPort } from "./adapters/db/work-order-read";
export { createInMemoryApprovalRequestStore } from "./adapters/poc/approval-request-store";
export { createInMemoryAssetReadPort } from "./adapters/poc/asset-read";
export { createInMemoryExecutorResultStore } from "./adapters/poc/executor-result-store";
export { createInMemoryIdempotencyStore } from "./adapters/poc/idempotency-store";
export { createInMemoryMaintenanceReadPort } from "./adapters/poc/maintenance-read";
export { createInMemoryMaintenanceStore } from "./adapters/poc/maintenance-store";
export { createInMemoryMeasurementStore } from "./adapters/poc/measurement-store";
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
export type {
  ApprovalRequest,
  ApprovalRequestKind,
  BuildingPlacement,
  OpenIsolation,
  ScopeRecord,
  WaterIsolation,
} from "./domain/approval-request";
export type { Asset } from "./domain/asset";
export type {
  ChecklistItem,
  ExecutorResult,
  Part,
  ValidationStatus,
} from "./domain/executor-result";
export type { MaintenanceEvent } from "./domain/maintenance";
export type {
  MeasuredBy,
  Measurement,
  MeasurementSource,
} from "./domain/measurement";
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
export type {
  Check,
  CheckStatus,
  SopBasis,
  Verification,
  VerificationStatus,
} from "./domain/verification";
export type {
  AssignmentRecord,
  EvidenceLookup,
  WorkOrderContext,
} from "./domain/work-order";
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
export type { ExecutorResultStore } from "./ports/executor-result-store";
export type {
  IdempotencyScope,
  IdempotencyStore,
  Reservation,
  StoredOutcome,
} from "./ports/idempotency-store";
export type {
  InterruptionQuery,
  InterruptionReadPort,
} from "./ports/interruption-read";
export type {
  MaintenanceQuery,
  MaintenanceReadPort,
} from "./ports/maintenance-read";
export type {
  AppendOutcome,
  MaintenanceStore,
} from "./ports/maintenance-store";
export type { MeasurementStore } from "./ports/measurement-store";
export type {
  ApprovalRequestStore,
  IsolationWriter,
  ScopeReadPort,
} from "./ports/request-ports";
export type { SensorQuery, SensorReadPort } from "./ports/sensor-read";
export type {
  SopProfilePort,
  SopQuery,
  SopReadPort,
} from "./ports/sop-read";
export type { WorkOrderReadPort } from "./ports/work-order-read";
export {
  ISSUE_CODES,
  type IssueCode,
  type IssueLevel,
  issueCode,
} from "./reference/issue-codes";
export {
  METRICS,
  type MetricDefinition,
  metricDefinition,
  unitAccepted,
} from "./reference/metrics";
export {
  defineTool,
  type ToolDependencies,
  type ToolOutcome,
} from "./tool";
