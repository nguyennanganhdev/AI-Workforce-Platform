# Bàn giao consumer Người 2 — 18/10/2026

Baseline: `dev_Chien@1ec4465d7f2928f9610b02b0126d39b1443f4163`.
Worktree: `E:/AI-Workforce-Platform-user2`, branch `feat/vin-user2-experience-20261018`.
Không chạy model API, Discord hoặc mutation Domain thật trong quá trình phát triển.

## Consumer đã giao

- Bỏ seed key: commit `e6cb3495`, chỉ console/Studio và consumer tests. `_model_config` lấy
  `storage.vin_platform_service` do Người 1 đăng ký, gọi `platform_model_config` thật.
  Vin mode thiếu authority thì chặn; không fallback credential user.
- Shell dùng C01 `vin-platform-1` và map boolean hiện tại; không gọi endpoint `/me/workspace` giả định.
- Đăng ký dùng `/auth/register-personal`; usage/link/start/complete/unlink dùng route thực trong producer.
- Cư dân/khách hàng và BQL dùng cùng shell, sidebar, Leader, chat và agent pages. Không có frontend cư dân riêng.
  Chuyển không gian hiển thị nằm trong menu tài khoản; route guard không suy quyền theo role.
- Knowledge catalog/readiness/stage/rollback/runtime nhận `ResourceAccessService` của app;
  shared documents được đọc bằng owner resolver trả về, không đổi owner thành cư dân.

## C01: delta cần Người 1 xác nhận

Đã đọc producer đang soạn tại `E:/AI-Workforce-Platform-user1/.../vin_platform/_service.py`.
`capabilities()` hiện trả `contract_version=vin-platform-1`, ExecutionContext và map boolean capability.
Consumer đã dùng đúng version/map này; không suy capability từ role.

Producer hiện chỉ có `workspace_id=personal:<user>`, chưa có danh sách scope được phép hoặc thao tác chuyển scope.
Cần bổ sung DTO có danh sách scope cá nhân/vận hành/quản trị, ID server cấp, tên hiển thị, capability theo scope,
active scope và authorization revision. Chuyển scope phải xác thực lại membership, CAS revision, trả view mới;
timeout phải có thể tải lại scope canonical. UI không gửi acting/billing subject hoặc owner tự khai.

Hiện consumer chỉ chuyển **không gian hiển thị** từ capability server, hủy request/xóa cache/remount.
Đây chưa phải chuyển authority workspace server. Không mở flag cư dân trước khi hoàn tất phần này.

Các capability UI cần phân biệt: đọc và chạy Leader/chat; xem và author agent; xem/manage Knowledge riêng;
schedule; xem/start/revoke domain link; xem usage; management read/operator actions;
account administration; catalog/provider/quota administration. Không dùng `personal.read` thay quyền execute,
không dùng `catalog.manage` thay quyền quản trị tài khoản.

Producer chưa có `accounts.manage`, `providers.manage`, `schedules.manage`/`channels.manage`;
consumer giữ các route tương ứng bị chặn. DOMAIN_ADMIN không tự được quyền admin từ role.

N2-01 có release gate `VITE_VIN_EXPERIENCE_ENABLED`, mặc định tắt. Chưa có matching C01 thì route bị chặn;
không fallback sang role-based admin hoặc response fixture trong production.

Đăng ký cá nhân cần body `{email, username, password}` ở route Người 1 chốt. Không gửi role/domain/area;
không gọi đường đăng ký BQL legacy để tạo cư dân. Cần giữ đường đăng ký BQL riêng nếu còn sử dụng.

## C02/C03: slice ưu tiên

Đã gỡ `_platform_credential`, thay `_model_config` và consumer Studio bằng resolver thật của Người 1.
Consumer test xác minh không persist key vào user và không lookup credential legacy khi authority bị thiếu.

C03 `/me/usage` hiện trả buckets và pending reconciliation; cần thêm effective limits/remaining theo user +
group/pool và kỳ hiện tại. UI chưa tự tính tổng hạn mức từ policy thiếu.

C02 cần resolver chung cho MCP/skill với owner/version/permission và recheck khi dùng/download;
`ResourceAccessService` hiện có credential/agent/Knowledge. Consumer chưa tự viết ACL MCP/skill.
Cần fields/storage purpose/visibility do server gán để hoàn tất N2-02; không dùng `system_role=business`
thay quyền BQL. Shared KB đã có regression binding/readiness; RAG/citation thật vẫn PENDING.

## C09: state transitions cần persistence

- Schedule: scheduled → claimed (lease/fence + logical run ID) → running → succeeded/failed/blocked_auth/
  blocked_quota/waiting_approval/unknown_outcome. Once có timestamp tuyệt đối; claim đến hạn nguyên tử;
  expiry/misfire không biến thành cron hàng năm. Delivery có ledger riêng, retry không rerun model.
- Channel: external provider/app/user ID đã xác minh → exact Platform user/workspace; mỗi event recheck
  revocation. Claim provider event ID và outbox delivery độc lập; DM session không gộp per-chat cư dân.
- Batch publish: manifest bền vững gồm proposal ID/revision, input hash, stable agent IDs, stage/activate
  status từng item, result/receipt và repair cursor. Claim có lease/fence; activation cần atomic batch hoặc
  trạng thái partial có thể repair; không đánh dấu published trước toàn bộ item được xác nhận.

Không sửa storage/migration/shared authority trong lane Người 2. Các gate tích hợp/live giữ PENDING
cho đến khi producer và consumer chạy trên cùng candidate/schema.
