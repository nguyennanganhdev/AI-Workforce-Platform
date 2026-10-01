import { z } from "zod";
import { ToolError } from "./errors";
import type { TechnicalToolName } from "./schemas";

/** Metadata is supplied by the authenticated host, never parsed from model arguments. */
export const runtimeMetadataSchema = z.strictObject({
  tenant_id: z.uuid(),
  workspace_id: z.uuid().optional(),
  principal_id: z.string().min(1),
  source_run_id: z.uuid(),
  trace_id: z.string().min(1).max(128),
  agent_version: z.string().min(1).max(128),
  received_at: z.iso.datetime({ offset: true }),
});

export type RuntimeMetadata = z.infer<typeof runtimeMetadataSchema>;

export interface CapabilityGrant {
  tool: TechnicalToolName;
  capability: string;
  /** Scope IDs resolved by the host, not building IDs supplied by the caller. */
  scopeIds: readonly string[];
}

export interface ExecutionContext extends RuntimeMetadata {
  readonly grants: readonly CapabilityGrant[];
}

/** Implemented by the backend owner; it resolves building ancestry and principal scope. */
export interface BuildingAccessPort {
  canAccessBuilding(
    context: ExecutionContext,
    buildingId: string,
    grantedScopeIds: readonly string[],
  ): Promise<boolean>;
}

export async function requireBuildingAccess(
  context: ExecutionContext,
  tool: TechnicalToolName,
  capability: string,
  buildingId: string,
  access: BuildingAccessPort,
): Promise<void> {
  // This validates metadata shape. The caller must still supply it from an authenticated host.
  runtimeMetadataSchema.parse({
    tenant_id: context.tenant_id,
    workspace_id: context.workspace_id,
    principal_id: context.principal_id,
    source_run_id: context.source_run_id,
    trace_id: context.trace_id,
    agent_version: context.agent_version,
    received_at: context.received_at,
  });
  const grants = context.grants.filter(
    (grant) => grant.tool === tool && grant.capability === capability,
  );
  for (const grant of grants) {
    if (
      grant.scopeIds.length > 0 &&
      (await access.canAccessBuilding(context, buildingId, grant.scopeIds))
    ) {
      return;
    }
  }
  // Do not reveal whether the building exists in another tenant or scope.
  throw new ToolError(
    "FORBIDDEN",
    "Access to this tool or building is denied.",
  );
}
