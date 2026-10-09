# Script tích hợp Workforce

Owner của file gốc và cấu hình dùng chung: **Nguyễn Chí Hoàng**.

Đọc [kế hoạch triển khai và phân công sáu thành viên](../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Các thư mục con có README ghi rõ owner; không suy ra quyền sửa mọi thư mục con từ quyền sở hữu thư mục gốc.

Đây là khung thư mục được chuẩn bị để làm song song. Chưa có runtime, script, migration hay kiểm thử Workforce được triển khai tại đây.

Mọi thay đổi hợp đồng, dependency, migration, CI và route composition phải được tích hợp tập trung theo mục 5 và mục 14 của kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4](../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3. POST nhận việc rồi kết thúc; workflow chờ bằng checkpoint trong DB, callback nối đúng job/ticket/chat, public event log hỗ trợ replay và outbox chịu retry thông báo. ACK hoặc ngắt SSE không đóng ticket.

Owner Nguyễn Chí Hoàng bổ sung **NCH-13–NCH-16**: contracts async, delivery/outbox, auth hai chiều, SSE transport và tích hợp runtime. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [event_delivery/](event_delivery/README.md) — Công cụ replay/retention có dry-run và scope; không tự chạy xóa dữ liệu.

Đây là phạm vi cần code/test. Chưa có webhook, worker, migration hoặc UI mới được triển khai bởi README này.

