# Fresh migration baseline

The previous SQL migrations, snapshots and journal were removed at the project's
explicit request. No live database or its `drizzle.__drizzle_migrations` table was changed.

From the repository root:

```sh
bun run --cwd server db:generate
bun run --cwd server db:migrate
```

Use `db:generate`, not a direct `drizzle-kit generate`: the wrapper adds pgvector,
cross-row triggers, exclusion constraints and FORCE RLS from `src/db/invariants.sql`
and `src/db/generated-invariants.sql` to the first baseline. PostgreSQL must provide
the `vector` and `btree_gist` extensions. Framework checkpoint schemas have their own
setup/migrations and are deliberately excluded.

This is a new baseline for an **empty database**. Existing databases require a
separate reconciled upgrade/baselining plan; deleting local migration files does
not reset their applied history. Subsequent changes to invariant SQL must be shipped
as an explicit custom migration, because Drizzle's snapshots do not track functions
and triggers. The wrapper only installs those sources in the first baseline.

## Vinhomes extensions

`0001`/`0002` and the `vh_*` tables in `0004` are explicit SQL migrations, maintained
like the existing operations extension. Their FK, checks and FORCE RLS are defined
in SQL; FastAPI uses SQLAlchemy SQL against those tables. Do not recreate these
tables via ad-hoc startup DDL. Drizzle snapshots track the generated canonical
schema (including the removed `tickets.channel_id` unique in `0004`), while the
custom extension tables remain outside the generated TypeScript model.

`0003` adds the generated `security.ts` schema. Local demo startup runs migrations
before extra fixtures and runtime role grants. Applied migration files must stay
immutable; future schema changes require a new journal entry.

`0005` replaces the assignment capacity function so historical accepted assignments
on completed/cancelled/rejected work do not consume concurrent staff capacity.
The matching baseline source is updated in `invariants.sql`; applied SQL is preserved.

`0006_resident_contract` adds resident Cases, staged unit-scoped image metadata,
explicit public resolutions, response history, command receipts and an outbox.
It extends canonical `files` with a resident/unit scope. Snapshot `0006` records
the canonical files changes; extension tables remain explicit SQL like `0004`.
