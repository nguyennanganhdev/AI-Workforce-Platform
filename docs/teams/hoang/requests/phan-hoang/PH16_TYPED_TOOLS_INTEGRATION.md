# PH16 — Tích hợp typed facade và contract API

Owner yêu cầu: Phan Hoàng. Ngày: 01/10/2026.
Trạng thái: **OPEN — tài liệu trong repo, chưa gửi ra ngoài hoặc được owner duyệt**.

## Kết quả thuộc phạm vi Phan Hoàng

- `agent-reception/src/tools/contracts.py`: kiểu input/output strict của 14 operation.
- `agent-reception/src/tools/facade.py`: `ReceptionTools` có method tường minh, trả
  `Success[Output] | Accepted | Failure`; không có public generic `invoke`.
- `agent-reception/src/tools/validation.py`: catalog `system/internal`, không có
  LLM tools; validator độc lập transport.
- `BackendToolPort.invoke/reconcile`: cùng validation và cùng canonical body/key.

Đây là consumer proposal **`ph16.draft.1`**, chưa phải producer contract của Chiến.
Schema message liên team đã chốt **V2** ở `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md`;
không đổi tên file hoặc tự sửa schema chung.

## Phan Dũng — chuyển graph sang facade

`src/graph/workflow_contracts.py` và `workflow.py` vẫn dùng generic `invoke`, V1
handoff, `status/customer_message` và `interaction_id/answers`. Các file này chưa
được sửa trong PH16 vì thuộc Phan Dũng. Điều kiện “graph gọi hàm có kiểu” của PH16
**chưa nghiệm thu**, không đánh dấu toàn bộ PH16 DONE.

Đã có test tái hiện chạy graph thật với adapter mới:
`tests/tools/test_adversarial.py::test_existing_graph_can_reach_http_with_new_backend_port`.
Hiện FAIL: phase `waiting_operation`, pending `create_ticket_draft`, HTTP calls = 0.
Chi tiết và giới hạn bằng chứng nằm ở
[PH16_ADVERSARIAL_TESTS](../../handoffs/phan-hoang/PH16_ADVERSARIAL_TESTS.md).

Đề nghị review và cập nhật:

1. Protocol/`GraphDependencies.tools` dùng các method của `ReceptionTools`; mỗi node
   tạo model input tương ứng và gọi method cố định. Không lấy tên operation từ LLM.
   Catalog có thể phục vụ kiểm tra pending operation, không phải tool registry LLM.
2. Graph vẫn lưu key/input trước side effect. V1 checkpoint/pending request không
   được tự relabel/replay thành `ph16.draft.1`; chốt version marker và cách tiếp tục
   hoặc từ chối checkpoint cũ với owner runtime/persistence.
3. Dùng context đã resolve ở runtime, chỉ project năm trường `tenantId`,
   `principalId`, `bindingId`, `runId`, `requestId`. Không gán principal từ initiated
   user hoặc từ resident ID. Deadline/cancellation là outer runtime budget, không
   thêm `timeoutMs`/`signal` vào strict HTTP envelope.
4. Thay các projection dưới đây một cách tường minh:

| Operation | Consumer proposal PH16 | Thay đổi so với graph hiện tại |
|---|---|---|
| `handoff_ticket` | ticket triple + `correlation_id` + `handoff_reason` | Không gửi full V1 message hoặc tự điền destination/routing; backend dựng full V2 từ dữ liệu đã xác minh |
| `register_supervisor_wait` | ticket triple + `correlation_id` | Không truyền `workspace_id`, `team_id`, `coordination_binding_id`; backend resolve từ binding/ticket |
| `get_supervisor_event` | ticket triple + `event_id` + `aggregate_version` + `correlation_id` | Resolver/event consumer phải cung cấp reference đầy đủ đã kiểm chứng; không tự dựng ticket version từ aggregate version |
| `respond_supervisor_interaction` | ticket triple + `source_message_id`, `message_type`, `message`, `facts`, `file_ids` | Dùng enum V2, giữ phiên bản của yêu cầu cư dân đã thấy; không suy “đồng ý” mơ hồ thành approval |
| `process_self_help` | channel/session + source message + `policy_version` + optional attempt | Không gửi assessment do model tự khai như bằng chứng eligibility; backend kiểm policy/consent |

Các operation còn lại giữ ý nghĩa baseline, nhưng giờ từ chối field thừa, kiểu sai
và thiếu required fields. `facts` do Reception gửi chỉ có `customer_report` hoặc
`agent_inference`; `staff_verified` chỉ được backend trả sau xác minh.

