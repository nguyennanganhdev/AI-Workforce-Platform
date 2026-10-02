import type { JsonValue } from "./context.js";

/** Extend with a typed payload when implementing each use case. */
export interface PlatformEvent<
  TType extends string,
  TPayload extends JsonValue,
> {
  readonly stream: "platform";
  readonly eventId: string;
  readonly tenantId: string;
  readonly correlationId: string;
  readonly type: TType;
  readonly occurredAt: string;
  readonly payload: TPayload;
}
