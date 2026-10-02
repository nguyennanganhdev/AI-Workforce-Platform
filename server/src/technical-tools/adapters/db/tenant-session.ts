import { sql } from "drizzle-orm";
import type { TechnicalToolsDatabase } from "./interruption-read";

/** The transaction a tenant session hands its callback. */
export type TenantTransaction = Parameters<
  Parameters<TechnicalToolsDatabase["transaction"]>[0]
>[0];

/**
 * A database session already bound to one tenant, which the backend supplies.
 *
 * Every database adapter here runs its queries inside one, so where `app.tenant_id` is set and
 * which connection or role a query runs on is the backend's decision, made once, and not a detail
 * every adapter repeats. The adapters still filter on `tenant_id` themselves: row-level security is
 * the second check, not the only one.
 *
 * `read` runs a read-only transaction; `write` one that may insert. Neither is a way round the
 * role's grants: what the role cannot do, a session cannot either.
 */
export type TenantSession = {
  readonly kind: "tenant-session";
  read<T>(
    tenantId: string,
    work: (tx: TenantTransaction) => Promise<T>,
  ): Promise<T>;
  write<T>(
    tenantId: string,
    work: (tx: TenantTransaction) => Promise<T>,
  ): Promise<T>;
};

/**
 * The default session: a transaction per call on the given database, `app.tenant_id` set with
 * `set_config(..., true)` first so it ends with the transaction and cannot follow the connection
 * back into the pool.
 */
export function tenantSessionFrom(
  database: TechnicalToolsDatabase,
): TenantSession {
  const scoped =
    <T>(work: (tx: TenantTransaction) => Promise<T>, tenantId: string) =>
    async (tx: TenantTransaction) => {
      await tx.execute(
        sql`select set_config('app.tenant_id', ${tenantId}, true)`,
      );
      return work(tx);
    };
  return {
    kind: "tenant-session",
    read: (tenantId, work) =>
      database.transaction(scoped(work, tenantId), {
        accessMode: "read only",
      }),
    write: (tenantId, work) => database.transaction(scoped(work, tenantId)),
  };
}

/** What a database adapter accepts: the backend's session, or a database to build the default one. */
export type TenantSessionSource = TechnicalToolsDatabase | TenantSession;

export function asTenantSession(source: TenantSessionSource): TenantSession {
  return "kind" in source && source.kind === "tenant-session"
    ? source
    : tenantSessionFrom(source as TechnicalToolsDatabase);
}
