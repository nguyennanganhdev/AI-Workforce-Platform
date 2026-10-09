# async_partners — API/event/workflow v1.4

Chủ sở hữu: **Phan Hoàng Dũng**. Branch: `feat/wf-execution`.
Task bổ sung của owner: **PHD-14–PHD-17**; chọn phần tương ứng phạm vi folder dưới đây.

Đọc [kế hoạch triển khai](../../../../docs/workforce/KE_HOACH_TRIEN_KHAI.md) và [bàn giao cá nhân](../../../../docs/workforce/handoffs/phan-hoang-dung/README.md) trước khi code. Đặc tả chung nằm ở mục 17; ranh giới ownership ở 5.3 và task chi tiết trong phần mang tên owner. Các đường dẫn link tính từ folder này.

Phạm vi: Fake backend khách hàng gọi Customer API cho response-only/interactive/external-tracking, gồm một user mở hai ticket/hộp chat; fake backend provider gọi Provider Event API và SSE client chỉ khi next_action yêu cầu; dữ liệu giả, inject faults và fake clock.

File dự kiến khi triển khai: `customer_backend.py`, `technician_backend.py`, `sse_client.py`, `event_samples.json`. Đây chỉ là gợi ý chia file; chưa có code được tạo trong folder.

Nguyên tắc triển khai:

- Một role AREA_MANAGER, Scope đủ tenant/domain/area/manager và audience cư dân; không route theo payload tự khai.
- Dùng DTO/ports chung; không import private service hoặc ghi bảng module khác. uow đi xuyên inbox → workflow/public event → trigger khi cần atomicity.
- Customer request/reply POST ưu tiên `200`, chỉ `202/watch_request` khi hết thời gian chờ; response luôn có `workflow_state` và `next_action`. Response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; Provider Event/SSE tracking chỉ dùng khi operation thật sự pending.
- Không dựng fake outbound receiver vì platform v1 không gọi HTTP ngược sang đối tác.
- Fake customer lưu hai record TICKET-A/CHAT-A/wf_A/conv_A và TICKET-B/CHAT-B/wf_B/conv_B, gửi xen kẽ và giữ cursor SSE riêng; có fixtures ghép sai tuple để chứng minh platform không route theo “workflow gần nhất”.
- Tự viết test trong vùng test được giao, dùng fake port khi module khác chưa có. Chỉ đánh dấu live integration khi có bằng chứng thật.
- Cần đổi contract/migration/core/global frontend thì ghi INTEGRATION_REQUEST trong handoff; Chí Hoàng tích hợp file chung.

Thư mục được giữ trong Git bằng README này để thành viên bắt đầu code song song. Chưa triển khai API, worker, migration hay test; không tạo stub thành công trong production.
