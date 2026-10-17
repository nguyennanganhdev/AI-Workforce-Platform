# event_transport — API/event/workflow v1.4

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch: `feat/wf-foundation`.
Task bổ sung của owner: **NCH-13–NCH-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../../../../../docs/workforce/handoffs/nguyen-chi-hoang/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Transport fetch-SSE/token refresh/cursor; không chứa quy tắc ticket.

File dự kiến khi triển khai: `index.ts`, `sseClient.ts`, `cursor.ts`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

## Trạng thái Phase B

Đã có fetch-SSE transport trong `sseClient.ts` và cursor abstraction trong
`cursor.ts`:

- gửi bearer token và `Last-Event-ID`, hỗ trợ refresh token một lần khi 401;
- parse chunk/multiline SSE, kiểm tra `id`/`event` khớp public envelope;
- cách ly đúng `conversation_id`, reconnect có backoff và tôn trọng `retry`;
- 410 sinh `EventCursorExpiredError` để caller lấy snapshot;
- cursor chỉ advance khi consumer yêu cầu item tiếp theo, nên event chưa xử lý
  xong sẽ được replay sau reconnect.

Transport không chứa luật ticket, không tự mở stream mới sau mỗi POST và không
quản lý lifecycle workflow. Caller giữ một stream cho mỗi conversation đang
theo dõi và dedupe message theo `message_id` ở projection/UI.
