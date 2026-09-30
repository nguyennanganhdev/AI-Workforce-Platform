# PD03–PD08 — Consumer contracts và yêu cầu tích hợp

Owner ghi: Phan Dũng, Team Hoàng. Ngày 30/09/2026.
Owner đích: Dương Dũng DD02–DD08, Phan Hoàng PH02–PH08; Chiến C01/C03–C09/C14,
Quang Q01/Q04, Đông D02/D04/D08 và Team 5 qua đầu mối Hoàng.
Request chỉ được ghi trong repo; chưa gửi tin nhắn/chấp thuận thay owner.

## Kiểm tra thực tế

Khi triển khai ban đầu, checkout có PH01 bootstrap/contract TS draft `0.1.0-draft.1`.
Hiện code PD01–PD08 đã chuyển Python, consumer version `0.1.0-python.draft.1`;
contract/entrypoint TS của PH vẫn được giữ nguyên và chưa nối Python.
Không tìm thấy implementation tool Reception, backend runtime/knowledge/business APIs
hoặc shared C01 schema trong những folder dự kiến qua inventory. Report folders trước
task chưa tồn tại. Graph mới chỉ dùng consumer interfaces, không tự đặt URL/API thật,
không sửa contracts/package/entrypoint của Phan Hoàng hay module/backend owner khác.

## Reception factory và session

`agent-reception/src/graph/workflow.py` export `create_reception_workflow_factory(options)`;
`workflow_contracts.py` là **proposal consumer pd-workflow-python-1**, không catalog đã freeze.
Yêu cầu composition Python mới: [PYTHON_RUNTIME_INTEGRATION](PYTHON_RUNTIME_INTEGRATION.md).
Composer inject `GraphDependencies(model, tools, checkpointer)` với `AsyncModel`/`ToolPort` Python,
intake policy/knowledge, `resolve_session(context,signal)`, optional `reconcile`.
PH02/backend authorize trước run/read/resume/recover, resolve channel/session/binding,
đối chiếu ticket đang active với state. Browser/model không chọn framework key.
Workflow yêu cầu session ổn định, owner/context đúng và active_ticket_id khớp ticket.

Giữ generic PD01 tại `factory.py` với marker `pd01-python-1`; graph mới giữ schema envelope 1 nhưng bổ sung
`workflow_version: "pd-workflow-python-1"`. Không chạy trên checkpoint PD01 cũ rồi migrate
âm thầm; PH03 chốt namespace/topology migration trước tích hợp. Không default InMemorySaver.
Root thread codec vẫn JSON tuple `[namespace,threadId]`, root checkpoint_ns rỗng.

## Typed operations cần DD/PH bind với catalog thật

Input TypedDict/protocol/`OPERATION_INPUTS` nằm trong `workflow_contracts.py`;
response thực được kiểm tra trong `workflow_validation.py` và `_apply_output` tại
`workflow.py`. Các semantic operations cần backend chốt gồm:

- create draft: channel đã resolve, handoff reason; Ticket output ID/code/generation,
  opaque ticket_version, aggregate_version, created_at. User do auth/backend lấy.
- load context: ticket/version/generation và resident_response; backend xác minh
  tenancy/căn hộ. Trả verified profile hoặc missing/selection_required + questions.
  Tuyệt đối không chọn căn hộ đầu tiên hoặc xác minh bằng lời model.
- update incident: ticket/version + title/description/facts provenance/file references;
  trả ticket snapshot mới, incident đã authorize/validate, missing_fields. Unknown field
  hỏi thêm, chưa route. `file_ids` có thể thiếu với emergency theo backend policy;
  thiếu mô tả/profile không tự điền. Backend cần emergency notification sớm theo policy,
  không chờ graph hỏi ảnh mới gửi cảnh báo.
- assessment: ticket/version/facts; trả applied official triage + updated ticket,
  hoặc policy_missing/review_required. Emergency downgrade bị graph chặn trước handoff;
  authoritative floor/human review vẫn do C05 enforce.
- resolve: chỉ ticket/version, backend đọc building/domain, trả route IDs/revision/binding
  và scope/ticket_version snapshot hoặc unresolved. Graph không chọn workspace.
- handoff: ticket/version/destination/revision + schema v1. ACK phải persisted=true,
  enqueued=true, correlation đúng và operation_id. Partial ACK không Supervisor wait.
- append: ticket/version/message/facts/files → updated ticket/delivered/scope_changed.
  Nếu scope_changed graph bỏ profile/route/triage/ACK rồi reload và resolve lại.
- interaction: ticket/version/interaction_id/revision/answers + source_message_id.
  Trả accepted/conflict/expired; không blind retry stale interaction.
- cancellation: ticket/version/reason/source_message_id → accepted/rejected/review.
  Accepted không có nghĩa đã hủy; status backend phải xác nhận kết quả cuối.
- status: updated ticket, lifecycle status, completion_confirmed, scope_changed.
  completion_confirmed phải do backend kiểm chứng evidence/work order/policy; không
  chỉ copy Supervisor completed. Graph chỉ thông báo hoàn tất/hủy khi confirmed.

