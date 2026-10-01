export type ToolErrorCode =
  | "INVALID_INPUT"
  | "NEEDS_INPUT"
  | "NOT_FOUND"
  | "FORBIDDEN"
  | "STALE_DATA"
  | "CONFLICT"
  | "PENDING_APPROVAL"
  | "INTERNAL_ERROR";

export class ToolError extends Error {
  constructor(
    readonly code: ToolErrorCode,
    message: string,
    readonly options: {
      field?: string;
      retryable?: boolean;
      missingFields?: readonly string[];
    } = {},
  ) {
    super(message);
    this.name = "ToolError";
  }
}
