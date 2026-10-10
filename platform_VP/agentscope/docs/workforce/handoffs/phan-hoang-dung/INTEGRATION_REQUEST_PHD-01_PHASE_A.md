# PHD-01/02/03/05/06/13–16 — Đối chiếu contracts Phase A

Ngày 10/10/2026. Người gửi: Phan Hoàng Dũng. Người nhận: Nguyễn Chí Hoàng; phối hợp Nguyễn Phương Đông và Phan Huy Hoàng.

Đã kiểm tra commit `1ff8fb6` (merge `a99d506`), `contracts/__init__.py`, các DTO/ports, TypeScript v1 và STATUS của Chí Hoàng. Output mới là Phase A, chưa có auth/routing/persistence/worker/migration/composition. Lần bổ sung Execution này dựa trên HEAD `383a387`; không sửa file chung hoặc module owner khác.

## Phần đã nối được

| Task | Thay đổi đã thực hiện |
|---|---|
| PHD-01/13 | Nhận `Scope` chung; Registry snapshot được gọi với `Scope` DTO. Validate đủ bốn chiều và kiểu/giới hạn ID trước SQL. `PartnerAudience` được normalize, bỏ optional null khi so sánh với approval/call cũ; vẫn so đúng user/ticket/chat/residence |
| PHD-02 | MCP credential/client/projector adapter nhận `Scope` DTO chung; không tạo Scope thứ hai |
| PHD-03 | Thêm export `calculator_catalog_descriptor(scope) -> ToolDescriptor` hợp lệ theo shared contracts; `calculator_descriptor` giữ metadata execution riêng để không bỏ guard reviewed-effect |
| PHD-05/13 | HTTP và service dùng `PartnerApprovalDecision`; actor phải là `ActorContext` với `credential_purpose=customer_api`. `claim_or_read` nhận ActorContext, `record_result` nhận `RequestResult(data=decision_response)`; replay unwrap data, đọc được cached response dạng cũ |
| PHD-14/09 | Operation mới lưu `creation_status=prepared` theo enum chung. Gateway vẫn đọc trạng thái `intent` cũ; UI nhận cả hai |
| PHD-15 | Dùng `ProviderEventEnvelope`, bỏ JSON schema riêng. ACK/read dùng `ProviderEventReceipt`, có received_at; không lộ internal error. Internal ignored/stale được public thành rejected vì fact không được apply |
| PHD-16 | Query schedule truyền Scope DTO và timezone-aware datetime cho `JobPort.enqueue(..., not_before=...)` |
| Chung | `ExecutionError.public()` dùng `ErrorResponse`/`PublicError`, có request_id không rỗng, ổn định trong cùng exception; không đưa provider exception vào message/details |

Provider envelope canonical hóa bằng `model_dump(mode='json', exclude_none=True)` trước business hash. Optional null/omitted và shared DTO/mapping cùng dữ kiện tạo cùng receipt. Timezone bắt buộc; không coerce bool/float thành provider_version hoặc expected_revision. Signature vẫn xác minh trên raw body trước parse/normalize. Row inbox cũ được so sánh lại canonical envelope nếu hash khác; giữ nguyên payload/hash audit của row, vẫn reject changed business payload.

## Điểm còn thiếu — chưa thể coi là conformant port implementation

