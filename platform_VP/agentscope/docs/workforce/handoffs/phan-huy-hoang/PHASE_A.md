# PHH Phase A — Workflow/checkpoint/event schema

Phạm vi là hàng **A — chốt hợp đồng** tại mục 17.9 của [kế hoạch](../../KE_HOACH_TRIEN_KHAI.md), không phải lát cắt nghiệp vụ “A. Response-only” tại mục 17.1 và không phải toàn bộ PHH-01–PHH-17. Baseline và bằng chứng chạy ở [STATUS.md](STATUS.md).

## Đầu vào đã đối chiếu

| Owner | Output hiện có trong develop2 | Cách PHH dùng / giới hạn |
|---|---|---|
| NCH | `contracts/_conversation.py`, `_events.py`, `_execution.py`, `_ports.py`; STATUS và INTEGRATION_REQUEST_NCH_PHASE_A | Tái dùng Scope, WorkflowRecord, TicketConversationBinding, RequestResult, InboundReceipt, ConversationEvent, AsyncProtocolSnapshotRef và ports. Các `object`/`Mapping` chưa phải typed aggregate đã chốt. Không có bằng chứng concrete auth/UOW/runtime hoạt động từ schema. |
| NPD | `registry/event_protocols`, PHASE_A.md, phase_a_samples.json, INTEGRATION_REQUEST_NPD_PHASE_A | Test PHH nhận `snapshot_ref` thật vào checkpoint; giữ `protocol_version`, `schema_hash`, `tool_version_id`. Resolver full snapshot còn cần bàn giao. Không chỉ lưu tên tool rồi resolve latest khi resume. |
| BHN | `builder/async_capabilities`, STATUS, INTEGRATION_REQUEST_BHN_PHASE_A | Đã đọc requirements và HandlingPolicyProposal. Policy là đề xuất, không tự biến thành policy runtime canonical. |
| PTA | `lifecycle/_models.py`, `lifecycle/async_evaluation/_schema.py`, STATUS | Đã đọc validation/eval snapshot; không dùng validation report để tự xác nhận published/deployed. Policy proposal khác BHN như bảng dưới. |
| PHD | INTEGRATION_REQUEST_PHD-01_PHASE_A, operation/inbox shared contracts | Giữ `apply_external_event(scope, operation_ref, NormalizedJobEvent, uow)`. Mapping nội bộ Execution chưa khớp hoàn toàn port; yêu cầu adapter/typed DTO, không bỏ fields âm thầm. |

Các tài liệu owner trên nằm trong thư mục handoff tương ứng cạnh handoff PHH. “Có output” ở bảng này là bằng chứng source tồn tại, không phải chữ ký xác nhận tích hợp.

### Điểm chưa thống nhất đã phát hiện

| Trường policy | BHN HandlingPolicyProposal | PTA AsyncHandlingPolicyProposal |
|---|---|---|
| `timeout_behavior` | `request_attention` / `query_status` | `needs_attention` / `status_query` |
| `timeout_seconds` | Bắt buộc, số nguyên > 0 | Không khai báo, extra fields bị cấm |
| `event_types`, `required_facts` | Có thể rỗng, default rỗng | Bắt buộc, ít nhất 1 phần tử |

Không có policy DTO dùng chung trong baseline để giải quyết khác biệt trên. PHH không tạo schema policy thứ ba và không tự dịch enum. BHN/PTA/NCH cần chốt kiểu chung, hash/pinning và semantics trước khi PHH dùng nó cho quyết định runtime.

## Thiết kế schema đề xuất

`WorkflowRecord`, binding, request/close/receipt, public event/history đều dùng **class shared thật**, không subclass để đổi wire contract. Gói JSON chứa schema canonical nguyên bản và đánh dấu các aggregate mới là proposal.

