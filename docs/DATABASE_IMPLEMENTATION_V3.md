# Triển khai database V2 + V3

## Nguồn và phạm vi

Schema ứng dụng có **148 bảng**: 136 bảng trong Reviewed V2, cộng 12 bảng mới của V3; 6 bảng V3 thay thế định nghĩa V2. Ba bảng legacy được giữ để tương thích theo thiết kế. Từ điển gốc được lưu trong `server/src/db/design/v2.json`, `v3.json`; bản hợp nhất là `merged.json`.

- `server/src/db/schema/tables.ts`: toàn bộ bảng Drizzle, kiểu, khóa, CHECK, index và tenant RLS.
- `server/src/db/invariants.sql`: ràng buộc liên bảng, trigger, khoảng hiệu lực không chồng lấn.
- `server/src/db/generated-invariants.sql`: FORCE RLS, append-only, updated_at và index bổ sung.
- `scripts/generate-db-schema.py`: tái tạo schema từ từ điển có bổ sung quy tắc triển khai. Khi thay đổi thiết kế cần cập nhật cả catalog/quy tắc sinh, không chỉ sửa file sinh.

Các module schema cũ được giữ dưới dạng re-export để các import hiện có dùng cùng một định nghĩa bảng. Đã điều chỉnh caller liên quan ở server, worker, authentication, people, tenant package, plugin, computer và routine; role ứng dụng gồm `admin`, `management`, `staff`, `customer`.

## Tạo migration mới

Chạy tại thư mục dự án:

```sh
bun run --cwd server db:generate
```

Lệnh này sinh baseline và nối extension `vector`, `btree_gist`, trigger, exclusion constraint và FORCE RLS. Không dùng trực tiếp `drizzle-kit generate` cho baseline vì snapshot Drizzle không quản lý SQL bổ sung này.

Sau khi xem SQL và cấu hình đúng database trống:

```sh
bun run --cwd server db:migrate
```

Migration/snapshot/journal cũ đã xóa khỏi mã nguồn. Không xóa dữ liệu hay lịch sử migration trong database đang chạy. Baseline mới dành cho **database trống**; database có dữ liệu cần kế hoạch chuyển đổi riêng. Những lần sửa trigger/function sau baseline phải có custom migration tương ứng.

## Tenant, role và runtime

`platform_admins` lưu quyền admin toàn nền tảng; `scoped_user_roles` gắn ba role nghiệp vụ với `tenant_memberships` và `access_scopes`. `user_roles` chỉ còn là bảng legacy, không được dùng làm nguồn cấp quyền. Màn hình admin cũ hỗ trợ bật/tắt admin; cấp management/staff cần scope cụ thể và API nghiệp vụ riêng.

Host OpenBot hiện có dùng một tenant package, được ánh xạ sang UUID tenant/workspace ổn định qua `deployment-scope.ts`. Các insert cũ có default lấy tenant/workspace từ connection context; thiếu context thì thất bại. API đa tenant phải xác minh quyền rồi dùng `withDatabaseScope` với `SET LOCAL` trong transaction, không tin tenant/user ID trong request.

Khóa ngoại tenant-composite chặn tham chiếu chéo tenant. RLS hiện bảo vệ biên tenant; phân quyền chi tiết theo user, workspace, scope, ticket và RAG ACL vẫn phải được kiểm tra tại service. Dùng tài khoản runtime không có SUPERUSER/BYPASSRLS; FORCE RLS không hạn chế superuser.

Ứng dụng lưu mapping ownership/runtime và memory namespace; trigger kiểm tra principal/user/team/agent version và chặn đổi chủ mapping. Bảng checkpoint vật lý của LangGraph cùng dữ liệu nội bộ do framework quản lý **không thuộc 148 bảng** và không bị ứng dụng tạo lại. Adapter phải tra binding đã được xác thực trước khi gọi framework; không cho client truyền tùy ý thread ID. Việc tích hợp LangGraph/AgentScope runtime và các endpoint V3 là công việc nghiệp vụ tiếp theo, không được tự sinh chỉ nhờ migration.

## Triage và ảnh hiện trường

Assessment và decision là lịch sử bất biến. Áp dụng quyết định và cập nhật projection ticket phải nằm trong cùng transaction; có kiểm tra generation/version, nguồn policy/rule và yêu cầu phê duyệt khi hạ mức. Policy đã publish không được sửa nội dung. Service vẫn phải kiểm tra thẩm quyền người phê duyệt và thực thi bộ đánh giá rule.

Ảnh lưu bytes ở S3/MinIO; database lưu `storage_locations`, `files`, `file_objects`, upload/evidence và audit liên quan. Ràng buộc kiểm tra tenant prefix của object key, file/object cùng scope, bản gốc đã được xác minh và tính bất biến hash/version của ảnh được chấp nhận. Không lưu presigned URL như địa chỉ lâu dài hoặc secret S3 dạng plaintext. Upload, quét nội dung, xác minh hash bằng server và lifecycle xóa object cần service thực thi; database không thay thế các bước đó.

## Kiểm chứng

```sh
bun run --cwd server db:check
bun run --cwd server db:verify
```

`db:verify` dùng PostgreSQL WASM cô lập với pgvector, không truy cập `DATABASE_URL`. Đã áp dụng baseline thật sinh từ wrapper, kiểm tra đủ 148 bảng và 18 trường hợp: khóa ngoại chéo tenant, ownership thread/memory, triage đồng bộ/version, policy bất biến, S3 prefix/hash, audit và tenant RLS.

TypeScript server, worker, app đã được kiểm tra. Các bài integration cũ cần PostgreSQL riêng qua `TEST_DATABASE_URL`; chưa xác nhận toàn bộ suite đó trên database thực. Các test/schema thành công không có nghĩa mọi workflow V3 đã có endpoint hoặc UI.
