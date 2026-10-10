# PHH Phase A — đề xuất tích hợp, chưa được owner chấp thuận

Task liên quan: PHH-12–PHH-17. Baseline `254ec21a52c0f23511aee44248e9ca732b9c6cd3`.
Producer PHH; consumer NCH/PHD, phối hợp NPD/BHN/PTA. Tài liệu này là bàn giao local, không phải thông báo đã gửi cho thành viên khác.

## IR-PHH-A01 — typed aggregate và chữ ký port

Owner shared: NCH. Owner proposal: PHH. Reviewer: PHD cho command/operation, NCH cho continuation/UOW.

| Port | Chữ ký hiện tại (lược self) | Đề xuất sau review |
|---|---|---|
| PartnerCommandPort.claim_or_read | `(actor, external_request_id, command_kind: str, target_ref: OpaqueId or None, payload_hash: str, uow=None) -> object` | Giữ các tham số; đổi return thành `CommandClaimResult`. Phải bổ sung trusted authorization context hoặc quy định preflight auth/audience bắt buộc trước cached read; hiện signature không có audience. Chưa chốt cơ chế. |
| WorkflowPort.enqueue_trigger | `(scope, trigger: Mapping[str, object], uow=None) -> OpaqueId` | `trigger: WorkflowTrigger` sau khi NCH promote discriminated cause; return không đổi. |
| WorkflowPort.close | `(scope, actor, audience, command: Mapping[str, object], uow=None) -> WorkflowRecord` | `command: CloseWorkflowCommand` canonical; target workflow phải pin theo binding/endpoint, cần chốt cách truyền ID để không tin body. |
| RuntimeContinuationPort.load_pinned_context | `(scope, checkpoint: OpaqueId) -> object` | `-> PinnedRuntimeContext`; NCH xác nhận semantics revision khi workflow đã đổi mà checkpoint chưa tiến. |
| RuntimeContinuationPort.invoke_turn | `(scope, trigger: Mapping[str, object], checkpoint: object, execution_guard: object) -> object` | `trigger: WorkflowTrigger`, `checkpoint: PinnedRuntimeContext`, `-> RuntimeTurnResult`. `execution_guard` phải là trusted capability/interface của Foundation/Execution, không serialize credential/fence do LLM khai báo. Kiểu guard còn chờ NCH/PHD. |
| RuntimeContinuationPort.persist_checkpoint | `(scope, workflow_id, checkpoint: object, uow=None) -> OpaqueId` | `checkpoint: WorkflowCheckpoint`; CAS/fence/lease validation cần server context hoặc tham số riêng do NCH duyệt. DTO đơn lẻ không đủ fencing. |
| ConversationEventPort.snapshot | `(actor, conversation_id) -> JsonObject` | Đề xuất dùng `ConversationSnapshot` canonical sau khi NCH chốt authorization/audience context. |

`WorkflowPort.start_with_binding/accept_reply` hiện nhận message mapping; không tự đổi thành TextMessageInput vì chưa chốt liệu mapping còn mang request/cause metadata. `PartnerIngressPort`, `ConversationEventPort.append/list_after/subscribe`, `PublicEventSignalPort` giữ chữ ký shared hiện tại.

Compatibility: không sửa interface production trong nhánh này. Các proposal phải được promote vào shared một lần, adapter producer/consumer và TS/schema export cập nhật cùng phiên bản. Không để hai DTO PHH/shared cùng là source of truth. Cần quy định conversion hoặc version rejection cho trigger/checkpoint cũ khi nested cause/revision contract được chốt.

Valid input: [samples.json](phase_a/samples.json), keys `models`, `triggers`, `ticket_contexts`. Ví dụ lỗi có thể tái lập:

```json
{"trigger_id":"tr-1","workflow_id":"workflow-A","cause":{"kind":"request","request_id":"r-1","timer_id":"t-1"}}
```

Kết quả mong đợi: extra field của cause bị từ chối. Cặp workflow-A + checkpoint workflow-B cũng bị từ chối; see PHA-064. 80 mutation cụ thể trong [TEST_MATRIX.md](phase_a/TEST_MATRIX.md).

## IR-PHH-A02 — Execution/Orchestration bridge

Đối chiếu [yêu cầu PHD](../phan-hoang-dung/INTEGRATION_REQUEST_PHD-01_PHASE_A.md):

