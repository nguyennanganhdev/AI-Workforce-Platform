# Migration và vận hành

## Artifact

- `0046_workforce_database.sql`: 127 bảng, PK/FK/unique/index/CHECK và RLS policies.
- `0047_workforce_integrity.sql`: btree_gist, exclusion constraints, triggers, FORCE RLS.
- `0048_coordination_and_field_operations.sql`: 25 bảng conversation/collaboration/workforce/dispatch/projection/SLA.
- `0049_coordination_integrity.sql`: ràng buộc liên hàng/thời gian, checkpoint/handoff và FORCE RLS mới.
- `0050_coordination_queue_indexes.sql`: index cho hàng đợi, lease và deadline.
- Snapshot 0046–0050 và `_journal.json`: cùng ledger trong `server/drizzle/`.

File `.sql` là lệnh runner thực thi. `meta/*_snapshot.json` là ảnh chụp cấu trúc để
Drizzle so sánh khi sinh migration tiếp theo, không chạy trực tiếp vào PostgreSQL.
Snapshot 0049 gần giống 0048 vì trigger/exclusion/FORCE RLS không được snapshot;
0050 khác ở tám index phục vụ hàng đợi/deadline. Đây không phải ba database khác nhau.

Drizzle không snapshot trigger/exclusion/FORCE RLS. Giữ migration 0047/0049 khi sinh migration
mới; thay đổi guard nâng cao bằng SQL migration riêng. Không dùng `drizzle-kit push`
để bỏ qua ledger. Không chỉnh migration đã áp dụng thật ở một môi trường.

## Database thử nghiệm

Migration cũ 0000 yêu cầu extension `vector` dù workforce không lưu embedding. Dùng
PostgreSQL có pgvector để khởi tạo database rỗng. 0047 yêu cầu btree_gist. Migration
role có quyền extension/DDL; runtime role không có các quyền đó.

```powershell
docker run --detach --name workforce-db-test --publish 127.0.0.1:55439:5432 --env POSTGRES_PASSWORD=workforce_test --env POSTGRES_DB=workforce_test pgvector/pgvector:pg16
$env:DATABASE_URL='postgres://postgres:workforce_test@127.0.0.1:55439/workforce_test'
bun server/scripts/migrate.ts
$env:TEST_DATABASE_URL=$env:DATABASE_URL
bun test server/tests/workforce-schema.test.ts server/tests/workforce-database.integration.test.ts server/tests/workforce-coordination.integration.test.ts server/tests/workforce-migration.integration.test.ts server/tests/schema.test.ts server/tests/migration-journal.test.ts tests/architecture.test.mjs --timeout 30000
```

Các giá trị trên chỉ dành cho container test. Integration test cần CREATE ROLE để
thử RLS với role không sở hữu bảng; migration-upgrade test cần CREATEDB và tự xóa
database ngẫu nhiên mà nó tạo. Test thường rollback; concurrency test để lại
fixture tenant ngẫu nhiên. Luôn dùng database riêng, không chạy vào database nghiệp vụ.

## Nâng cấp môi trường hiện có

1. Backup theo quy trình vận hành, kiểm tra ledger hiện tại và quyền cài extensions (đã kiểm thử nâng cấp từ 0045).
2. Chạy `bun server/scripts/migrate.ts` với DATABASE_URL của môi trường đích.
3. Runner áp dụng migration còn thiếu theo thứ tự. Chạy lần hai không tạo lại bảng.
4. Bootstrap tenant/membership bằng dữ liệu quản trị đã xác minh; không tự map toàn bộ
   user vào một tenant mặc định hoặc tạo tài khoản demo trong môi trường thật.
5. Cấp runtime role tối thiểu và tích hợp transaction-local tenant context trước khi dùng bảng.

Migration không drop/sửa cấu trúc bảng OpenBot. Sau khi có workforce data, xóa users
có lịch sử bị FK RESTRICT theo thiết kế. Rollback ứng dụng có thể giữ bảng mới chưa dùng;
khi đã có nghiệp vụ, ưu tiên forward fix, không drop history để rollback.

Đợt triển khai này chỉ chạy migration trong container/database thử nghiệm riêng.
Database phát triển/sản xuất của repo chưa được migrate bởi tác vụ này.

## Runtime role và RLS

Runtime cần NOSUPERUSER NOBYPASSRLS, không sở hữu bảng, không có TRUNCATE/DDL.
Grant theo module/service, không blanket grant toàn public schema đang có credentials/auth.
Global domain package chỉ cho runtime SELECT. Policy không tự cấp GRANT.

Mỗi transaction theo tenant đặt context do backend đã xác thực:

```sql
BEGIN;
-- Bind $1 to the tenant authorized by the server.
SELECT set_config('app.tenant_id', $1, true);
-- Scoped statements, including expectedVersion on aggregate updates.
COMMIT;
```

`true` là transaction-local, tránh rò tenant context qua connection pool. Identity
discovery trước chọn tenant dùng resolver chỉ đọc membership theo authenticated user;
không mở BYPASSRLS cho toàn resident API. Worker xử lý từng tenant với context riêng
hoặc role quản trị riêng được giới hạn quyền.

## Transaction command

1. Xác thực user/tenant; BEGIN + SET LOCAL context.
2. Kiểm tra tenant/property membership ACTIVE, in-date; khóa aggregate/slot cần thiết.
3. Dùng domain receipt key `(tenant, actor_user, command_type, idempotency_key)`.
   Key cùng hash trả response cũ; khác hash trả conflict.
4. Mutation dùng expectedVersion; xác minh rule/approval/grant trong service.
5. Ghi BusinessEvent + Outbox + completed receipt trong cùng transaction.
6. COMMIT rồi mới trả success. External I/O đi qua worker với stable event/key.

Quy ước khóa: incident/session/slot/event/invoice trước child/payment. Batch khóa ID
theo thứ tự tăng dần. Retry toàn transaction khi deadlock/serialization failure bằng
idempotency key, không retry riêng SQL sau một external side effect.

## Kiểm tra khi thay đổi schema

```powershell
bun run --filter server typecheck
bun run typecheck:workforce
bun run check:architecture
bun run --filter server db:erd:check
bun test server/tests/schema.test.ts server/tests/migration-journal.test.ts server/tests/workforce-schema.test.ts tests/architecture.test.mjs --timeout 30000
```

Thêm schema file vào config/barrel/exporter; generate từ thư mục server; review SQL và
snapshot; chạy integration tests trên PostgreSQL; sinh lại `db:erd`. Commit schema,
migration, snapshot và catalog cùng nhau. Metadata test không thay integration test.
