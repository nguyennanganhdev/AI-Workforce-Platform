import { createHash } from "node:crypto";
import { sql } from "drizzle-orm";
import type { Database } from "./client";
import { tenants, managementUnits, workspaces, accessScopes } from "./schema";

/** Stable internal UUID, distinct from the package's external tenant key. */
export function scopedUuid(kind: string, key: string): string {
  const hex = createHash("sha256")
    .update(`openbot:${kind}:${key}`)
    .digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

export function deploymentScope(externalKey: string) {
  if (!externalKey.trim())
    throw new Error("A verified deployment tenant key is required");
  return {
    tenantId: scopedUuid("tenant", externalKey),
    workspaceId: scopedUuid("workspace", externalKey),
    managementUnitId: scopedUuid("management", externalKey),
    scopeId: scopedUuid("scope", externalKey),
  };
}

/** Bootstrap the existing single-package host. Multi-tenant APIs must use explicit scoped transactions. */
export async function initializeDeploymentScope(
  database: Database,
  externalKey: string,
) {
  const scope = deploymentScope(externalKey);
  await database.transaction(async (tx) => {
    await tx.execute(
      sql`select set_config('app.tenant_id', ${scope.tenantId}, true), set_config('app.workspace_id', ${scope.workspaceId}, true)`,
    );
    await tx
      .insert(tenants)
      .values({
        id: scope.tenantId,
        code: externalKey,
        name: externalKey,
        status: "active",
      })
      .onConflictDoNothing();
    await tx
      .insert(managementUnits)
      .values({
        id: scope.managementUnitId,
        tenantId: scope.tenantId,
        code: "deployment",
        name: externalKey,
        status: "active",
      })
      .onConflictDoNothing();
    await tx
      .insert(workspaces)
      .values({
        id: scope.workspaceId,
        tenantId: scope.tenantId,
        managementUnitId: scope.managementUnitId,
        code: "deployment",
        name: externalKey,
        status: "active",
      })
      .onConflictDoNothing();
    await tx
      .insert(accessScopes)
      .values({ id: scope.scopeId, tenantId: scope.tenantId, kind: "tenant" })
      .onConflictDoNothing();
  });
  return scope;
}

/** Use only server-verified scope, never request body tenant IDs. SET LOCAL cannot leak through a pool. */
export async function withDatabaseScope<T>(
  database: Database,
  scope: { tenantId: string; workspaceId?: string; userId: string },
  run: (
    tx: Parameters<Parameters<Database["transaction"]>[0]>[0],
  ) => Promise<T>,
) {
  return database.transaction(async (tx) => {
    await tx.execute(
      sql`select set_config('app.tenant_id', ${scope.tenantId}, true), set_config('app.workspace_id', ${scope.workspaceId ?? ""}, true), set_config('app.user_id', ${scope.userId}, true)`,
    );
    return run(tx);
  });
}
