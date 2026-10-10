# Workforce tests: lifecycle

Chủ sở hữu: **Phó Tiến Anh**. Branch đề xuất: `feat/wf-lifecycle`.

Phạm vi lane: vòng đời riêng từng agent, batch publish, thư viện chung, Settings và version/rollback. Đầu việc: **PTA-01–PTA-16**.

Đọc [kế hoạch triển khai chung](../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) trước khi code, đặc biệt hợp đồng mục 6 và phần công việc mang đúng họ tên.

Tests hiện có kiểm tra SQL/CAS/unique/atomic publish, draft/reuse/batch,
validation/gates, API scope/error, restart/cancel, async snapshots và version
pins. Fakes chỉ ở `_fakes.py`. `frontend/` có DOM behavior tests và runner trong
copy tạm. Xem STATUS trong handoff để biết lệnh chạy và bằng chứng PostgreSQL.

Ghi tiến độ và yêu cầu tích hợp ở [thư mục bàn giao](../../../docs/workforce/handoffs/pho-tien-anh/README.md). File core, contracts dùng chung, migration, dependency và global route cần chuyển cho Nguyễn Chí Hoàng theo kế hoạch.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và binding nhiều ticket/hộp chat. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Phó Tiến Anh bổ sung **PTA-14–PTA-16**: validation/eval nhiều lượt sự kiện và giữ version cho workflow đang chờ. Task chi tiết và các folder con nằm trong mục 5.3 và phần mang tên bạn ở kế hoạch. Quyền của folder gốc không cho phép sửa folder có owner khác.

Folder con mới thuộc phạm vi này:

- [async_evaluation/](async_evaluation/README.md) — Fake clock/runner, pin version qua chờ và stale evaluation.

Đây là phạm vi cần code/test. Chưa có Customer API, Provider Event API, SSE worker, migration hoặc UI mới được triển khai bởi README này.

