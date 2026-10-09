# event_delivery — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch: `feat/wf-foundation`.
Task bổ sung của owner: **NCH-13–NCH-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/nguyen-chi-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Tên folder là scaffold cũ. Triển khai provider credential guard, durable jobs/triggers, SSE notification/recovery và transport auth; không lưu workflow của Huy Hoàng và không gửi HTTP outbound tới đối tác.

File dự kiến khi triển khai: `_auth.py`, `_signals.py`, `_worker.py`, `_recovery.py`, `_repository.py`, `_tables.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- DB public event log là nguồn bền vững; Redis/outbox chỉ đánh thức worker/SSE reader. Không xây subscription endpoint, HTTP sender hoặc retry delivery tới backend đối tác.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.
