import type { AuditInitiator } from "../../audit";
import type { ToolStatus } from "../contracts/envelope";

/**
 * One tool call, as the trail keeps it (general.md A2-FR-014: trace id, agent version and time).
 *
 * It carries what was asked for and how it ended, never what came back: the result belongs to the
 * caller, and a trail holding other people's outage data would be a second copy with weaker access
 * rules than the first.
 */
export type ToolAuditEntry = {
  tool: string;
  tool_version: string;
  status: ToolStatus;
  /** Why a call was refused or failed, for the person reading the trail. Never sent to the agent. */
  detail?: string;
  trace_id: string;
  agent_version: string | null;
  tenant_id: string | null;
  principal_id: string | null;
  source_run_id: string | null;
  bot_id: string;
  actor_id: string;
  initiator?: AuditInitiator;
  building_id: string | null;
  /**
   * The answer was the stored result of an earlier call with the same key, and nothing was written.
   * Kept apart from an ordinary success so the trail does not show one write as two.
   */
  idempotent_replay?: boolean;
  result_count: number | null;
  duration_ms: number;
  occurred_at: string;
};

/**
 * Where tool calls are recorded.
 *
 * A port rather than `recordAuditEvent` directly, because `auditEventTypes` in `server/src/audit.ts`
 * is a closed list with no technical-tool event in it yet, and that file is not this module's to
 * change. The production sink is whatever the owner of the audit trail maps these entries onto.
 */
export type AuditSink = { record(entry: ToolAuditEntry): Promise<void> };
