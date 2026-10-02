# Đẩy sửa lỗi API/database lên nhánh backend

- Ngày: 2026-10-02
- Yêu cầu: push các sửa gần nhất lên `dev_TeamChien-beHuy`; giữ phạm vi API và tài liệu, không đưa frontend/tích hợp FE–BE lên Git.

## Thay đổi
- Đóng gói migration 0008, seed Supervisor version, sửa triage tùy chọn và cursor PostgreSQL trong API schema_v2.
- Đưa kèm test database và báo cáo 39 test đã chạy ở task trước, tài liệu nghiệp vụ/schema/kế hoạch và đánh dấu tài liệu cũ.
- Test adapter cư dân bỏ qua khi checkout backend không có mã frontend; các test API/PostgreSQL vẫn khả dụng.
- File `no_need_` trong my-docs đã được chủ dự án bỏ khỏi workspace sau lượt đánh dấu; không khôi phục. Liên kết backlog trỏ vào nghiệp vụ mới và bộ quy tắc gốc.

## Quyết định & giả định
- Chỉ stage danh sách file cụ thể. FE, Hono proxy/gateway, demo UI/launcher, cấu hình integration và dependency thay đổi giữ ở local.
- Không đưa credential, local database, virtualenv, ảnh/log vào Git.

## Xác minh
- Fetch nhánh remote: HEAD và origin cùng commit 6266af0 trước commit mới.
- Không chạy lại test trong task push; kết quả suite và giới hạn thuộc `2026-10-01-api-database-flow-tests.md`.
- Kiểm tra danh sách staged, diff/whitespace và dependency test trước commit.

## Rủi ro / việc còn lại
- Bộ test adapter frontend sẽ skip trên checkout API-only; đây không phải bằng chứng tích hợp FE.
- Các nhóm thay đổi ngoài phạm vi backend vẫn nằm trong workspace.
