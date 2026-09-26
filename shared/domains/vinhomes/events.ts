import type { JsonValue } from '../../platform/context.js';

export interface VinhomesEvent<TType extends string, TPayload extends JsonValue> {
  readonly stream: 'vinhomes';
  readonly eventId: string;
  readonly tenantId: string;
  readonly incidentId: string | null;
  readonly correlationId: string;
  readonly type: TType;
  readonly occurredAt: string;
  readonly payload: TPayload;
}
