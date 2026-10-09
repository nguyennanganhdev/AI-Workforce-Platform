# async_api — API/lifecycle đa lĩnh vực và nhiều ticket v1.4.3

Chủ sở hữu: **Nguyễn Chí Hoàng**. Branch: `feat/wf-foundation`.
Task bổ sung của owner: **NCH-13–NCH-16**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: shared DTO/OpenAPI/hướng dẫn cho Customer API dùng chung mọi lĩnh vực, gồm external ticket/conversation binding; SSE/history và Provider Event là capability tùy chọn khi next_action yêu cầu tracking. Không đặc tả endpoint đối tác phải host hoặc tổ chức nội bộ MCP.

File dự kiến khi triển khai: `INTEGRATION_GUIDE.md`, `API_EXAMPLES.md`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience người dùng; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- DTO phải biểu diễn `external_ticket_id?`, TicketConversationBinding và lỗi mismatch; route ticketed yêu cầu external ticket. Không nhận group_id/internal ticket/conversation để route. Hai hộp chat cùng user có binding riêng và public event project đúng external_ticket_id.
- Backend khách hàng chỉ cần SSE/history cho watch_request/watch_events hoặc UX realtime; không bắt buộc ở response-only/interactive. Không xây outbound webhook sender.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.

Contract API đích: [CONTRACT_TICH_HOP_DOI_TAC.md](../../../CONTRACT_TICH_HOP_DOI_TAC.md). OpenAPI/sample phải có read-only `closed/none`, plan/booking interactive, external-tracking, request/reply `200`, fallback `202/watch_request`, optional SSE/history, close `200/none` và một external user có hai external ticket/conversation. Không để code/schema/tài liệu lệch nhau.
