import { z } from "zod";
import type { ToolDescriptor } from "./types";

const jsonSchema = z.record(z.string(), z.unknown());
const nonBlank = z.string().trim().min(1);

/** Runtime validation for descriptors coming from code or an MCP listing. */
export const toolDescriptorSchema = z
  .object({
    ref: nonBlank.regex(
      /^[a-z0-9][a-z0-9._-]*\/[a-z0-9][a-z0-9._-]*$/,
      "ref must be a stable <namespace>/<tool-name> value",
    ),
    name: nonBlank.regex(
      /^[a-zA-Z0-9_-]+$/,
      "name may contain only letters, numbers, underscores, and hyphens",
    ),
    version: nonBlank.max(128),
    displayName: nonBlank.max(160),
    description: nonBlank.max(10_000),
    category: nonBlank.max(100),
    source: z.enum(["first-party", "mcp"]),
    inputSchema: jsonSchema,
    outputSchema: jsonSchema,
    visibility: z.enum(["builder", "system", "internal"]),
    allowedAgentTypes: z.array(nonBlank).min(1),
    requiredPermissions: z.array(nonBlank),
    effect: z.enum(["read", "write"]),
    destructive: z.boolean(),
    timeoutMs: z.number().int().positive().max(300_000),
    retry: z.object({
      maxRetries: z.number().int().min(0).max(10),
      backoffMs: z.number().int().min(0).max(60_000),
    }),
    requiresIdempotencyKey: z.boolean(),
    execution: z.discriminatedUnion("kind", [
      z.object({ kind: z.literal("first-party"), handler: nonBlank }),
      z.object({
        kind: z.literal("mcp"),
        serverId: nonBlank,
        toolName: nonBlank,
      }),
    ]),
  })
  .superRefine((descriptor, context) => {
    if (descriptor.source !== descriptor.execution.kind) {
      context.addIssue({
        code: "custom",
        path: ["execution", "kind"],
        message: "source must match execution.kind",
      });
    }
    if (descriptor.destructive && descriptor.effect !== "write") {
      context.addIssue({
        code: "custom",
        path: ["destructive"],
        message: "a destructive tool must be classified as write",
      });
    }
    if (descriptor.requiresIdempotencyKey && descriptor.effect !== "write") {
      context.addIssue({
        code: "custom",
        path: ["requiresIdempotencyKey"],
        message: "idempotency keys apply only to write tools",
      });
    }
  });

export function validateToolDescriptor(input: unknown): ToolDescriptor {
  return toolDescriptorSchema.parse(input) as ToolDescriptor;
}

/** Validate a complete catalogue and reject ambiguous identities. */
export function validateToolDescriptors(
  inputs: readonly unknown[],
): readonly ToolDescriptor[] {
  const descriptors = inputs.map(validateToolDescriptor);
  const refs = new Set<string>();

  for (const descriptor of descriptors) {
    if (refs.has(descriptor.ref)) {
      throw new Error(`Duplicate tool descriptor ref: ${descriptor.ref}`);
    }
    refs.add(descriptor.ref);
  }

  return Object.freeze(descriptors);
}
