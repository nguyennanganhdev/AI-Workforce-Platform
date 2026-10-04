/**
 * One pass of the audit trail's retention, for a deployment that does not run the platform server.
 *
 * Removes audit rows older than AUDIT_RETENTION_DAYS and nothing else; unset, it removes nothing.
 * The batching, the lock and the database's own refusal of any row inside the declared window are
 * the platform's (server/src/audit-retention.ts).
 *
 * The tenant is named on the connection. The trail is under row security, and without it the delete
 * sees only rows that belong to no tenant: the sweep reports 0 and the table keeps growing.
 */
const owner = process.env.DATABASE_URL;
const tenant = process.env.VINHOMES_TENANT_ID;
if (!owner || !tenant)
  throw new Error(
    "MIGRATION_DATABASE_URL (the database owner) and VINHOMES_TENANT_ID are required",
  );
const setting = process.env.AUDIT_RETENTION_DAYS?.trim() ?? "";
const days = Number(setting);
if (setting === "") {
  console.log(JSON.stringify({ type: "audit-retention-off" }));
} else if (!Number.isInteger(days) || days < 1) {
  throw new Error("AUDIT_RETENTION_DAYS must be a whole number of days, 1 or more");
} else {
  // Resolved from the working directory, as upgrade.ts does: this file is copied beside the server's scripts.
  const { sweepAuditTrail } = await import(
    `${process.cwd()}/server/src/audit-retention`
  );
  const url = new URL(owner);
  url.searchParams.set("app.tenant_id", tenant);
  const { deleted } = await sweepAuditTrail(url.toString(), days);
  // Null: another sweep holds the lock, so this one did nothing.
  console.log(
    JSON.stringify({ type: "audit-retention-swept", retentionDays: days, deleted }),
  );
}
