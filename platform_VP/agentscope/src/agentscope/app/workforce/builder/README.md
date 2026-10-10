# Workforce backend: builder

Chủ sở hữu: **Bùi Hữu Nghĩa**. Branch đề xuất: `feat/wf-builder`.

Phạm vi lane: chat tạo một/nhiều agent độc lập, phát hiện trùng, chọn tool và sinh manifest từng agent. Đầu việc: **BHN-01–BHN-14**.

Đọc [kế hoạch triển khai chung](../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) trước khi code, đặc biệt hợp đồng mục 6 và phần công việc mang đúng họ tên.

Phase B đã có RequirementExtractor, CapabilitySelector, ReuseMatcher và ProposalService preview. Policy theo schema Tiến Anh; ports/DTO chung giữ nguyên. Session hiện process-local; confirm chỉ xác nhận proposal, chưa tạo draft/agent hoặc publish. Xem [bàn giao Phase B](../../../../../docs/workforce/handoffs/bui-huu-nghia/PHASE_B.md) để chạy test/demo và đọc các điểm tích hợp còn mở.

Ghi tiến độ và yêu cầu tích hợp ở [thư mục bàn giao](../../../../../docs/workforce/handoffs/bui-huu-nghia/README.md). File core, contracts dùng chung, migration, dependency và global route cần chuyển cho Nguyễn Chí Hoàng theo kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và binding nhiều ticket/hộp chat. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Bùi Hữu Nghĩa bổ sung **BHN-12–BHN-14**: Builder hiểu yêu cầu theo dõi dài hạn, chọn năng lực async và tái sử dụng agent. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [async_capabilities/](async_capabilities/README.md) — Requirements và sinh policy theo dõi; reuse/revise, missing capability.

Đây là phạm vi cần code/test. Chưa có Customer API, Provider Event API, SSE worker, migration hoặc UI mới được triển khai bởi README này.

