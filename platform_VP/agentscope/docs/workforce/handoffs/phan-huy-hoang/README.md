# Bàn giao — Phan Huy Hoàng

Branch đề xuất: `feat/wf-orchestration`. Đầu việc: **PHH-01–PHH-17**.

Phạm vi: Leader chọn group khi có request, chat/@agent và context từ thư viện agent chung.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Phan Huy Hoàng”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: PHH-02/03/04/12 chọn agent từ toàn bộ thư viện khi có request, tạo group/session lúc đó, không lọc theo batch. Run hiện tại giữ version pin; request mới chọn subset/version phù hợp mà không cần phát hành team. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

PHH-13 sở hữu PartnerIngressPort, request idempotency, conversation binding, dispatch, partner result/SSE projection. Dùng PartnerRoutingPort/uow của Chí Hoàng; không viết lại mapping/auth hoặc sửa BusinessService. Scope owner và audience được pin, remap/retry không đổi chủ hoặc trộn context.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3. POST nhận việc rồi kết thúc; workflow chờ bằng checkpoint trong DB, callback nối đúng job/ticket/chat, public event log hỗ trợ replay và outbox chịu retry thông báo. ACK hoặc ngắt SSE không đóng ticket.

Owner Phan Huy Hoàng bổ sung **PHH-14–PHH-17**: workflow ticket, checkpoint/continuation, public event log, SSE/history và chat timeline. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **PHH-14 — Workflow sống qua nhiều lượt:** orchestration/workflows/ triển khai WorkflowPort, workflow/trigger/wait/checkpoint repositories và request/reply/close logic mục 17.2. Mỗi turn ngắn có run_id nhưng giữ workflow/group/session/pins; active/waiting/blocked/needs_attention/closed rõ. Close một ticket không đóng cả conversation hoặc tự cancel provider job.
- [ ] **PHH-15 — Tiếp tục runtime đúng nguyên nhân:** Scheduler/continuation trong workflows/ gọi RuntimeContinuationPort và JobPort bằng trigger dedupe, lease/fence/revision. Áp event + checkpoint/message/outbox đúng uow; serialize per workflow/session, xử lý event đến lúc ngủ và pending HITL. Chỉ Leader/member cần thiết chạy, không build hoặc thêm mọi agent; thời gian chờ không tiêu token.
- [ ] **PHH-16 — Event log và API kết quả:** orchestration/partner_events/ triển khai ConversationEventPort, public projection, SSE/history/snapshot và API partner mở rộng mục 17.3. Cursor commit-order, reconnect không mất event, snapshot watermark, expired cursor 410, audience/filter, close/reply idempotency. Dùng DeliveryPort để enqueue outbound, không tự viết sender/webhook credentials/outbox table thứ hai.
- [ ] **PHH-17 — Timeline và kiểm thử workflow:** chat/ticket_timeline/ hiển thị tiến độ ticket, speaker, waiting/blocked/reconnecting, nhiều ticket trong một chat, đóng đúng ticket và catch-up không trùng bubble. Dùng shared/event_transport và component Execution của Dũng. tests/workforce/orchestration/async_workflows/ kiểm tra fake clock/ports, race close/update/reply, crash/checkpoint, scope/audience và SSE replay; không sửa service core ngoài owner.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/orchestration/workflows/](../../../../src/agentscope/app/workforce/orchestration/workflows/README.md) — Workflow state/trigger/checkpoint/close/continuation; không lưu provider inbox.
- [src/agentscope/app/workforce/orchestration/partner_events/](../../../../src/agentscope/app/workforce/orchestration/partner_events/README.md) — Public event log, SSE/history/snapshot, DeliveryPort enqueue; không sender outbound.
- [examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/](../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/README.md) — Timeline/close nhiều workflow, reconnect và event/message dedupe.
- [tests/workforce/orchestration/async_workflows/](../../../../tests/workforce/orchestration/async_workflows/README.md) — Workflow transitions/checkpoint/HITL/cursor/isolation/crash windows.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

