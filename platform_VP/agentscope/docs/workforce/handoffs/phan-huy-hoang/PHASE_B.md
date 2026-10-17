# Phan Huy Hoàng — bàn giao Phase B

Tài liệu này mô tả implementation PHH-13–PHH-17. Kế hoạch tổng vẫn là nguồn xác định nghiệp vụ và ownership; tài liệu này chỉ mô tả code Phase B đã tạo.

## 1. Luồng request và hai hộp chat

`PartnerIngressService.accept()` xác thực actor `partner/customer_api`, resolve route từ `external_management_ref`, rồi pin `Scope`, route revision và toàn bộ `PartnerAudience`. Với `start_workflow`, bootstrap tạo đúng một workflow/conversation/group/session. Với `workflow_reply`, service đọc request gốc và bắt buộc khớp toàn tuple ticket/conversation/user/client trước khi ghi input hoặc enqueue trigger.

Idempotency ledger và request/binding/event/job cùng đi qua UOW. Handler phải commit trước khi bounded-wait. Retry cùng key và cùng payload đọc lại request cũ; dùng lại key với command/target/hash khác phải conflict. `receipt_http_status()` trả `202` khi request còn accepted/queued/running, còn terminal result trả `200`.

Hai hộp chat của cùng một cư dân không dùng “ticket gần nhất”. Mỗi hộp giữ riêng:

```text
(partner_client_id, external_user_id,
 external_ticket_id, external_conversation_id)
              ↓ immutable binding
(workflow_id, conversation_id, group_id,
 session_refs, checkpoint, pending waits)
```

## 2. Workflow và continuation

`WorkflowService` triển khai start, reply, external event, enqueue và close. Reply tăng revision bằng CAS trước khi schedule nên hai reply cùng revision không thể cùng thắng. Ba pattern có luật riêng:

- `response_only`: chỉ policy đã publish và read-only được auto-close sau một turn hoàn tất.
- `interactive`: ngủ ở awaiting user/approval/confirmation và đóng bằng command rõ ràng.
- `external_tracking`: chỉ vào waiting state khi có operation pending, creation đã thành công và protocol pin có `receive_status` hoặc `status_query`.

`WorkflowContinuation` lấy lease/fencing token trước khi load checkpoint. Runtime chạy ngoài transaction. Trước side effect và trước commit, guard kiểm tra lại workflow/checkpoint/binding, authorization, revision và fence. Commit cuối ghi checkpoint, workflow, result và public event trong một UOW. Trigger đã có trong `last_processed_causes` không chạy lại. Khi đang chờ human/approval, external/timer trigger được defer mà không gọi model và không tăng token.

Close ghi state/event trước; turn đang chạy nhìn thấy closed/revision change và không được phát message hoặc mở lại workflow. `stop_tracking_only=true` cho phép đóng phần theo dõi của platform trong khi operation phía provider vẫn tồn tại.

## 3. Provider event và public event

Execution là owner của provider inbox/operation fact. PHH chỉ đọc operation đã cập nhật và `NormalizedJobEvent` trong cùng UOW, kiểm tra scope/audience/workflow/conversation/ticket/protocol/correlation rồi project public event và trigger.

Một external update hợp lệ phát:

1. `operation.status_changed` với `operation_type`, `status_schema`, `status`, `external_reference`;
2. `workflow.status_changed` giữ nguyên state nghiệp vụ nhưng mang revision mới;
3. một durable continuation job theo cause/event id.

Nếu workflow đã closed hoặc quyền gửi về cư dân đã revoke, fact provider vẫn được caller commit nhưng PHH không phát public event và không wake runtime. Đây là chủ ý để không rollback lịch sử thật và không rò dữ liệu sau revoke.

`ConversationEventService` dùng durable log làm source of truth. Signal Redis/message bus chỉ là wake-up sau commit; mất signal vẫn replay từ cursor. Mỗi lần history/snapshot/SSE đều authorize lại audience. Cursor hết hạn được repository ném `EventCursorExpired` để HTTP adapter map thành `410` và client tải snapshot. Không có code platform gọi webhook outbound sang backend đối tác.

## 4. Timeline web

`ticket_timeline/state.ts` là reducer fail-closed cho receipt, snapshot và public event. Khóa state gồm identity, conversation, workflow, external user/conversation/ticket. Event khác binding bị từ chối, cùng event ID/cùng nội dung được dedupe, cùng ID/khác nội dung là conflict. Khi đã nhận close, closed barrier từ chối event mới đến muộn.

`followTimeline()` tái sử dụng shared `event_transport`, lưu cursor theo khóa hộp chat, refresh token một lần, dùng snapshot khi server trả `410`, và không chia sẻ cursor giữa ticket A/B. `TicketTimeline` hiển thị assistant message, trạng thái workflow, tiến độ operation/ticket, approval component của Execution, reconnect/blocked và close đúng binding/revision.

## 5. Public exports

- Python: `agentscope.app.workforce.orchestration`
- Workflow: `agentscope.app.workforce.orchestration.workflows`
- Event: `agentscope.app.workforce.orchestration.partner_events`
- Web: `features/workforce/chat/ticket_timeline`

Persistence và HTTP adapter được inject qua ports; production không có fake thành công mặc định. Fake chỉ nằm dưới `tests/workforce/orchestration/async_workflows/`.
