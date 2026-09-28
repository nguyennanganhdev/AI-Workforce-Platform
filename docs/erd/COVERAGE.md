# Coverage: nguồn → physical database

| Nguồn | Đã triển khai | Kiểm chứng |
|---|---|---|
| 01 Shared Kernel | Tenant, user bridge, memberships, roles, packages/installations | Schema + tenant FK/RLS tests |
| 01/04 boundary | Prefix/module ownership, một ledger, soft subject/actor refs | Architecture + FK boundary tests |
| 02 §4,19 | Property hierarchy, timed memberships, applications/proof | Wrong tenant/project rejected; overlap exclusion |
| 02 §5,20 | Case/request/candidate/report/attachments/feedback/confirmation | Candidate unique, file guard, scoped report/reporter/confirmation |
| 02 §6–9 | Incident/task/action/rule/approval/grant/work order | Version/CAS, payload/policy FK, cycle/redo tests |
| 02 §10–12 | Checklist/files/evidence/QC/communication/root cause | Append-only guards; runtime FK forbidden |
| 02 §13 | CleaningPlan A5 | `vh_task.domain_data` + schema version |
| 02 §14,21 | Services/booking/billing/loyalty/content/community/discovery | Full inventory test; booking/payment/event integrity |
| 02 §22 | Command receipt/outbox | Scoped uniqueness, completed receipt pin, lease/retry metadata |
| 03 §4–10 | Registry/factory/resource catalogs/bindings | Normalized revisions; frozen spec/bindings/catalog content |
| 03 §11–13 | Evaluation/baseline/gates/approvals/deployment | Publish prerequisites, deployment eligibility, suite pinning |
| 03 §14 | Session/step/run/tool/artifact/decision/proposal/grant ref | Parent FKs, acyclic graph, production eligibility |
| 03 §15 | Memory namespace/item/revision/review/vector | Approval required; revoke queues deletion; content pinning |
| 03 §16 | Audit/outbox/idempotency | Append-only audit, unique key, retry/lease fields |
| Luồng lễ tân/điều phối bổ sung | Conversation/subject/message, handoff, event receipt | Owner/order/history, consumer dedupe, acknowledgement/expiry |
| Group chat và recovery bổ sung | Participants/control/messages/checkpoint/wait | Session/version scope, production eligibility, lease fence/cursor, concurrent append |
| Vận hành kỹ thuật bổ sung | Team/member/skill/shift, asset/incident asset, assignment/appointment/progress | Staff eligibility, overlap, active assignment, asset location, event provenance |
| Phản hồi cư dân bổ sung | Report update, notification delivery | Recipient FK, ETA/source time/version, delivery recipient/event |
| SLA/tích hợp bổ sung | SLA policy/incident SLA/escalation, provider event | Pinned elapsed deadlines, deadline mirror, callback dedupe |

Mọi bảng/cột/khóa/index/CHECK ở [physical catalog](physical/README.md).
Schema test đối chiếu inventory Vinhomes trong nguồn. `db:erd:check` phát hiện catalog
lệch schema; migration-journal test đối chiếu file/entry/snapshot và thứ tự ledger.

## Kết quả hiện tại — 2026-09-28

- **63 tests đạt, 0 lỗi**, 3.239 assertions trong bảy file schema/architecture/migration/integration, gồm 13 test coordination/field mới.
- PostgreSQL 16/pgvector: migrate database rỗng, nâng cấp từ 0045, chạy lại ledger đều đạt; **190 bảng, 151 FORCE RLS** được đối chiếu trực tiếp. Snapshot gồm 2.078 cột, 558 FK và 412 CHECK.
- Đã kiểm thử hai message append đồng thời; chỉ một bản ghi nhận cùng next sequence. Bộ baseline vẫn kiểm thử tranh chấp slot booking.
- Server và workforce typecheck đạt; kiểm tra architecture đạt. Lần chạy ban đầu architecture vượt timeout mặc định 5 giây; chạy bộ kiểm thử với `--timeout 30000` đạt, không thay logic kiểm thử.
- ERD tự sinh bao phủ 40 module và có mô tả nhiệm vụ mọi bảng, kể cả shell cũ. Drizzle báo không có schema drift; `db:erd:check` và kiểm tra link đều đạt. Biome kiểm tra 38 file không có lỗi.
- Mermaid parser kiểm tra thành công cả 86 sơ đồ trong bộ tài liệu; sơ đồ quan hệ toàn dự án chia theo module để dễ xem.
- Chỉ dùng container/database thử nghiệm riêng. Chưa migrate database ứng dụng thật; chưa chạy end-to-end của API/worker và toàn bộ suite OpenBot không liên quan.

## Baseline đã kiểm chứng — 2026-09-27

- 49 tests đạt, 0 lỗi, trong sáu file schema/architecture/migration/integration.
- PostgreSQL 16 có pgvector: migrate database rỗng thành công; nâng cấp từ 0045
  giữ nguyên text user ID; chạy migration lần hai không tạo trùng; 165 bảng và
  126 bảng có FORCE RLS được đối chiếu trực tiếp từ PostgreSQL.
- Có test ghi đồng thời để xác nhận chỉ một booking chiếm được capacity cuối cùng.
- Server typecheck và workforce typecheck đạt; Biome kiểm tra 29 file schema/exporter/test đạt.
- Drizzle generate báo không có schema drift; catalog ERD check và toàn bộ link tài liệu đạt.
- Chỉ chạy trên database thử nghiệm riêng. Chưa chạy toàn bộ integration suite của
  các module OpenBot không thay đổi và chưa migrate database ứng dụng thật.

## Quyết định bổ sung

- User ID giữ text; entity mới dùng UUID. TENANT_DOMAIN hợp nhất vào DOMAIN_INSTALLATION.
- PostgreSQL dùng public prefix/module ownership; không di chuyển bảng shell.
- Resource catalog luôn có tenant; domain package catalog là global.
- FK ghép bổ sung parent context; timestamp/version chung cho mutable records.
- Execution grant có token hash cụ thể hóa authorization boundary nguồn 01/04.
- Workflow session thêm environment để tách evaluation/dev khỏi production.
- Domain receipt dùng actor/command scoped key theo §22; platform vẫn tenant/key.
- Facility dùng non-overlapping slots và capacity N cho shared resources.
- Payment ref unique theo provider; provider identifier phải chứa merchant/account
  nếu reference của nhà cung cấp không unique toàn hệ thống.

## Bước API/integration tiếp theo

Actor authorization, hiệu lực membership mỗi request, private projections, rule execution,
webhook signatures, download ACL, outbox workers, Qdrant sync, device receipts, frontend
transport và tenant policy đóng incident/cancellation/retention. Database đã có mô hình
và integrity guards; chưa có endpoint/provider implementation cho các phần này.
