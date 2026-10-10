# PHD-01/05/06/08/13–16 — Foundation integration

Người gửi: Phan Hoàng Dũng. Người nhận: Nguyễn Chí Hoàng. Baseline contract: kế hoạch 1.4.3 mục 6 và 17.

Hiện trạng: Foundation/contracts/integrations chỉ scaffold. Execution đã có implementation và tests với fake ports; không thể include router, tạo Alembic migration, sửa core tool assembly/HITL hoặc giả auth production trong lane này.

File/module nhận cần sửa: Workforce contracts/async_api, foundation, integrations, shared frontend; core tool assembly/ChatService/HITL và Alembic theo ownership kế hoạch. Không yêu cầu thay StorageBase hay tạo migration chain thứ hai.

## Exports và composition đề xuất

`execution.create_repository(session_factory)` dùng **AsyncSession** cùng DB Foundation. `execution.get_metadata()` export sáu bảng: wf_tool_calls, wf_approvals, wf_booking_operations, wf_execution_events, wf_external_operations, wf_provider_event_inbox. Không auto-create trong production; metadata.create_all chỉ nằm ở test.

Unique: owner+run+idempotency_key cho call; approval.call_id; booking.call_id; operation.call_id; global correlation_id; tenant+integration+external_job_id (nullable); inbox tenant+integration+external_event_id + payload_hash. Các row có revision CAS; provider processor khóa row operation/inbox, no network trong transaction. Thêm FK/checks sang bảng Workflow/run khi shared table names được chốt trong migration; giữ immutable scope/audience và không cascade xóa version/agent.

Inject services/router theo chữ ký thực trong execution. Runtime adapters cần read/revalidate pin, membership, route, actor/audience và workflow close state; **tất cả đường legacy/raw MCP phải qua GuardedTool/gateway**, không mount public execute endpoint. Inject gateway `call_factory(scope, run_context, agent_spec, tool_version_id, arguments)` cấp call_id/key ổn định theo cause/tool-call, không cấp ID mới khi replay checkpoint.

Ports cần chốt additive:

- `SecretStore.resolve_for_execution(scope, credential_ref, mode)` → credential bundle nội bộ có environment mock/sandbox/production và identity. Đây là adapter đề xuất bọc resolve có sẵn, không export browser. `McpAdapter` client_factory là async context manager, mỗi call/client riêng; không mutate headers client đa user. Evaluation cấm production credential.
- `ProviderAuth.authenticate(raw_body, headers)` → verified principal purpose=provider_events. Identity refs: tenant_id, provider_integration_id, actor_id/kind/purpose; auth kiểm tra credential, signature/replay window/rate limit. `authorize_integration(principal, operation, uow?)` kiểm tra publish_job_event/read_event_receipt và internal process_job_event. Raw-body auth trước parse; signature/header không vào payload hash hay DB.
- `JobPort.enqueue_provider(principal, job_type, {receipt_id}, idempotency_key, uow)` cần namespace provider trước khi có scope. Đây là **yêu cầu additive chưa được contracts chốt**, không tự chọn manager giả để enqueue. Inbox+job cùng UOW, ACK sau commit. Worker scope resolve từ inbox/operation, không tin broker scope.
- `JobPort.enqueue(scope, job_type, payload, idempotency_key, not_before, uow)` cho status query timer. Worker lease/fence/retry/scanner gọi ProviderEventProcessor.process / OperationReconciler.reconcile / TransactionService.recover_abandoned sau xác minh lease hết hạn. Không giữ worker/model/transaction khi waiting.
- Shared command namespace qua PartnerCommandPort của Huy Hoàng, tuyệt đối không tạo wf_partner_approval_commands riêng.

Workflow/public event/trigger port phải join cùng AsyncSession UOW, không commit nội bộ. Notification chỉ sau commit; crash sau signal không làm mất business event. Provider `.process` hiện thuộc ProviderEventProcessor, HTTP `.accept/read_receipt` thuộc ProviderEventIngress: composition inject đúng handler, có thể façade cho Port chung.

Frontend `createApprovalApi(transport)` cần shared authenticated transport có `request<T>(path, {method?,body?})`; không gắn secret URL hay sửa global api barrel từ lane Dũng. Replace component view models/Any annotations bằng generated shared contracts khi bàn giao.

## Errors, samples, validation

Error envelope ExecutionError: code/message/details/request_id/retryable, không raw exception/provider payload. Owner reads dùng cả bốn Scope fields; provider receipt dùng đúng namespace principal. Router auth dependencies bắt buộc inject, không có default permissive/fake.

Tests: `tests/workforce/execution/test_http_and_tools.py`, `test_recovery.py`, `provider_events/test_provider_events.py`, `test_postgres_concurrency.py`. SQLite tests xác minh UOW rollback; PostgreSQL test cần WORKFORCE_TEST_POSTGRES_URL, tự tạo/xóa random test schema của chính test. Chưa chạy PostgreSQL vì daemon/DSN thiếu. Cần migration fresh+upgrade/backfill và integration test core bypass/lease fence thật trước release.

Contract discrepancy cần owner quyết định: kế hoạch nói response có workflow_state/workflow_revision, nhưng partner contract close sample mục 9.9 dùng state/revision. Mock customer đọc được hai projection; không sửa tài liệu chung trong lane này. Partner approval HTTP hiện theo contract mục 9.8: 202 sau decision commit, schema_version/expected_revision/arguments_hash/quote_ref; manager UI dùng quote_hash nội bộ.

