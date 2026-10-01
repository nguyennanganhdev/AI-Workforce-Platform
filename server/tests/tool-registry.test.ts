import { describe, expect, test } from "bun:test";
import {
  createToolRegistry,
  descriptorFromMcpTool,
  ToolRegistry,
} from "../src/plugins/registry";

describe("tool registry", () => {
  test("maps MCP tools into builder descriptors", () => {
    const descriptor = descriptorFromMcpTool({
      serverId: "building-ops",
      name: "find_ticket",
      description: "Find a ticket in the authorized management scope.",
      inputSchema: { type: "object", properties: {} },
      version: "1",
      effect: "read",
    });

    expect(descriptor.ref).toBe("building-ops/find_ticket");
    expect(descriptor.execution).toEqual({
      kind: "mcp",
      serverId: "building-ops",
      toolName: "find_ticket",
    });
    expect(descriptor.retry.maxRetries).toBe(2);
  });

  test("shows only compatible builder tools", () => {
    const registry = createToolRegistry({
      firstPartyTools: [
        {
          ref: "reporting/revenue-summary",
          name: "revenue_summary",
          version: "1",
          displayName: "Revenue summary",
          description: "Summarize repair revenue in the authorized scope.",
          category: "reporting",
          source: "first-party",
          inputSchema: { type: "object", properties: {} },
          outputSchema: { type: "object", properties: {} },
          visibility: "builder",
          allowedAgentTypes: ["report"],
          requiredPermissions: ["reports:read"],
          effect: "read",
          destructive: false,
          timeoutMs: 10_000,
          retry: { maxRetries: 1, backoffMs: 200 },
          requiresIdempotencyKey: false,
          execution: {
            kind: "first-party",
            handler: "reporting.revenue-summary",
          },
        },
        {
          ref: "runtime/restore-session",
          name: "restore_session",
          version: "1",
          displayName: "Restore session",
          description: "Restore internal runtime state.",
          category: "runtime",
          source: "first-party",
          inputSchema: { type: "object", properties: {} },
          outputSchema: { type: "object", properties: {} },
          visibility: "internal",
          allowedAgentTypes: ["*"],
          requiredPermissions: ["runtime:restore"],
          effect: "read",
          destructive: false,
          timeoutMs: 10_000,
          retry: { maxRetries: 1, backoffMs: 200 },
          requiresIdempotencyKey: false,
          execution: {
            kind: "first-party",
            handler: "runtime.restore-session",
          },
        },
      ],
    });

    expect(registry.forBuilder("report").map((tool) => tool.ref)).toEqual([
      "reporting/revenue-summary",
    ]);
    expect(registry.forBuilder("technical")).toEqual([]);
  });

  test("rejects duplicate refs", () => {
    const descriptor = descriptorFromMcpTool({
      serverId: "duplicate",
      name: "lookup",
      description: "Look up a record.",
      inputSchema: { type: "object", properties: {} },
      effect: "read",
    });

    expect(() => new ToolRegistry([descriptor, descriptor])).toThrow(
      "Duplicate tool descriptor ref: duplicate/lookup",
    );
  });
});
