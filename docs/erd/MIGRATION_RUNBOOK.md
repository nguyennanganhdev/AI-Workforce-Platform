# Chạy migration và điều kiện tích hợp

## Phạm vi

0051/0052 dành cho trường hợp đã xác nhận: local chưa có dữ liệu nghiệp vụ cần giữ. Không sửa 0000–0050; không migrate database thật trong tác vụ thiết kế này.

0051 từ chối nếu bảng business/runtime hoặc nền bị ảnh hưởng có dữ liệu. Auth user có thể còn và được giữ ID. Nếu gặp từ chối, xuất dữ liệu và thiết kế mapping riêng; không bỏ guard, không tự TRUNCATE, không gán tenant đầu tiên.

## Thứ tự triển khai

1. Review SQL, schema và [đối chiếu](P0_REDESIGN_TRACKER.md).
2. Tạo PostgreSQL/pgvector riêng cho test; tuyệt đối không lấy DATABASE_URL ứng dụng làm test fallback.
3. Chạy ledger vào database test.
4. Chạy schema/integration/architecture/typecheck và ERD check.
5. Hoàn tất tích hợp ứng dụng bên dưới trước khi áp dụng vào môi trường phục vụ người dùng.

PowerShell tại repo root (URL ví dụ, chỉ dành cho test):

```powershell
$env:TEST_DATABASE_URL = 'postgres://postgres:test_password@127.0.0.1:55439/workforce_test'
$env:DATABASE_URL = $env:TEST_DATABASE_URL
bun run --cwd server db:migrate
bun test ./server/tests/workforce-schema.test.ts ./server/tests/workforce-database.integration.test.ts ./server/tests/workforce-coordination.integration.test.ts ./server/tests/workforce-migration.integration.test.ts ./server/tests/unified-database.integration.test.ts --timeout 30000
bun run --cwd server typecheck
bun run typecheck:workforce
bun run check:architecture
bun run --cwd server db:erd:check
```

Kiểm tra endpoint trước khi chạy. Migration cần quyền DDL và nhìn thấy toàn bộ dữ liệu để preflight kiểm tra được; tài khoản API không dùng quyền đó.

## Trạng thái runtime trước khi triển khai

| Việc bắt buộc | Vì sao |
|---|---|
| Provision tenant và tenant membership | Global login không tự tạo đơn vị nghiệp vụ |
| Bọc reader/writer bằng transaction tenant đã xác thực | Bảng nền mới fail closed nếu thiếu app.tenant_id |
| Rà package sync, scheduler, audit, callbacks, credential resolver | Các đường nền hiện chưa đồng loạt truyền tenant |
| Sửa loader theo deployment → AgentVersion → bindings | agents.configuration không được lách bản đã kiểm duyệt |
| Reader/writer chat dùng channel_messages | UI hiện có chưa tự đổi nguồn transcript khi migrate |
| Worker outbox và Intelligence adapter | Cần retry/replay/receipt; không tuyên bố đã đồng bộ từ schema |
| Domain API kiểm tra người đọc/cư dân | RLS tenant không thay ACL cùng tenant |
| AgentScope service/adapters | agent-runtime hiện là contract/scaffold |
| Regression app/server/worker toàn bộ | Test database không chứng minh upstream application đã tương thích |

Đây là thay đổi database có yêu cầu phối hợp triển khai ứng dụng, không phải migration tương thích ngược có thể bật riêng trên bản app cũ.

## Context và database role

Runtime role NOSUPERUSER NOBYPASSRLS, không sở hữu bảng, không TRUNCATE/DDL. Grant theo service; không cấp SELECT toàn schema cho cư dân. Worker queue có quyền vận hành riêng.

```sql
BEGIN;
-- $1 lấy từ authenticated membership, không tin tenant_id từ request.
SELECT set_config('app.tenant_id', $1, true);
-- Truy vấn có quyền nghiệp vụ; UPDATE với expectedVersion/revision.
COMMIT;
```

Không SET tenant cấp connection rồi trả connection vào pool; dùng transaction-local context.

## Metadata và khả năng khôi phục

meta chỉ có journal/snapshot JSON; hướng dẫn đặt tại [server/drizzle/README](../../server/drizzle/README.md). Giữ mọi snapshot lịch sử. FORCE RLS, trigger và exclusion nằm trong SQL thủ công.

Migration mới từ chối dữ liệu không rỗng và chạy trong transaction của migrator. Không có down migration tự xóa schema. Với local disposable có thể tạo database mới riêng; với dữ liệu thực phải có backup/restore và mapping được kiểm chứng.