5. Response có kiểu: chỉ đọc `.value` khi `kind=success`. Với `accepted` hoặc lỗi
   `unknown`, giữ pending và dùng reconcile cùng input/context/key. Lỗi decoder
   sau HTTP không có nghĩa mutation chưa áp dụng. Không xóa pending file trước
   khi xác nhận liên kết.
6. Event V2 dùng `message_type/message`, không tự gắn lại nhãn V1. Backend quản lý
   tối đa một yêu cầu đang chờ trong generation; graph xử lý `information_requested`
   và `plan_approval_requested` theo enum tương ứng. `completed` cần `work_completed`
   nhưng vẫn phải hỏi backend về trạng thái đóng ticket.

Tests mong đợi sau consumer migration: business graph thật + facade + HTTP
MockTransport đi đủ tám bước đầu, interrupt/resume V2, pending mutation qua restart,
event/binding/tenant sai bị chặn, không mất ảnh và không tạo ticket thứ hai.
Test `tests/tools/test_flow_contract.py` hiện chỉ chứng minh chuỗi facade/HTTP;
**chưa chứng minh graph thật đã gọi facade**.

## Team Chiến — freeze producer contract trước PH18

Hai cổng dự kiến theo phân công:

```text
POST /internal/reception/operations/execute
POST /internal/reception/operations/reconcile
```

Envelope JSON:

```json
{
  "operation": "handoff_ticket",
  "input": {
    "ticket_id": "ticket-synthetic",
    "ticket_generation": 0,
    "ticket_version": "opaque-version-from-backend",
    "correlation_id": "correlation-synthetic",
    "handoff_reason": "needs_staff"
  },
  "context": {
    "tenantId": "tenant-synthetic",
    "principalId": "principal-synthetic",
    "bindingId": "binding-synthetic",
    "runId": "run-synthetic",
    "requestId": "request-synthetic"
  },
  "idempotency_key": "stable-key-from-pending-operation"
}
```

Đây là input operation giữa Reception và backend, **không thay đổi schema V2 đầy đủ
giữa backend và Supervisor**. Backend dựng message gồm resident/location/triage và
routing từ nguồn đã xác minh, rồi lưu/enqueue nguyên tử. Input model không nhận các
field hệ thống để tránh một contract cho phép LLM tự nhận quyền.

Handoff receipt đề xuất:

```json
{
  "kind": "success",
  "value": {
    "schema_version": "2.0",
    "ticket_id": "ticket-synthetic",
    "ticket_generation": 0,
    "ticket_version": "opaque-version-from-backend",
    "correlation_id": "correlation-synthetic",
    "persisted": true,
    "enqueued": true,
    "operation_id": "handoff-operation-synthetic"
  }
}
```

Xin xác nhận:

- OpenAPI/JSON Schema và version negotiation cho 14 operation, request/result/error,
  ý nghĩa của event reference và buffered event. Tên `ph16.draft.1` chỉ là version
  catalog local, chưa thêm field version vào wire mà backend chưa chốt.
- Receipt handoff/wait phải pin expected ticket version/correlation. Các operation
  trả `ticket` sau mutation/status có thể trả version mới; version là opaque string,
  không parse số để tự quyết định mới/cũ. Backend kiểm expected version và generation.
- `accepted` chỉ có operation ID; `failure` gồm code/retryable/outcome
  `not_applied|unknown`; không chuyển raw error text/PII cho consumer.
- Cùng key khác body phải conflict; reconcile trả kết quả mutation trước, không
  thực hiện lại mutation. Trả `linked_file_ids` hoặc incident file list đã liên kết.
- Service auth/audience, revoked context, binding ownership và quyền file; không
  coi model Pydantic tên `VerifiedContext` là chứng cứ xác thực.
- Authenticated event resolver phải cấp ticket version/correlation chính xác;
  không suy chúng từ các mã V1 chưa có mapping được chốt.
- Self-help kiểm eligibility/version/expiry/consent; emergency alert không phải
  một đường cho model tự chọn severity hoặc cấp quyền.

Fixtures tổng hợp nằm ở `agent-reception/tests/tools/tool_fixtures.py`; schema có
thể xem qua `input_model.model_json_schema()` và output types trong catalog.
PH17 còn phụ trách ma trận HTTP lỗi đầy đủ; PH18 mới chạy producer-consumer với
endpoint thật. Không có endpoint, SQL, fake production hoặc thay đổi backend trong PH16.
