# PHD-01/05/08/09/13–17 — Orchestration ports và Chat integration

Người gửi: Phan Hoàng Dũng. Người nhận: Phan Huy Hoàng; Chí Hoàng nối core/shared contracts. Hiện trạng Orchestration chỉ scaffold; không có Customer API/Workflow/SSE để chạy full E2E.

Input/output đề xuất cho adapter runtime dùng trong ExecutionPolicy/ApprovalService:

```text
load(scope, run_id, uow?) -> persisted RunContext
get_agent_spec(scope, agent_id, version_id, uow?) -> pinned AgentSpec (PublishedCatalog adapter)
revalidate(scope, context, operation, uow?) -> check original binding/route/membership/grant/audience/cancel/close
authorize_tool(scope, context, descriptor, uow?) -> actor/audience + connection capability policy
authorize_conversation(scope, conversation_id) -> owner check for manager approval list
```

Context cần scope/run/workflow/conversation/group/partner_audience/version_pins/mode/status và **allowed_decider** do server policy gán. Đây không phải Actor/Scope lấy từ request model. Callback call_factory cấp stable call_id/key theo tool-call cause; replay checkpoint không tạo ID mới. Hủy run chặn call mới, provider call đang gửi vẫn persist succeeded/failed/unknown. Resume approval phải giữ call/run gốc và revalidate workflow group, không ghép sang run/group khác.

HITL bridge `required(scope, approval_record, context, uow)` / `resolved(...)` reuse AgentScope event/projector đang có; record transactional approval không thay parked agent state bằng event giả. Khi approval pending, provider fact không auto-approve hoặc giả UserConfirmResult/ExternalExecutionResult cho call cũ. Chí Hoàng thực hiện hook core tối thiểu.

PartnerCommandPort cần:

- `authorize_approval(actor, approval_id, body, uow)` → scope/audience từ original approval binding, check full external user/ticket/conversation/workflow và grant submit_consent. Đây là extension adapter đề xuất để không tự làm route/mapping service thứ hai.
- `claim_or_read(actor, external_request_id, 'approval_decision', approval_id, payload_hash, uow)` → `{is_new, request_id, result?}` chung namespace wf_inbound_requests với request/reply/close.
- `record_result(request_id, public_result, uow)`, commit cùng approval/HITL. Authorize trước đọc cache; replay trước expected_revision. ID khác command/body trả IDEMPOTENCY_CONFLICT, remap không tạo owner mới.

ProviderEventProcessor gọi `WorkflowPort.apply_external_event(scope, stored_operation, normalized_event, uow)`. Cần lock/CAS binding, state, checkpoint/waits, append public status từ sanitized facts và enqueue cause-deduped trigger **trong cùng AsyncSession**. Không route theo external ref hiện tại hoặc payload provider. Close/revoke giữ job fact/inbox audit, chặn chat/model/resume và không reopen. Public external_ticket/conversation lấy từ binding gốc. Signal sau commit, readers catch-up DB kể cả mất signal.

Hooks bổ sung cho query/recovery: `mark_operation_attention(scope, operation, cause_id, reason, uow)` chuyển needs_attention theo policy mà không giả completed; `apply_execution_result(scope, stored_call, cause_id, uow)` tiếp tục unknown sync booking đã được đối soát, không hoàn thành một tool call hai lần. Đây là **yêu cầu chốt contract**, chưa có implementation bên Workflow.

Frontend import riêng từ `features/workforce/approvals/index.ts`. `WorkforceApprovalCard` nhận approval view, canDecide, async onDecide; callback chỉ resolve khi server persist, parent refresh qua shared transport. ExternalOperationStatus tách creation_status và job progress; progressLabel từ normalized projection/locale, không coi create succeeded là job completed. Không cần sửa trang Chat từ lane Dũng.

Test hiện có: `test_http_and_tools.py` partner consent/quasi shared namespace, `test_execution_slice.py` hai group/operation xen kẽ và close sink; test ports có transaction rollback thật. Đây chưa chứng minh Customer API/worker/SSE/context đầy đủ. Cần ports thật để chạy cases 56–88 và observation hooks trong INTEGRATION_REQUEST_PHD-11.