- Shared `apply_external_event(scope, operation_ref: OpaqueId, normalized_event: NormalizedJobEvent, uow=None) -> WorkflowRecord`; PHD đang dùng internal operation/event mappings. Giữ shared shape làm điểm review; yêu cầu PHD cung cấp adapter đầy đủ gồm inbox identity/hash/time/protocol và operation ref, hoặc cùng NCH đề xuất DTO mở rộng. Không drop dữ liệu để vừa signature.
- Các hook `mark_operation_attention`, `apply_execution_result`, `authorize_approval` PHD cần chưa có trong shared port; cần chữ ký/input/output/transaction boundary được NCH/PHD/PHH duyệt, không duck-type lặng lẽ.
- `CommandClaimResult` có `is_new/request_id/result`, không bắt workflow; failed/blocked error details cần chốt thêm. PHD phải xác thực quyền quyết định approval trước cả cached result lookup. Việc request_id trùng nhưng command/target/hash khác luôn conflict ở namespace chung.
- Provider verified namespace, JobPort trước khi có Scope, và UOW generic so với AsyncSession bridge là các request của PHD/NCH còn mở. PHH không tự thay UOW hoặc nhận scope từ provider body.

Gate yêu cầu fixtures producer/consumer: operation bound A + normalized inbox A hợp lệ; operation A + workflow B bị từ chối; duplicate/same hash trả cùng outcome; same event/version khác hash conflict; event unknown chưa binding quarantine; approval retry có grant đã revoke bị từ chối trước cached read. Đây là **tiêu chí giai đoạn sau, chưa chạy** bằng suite schema PHH.

## IR-PHH-A03 — policy và pinned protocol

Owner BHN/PTA/NCH cần giải quyết khác biệt `timeout_behavior`, `timeout_seconds`, empty lists được nêu trong [PHASE_A.md](PHASE_A.md). Cần canonical schema, policy version/hash và xác nhận validation/publish snapshot giữ cùng policy. PHH chưa gắn runtime completion policy tự chế vào checkpoint.

Owner NPD/NCH cần resolver theo `(protocol_id, protocol_version, tool_version_id, schema_hash)` tới full immutable config. Snapshot ref hiện tại được checkpoint nhận nguyên kiểu shared; ref không chứa ordering/mapping/policy để worker tự suy luận. Không query latest thay cho pin.

## IR-PHH-A04 — persistence, public payload và migration

NCH duyệt layout checkpoint/run bindings hiện có, unique constraints, revision/CAS/lease/fencing và after-commit signals theo PHASE_A.md. PHH chỉ gửi spec; NCH tạo migration. Không thêm dependency production.

NCH/PHD/legacy ticket owner duyệt 11 payload schema đề xuất, đặc biệt approval status vocabulary, summary/expiry, ticket public_details và nullable envelope keys. Không dùng `ShortCode` để kết luận status có quyền hay đúng transition. Public model validators không thay thế auth/projection/filtering.

Bằng chứng hiện có: 242 tests contract-only PHH PASS; 13/13 workflow guard mutants bị phát hiện; 9 shared schema được tái dùng, 5 PHH aggregate mới và 11 payload allowlist. Kiểm toán shared bên dưới vẫn có 2 điểm OPEN. Chưa có DB/runtime/HTTP/Redis/provider verification. Trạng thái tất cả IR: **OPEN — chờ owner review**, chưa có xác nhận MA.

## IR-PHH-A05 — shared validation khác JSON Schema

Owner NCH; phát hiện khi kiểm thử đối kháng Phase A, chưa sửa file shared.

| DTO / input | Pydantic hiện tại | JSON Schema + RFC3339 checker | Đề nghị |
|---|---|---|---|
| WorkflowRecord: `revision=true` | Chấp nhận và ép thành 1 | Từ chối boolean tại integer | NCH chốt strict integer cho revision và các số đếm dùng chung; rà soát ảnh hưởng wire compatibility |
| ConversationEvent: `occurred_at="2026-10-10T09:00:00"` | Chấp nhận datetime thiếu timezone | Từ chối date-time không có offset | NCH chốt aware/RFC3339 cho thời gian public, cả occurred_at/recorded_at; rà soát các timestamp shared khác |

Reproduce: chạy runner với `--shared-audit` cùng các cờ môi trường trong STATUS.md. Lệnh hiện trả exit 1 và ghi [shared-boundary-audit.json](phase_a/shared-boundary-audit.json) với 2 trạng thái OPEN; đây không phải test pass. Cùng input hợp lệ gốc lấy từ samples.json, chỉ sửa trường được ghi trong bảng. Đề nghị không thay enum/field names; cần đồng bộ Python/JSON Schema/TS validation trước MA. Các validator payload riêng của PHH đã dùng timezone/RFC3339, nhưng không thay canonical ConversationEvent hay WorkflowRecord.
