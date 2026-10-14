# Integration request — Điểm nối sau Execution C3

Ngày: **11/10/2026**. Người gửi: **Phan Hoàng Dũng**.
Tasks: **PHD-14/15/16**, lane **C3**. Baseline: `67ff871` chứa C1/C2.
Người nhận: **Phan Huy Hoàng (C4)**, **Nguyễn Chí Hoàng (C7)**;
Nguyễn Phương Đông theo dõi producer Registry C2.

**Cập nhật C6, 11/10/2026:** C4/C5 đã merge. Workflow sink/query hook trong
caller UOW đã được tiêu thụ với SQL thật, không còn request thiếu producer C4.
Query sau revoke đã xử lý, C6 đạt zero xfail ngày 12/10/2026; wiring C7 theo
[INTEGRATION_REQUEST_PHD_C6.md](INTEGRATION_REQUEST_PHD_C6.md).
Các tiêu chí và kết quả fake C4 bên dưới là lịch sử tại lượt C3.

## Đã xong phía Execution

[PHASE_C_C3.md](PHASE_C_C3.md) bàn giao canonical UOW consumer, full persisted
VerifiedProviderContext, request-local inbox loader, exact SQL protocol pin và
Foundation JobHandler. C1/C2 đã có code và đã tiêu thụ bằng tests SQL thật;
không còn request bàn giao lại auth context, detailed resolver hoặc UOW bridge.

## C4 — Workflow sink trong cùng UOW

Module nhận: `src/agentscope/app/workforce/orchestration/workflows/`.
Caller: `ProviderEventProcessor` → `WorkflowEventAdapter`.

- Dùng shared `apply_external_event(scope, operation_ref,
  NormalizedJobEvent, uow) -> WorkflowRecord`. Event giữ persisted inbox ID,
  source hash, occurred/received-at, provider version và exact protocol hash.
- Join caller UOW, không tự commit; cập nhật state/checkpoint/event/trigger
  atomic và signal sau commit. Revalidate original binding/grant/closed state;
  close/revoke không reopen hoặc gửi chat/model trái quyền.
- Trả record đúng Scope/workflow/conversation/group/ticket/audience.
  Sink throw hoặc response sai binding làm Execution rollback toàn apply;
  retry cùng receipt phải dedupe, không sinh workflow/group mới.
- Query không có provider inbox. Chốt callable query hook với signature
  `(scope, operation_ref, query_result, uow) -> WorkflowRecord`; query_result gồm
  `timer_id`, `protocol_schema_hash`, `source_hash`, `observed_at`,
  `status`, `facts`, `provider_version`, `terminal`. Execution inject qua
  `WorkflowEventAdapter(..., query_sink=hook)`, thiếu hook trả 503/rollback.
- Attention/result hooks còn là explicit extensions trong request A/B;
  không mặc định đã được shared WorkflowPort chấp nhận.

Đã kiểm tra với fake C4 sink: wrong binding, rollback sau SQL write,
after-commit callback, hai Scope xen kẽ và query TimerCause. C4 cung cấp test
consumer với Workflow thật; Dũng không sửa module Orchestration để thay owner.

## C7 — Composition và migration

Module nhận: Foundation/integrations async runtime/root bootstrap/Alembic.

- Dùng duy nhất `WorkforceDatabase.uows` cho C1 jobs/auth, Registry C2 và
  `execution.create_repository(uow_factory=uows)`.
- Tạo `RegistryExecutionProtocols(registry_provider, repo, auth, operations)`;
  dùng cùng instance dependencies cho gateway/ingress/reconciler. Registry
  service bind theo Scope của operation, không theo public provider body.
- Đăng ký `"provider_event": processor.handle_job` trong worker handler map;
  mount Execution `create_router` với auth và dependencies thật. C3 không
  chỉnh global route/lifespan hoặc tự khởi động worker.
- Lấy metadata từ `execution.get_metadata()`: `wf_tool_calls`, `wf_approvals`,
  `wf_booking_operations`, `wf_execution_events`, `wf_external_operations`,
  `wf_provider_event_inbox`. Giữ unique/CAS/correlation/provider namespace của
  metadata. Chỉ tạo revision additive sau head thực tế, không sửa `0009`.
- `provider_ref` mới nằm trong JSON payload, không thêm bảng/cột C3.
  Inbox legacy thiếu full verified context phải có quyết định xử lý rõ;
  không backfill credential/signing-key/time từ phỏng đoán hoặc current route.

Tests cần owner nối: PostgreSQL atomic inbox+job/apply+sink, worker retry và
HTTP receipt sau durable commit trong composition app thật. Dedicated DSN và
full-platform factory chưa được cung cấp; không đánh dấu các gate bị skip là pass.

## Phạm vi tại thời điểm C3 — lịch sử

C4 runtime/POST/Leader/event log/SSE và C7 global composition/migration thuộc
owner nhận. C6 E2E toàn lát cắt chưa bắt đầu trong lượt C3 này.