| Port/model Phase A hiện có | Execution đang cần | Đề xuất owner chốt |
|---|---|---|
| ProviderAuthPort trả ActorContext; DTO không có tenant_id/provider_integration_id | Namespace phải được xác minh trước khi nhận inbox/đọc receipt; hiện adapter nội bộ nhận mapping verified principal với hai trường này | Thêm `resolve_provider_namespace(actor, operation, uow?) -> verified context` hoặc DTO server-only chứa ActorContext + namespace. Không thêm namespace vào public envelope, không suy từ payload hoặc giả manager scope |
| JobPort chỉ enqueue(scope, ...) | Inbox có thể đến trước operation, chưa biết owner Scope; phải inbox+job cùng transaction | Additive provider-namespace enqueue hoặc namespace job aggregate do Foundation sở hữu. Chưa có `enqueue_provider` trong shared port |
| UnitOfWork có commit/rollback/after_commit | Repository hiện dùng AsyncSession.execute/bind/begin_nested | Foundation cung cấp session adapter/UOW bridge; không truyền arbitrary UnitOfWork vào repository rồi coi là SQL session. Chưa có concrete UOW/migrations |
| ToolDescriptor.effect = read/write/external_operation; không có reviewed/credential/async metadata | Policy cần reviewed effect; booking/cancel có consent, credential_ref riêng và async protocol pin | Chốt execution snapshot/metadata adapter và mapping effect đã review; không tự coi external_operation là write hoặc tự gán reviewed=True. Canonical ToolDescriptor trần hiện bị guard chặn an toàn |
| AsyncProtocolSnapshotRef chỉ có protocol/version/hash/tool/integration/capabilities | Cần immutable detailed protocol: create_fields, event/query support, ordering/transition, terminal policy, timeouts, normalizers creation/query | Đông cung cấp resolver detailed snapshot pin theo shared ref/hash và các hooks còn thiếu. Không giả detailed policy từ capabilities hoặc query LLM |
| normalize_verified_event trả NormalizedJobEvent, cần inbox_event_id/received_at nhưng signature không nhận inbox metadata; DTO không có order_mode/terminal | Processor phải có metadata server-owned và ordering/terminal/transition policy | Chốt metadata bổ sung sau normalize hay input context; chốt policy separate from normalized fact. Current processor chưa tiêu thụ trực tiếp normalized DTO Phase A |
| WorkflowPort.apply_external_event(scope, operation_ref: str, NormalizedJobEvent) | Execution hiện truyền full internal operation/event mapping; có mark_operation_attention/apply_execution_result hooks bổ sung | Huy Hoàng cung cấp binding lookup và atomic event/attention/result adapter cùng session; không đơn giản đổi mapping thành ID rồi bỏ policy |
| PartnerCommandPort thiếu authorize_approval; claim trả object chưa chốt aggregate | Resolve approval owner + exact audience/binding trước cached read, claim-result shape is_new/request_id/result | Chốt server-only authorize hook và claim DTO với Huy Hoàng. Đã nối ActorContext/RequestResult, chưa giả rằng namespace service đã có |
| ExternalOperationPort có optional UnitOfWork, trả ExternalOperation | Service nội bộ yêu cầu AsyncSession do caller giữ, trả record chứa protocol detail/pending/group; canonical audience bắt buộc trong khi manager-only run có thể không có partner audience | Chốt adapter aggregate và semantics manager-only async; bổ sung call/result DTO vào contracts sau khi nhận sample bên dưới. Không tạo DTO công khai thứ hai trong Execution |
| TypeScript v1 có Scope/provider envelope, chưa có approval money/view/operation DTO/transport | UI hiện dùng component view models và injected request transport | Giữ view models trong lane Dũng; chờ shared transport và projection types tương ứng, không copy shared DTO hoặc sửa global barrel |

## Sample bàn giao cho call/result và provider receipt

Call được runtime cấp từ checkpoint/cause, không phải public body:

```json
{
  "call_id": "call-A",
  "run_id": "run-A",
  "agent_id": "hotel",
  "version_id": "v1",
  "tool_version_id": "hotel.book.v1",
  "idempotency_key": "cause-1/tool-call-1",
  "arguments": {"room": "FAKE-seaview"},
  "approval_id": "approval-A"
}
```

Normalized create result từ reviewed provider adapter, tách job progress:

```json
{
  "creation_status": "succeeded",
  "external_job_id": "FAKE-job-1",
  "job_status": "assigned",
  "pending": true
}
```

Canonical provider envelope và ACK:

```json
{
  "schema_version": "1",
  "external_event_id": "A2",
  "client_reference": "server-correlation-A",
  "event_type": "FAKE.progress",
  "provider_version": 2,
  "occurred_at": "2026-10-09T02:30:00Z",
  "data": {"status": "completed"}
}
```

```json
{
  "receipt_id": "server-receipt-A",
  "ingestion_status": "accepted",
  "duplicate": false,
  "received_at": "2026-10-09T02:30:01Z"
}
```

Invalid examples: thêm scope/group/actor vào envelope → PROVIDER_EVENT_INVALID 422; cùng external_event_id khác data → EVENT_ID_CONFLICT 409; provider_events credential dùng customer approval → CUSTOMER_AUTH_REQUIRED 403; khác user/ticket/chat/residence → binding/decider/audience error, zero provider call.

## Kiểm chứng và compatibility

`tests/workforce/execution/test_shared_contracts.py` thêm 16 cases cho DTO interoperability, rejected injection/coercion, original receipt timestamp, audit hash cũ, canonical receipt cho stale fact, actor purpose và consent/resident isolation. ASGI partner test dùng ActorContext thật và fake command namespace cùng SQL transaction, assert RequestResult trước persist. Timer fixture assert Scope/datetime đúng shared signature. Đây vẫn là fake adapters, chưa là Foundation/Orchestration production service.

Không cần SQL schema mới cho các chỉnh sửa JSON payload/projection hiện tại. Khi Foundation tạo migration/composition, cần quyết định backfill intent→prepared, xử lý cached approval result/body hash cũ và map internal ignored→public rejected; **không đổi hash audit inplace**. Chi tiết checks/skips tại [VALIDATION.md](VALIDATION.md). Các integration requests trước vẫn mở, chỉ phần DTO đã nhận được là gỡ phụ thuộc.
