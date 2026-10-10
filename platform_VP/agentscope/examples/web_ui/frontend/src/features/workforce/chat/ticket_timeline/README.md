# ticket_timeline — API/event/workflow v1.4

Chủ sở hữu: **Phan Huy Hoàng**. Branch: `feat/wf-orchestration`.
Task bổ sung của owner: **PHH-14–PHH-17**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../../../docs/workforce/handoffs/phan-huy-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Timeline/close nhiều ticket/workflow, mỗi hộp chat giữ đúng binding, reconnect và event/message dedupe.

File dự kiến khi triển khai: `index.ts`, `TicketTimeline.tsx`, `WorkflowStatus.tsx`, `api.ts`. Phase B đã triển khai component/API/controller/state trong folder này.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- State UI được key theo conversation_id + workflow_id/external_ticket_id, không theo user hoặc “ticket gần nhất”. Hai hộp chat có cursor/stream/status/close riêng; event không khớp binding không được render sang hộp đang mở.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục có component/API controller và test Phase B; mounting, worker và migration thật thuộc Phase C. Không tạo stub thành công trong production.

## Phase B — 2026-10-10

Đã có TicketTimeline/WorkflowStatus, state reducer và API/followTimeline controller. Dùng shared/event_transport và Execution WorkforceApprovalCard. Key theo identity + conversation + workflow + ticket + user + chat; snapshot/410, abort, auth failure và message dedupe có test. UI consumer abort follower khi đổi binding và dùng manager JWT/BFF đã được phê duyệt, không đưa machine key vào browser. Real mounting/auth/quote wiring ở C.
