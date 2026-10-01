import { z } from "zod";
import type { RuntimeMetadata } from "./context";
import { ToolError, type ToolErrorCode } from "./errors";

const timestamp = z.iso.datetime({ offset: true });
export const toolStatusSchema = z.enum([
  "OK",
  "NEEDS_INPUT",
  "NOT_FOUND",
  "FORBIDDEN",
  "STALE_DATA",
  "CONFLICT",
  "PENDING_APPROVAL",
  "INTERNAL_ERROR",
]);
export const toolErrorSchema = z.strictObject({
  code: z.enum([
    "INVALID_INPUT",
    "NEEDS_INPUT",
    "NOT_FOUND",
    "FORBIDDEN",
    "STALE_DATA",
    "CONFLICT",
    "PENDING_APPROVAL",
    "INTERNAL_ERROR",
  ]),
  message: z.string(),
  field: z.string().optional(),
  retryable: z.boolean(),
});
export const provenanceSchema = z.strictObject({
  source_system: z.string(),
  source_record_id: z.string().optional(),
  source_version: z.union([z.string(), z.number().int(), z.null()]).optional(),
  retrieved_at: timestamp,
});
export const envelopeSchema = z.strictObject({
  status: toolStatusSchema,
  trace_id: z.string(),
  server_time: timestamp,
  data: z.union([
    z.record(z.string(), z.unknown()),
    z.array(z.unknown()),
    z.null(),
  ]),
  errors: z.array(toolErrorSchema),
  missing_fields: z
    .array(z.string())
    .refine((items) => new Set(items).size === items.length),
  provenance: z.array(provenanceSchema),
});

export type Provenance = z.infer<typeof provenanceSchema>;
export type ToolEnvelope = z.infer<typeof envelopeSchema>;

export function successEnvelope(
  context: Pick<RuntimeMetadata, "trace_id">,
  data: Record<string, unknown> | unknown[],
  provenance: readonly Provenance[],
  now: Date = new Date(),
): ToolEnvelope {
  return envelopeSchema.parse({
    status: "OK",
    trace_id: context.trace_id,
    server_time: now.toISOString(),
    data,
    errors: [],
    missing_fields: [],
    provenance,
  });
}

export function noticeEnvelope(
  context: Pick<RuntimeMetadata, "trace_id">,
  data: Record<string, unknown> | unknown[],
  provenance: readonly Provenance[],
  notice: {
    code: "NEEDS_INPUT" | "STALE_DATA";
    message: string;
    missingFields?: readonly string[];
  },
  now: Date = new Date(),
): ToolEnvelope {
  return envelopeSchema.parse({
    status: notice.code,
    trace_id: context.trace_id,
    server_time: now.toISOString(),
    data,
    errors: [{ code: notice.code, message: notice.message, retryable: false }],
    missing_fields: [...new Set(notice.missingFields ?? [])],
    provenance,
  });
}

const statusForError: Record<
  ToolErrorCode,
  z.infer<typeof toolStatusSchema>
> = {
  INVALID_INPUT: "NEEDS_INPUT", // The contract has INVALID_INPUT as an error code, not a status.
  NEEDS_INPUT: "NEEDS_INPUT",
  NOT_FOUND: "NOT_FOUND",
  FORBIDDEN: "FORBIDDEN",
  STALE_DATA: "STALE_DATA",
  CONFLICT: "CONFLICT",
  PENDING_APPROVAL: "PENDING_APPROVAL",
  INTERNAL_ERROR: "INTERNAL_ERROR",
};

/** Unknown exceptions get a fixed message, so credentials/SQL cannot escape via error text. */
export function errorEnvelope(
  context: Pick<RuntimeMetadata, "trace_id">,
  error: unknown,
  now: Date = new Date(),
): ToolEnvelope {
  const safe =
    error instanceof ToolError
      ? error
      : new ToolError(
          "INTERNAL_ERROR",
          "The tool could not complete the request.",
          { retryable: true },
        );
  return envelopeSchema.parse({
    status: statusForError[safe.code],
    trace_id: context.trace_id,
    server_time: now.toISOString(),
    data: null,
    errors: [
      {
        code: safe.code,
        message: safe.message,
        retryable: safe.options.retryable ?? false,
        ...(safe.options.field ? { field: safe.options.field } : {}),
      },
    ],
    missing_fields: [...new Set(safe.options.missingFields ?? [])],
    provenance: [],
  });
}
