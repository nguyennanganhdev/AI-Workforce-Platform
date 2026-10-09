# workflows — API/event/workflow v1.4

Chủ sở hữu: **Phan Huy Hoàng**. Branch: `feat/wf-orchestration`.
Task bổ sung của owner: **PHH-14–PHH-17**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/phan-huy-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Workflow state/trigger/checkpoint/close/continuation và persisted external ticket/conversation/workflow/group binding; không lưu provider inbox.

File dự kiến khi triển khai: `_models.py`, `_tables.py`, `_repository.py`, `_service.py`, `_scheduler.py`, `_checkpoint.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- start_workflow của external ticket mới tạo đúng một workflow/conversation/group; reply/close resolve group từ binding trước Leader. Hai ticket cùng user có session/context/pending waits riêng; tuple ghép sai bị từ chối trước dispatch và retry không tạo group thứ hai.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.
