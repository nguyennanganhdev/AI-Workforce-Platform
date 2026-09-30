/**
 * Technical Agent A2's tools (docs/teams/quang/tools.md).
 *
 * What the rest of the server needs in order to mount them: the caller for `/api/agent-tools/call`,
 * the database-backed port behind it, and the catalogue.
 */
export {
  createDbInterruptionReadPort,
  type TechnicalToolsDatabase,
  technicalToolsDatabase,
} from "./adapters/db/interruption-read";
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
export { createTechnicalToolCaller } from "./entry";
export {
  createTechnicalToolHost,
  type HostDependencies,
  type HostOptions,
} from "./host";
export type { AuditSink, ToolAuditEntry } from "./ports/audit-sink";
export { type Clock, systemClock } from "./ports/clock";
export type { ContextResolver, ToolCaller } from "./ports/context-resolver";
export type {
  InterruptionQuery,
  InterruptionReadPort,
} from "./ports/interruption-read";
