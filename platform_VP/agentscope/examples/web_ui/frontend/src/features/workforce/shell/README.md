# Workforce frontend: shell

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch đề xuất: `feat/wf-foundation`.

Phạm vi lane: contracts single/batch, AREA_MANAGER + domain/area/account, partner mapping/grant và tích hợp AgentScope. Đầu việc: **NCH-01–NCH-16**.

Đọc [kế hoạch triển khai chung](../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) trước khi code, đặc biệt hợp đồng mục 6 và phần công việc mang đúng họ tên.

Thư mục này mới là khung phân vùng công việc, chưa triển khai tính năng. Chủ sở hữu tạo code/test và file con tại đây; không sửa module của thành viên khác.

Ghi tiến độ và yêu cầu tích hợp ở [thư mục bàn giao](../../../../../../../docs/workforce/handoffs/nguyen-chi-hoang/README.md). File core, contracts dùng chung, migration, dependency và global route cần chuyển cho Nguyễn Chí Hoàng theo kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và binding nhiều ticket/hộp chat. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Nguyễn Chí Hoàng bổ sung **NCH-13–NCH-16**: contracts async, delivery/outbox, auth hai chiều, SSE transport và tích hợp runtime. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [delivery_monitor/](delivery_monitor/README.md) — Tên scaffold cũ; theo dõi SSE/replay/cursor và event backlog theo manager scope.

Đây là phạm vi cần code/test. Chưa có Customer API, Provider Event API, SSE worker, migration hoặc UI mới được triển khai bởi README này.

