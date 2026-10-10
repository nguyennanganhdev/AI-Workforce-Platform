# async_workflows — API/event/workflow v1.4

Chủ sở hữu: **Phan Huy Hoàng**. Branch: `feat/wf-orchestration`.
Task bổ sung của owner: **PHH-14–PHH-17**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../docs/workforce/handoffs/phan-huy-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Workflow transitions/checkpoint/HITL/cursor/isolation/crash windows và hai ticket/hộp chat cùng user chạy xen kẽ.

File dự kiến khi triển khai: `test_workflow.py`, `test_replay.py`, `test_close_race.py`, `test_continuation.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Test A1/B1/A2/B2 luôn resolve group A/B tương ứng; shared state/approval/operation/SSE/close không lẫn. Mismatch ticket/conversation/workflow phải zero dispatch/model/tool; hai start đồng thời cho cùng ticket chỉ tạo một binding/group.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.

## Phase B — 2026-10-10

Runner run_phase_b.py: 112 backend scenarios; timeline.test.ts và timeline-render.test.tsx: 36 frontend scenarios. Fake atomic store/UOW/clock/runtime/operations/signals chỉ ở test. Các source PHH/NCH/Execution import thật. B106 kiểm trọn MB lifecycle; B112 chặn start mới trên ticket đã bound; matrix và log nằm trong handoff PHH. Chưa database/HTTP/provider/process crash thật.
