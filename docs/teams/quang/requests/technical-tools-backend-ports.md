# Bàn giao backend để tích hợp 7 technical tools đầu

Module Quang export `createSevenTechnicalTools` tại `server/src/technical-tools/tools.ts`. Host cần cung cấp execution context đã xác thực, không lấy tenant, actor, role hoặc quyền từ business input của agent.

## Port cần Chiến nối

1. `BuildingAccessPort`: xác minh capability grant và building nằm trong scope của principal. `building_id` trong input chỉ là điều kiện chọn dữ liệu.
2. `TenantReadSessionPort`: chạy callback đọc DB với `app.tenant_id` đúng context để RLS có hiệu lực. Adapter outage vẫn có `tenant_id` trong điều kiện truy vấn.
3. `CoveringScopesPort`: trả các `access_scopes.id` bao phủ building (building, zone, site, management hoặc tenant khi được phép). Không truyền `building_id` trực tiếp làm `scope_id`.
4. Gateway `/internal/tools/*`: đăng ký đúng bảy tên trong catalog, cấp context đã xác thực, timeout, audit và chỉ expose tool được grant. Chiến sở hữu `app.ts`/entrypoint.
5. Authorized knowledge retrieval: thay `createMockSopPort` bằng adapter đọc tài liệu `published`, active version đã review/ingest và còn hiệu lực; lọc knowledge-base ACL, document ACL và document scope **trước khi xếp hạng/top-k**. Trả excerpt, acceptance criteria và citation đúng version.
6. Asset/BMS/maintenance source: thay `createMockReadPorts` bằng adapter hoặc mock POC được host cấp và định danh tenant/building. Chốt metric-unit allowlist và ngưỡng stale với Domain Owner.
7. Maintenance write repository: thay `createMockMaintenancePort` bằng lưu trữ bền vững. Transaction phải xác minh result `VERIFIED`, work order, asset, assignment/management, quyền; ghi event append-only, audit/outbox và idempotency key + payload hash nguyên tử. Retry cùng key/payload trả cùng result; payload khác trả `CONFLICT`.

Adapter mock hiện chỉ dùng cho POC/test, không làm bằng chứng đã có kết nối hệ thống ngoài hoặc persistence production. `createInterruptionDbPort` đã có query thật nhưng chưa được host cấp session và scope resolver. Không cần Quang sửa schema/migration hoặc server entrypoint để hoàn thành phần module.
