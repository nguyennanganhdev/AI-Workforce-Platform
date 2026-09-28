# Hướng dẫn review ERD/database cho thành viên

## Kết quả bàn giao

Đợt này triển khai persistence theo `docx/01–04` và luồng lễ tân → điều phối → group chat → kỹ thuật → cư dân. Có **190 bảng**, gồm 38 bảng nền OpenBot và 152 bảng workforce; **2.078 cột, 558 FK, 412 CHECK** trong snapshot. Các con số này không tính trigger/exclusion như CHECK.

Đã có schema Drizzle, migration 0046–0050, tenant RLS, integrity guards, data dictionary, ERD và PostgreSQL integration tests. Có 63 test đạt trong bộ kiểm thử liên quan. Database ứng dụng thật chưa được migrate; API/runtime/worker/UI không được triển khai trong đợt này.

## Đọc theo thứ tự

1. [SYSTEM_FLOW](SYSTEM_FLOW.md): hiểu quyền sở hữu dữ liệu, nơi tạo session và nguồn tiến độ cư dân.
2. [COMPLETENESS_REVIEW](COMPLETENESS_REVIEW.md): kiểm tra phạm vi, quyết định và phần service còn phải làm.
3. [TABLE_CATALOG](physical/TABLE_CATALOG.md): tìm tên bảng/nhiệm vụ, mở module tương ứng để đọc từng cột.
4. [Schema TypeScript](../../server/src/db/schema/index.ts): review model thực thi theo module.
5. [Migration 0047](../../server/drizzle/0047_workforce_integrity.sql) và [0049](../../server/drizzle/0049_coordination_integrity.sql): đọc các quy tắc liên hàng/thời gian không có trong snapshot.
6. [COVERAGE](COVERAGE.md) và [MIGRATION_RUNBOOK](MIGRATION_RUNBOOK.md): xem bằng chứng kiểm thử, giới hạn và cách tái hiện.

## Tổ chức thư mục

| Đường dẫn | Nội dung | Cách thay đổi |
|---|---|---|
| `docx/01–04` | Đặc tả logic và ranh giới kiến trúc; `02` có mở rộng resident/tenant | Review quyết định nghiệp vụ trước khi đổi |
| `server/src/db/schema/platform/` | Shared Kernel, agent governance, runtime, conversation/collaboration, audit/memory | Sửa schema theo module; không import repository Vinhomes |
| `server/src/db/schema/domains/vinhomes/` | Property/intake/operations, kỹ thuật, dịch vụ, tài chính, tiến độ cư dân | FK sang identity dùng chung; không FK tới runtime/agent |
| `server/src/db/schema/columns.ts` | Cột thời gian/version, JSONB và CHECK helper dùng chung | Giữ hành vi nhất quán |
| `server/drizzle/*.sql` | Thay đổi database có thứ tự, cả DDL tự sinh và integrity viết tay | Một runner/ledger, không chỉnh lịch sử đã triển khai |
| `server/drizzle/meta/` | Journal và full-schema snapshots theo mốc | Xem [giải thích meta](../../server/drizzle/meta/README.md); không review như dữ liệu nghiệp vụ |
| `server/scripts/table-purposes.json` | Mô tả nhiệm vụ của từng bảng, kể cả OpenBot shell | Sửa ở đây để nội dung được sinh lại nhất quán |
| `server/scripts/export-workforce-erd.ts` | Sinh ERD/data dictionary từ schema | `db:erd`, `db:erd:check` |
| `docs/erd/physical/` | 40 module ERD, danh mục 190 bảng và mọi trường/khóa | Tự sinh; không chỉnh trực tiếp |
| `docs/erd/` và `docs/adr/platform/0011–0012` | Flow, review, coverage, runbook và quyết định thiết kế | Tài liệu viết tay cần review cùng schema |
| `server/tests/workforce-*.test.ts` | Schema inventory, integration và upgrade test | Dùng PostgreSQL test riêng |
| `scripts/check-architecture.mjs`, `tests/architecture.test.mjs` | Bảo vệ ranh giới import giữa Platform/domain/shell | Không mở quyền import rộng để lách boundary |

## Phân công review gợi ý

| Thành viên phụ trách | Cần xác nhận | Điểm đọc chính |
|---|---|---|
| Nghiệp vụ/BQL | Incident khác report/session; giao nhận, hẹn, QC, redo, resident confirmation; giới hạn SLA | SYSTEM_FLOW, COMPLETENESS_REVIEW, catalog Vinhomes |
| Backend Vinhomes | Tenant/project/parent scope, action/approval/grant, CAS, transaction + event/outbox, private projection | Schema Vinhomes, SQL 0047/0049, database/coordination tests |
| Agent/runtime | Handoff ack/retry, participant version, session/lease/checkpoint/wait, idempotency và soft domain refs | Schema platform runtime/collaboration/conversations, flow mục 3–4 |
| Data/DevOps | Nâng cấp giữ dữ liệu, ledger thứ tự, indexes, FORCE RLS, least-privilege role, rollback strategy | SQL 0046–0050, meta README, runbook, upgrade test |
| QA | Case đúng/sai và concurrency; phân biệt DB invariant với end-to-end chưa có | COVERAGE, các integration tests, scope table |

## Những điểm cần review kỹ

- `users.id` vẫn là text; tenant mới là UUID. Không coi tenant ID cũ của shell là UUID mới một cách tự động.
- RLS bảo vệ tenant, không tự phân quyền mọi cư dân trong cùng tenant. Service phải xác minh membership, report owner và visibility.
- `platform_workflow_session` không thay `vh_incident`; completion của agent không xác nhận việc đã sửa xong.
- Lễ tân đọc `vh_report_update` theo quyền cư dân. ETA phải có field progress xác nhận; group chat không được đưa thẳng ra ngoài.
- Handoff/outbox/inbox cần worker để hoạt động. DB có state/dedupe/guard, chưa có delivery thật hoặc exactly-once qua mạng.
- Checkpoint fencing không tự bảo vệ mọi side effect. Tool/command phải kiểm tra lease, quyền, version và idempotency tại service.
- SLA hiện là ELAPSED; kho vật tư, HR đầy đủ và kế toán/hoàn tiền đầy đủ chưa thuộc phạm vi.

PR chỉ bàn giao database/ERD và đặc tả liên quan. Các thay đổi frontend/demo đang có ở workspace được giữ ngoài commit này.
