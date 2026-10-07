# Bàn giao tool vệ sinh

Ngày 06/10/2026. Nhánh `dev_TeamHoang_PhanDung`.

## Kết quả

Module `server/src/cleaning-tools/` ngang hàng với `technical-tools/`. Đủ 14 đối ứng dùng trực tiếp implementation và schema kỹ thuật hiện có. Đổi namespace, work/assignment/SOP/specialty được chọn sang vệ sinh; giữ nguyên nghiệp vụ. Năm tool bọc API V3 hiện có hỗ trợ tìm người, đọc/tạo việc, phân công và cập nhật tiến độ; catalogue có 19 entry. Mapping đầy đủ tại [TOOLS.md](TOOLS.md).

Đã bỏ implementation result/verify/SOP tự viết và port result riêng, dùng lại các tool/port gốc. Bỏ yêu cầu VERIFIED/result/SOP khi cập nhật completed; backend quyết định quyền/transition/consent/evidence như luồng hiện có. Không dựng policy hoặc kho dữ liệu mới.

## Điểm nối deployment

`index.ts` xuất catalogue/descriptor, host/caller, V3 operations, category check, mapping và contracts. `CleaningDependencies` dùng nguyên `ToolDependencies` kỹ thuật, bổ sung operations và hai hàm xác minh đối tượng `isCleaningWorkOrder`/`isCleaningSpecialty` do deployment cung cấp.

Adapter `technical-dependencies.ts` lọc work orders/assignments sang category vệ sinh, SOP/profile sang CLEAN và nhà thầu sang specialty vệ sinh. Các port storage, utility, asset, sensor, history, measurements, approvals, unit, audit và idempotency giữ interface kỹ thuật. Có thể dùng adapter/store hiện có với dữ liệu được scope đúng; không thêm implementation persistence riêng.

`createDbCleaningWorkOrderCheck` chỉ đọc category/work/ticket trên schema hiện có. Không có migration/table, receipt hoặc transactional caller riêng. Host vệ sinh là wrapper gọi trực tiếp `createTechnicalToolHost` hiện có với catalogue/dependencies vệ sinh, không chỉnh hoặc sao chép source host kỹ thuật.

Deployment cung cấp danh tính/grants/building scope, backend bridge V3 và dữ liệu thật. `CleaningBackend` giữ danh tính và quyền đã xác thực; không giả nhân viên/admin. Repository chưa mount caller hoặc cấp tool cho groupchat. Các fixture chỉ dùng test, không chứng minh đã gọi người hay lưu kết quả production.

## Kiểm tra

- Tests vệ sinh: 45 pass, 0 fail, gồm 14 đối chiếu schema/metadata/delegation; SOP/ACL, result/verify, measurement, request nhà thầu, target scope, dispatch/version/idempotency và cập nhật completed theo V3.
- Một test trong bộ vệ sinh dùng PGlite/schema hiện có để kiểm category/building/tenant; các test còn lại dùng ports/backend mô phỏng.
- Tests kỹ thuật: 882 pass, 0 fail.
- Typecheck server và strict TypeScript check hai file test vệ sinh: pass.
- Git diff phần hiện hữu rỗng; chỉ còn module/test/tài liệu vệ sinh mới. Không đổi agent/groupchat, backend, UI, database/migration hoặc bất kỳ file kỹ thuật hiện hữu nào.

Chưa commit/push hoặc kiểm V3 deployment/groupchat thật.
