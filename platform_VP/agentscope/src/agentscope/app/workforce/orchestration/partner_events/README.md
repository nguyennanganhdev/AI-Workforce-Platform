# partner_events — API/event/workflow v1.4

Chủ sở hữu: **Phan Huy Hoàng**. Branch: `feat/wf-orchestration`.
Task bổ sung của owner: **PHH-14–PHH-17**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../docs/workforce/handoffs/phan-huy-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Public event log, SSE/history/snapshot và notification signal sau commit; không sender outbound.

File dự kiến khi triển khai: `_tables.py`, `_repository.py`, `_projection.py`, `_router.py`, `_stream.py`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- SSE/history đọc cùng DB public event log; notification mất vẫn phải catch-up được. Không enqueue HTTP delivery tới endpoint đối tác.
- Public event project external_ticket_id từ persisted binding. Conversation/stream A không phát event workflow B; cursor/snapshot/history kiểm tra client + user + ticket/conversation binding và không lộ group_id.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.

## Phase B — 2026-10-10

Public exports: ConversationEventService, PublicEventWriter, EventRepository/ConversationAccess và EventCursorExpired. Append/history/snapshot lọc binding/allowlist; after-commit advisory signals và NCH ConversationSseService replay durable log. SQL/auth/HTTP/proxy wiring ở C, không có outbound sender. Bàn giao: PHH PHASE_B.md.
