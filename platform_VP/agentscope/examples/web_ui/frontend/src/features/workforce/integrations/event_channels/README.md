# event_channels — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Phương Đông**. Branch: `feat/wf-registry`.
Task bổ sung của owner: **NPD-10–NPD-12**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../../../docs/workforce/handoffs/nguyen-phuong-dong/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: UI theo dõi readiness Provider Event API/MCP query/correlation, không quản lý SSE transport của Chí Hoàng.

Files hiện có: `index.ts`, `EventChannelsPanel.tsx`, `readiness.ts`.
API/transport do shell inject khi nối Phase C.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Phase B export `EventChannelsPanel` và `EventChannelView` qua `index.ts`.
Caller inject channels/loading/error/onRetry; dùng house components, không tự tạo
transport hoặc root route. Readiness tách capability cấu hình khỏi auth/binding/
correlation thực tế; disable call mới không che reception hợp lệ cho job cũ.
Blocker dùng mã allowlist, không render raw error/credential/secret.
Tests và điểm nối API/shell Phase C xem
[PHASE_B.md](../../../../../../../../docs/workforce/handoffs/nguyen-phuong-dong/PHASE_B.md).
