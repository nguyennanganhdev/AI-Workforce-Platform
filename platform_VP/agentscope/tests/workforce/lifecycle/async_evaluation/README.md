# async_evaluation — API/event/workflow v1.4

Chủ sở hữu: **Phó Tiến Anh**. Branch: `feat/wf-lifecycle`.
Task bổ sung của owner: **PTA-14–PTA-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../docs/workforce/handoffs/pho-tien-anh/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Fake clock/runner, pin version qua chờ và stale evaluation.

File dự kiến khi triển khai: `test_evaluation.py`, `test_version_pins.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Đã có `test_evaluation.py` và `test_version_pins.py`, dùng fake ports trong
folder cha cùng SQL repository thật. Chạy được với SQLite hoặc PostgreSQL test
DB; không gọi provider/model thật. Xem STATUS để biết bằng chứng và giới hạn.
