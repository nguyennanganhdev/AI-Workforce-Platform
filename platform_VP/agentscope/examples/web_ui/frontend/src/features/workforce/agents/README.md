# Workforce frontend: agents

Chủ sở hữu: **Phó Tiến Anh**. Branch đề xuất: `feat/wf-lifecycle`.

Phạm vi lane: vòng đời riêng từng agent, batch publish, thư viện chung, Settings và version/rollback. Đầu việc: **PTA-01–PTA-16**.

Đọc [kế hoạch triển khai chung](../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) trước khi code, đặc biệt hợp đồng mục 6 và phần công việc mang đúng họ tên.

Thư mục này mới là khung phân vùng công việc, chưa triển khai tính năng. Chủ sở hữu tạo code/test và file con tại đây; không sửa module của thành viên khác.

Ghi tiến độ và yêu cầu tích hợp ở [thư mục bàn giao](../../../../../../../docs/workforce/handoffs/pho-tien-anh/README.md). File core, contracts dùng chung, migration, dependency và global route cần chuyển cho Nguyễn Chí Hoàng theo kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4](../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3. POST nhận việc rồi kết thúc; workflow chờ bằng checkpoint trong DB, callback nối đúng job/ticket/chat, public event log hỗ trợ replay và outbox chịu retry thông báo. ACK hoặc ngắt SSE không đóng ticket.

Owner Phó Tiến Anh bổ sung **PTA-14–PTA-16**: validation/eval nhiều lượt sự kiện và giữ version cho workflow đang chờ. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [async_evaluation/](async_evaluation/README.md) — Report nhiều event/turn và hard gates.

Đây là phạm vi cần code/test. Chưa có webhook, worker, migration hoặc UI mới được triển khai bởi README này.

