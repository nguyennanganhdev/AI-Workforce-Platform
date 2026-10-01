# Vinhomes Operations FastAPI

## Demo mock

Chạy `setup_demo_database.ps1`, rồi `start_demo.ps1` trong `scripts/` từ thư mục dự án, mở `http://localhost:8000/docs`. Xem [hướng dẫn demo database V3](HUONG_DAN_DEMO_DATABASE_V3.md). Demo dùng PostgreSQL với dữ liệu faker, không dùng RAM; chọn vai trò bằng `X-Demo-Actor`, quyền vẫn kiểm tra từ database.

Active HTTP routes query the canonical V3 PostgreSQL tables (`tickets`, `ticket_events`, `ticket_assessments`, `ticket_triage_decisions`, `work_orders`, `work_assignments`, `work_approvals`). The restored `vh_*` modules and Alembic migrations are retained as legacy reference and are not mounted by `main.py`. Do not run those migrations on a V3 database.

Run `python -m vinhomes_api` from this directory. The default bind address is `127.0.0.1:8000`; Swagger is at `/docs` and the OpenAPI document at `/openapi.json`.

Business endpoints require `VINHOMES_API_DATABASE_URL` (`postgresql+asyncpg://...`), a V3 tenant (`VINHOMES_API_TENANT_ID` or `VINHOMES_API_TENANT_KEY`), and server verified identity. Set `VINHOMES_API_AUTH_URL` to the platform's `/api/me` endpoint to forward the browser session cookie. For local loopback development, `VINHOMES_API_DEV_USER_ID` can select an existing active user; database grants are still checked. This development setting is rejected when binding to a non-loopback host.

`GET /health` checks the process. `GET /ready` checks required V3 tables. Business queries use a transaction with `SET LOCAL app.tenant_id` and `app.user_id`. Operations routes require active management/staff grants; `/resident/*` and `/my/notifications` require an active tenant membership and check ownership of each chat, ticket or notification. Room routes require room membership. Report, knowledge and admin routes apply additional management scope, document ACL or admin checks.

The API includes V3 read and write routes for tickets, assessment/review triage,
work orders, assignments, approvals, evidence, QC, cleaning, security, contractor
progress and budget requests. The complete route contract is visible at `/docs`.
New endpoints also cover resident chat/ticket tracking, in-app notifications,
management room messages, scoped knowledge search, available staff, water
interruptions, admin memory review, and JSON/DOCX incident or issued-invoice
reports. Security incident creation accepts `business_severity` P0–P3 and stores
the corresponding `p1`–`p4` value.
`POST /resident/chats/{channel_id}/tickets` creates one ticket for a verified
resident unit in an existing chat, resolves the active management coverage and
notifies scoped managers. `POST /tickets/{ticket_id}/routing/ack` records BQL
acceptance and notifies the requester.
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
`channels`, `channel_memberships`, `messages`, `message_mentions`, `tickets`,
`ticket_events`, `ticket_assessments`, `ticket_triage_decisions`,
`ticket_triage_reviews`, `work_orders`, `work_assignments`, `work_approvals`,
`service_interruptions`, `interruption_scopes`, `notification_deliveries`,
`memory_candidates`, `knowledge_reviews`, `evidence_items`, `execution_principals`,
`files`, `file_objects`, `ticket_files` and the seven `vh_*` extension tables.
It must not have `BYPASSRLS`. Data changes run inside a tenant scoped transaction.

An agent running without a browser session cannot yet call protected port 8000
routes. The planned Hono delegation path must pass a verified requesting user
identity to FastAPI; no route accepts a client supplied user ID as authority.

## Giao diện chạy thử API V3

Mở `services/CHAY_DEMO_API.cmd` hoặc chạy `scripts/start_demo.ps1`, rồi mở **http://localhost:8000/demo/ui**.
Trang là giao diện nghiệp vụ: cư dân gửi yêu cầu, BQL điều phối/phê duyệt, nhân viên nhận việc,
upload bằng chứng, an ninh, trao đổi phòng và báo cáo. Không cần nhập endpoint hoặc JSON.
Xem [hướng dẫn giao diện người dùng](../../my-docs/HUONG_DAN_GIAO_DIEN_NGUOI_DUNG_DEMO.md).
