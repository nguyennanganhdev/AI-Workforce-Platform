import type { Decision, Fact, JsonValue } from "./state";

export class GraphFault extends Error {
  constructor(
    readonly code: string,
    readonly retryable = false,
  ) {
    super(code);
  }
}

export function jsonValue(value: unknown): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean")
    return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(jsonValue);
  if (
    typeof value === "object" &&
    value !== null &&
    Object.getPrototypeOf(value) === Object.prototype
  ) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, jsonValue(item)]),
    );
  }
  throw new GraphFault("INVALID_JSON_VALUE");
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new GraphFault("INVALID_DECISION");
  }
  return value as Record<string, unknown>;
}

export function facts(value: unknown): readonly Fact[] {
  if (!Array.isArray(value) || value.length > 32)
    throw new GraphFault("INVALID_FACTS");
  return value.map((entry) => {
    const item = record(entry);
    if (
      typeof item.name !== "string" ||
      !item.name.trim() ||
      item.name.length > 128
    ) {
      throw new GraphFault("INVALID_FACTS");
    }
    return { name: item.name, value: jsonValue(item.value) };
  });
}

/** Strict graph-control protocol, not an API DTO or a tool response schema. */
export function parseDecision(text: string): Decision {
  if (text.length > 32_768) throw new GraphFault("INVALID_DECISION");
  let value: Record<string, unknown>;
  try {
    value = record(JSON.parse(text));
  } catch {
    throw new GraphFault("INVALID_DECISION");
  }
  const allowed =
    value.action === "tool"
      ? ["action", "operation", "input", "inferences"]
      : ["action", "text", "inferences"];
  if (Object.keys(value).some((key) => !allowed.includes(key))) {
    throw new GraphFault("INVALID_DECISION");
  }
  const inferences = facts(value.inferences ?? []);
  if (value.action === "tool") {
    if (typeof value.operation !== "string" || !value.operation.trim()) {
      throw new GraphFault("INVALID_DECISION");
    }
    return {
      action: "tool",
      operation: value.operation,
      input: jsonValue(value.input),
      inferences,
    };
  }
  if (
    !["clarify", "await_resident", "handoff", "complete"].includes(
      String(value.action),
    ) ||
    typeof value.text !== "string" ||
    !value.text.trim() ||
    value.text.length > 4_096
  ) {
    throw new GraphFault("INVALID_DECISION");
  }
  return {
    action: value.action as
      | "clarify"
      | "await_resident"
      | "handoff"
      | "complete",
    text: value.text,
    inferences,
  };
}
