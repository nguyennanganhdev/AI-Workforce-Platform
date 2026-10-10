# Integration request — Chốt contract và fake Phase A/B

Task IDs: PHD-01/02/05/06/13–16. Ngày: 10/10/2026.
Người gửi: Phan Hoàng Dũng. Người nhận: Nguyễn Chí Hoàng;
phối hợp Nguyễn Phương Đông và Phan Huy Hoàng. Baseline: `53a139b`.

Phạm vi: review schema/signature, thống nhất metadata và fake phục vụ consumer
tests của Phase A/B. Không yêu cầu triển khai production services trong file này.

## Hiện trạng và phần đã giải quyết trong lane

Đã nhận PHH schemas/proposals; consumer tests dùng FakeAsyncProtocolPort thật
của NPD và PHH cause/claim/WorkflowRecord. PHD đã hoàn thiện adapters tại
[PHASE_A.md](PHASE_A.md), kiểm chứng ở [PHASE_B.md](PHASE_B.md).
Không còn yêu cầu thêm enqueue_provider hoặc bàn giao lại protocol/Workflow schema.

Đã xử lý phía PHD: canonical config hash/detail pin, persisted normalization
metadata validation, ExternalOperation shared projection/optional UOW,
provider event → shared Workflow signature, CommandClaimResult interoperability.
Các seam nội bộ bên dưới vẫn cần shared owner chốt; chưa tự promote DTO/hook.

## File/module nhận và đề xuất

| Quyết định còn cần | Export/hook cần owner chốt | Owner |
|---|---|---|
| ProviderAuth trả ActorContext chưa có verified tenant/integration/inbox metadata | Canonical server-only verified event context: actor + namespace + persisted inbox ID/received_at, theo request NPD; thay request-local factory seam khi signature merge | NCH contracts/auth + NPD |
| AsyncProtocolPort trả ref, chưa có exact-detail accessor | Authorized resolver(scope, exact ref) → immutable config/DTO; hash phải bằng NPD snapshot_ref.schema_hash, không query latest | NCH contracts + NPD Registry |
| Query không có provider inbox | Canonical query result + timer cause hoặc shared query hook. Không dùng timer ID làm inbox_event_id/external_event_id | NCH + PHH + NPD |
| ExternalOperation DTO bắt buộc audience | Chốt manager-only async semantics; không fabricate partner audience. Adapter hiện reject thiếu audience, internal service vẫn hỗ trợ record cũ | NCH contracts + PHH/PHD |
| ToolDescriptor thiếu reviewed execution/credential metadata | Canonical reviewed snapshot adapter; không tự gán reviewed=True hoặc suy effect từ HTTP/annotations | NCH + NPD |
| PHH aggregate/hook còn proposal | Promote CommandClaimResult/cause/checkpoint và authorize_approval/query/attention/execution-result hook; giữ preflight trước cached read | NCH + PHH, review PHD |
| Generic UnitOfWork khác AsyncSession | Chốt contract join/commit/after_commit và fake UOW để kiểm tra consumer adapter | NCH Foundation |
| PHH IR-PHH-A05 | Strict revision integer và aware public timestamps, đồng bộ Python/JSON Schema/TS | NCH; không sửa shared trong lane PHD |

Theo dõi cùng [NPD Phase A request](../nguyen-phuong-dong/INTEGRATION_REQUEST_NPD_PHASE_A.md)
và [PHH Phase A request](../phan-huy-hoang/INTEGRATION_REQUEST_PHH_PHASE_A.md);
đây là đề nghị review/promotion, chưa có owner acceptance MA.

## Caller, input/output, error và scope

- ExecutionProtocolAdapter nhận shared AsyncProtocolPort + exact-detail resolver.
  event_port_factory(context) trả port riêng với actor/Scope/integration/
  inbox_event_id/received_at từ persisted inbox, không từ body.
- ProviderEventProcessor truyền metadata gốc; NormalizedJobEvent phải giữ
  external IDs/correlation/version/pin/source hash/time và đúng allowlist.
  Mismatch → PROVIDER_NORMALIZATION_INVALID/quarantine, zero Workflow apply.
- WorkflowEventAdapter gọi apply_external_event(Scope, operation_ref,
  NormalizedJobEvent, uow). Full operation/binding vẫn ở DB; không drop metadata
  để vừa signature. Query qua hook riêng với timer ID/source hash/observation,
  không giả provider inbox.
- ExternalOperationAdapter trả DTO chung; join caller session hoặc mở transaction
  khi uow=None; record legacy thiếu canonical pin bị từ chối projection, không tự đoán.
- PartnerApprovalService normalize typed claim, authorize trước replay;
  result chưa có → COMMAND_RESULT_UNAVAILABLE, không success giả.

Các signature dưới đây là **đề xuất để owner review và thống nhất fake**,
chưa phải shared exports đã được chấp nhận:

- `apply_operation_query(scope, operation_ref, query_result, uow) -> WorkflowRecord`.
  Query result gồm server `timer_id`, `protocol_schema_hash`, `source_hash`,
  `observed_at`, `status`, `facts`, `provider_version`, `terminal`; dùng TimerCause,
  không sinh provider inbox/event ID. Chốt query fact allowlist và version semantics
  với NPD; fake cần mẫu đúng/sai pin, job namespace và stale version.
- `mark_operation_attention(scope, operation, cause_id, reason, uow)` và
  `apply_execution_result(scope, call, cause_id, uow)` là injected extensions;
  cần thống nhất DTO/cause và fake, không duck-type vào shared WorkflowPort.
- `authorize_approval(actor, approval_id, body, uow)` xác minh original
  Scope/audience/binding/grant trước cached replay. Chốt typed CommandClaimResult
  và RequestResult cùng UOW; fake cần replay sau revoke và pending result.

## Transaction/retry/concurrency và tests

Inbox+enqueue commit trước ACK; operation+inbox outcome+Workflow sink cùng
session. Rollback toàn bộ khi sink throw hoặc trả sai Scope/workflow/conversation/
group/ticket/audience. Replays giữ original receipt/time/correlation/cause.
Không network/model trong apply transaction, unknown không retry create mù.

Tests mới tại test_phase_ab.py và typed consent tests đã pass với fake port/schema
đã bàn giao của NPD/PHH. Còn chờ owner xác nhận các contract/proposal trên và
thống nhất fake; chưa dùng module tests để xác nhận MA/MB toàn platform.