| Aggregate PHH | Nội dung / invariant |
|---|---|
| WorkflowTrigger | `trigger_id`, `workflow_id`, `cause`, `expected_state_revision?`. `cause` là discriminated union theo `kind`: request(request_id), approval(request_id + approval_id), external_event(cause_event_id + operation_id), timer(timer_id). Không nhận scope/actor/group/credential trong queue message. |
| WorkflowCheckpoint | workflow/state revision; session refs; agent/version pairs; protocol snapshot refs; shared state ref; pending task/question/approval IDs; operation refs; processed causes; token/turn/tool budget đã dùng. Các refs không trùng, mỗi agent một version, mỗi tool version một protocol pin. |
| CommandClaimResult | request_id/is_new/status/result; new = accepted; completed bắt buộc có RequestResult, các trạng thái khác chưa có result. Không bắt workflow ID để hỗ trợ approval không gắn workflow. Error-detail return còn cần NCH/PHD chốt. |
| PinnedRuntimeContext | Ghép WorkflowRecord canonical và checkpoint; workflow ID, revision và tập version phải khớp. Đây là snapshot để review, không chứng minh các ref tồn tại hay owner đã được xác thực. |
| RuntimeTurnResult | Candidate chưa commit: trigger_id, expected revision, checkpoint revision kế tiếp, RequestResult. Không message khác workflow, không trùng message ID. Fencing/lease/authorization thuộc trusted runtime context, không phải token do model gửi. |

Nested `cause` là đề xuất wire shape mới để schema loại trừ việc đưa nhiều cause cùng lúc; cần NCH/PHD duyệt, không được truyền thẳng vào port production đang nhận mapping rồi giả định tương thích. Dedupe trigger dự kiến `(workflow_id, cause.kind, cause-id)`; approval dùng request_id, external_event dùng inbox event ID, timer dùng timer_id. `trigger_id` của lần giao queue không thay thế khóa cause.

JSON Schema kiểm tra cấu trúc. Các ràng buộc so sánh liên trường, uniqueness theo key con, và enum/next_action validator của shared model phải chạy Pydantic validators; chúng không tự xuất đầy đủ vào JSON Schema. Adapter ngôn ngữ khác phải port các invariant này sau khi owner duyệt. Schema proposal không phải bằng chứng validation parity đa ngôn ngữ.

### Public events

Giữ nguyên `ConversationEvent`, `EventHistoryPage` và 11 tên event tại mục 9.7 [contract đối tác](../../CONTRACT_TICH_HOP_DOI_TAC.md). PHH đề xuất payload allowlist cho từng loại; không emit event trong Phase A.

- `assistant.message` chỉ message_id/text; POST và event mẫu có cùng ID/text.
- `operation.status_changed` có operation_type/status_schema/status/external_reference; status domain-specific không được đưa vào WorkflowState.
- `workflow.closed` có state=closed, revision, reason, closed_at.
- Các event còn lại có schema payload riêng, không dùng object mở cho raw provider data.
- `provider.event_received`, `provider.event_quarantined`, `workflow.waiting` không nằm trong allowlist public.
- Khi serialize phải giữ các key nullable của envelope bằng `model_dump(mode="json")`, không `exclude_none=True`.

`validate_public_event` kiểm tra lại cả envelope (kể cả object được tạo bằng `model_copy` không qua validation) và payload. Proposal payload yêu cầu timestamp RFC3339 có timezone; không nhận epoch ngầm. PinnedRuntimeContext từ chối version pin trùng. Nó không xác thực audience, không xác minh status/approval đã xảy ra, không phát hiện secret bị nhét trong text. Projection runtime phải xây payload từ dữ liệu đã lọc; mọi đọc history/SSE phải revalidate quyền. Approval status và ticket details cần PHD/legacy owner duyệt vocabulary; generic ShortCode chưa chứng minh transition hợp lệ. Các điểm coercion của envelope/shared DTO vẫn chờ NCH xử lý theo IR-PHH-A05.

## Persistence và transaction contract để owner duyệt

