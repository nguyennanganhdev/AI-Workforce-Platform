# Workforce backend: orchestration

Chủ sở hữu: **Phan Huy Hoàng**. Branch đề xuất: `feat/wf-orchestration`.

Phạm vi lane: Leader chọn group khi có request, chat/@agent và context từ thư viện agent chung. Đầu việc: **PHH-01–PHH-17**.

Đọc [kế hoạch triển khai chung](../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) trước khi code, đặc biệt hợp đồng mục 6 và phần công việc mang đúng họ tên.

Thư mục hiện có gói đề xuất schema Phase A tại `phase_a.py`, `workflows/phase_a.py` và `partner_events/phase_a.py`. Đã có service Phase B với các repository/runtime/auth ports được inject; HTTP/app wiring và adapter thật thuộc Phase C. Xem [trạng thái PHH](../../../../../docs/workforce/handoffs/phan-huy-hoang/STATUS.md). Chủ sở hữu chỉ tạo code/test trong lane của mình.

Ghi tiến độ và yêu cầu tích hợp ở [thư mục bàn giao](../../../../../docs/workforce/handoffs/phan-huy-hoang/README.md). File core, contracts dùng chung, migration, dependency và global route cần chuyển cho Nguyễn Chí Hoàng theo kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và binding nhiều ticket/hộp chat. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Phan Huy Hoàng bổ sung **PHH-14–PHH-17**: workflow ticket, checkpoint/continuation, public event log, SSE/history và chat timeline. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [workflows/](workflows/README.md) — Workflow state/trigger/checkpoint/close/continuation; không lưu provider inbox.
- [partner_events/](partner_events/README.md) — Public event log, SSE/history/snapshot và notification signal sau commit; không sender outbound.

Đây là phạm vi cần code/test. Chưa có Customer API, Provider Event API, SSE worker, migration hoặc UI mới được triển khai bởi README này.

