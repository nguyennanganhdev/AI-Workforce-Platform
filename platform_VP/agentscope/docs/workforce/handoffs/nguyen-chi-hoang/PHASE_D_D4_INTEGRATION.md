# Tích hợp cuối Phase D/D4 — Nguyễn Chí Hoàng

Ngày **2026-10-12**. Baseline đầu vào: `develop2@35cec29`, sau khi PR #73 của
Phó Tiến Anh đã merge. Trạng thái bàn giao: **đã hoàn thành, đã commit và đã
merge vào `develop2`** qua commit/PR chứa chính tài liệu này. Không còn đầu việc
code D4 integration đang chờ trong working tree của Nguyễn Chí Hoàng.

## Phạm vi đã ghép

- Thêm Alembic revision `0011_workforce_releases` cho bốn bảng release đã được
  D4 bàn giao; migration đóng băng định nghĩa, có downgrade theo thứ tự ngược.
- Cho Registry current/pinned protocol read dùng optional canonical UOW; current
  head có thể `FOR UPDATE` trên PostgreSQL.
- Thêm `TransactionalReleaseValidator`: tool, policy và protocol được resolve
  trong cùng UOW của publish; chặn tool identity drift và protocol bị disable.
- Thêm manager-only release router. Scope lấy từ authenticated principal qua
  `IdentityPort`; `ReleaseContext` lấy từ server resolver, không nhận từ body.
- Thêm `PublishedLeaderBootstrapResolver`: seed Leader phải trỏ đúng current
  published/enabled/non-archived deployment và đúng agent owner.
- Thêm `SqlWorkflowVersionUsageReader`: đọc exact version pin trong workflow,
  checkpoint và durable tool-call theo đủ Scope để bảo vệ retention. Group nằm
  trong workflow; operation hiện không có trường agent version riêng.
- Ghép release service, pinned authorization, published Leader resolver, usage
  reader và router vào `build_phase_c_runtime`; không dùng fake production.
- `ReleaseAwareEvaluationJobService` ghi frozen evaluation, release candidate
  và durable evaluation job trong cùng UOW. Publish vì vậy tiêu thụ đúng
  candidate do luồng eval tạo; update vẫn giữ CAS và trả conflict khi revision
  kỳ vọng đã cũ.
- CI Phase D chạy integration seam mới và toàn bộ Lifecycle D4/PostgreSQL gate;
  environment checker yêu cầu Alembic head `0011_workforce_releases`.

## API manager mới

Prefix: `/workforce/v1/manager/agent-releases`.

- `POST /publish`
- `POST /{agent_id}/rollback`
- `PATCH /{agent_id}/availability`
- `GET /?capability=...`
- `GET /versions/{version_id}`
- `GET /deployments/{agent_id}`
- `GET /versions/{version_id}/references`

Các endpoint trên dành cho area manager của platform, không thuộc contract API
đối tác. Client không được truyền `Scope` hoặc evaluation/runtime context.

## Kiểm chứng

- Integration API/bootstrap/validator/usage/eval staging: **8 pass**; bao phủ
  publish, rollback, availability, catalog, version/deployment reads,
  references và atomic Eval → candidate → job.
- Lifecycle D4 trên PostgreSQL local: **4 pass** cho concurrent publish,
  lost-response retry, edit-vs-publish và cancellation-vs-publish.
- Registry PostgreSQL gate: **1 pass**.
- Migration SQLite: upgrade head → downgrade `0010` → upgrade head; current là
  `0011_workforce_releases`.
- Gate đúng theo workflow Phase D trên checkout hiện tại: **213 pass và 76
  subtests pass**, không có PostgreSQL skip. Tổng này gồm 17 integration/
  Foundation D1, 31 Registry, 14 workflow A/B, 8 Orchestration C/D, 11 E2E C6,
  100 Builder D3 và 32 Lifecycle D4.

## Ranh giới còn giữ

Tool/policy catalog vẫn là module-owned dependency được inject vào composition;
adapter production bắt buộc resolver của owner đọc/lock bằng UOW được truyền.
Không nhét credential, Scope hay policy từ request body. Phạm vi của riêng D4
không triển khai D5/D6/D7; các bước đó tiếp tục sau D4 theo
`../PHASE_D_SEQUENCE.md`. Live sandbox/model/provider deployment là kiểm chứng
vận hành, không phải lý do để đổi contract D4.
