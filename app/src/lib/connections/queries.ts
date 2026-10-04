import { queryOptions } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";

/** An external MCP server an administrator connected for management's agents. Its token is never sent here. */
export type Connection = { id: string; title: string; url: string; workspace_id: string | null; workspace: string | null;
  has_token: boolean; tools_refreshed_at: string | null; last_error: string | null; tools: { name: string; description: string }[] };
export type Connections = { items: Connection[]; workspaces: { id: string; name: string }[] };
/** A tool the server offers now. `name` is what the catalogue calls it, `tool` what the server calls it. */
export type OfferedTool = { name: string; tool: string; description: string; destructive: boolean; usable: boolean; allowed: boolean };
export type ConnectionCheck = { ok: boolean; error: string | null; tools: OfferedTool[] };

export const connectionKeys = { all: ["connections"] as const };
export function connectionsQueryOptions() {
  return queryOptions({ queryKey: connectionKeys.all,
    queryFn: async (): Promise<Connections> => (await client("/api/business/admin/connections",
      { headers: businessHeaders(), fallback: "Không tải được danh sách kết nối." })).json() });
}
