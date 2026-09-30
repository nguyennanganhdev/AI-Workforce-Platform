# Vinhomes Operations FastAPI

Active HTTP routes query the canonical V3 PostgreSQL tables (`tickets`, `ticket_events`, `ticket_assessments`, `ticket_triage_decisions`, `work_orders`, `work_assignments`, `work_approvals`). The restored `vh_*` modules and Alembic migrations are retained as legacy reference and are not mounted by `main.py`. Do not run those migrations on a V3 database.

Run `python -m vinhomes_api` from this directory. The default bind address is `127.0.0.1:8000`; Swagger is at `/docs` and the OpenAPI document at `/openapi.json`.

Business endpoints require `VINHOMES_API_DATABASE_URL` (`postgresql+asyncpg://...`), a V3 tenant (`VINHOMES_API_TENANT_ID` or `VINHOMES_API_TENANT_KEY`), and server verified identity. Set `VINHOMES_API_AUTH_URL` to the platform's `/api/me` endpoint to forward the browser session cookie. For local loopback development, `VINHOMES_API_DEV_USER_ID` can select an existing active user; database grants are still checked. This development setting is rejected when binding to a non-loopback host.

`GET /health` checks the process. `GET /ready` checks that the configured database has the V3 `tickets` and `work_orders` tables. All business queries use a transaction with `SET LOCAL app.tenant_id` and `app.user_id`, plus a scope predicate from the active database grants. Customer accounts are refused by this Operations API.

The API includes V3 read and write routes for tickets, assessment/review triage,
work orders, assignments, approvals, evidence, QC, cleaning, security, contractor
progress and budget requests. The complete route contract is visible at `/docs`.
The V3 extension tables for field operations are in
`server/drizzle/0001_vinhomes_operations.sql` and
`server/drizzle/0002_vinhomes_qc_redo.sql`; apply the server Drizzle migrations
before starting this service. The old `vh_*` write routes remain unmounted.

For the local Docker fixture, `scripts/seed_v3_local.sql` creates a tenant, user,
building, management coverage, published triage policy and local evidence storage
location. The local file API accepts JPEG, PNG and WebP images of at most 10 MB and
stores them in the ignored `.local-v3-files` directory. It is available only with
`VINHOMES_API_DEV_USER_ID` on a loopback host. Deployments need a verified object
store and malware scanning before enabling production uploads.

The runtime database role needs `SELECT` on V3 tables and `INSERT`/`UPDATE` on
`channels`, `tickets`, `ticket_events`, `ticket_assessments`,
`ticket_triage_decisions`, `ticket_triage_reviews`, `work_orders`,
`work_assignments`, `work_approvals`, `evidence_items`, `execution_principals`,
`files`, `file_objects`, `ticket_files` and the seven `vh_*` extension tables.
It must not have `BYPASSRLS`. Data changes run inside a tenant scoped transaction.
