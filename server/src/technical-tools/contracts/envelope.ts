import { z } from "zod";

/**
 * The one response shape every technical tool answers with (docs/teams/quang/tools.md §1.3).
 *
 * `INVALID_INPUT` is in the status list although §1.3 leaves it out. §7 and the per-tool sections
 * both say a malformed request "returns INVALID_INPUT", and the error-code enum already carries it,
 * so a status enum without it would leave a rejected request with no status to report. Recorded in
 * docs/teams/quang/requests/Q02-interruptions.md as a spec discrepancy.
 */
export const TOOL_STATUSES = [
  "OK",
  "INVALID_INPUT",
  "NEEDS_INPUT",
  "NOT_FOUND",
  "FORBIDDEN",
  "STALE_DATA",
  "CONFLICT",
  "PENDING_APPROVAL",
  "INTERNAL_ERROR",
] as const;

export type ToolStatus = (typeof TOOL_STATUSES)[number];

export const toolErrorSchema = z.strictObject({
  code: z.enum(TOOL_STATUSES).exclude(["OK"]),
  message: z.string(),
  field: z.string().optional(),
  retryable: z.boolean(),
});

export type ToolError = z.infer<typeof toolErrorSchema>;

export const provenanceSchema = z.strictObject({
  source_system: z.string(),
  source_record_id: z.string().optional(),
  source_version: z.union([z.string(), z.number().int(), z.null()]).optional(),
  retrieved_at: z.iso.datetime({ offset: true }),
});

export type Provenance = z.infer<typeof provenanceSchema>;

export const responseEnvelopeSchema = z.strictObject({
  status: z.enum(TOOL_STATUSES),
  trace_id: z.string(),
  server_time: z.iso.datetime({ offset: true }),
  data: z
    .union([z.record(z.string(), z.unknown()), z.array(z.unknown())])
    .nullable(),
  errors: z.array(toolErrorSchema),
  missing_fields: z.array(z.string()),
  provenance: z.array(provenanceSchema),
});

export type ResponseEnvelope = z.infer<typeof responseEnvelopeSchema>;

/**
 * Statuses the model should read as "this did not work", as opposed to an answer it can act on.
 *
 * `NEEDS_INPUT`, `STALE_DATA` and `PENDING_APPROVAL` are answers: each tells the agent what to do
 * next. The transcript draws an error differently from a result, so calling those errors would make
 * a request that is correctly waiting for approval look like a failure.
 */
export function isErrorStatus(status: ToolStatus): boolean {
  return (
    status === "INVALID_INPUT" ||
    status === "NOT_FOUND" ||
    status === "FORBIDDEN" ||
    status === "CONFLICT" ||
    status === "INTERNAL_ERROR"
  );
}
