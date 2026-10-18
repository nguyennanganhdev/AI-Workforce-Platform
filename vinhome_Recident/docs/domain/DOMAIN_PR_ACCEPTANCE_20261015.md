# Kiểm tra và làm sạch Domain trước PR vào develop2

Ngày kiểm tra: 2026-10-15. Phạm vi nguồn: `dev_Vinhome`, Domain `vinhome_Recident` và workflow CI của Domain. Đợt này không triển khai lên VPS, không gọi model/Agent thật và không thay dữ liệu vận hành.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Toàn bộ API tests, PostgreSQL riêng và runtime role hạn chế | **409 passed, 10 skipped**, 292 giây |
| HTTP xác nhận hoàn thành/retry/concurrent decision và yêu cầu làm lại | **2 passed**, API thật và database test riêng |
| Object storage thật, direct upload có chữ ký/integrity/replay/quyền bucket | **5 passed**, MinIO riêng |
| Reception adapter/CSKH offline | **13 passed**, không gọi provider thật |
| Resident/staff frontend | **31 file, 169 test passed** |
| Typecheck/build hai frontend và shared package | Đạt |
| Ruff source API/Reception: F401/F811/F821/F841 | Đạt |
| `npm audit` với lockfile sau cleanup | **0 vulnerability** được báo cáo |
| Compose với env local hiện có | `config --quiet` đạt |
| Migration trên database có command cũ | Giữ bản ghi/nội dung, sequence tiếp tục sau backfill, chạy lại không áp trùng |

10 test bỏ qua trong suite API gồm 4 test S3, 2 test HTTP integration và 4 test deployment password legacy opt-in. S3/HTTP đã được chạy riêng như bảng trên; 4 test deployment legacy phụ thuộc launcher/path cũ không được dùng làm bằng chứng production hiện tại. Suite còn cảnh báo từ Starlette/Pydantic; MinIO test có cảnh báo datetime từ SDK. Không giấu warning bằng cấu hình lọc.

Log/XML/audit riêng nằm tại `E:\Vinhomes-Deploy\domain-maintenance-20261015`, ngoài Git. Bộ test dùng database/container riêng, không sửa tài khoản hoặc volume của stack đang chạy.

## Thay đổi bảo trì

- Gỡ 1.160 file Platform cũ khỏi index `dev_Vinhome`; mã cũ được chuyển ra `E:\Vinhomes-Deploy\retired-platform-20261015`. Chỉ giữ thư mục mock đang được container khác bind mount ở máy, không đưa vào Git/PR. Worktree Platform hiện tại được giữ nguyên.
- PR được tạo từ `origin/develop2`, chép riêng `vinhome_Recident/**` và `.github/workflows/vinhomes-domain.yml`. Tree `platform_VP` phải trùng hoàn toàn với nhánh đích; không PR trực tiếp lịch sử nhánh Domain vào develop2.
- Bỏ 4 dependency trực tiếp không dùng: font Inter ở resident, font Be Vietnam Pro ở staff, Streamdown và CLI shadcn. Giữ component vendored, font thực dùng và state CSS cần thiết; Vitest nâng lên 4.1.11.
- Dùng chung runner UI từng process cho local/CI; CI chạy toàn bộ backend, thêm lint source và MinIO riêng.
- Bỏ import không dùng; cập nhật README/ranh giới kiến trúc và ignore account/secret/log riêng.
- Sửa fixture BQL legacy sang staff hợp lệ; thêm kiểm tra token BQL cũ không mở lại quyền operations.
- MCP discovery **16 tool**; declaration điều phối mặc định **7 tool**. Kiểm tra không tự mở thêm quyền Travel/ngữ cảnh dịch vụ trên route cũ.

## Lỗi nghiệp vụ phát hiện và đã sửa

Các command được tạo trong cùng transaction dùng chung `created_at`; sắp xếp bằng timestamp rồi UUID ngẫu nhiên có thể gửi phần ảnh bổ sung trước lệnh mở workflow. Migration **0024_platform_command_order.sql** bổ sung `enqueue_seq` và index hàng đợi; worker dùng thứ tự này, vẫn ưu tiên quyết định approval.

Regression gửi 11 ảnh thành hai lệnh 10 + 1, cố tình đảo UUID so với thứ tự chèn và kiểm tra đủ 11 ảnh được chuyển qua transport Platform giả. Test này chứng minh Domain đóng gói/gửi đúng contract, không chứng minh Agent thật đã xử lý.

Migration backfill giữ thứ tự timestamp/UUID vốn có của command lịch sử; không thể suy ra lại thứ tự gửi đã mất của các command cũ cùng timestamp. Trước rollout cần dừng worker, backup, migrate và rà hàng đợi cũ, đặc biệt multipart chưa được bàn giao. Không replay mù các command đã được nhận ở Platform; giữ reference và đối soát biên nhận.

## Giới hạn nghiệm thu và bước tiếp theo

Domain đạt các kiểm tra source/API/DB/UI nêu trên để review PR. Chưa kết luận nghiệm thu production toàn diện:

1. Chạy CI trên PR và review phạm vi; PR ở trạng thái draft, chưa merge.
2. Rollout image mới cần backup và migration trước khi chạy worker; kiểm tra image/bundle đang phục vụ sau recreate. Đợt này chưa cập nhật Docker chính/VPS.
3. Nghiệm thu Platform/Agent thật hai chiều với route/grant/sự kiện/biên nhận và cư dân/staff. Không tính fallback là thành công nghiệp vụ.
4. Dữ liệu cư trú/nhân sự/ca/phí/SLA mô phỏng chưa thay hồ sơ operator xác nhận; Travel vẫn mock. Chưa expose thao tác cấp/hủy thẻ, khách, booking tiện ích, thanh toán/xóa nợ hoặc duyệt cải tạo qua MCP.
5. Xác minh TLS/DuckDNS bằng `renew --dry-run` trên VPS, phục hồi backup và kiểm thử tải theo số người dùng dự kiến.

Không xóa corpus, template/proposal, migration đã áp dụng, logo/ảnh responsive đang dùng, env, tài khoản riêng hoặc volume dữ liệu.
