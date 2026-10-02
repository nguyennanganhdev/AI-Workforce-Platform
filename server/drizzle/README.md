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