Proposal không có category_id/incident knowledge enrichment tùy ý ở model extraction;
nếu backend yêu cầu category, DD/C05 phải chốt cách normalize và version interface.

## PH04 wait registry/event port (không phải tự tạo HTTP tool)

`register_supervisor_wait` là capability composer bind cho **runtime PH04**, không
khẳng định C01 đã có tool này. Input ticket/version + correlation/workspace/team/
coordination binding. Return registered=true hoặc buffered_event envelope.
PH04 phải durable registry + inbox atomicity/fencing. Handoff ACK phải hoàn tất trước
đăng ký wait; graph checkpoint ACK, register rồi mới interrupt Supervisor. Buffered
event được lookup và consume trước interrupt, không mất event đến sớm.

`get_supervisor_event` lookup envelope PH01 theo backend-authenticated context,
return event_id/aggregate_version/reception binding + schema Supervisor v1 payload.
Do v1 requested_information thiếu revision, proposal bổ sung interaction_revision
ở wrapper envelope; PH/C01/Đông phải review trước freeze. Không tự sửa schema chung.
Graph kiểm tra tenant/ticket/code/generation/workspace/team/correlation/binding,
version và event ID trước consume interrupt. Payload lấy từ authorized lookup,
không nhận raw customer/browser event làm quyền. Event cập nhật ticket version snapshot
cho lệnh sau. PH04 vẫn phải kiểm tra origin, grant revoke và outbox/inbox dedup.

## Mutation/recovery semantics

Plan/input/idempotencyKey được checkpoint trước invoke, durability sync. Draft key
theo binding/session + operation + "draft", không theo runId. Các operation khác
theo binding/session/operation/message/ticket version/route revision/event version.
DD/C01 cần review format/length; backend lưu hash input và reject key khác payload.
Success chỉ được project sau validator; accepted/timeout/sai response giữ plan.
`reconcile(request)` phải authorized lookup operation result bằng **cùng input/key**;
không blind retry mutation. Not_applied → review. Không có reconcile → giữ dependency.

PH03 gọi `await graph.recover({"context": context, "operationId": operation_id, "signal": signal})` sau fenced recovery claim khi abort/crash
giữa mutation có pending và next node chưa interrupt. Chỉ pending operation cũ được
reconcile; operation mới sau recovery đi qua invoke bình thường. Không replay cả run.
Budget Python dùng `asyncio.wait`, cancellation token và task cancellation. Timeout
không chứng minh rollback side effect backend; vẫn cần idempotency/status lookup thật.
Port phải không chặn event loop hoặc nuốt cancellation; chi tiết ở request Python runtime.

Dedup resident operation/payload lưu trong checkpoint; graph không có lease hay
multi-replica lock. Completed_operations hiện giữ keys/payload fingerprints không
giới hạn; PH03 chốt retention và durable operation store/codec trước production,
không xóa giữa active session làm mất dedup. Event IDs gần nhất tối đa 256 + version
floor; backend inbox vẫn phải durable. Không log checkpoint/PII vào telemetry/UI.

## Report PD07/PD08

Template/schema/config/prompts/examples ở `agent-report/{templates,schemas,prompts,examples}`.
Versions hiện **consumer proposal 1.0.0**, không release backend đã publish. Capability
IDs authorized_report_snapshot/report_docx_export là semantic IDs để DD07/PH07/Đông bind,
không operation đăng ký sẵn. Builder C09/C14 authorize config và pin template/config/
metric/tool/agent versions. Không có arbitrary SQL/tools/workspace/prompt trong config.
Metric cohort/denominator/reopen/cancel proposal ở metric-contracts-v1.json; DD07/C14
review và tính bằng code, tăng version nếu thay nghĩa. Không dùng LLM tính KPI.

`build_report_narrative(raw,config,authorization)` thuộc PD08; snapshot consumer validator nằm
ở `server/src/reporting/narrative/operations.py`. C14/DD08 cung cấp real source_message_id,
authorized snapshot/workspace/scope, period/as_of, metrics/version/units/status/source IDs
và immutable references. Narrative không query DB hoặc authenticate grants; authorization
phải do backend xác minh, recheck khi run/export/download. Empty khác query error,
missing value=null, zero chỉ hợp lệ khi tool cung cấp đủ lineage. Source scope/version/
snapshot sai bị chặn. PH08 DOCX renderer dùng semantic layout tại layouts/operations.py;
HTML previews chỉ synthetic examples, không production UI/storage/export artifacts.

## Tests owner cần bổ sung trước đóng nghiệm thu

Producer/consumer normalize schemas + response validation, 401/403/404/409/410/422/429,
idempotency key/payload conflicts, optimistic version/generation, authorized files và
multiple units. Real persistent restart/fencing/two replicas/event-before-wait/revoke/
reroute/reopen; model tiếng Việt eval thật và early emergency notification.
Report: hai BQL publish hai agent, tool grants/lineage thật, scope revoke giữa run/export,
consistent snapshot, source_message_id thật, renderer DOCX visual QA, retries/cancel
không phát hành artifact trùng. Không dùng test fixtures làm production fallback.