Không có repository/DDL/migration được tạo ở Phase A. Theo mục 17.4, PHH sở hữu logic `wf_workflows`, `wf_workflow_waits`, `wf_workflow_triggers`, `wf_conversation_events`; mở rộng partner bindings và run/checkpoint/runtime bindings. NCH tạo revision Alembic thật; không tự thêm bảng checkpoint có tên mới làm nguồn thứ hai.

Các constraint cần thể hiện trong migration và test DB sau này:

- Binding ticket: unique `(tenant_id, partner_client_id, external_user_id, external_ticket_id)`; binding conversation: unique `(tenant_id, partner_client_id, external_user_id, external_conversation_id)` theo kế hoạch. Routing identity/group của ticket đã accept bất biến.
- Command namespace chung `(tenant_id, partner_client_id, external_request_id)`, **không thêm command_kind vào unique key**. Canonical hash gồm command kind, target, audience, body. Auth/audience phải kiểm tra trước khi đọc kết quả cũ; retry đúng hash đọc resource cũ trước CAS revision mới.
- Trigger unique `(workflow_id, cause_kind, cause_id)`; conversation event unique `(conversation_id, sequence)` và event_id ổn định qua replay. Checkpoint phải FK đúng workflow, session/version và scope đã pin; row revision/fence chống stale writer.
- Operation correlation/inbox thuộc PHD; jobs/outbox và fencing contract thuộc Foundation. Provider scope phải resolve từ operation trong integration namespace đã xác thực.

Thứ tự đề xuất (spec, chưa có implementation/test transaction):

1. Ingress xác thực purpose/grant, resolve hoặc revalidate binding trước Leader. Claim/read idempotency cùng UOW; start mới mới tạo group/workflow. Reply/close dùng original binding, không resolve remap.
2. PHD resolve operation + protocol pinned; một UOW ghi inbox outcome/progress, workflow update, public status và trigger/job. Port PHH không tự commit.
3. Chỉ sau commit mới đánh thức result waiter/SSE qua PublicEventSignalPort; signal không phải nguồn dữ liệu. Mất signal vẫn đọc DB để catch-up.
4. Worker sẽ load checkpoint/pins, serialize theo workflow/session, nhận lease/fence từ Foundation; không giữ DB transaction qua model/provider. Commit candidate dùng expected revision/fence cùng checkpoint/messages/outbox/trigger completion.
5. Event không giả approval/user reply để phá HITL. Close không tự reopen do provider event trễ; lưu sự thật operation qua PHD và áp policy public phù hợp. Unknown creation cần reconcile, không tạo giao dịch lần hai.
6. POST timeout trả trạng thái request đã có; không enqueue lại chỉ vì người gọi hết thời gian chờ.

Schema tests chỉ xác nhận dữ liệu biểu diễn được các bước này. Atomicity, race, quyền và exactly-once effect cần bằng chứng ở B–D và các adapter thật.

## Gate sang Phase B

- [x] PHH local schema/sample/test/handoff hoàn tất.
- [x] Đọc output thật của NCH/NPD/BHN/PTA/PHD trong clone mới; ghi mismatch, không dùng hợp đồng tưởng tượng từ dev2PHH cũ.
- [ ] NCH/PHH/PHD chốt typed claim/trigger/checkpoint/runtime turn và scope/UOW/authorization semantics.
- [ ] BHN/PTA/NCH thống nhất policy; NPD/NCH chốt full snapshot resolver/hash.
- [ ] PHD/PHH chốt operation/event/approval adapters và fixtures dùng cùng chữ ký shared.
- [ ] NCH ghi nhận gate MA, cập nhật contracts/export dùng chung; producer và consumer xác nhận.

Yêu cầu hiện tại chỉ cho phép Phase A. Không tự bắt đầu B, kể cả khi đủ gate MA; cần người dùng giao việc tiếp. Gói này chưa đăng ký HTTP route, worker, SSE reader, UI hay runtime service và chưa tạo fake adapter để che các mismatch.
