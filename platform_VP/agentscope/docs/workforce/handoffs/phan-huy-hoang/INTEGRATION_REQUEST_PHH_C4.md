# Integration request sau C4

Trạng thái: **C4 đã merge qua PR #63; C5 đã dùng đầu ra này và cũng đã merge.
Tài liệu hiện là đầu vào cho C6/C7.**

## C5 — Phó Tiến Anh

Dùng đúng runtime production seam của C4:

- inject `RuntimeEvidenceWriter` vào `WorkflowContinuation` để persist evidence
  evaluation theo Scope trong UOW của turn;
- dùng `LeaderTurnRunner`/`SqlRuntimeContinuation` và `ExecutionGuard` thật,
  chỉ mock model/provider/clock theo test context;
- map `CommittedTurnEvidence` sang evidence grader: cause, state/next_action,
  model/tool/token delta, checked effect, tracking record và audience;
- không gọi fake runner Phase B như thể đó là production runtime;
- bàn giao bảng/index report/evidence cho C7 và exports runner cho C6.

C5 không cần sửa repository C4. Nếu cần thêm evidence field, gửi integration
request và giữ payload không có prompt, message text, credential hoặc raw tool
arguments.

## C6 — Phan Hoàng Dũng

Sau khi C5 merge, compose test E2E:

```text
Customer POST → workflow job → Leader/Execution create operation
→ Provider Event API → Execution inbox/apply
→ WorkflowService.apply_external_event (same UOW)
→ public event history/SSE → explicit customer close
```

Với status-query, inject
`WorkflowEventAdapter(..., query_sink=workflow.apply_query_result)`. Không tạo
`NormalizedJobEvent` hoặc provider inbox giả cho timer query.

## C7 — Nguyễn Chí Hoàng

- Gom `orchestration.get_metadata()` vào một Alembic revision additive sau head
  thực tế. Không gọi `metadata.create_all()` trong production.
- Dùng cùng `WorkforceDatabase.uows` cho Foundation, Registry, Execution và
  Orchestration.
- Mount `orchestration.create_router(...)`, đăng ký
  `WorkflowContinuationJobHandler.job_type` vào `DurableJobWorker`.
- Inject customer auth, tenant resolver của partner credential,
  approval authorizer Execution, route/identity/jobs/signals, concrete
  Leader/team runtime và Execution repository.
- Metadata cần migrate: `wf_workflows`, `wf_workflow_bindings`,
  `wf_workflow_inputs`, `wf_workflow_checkpoints`, `wf_partner_commands`,
  `wf_partner_requests`, `wf_public_events` cùng toàn bộ unique/index trong
  `_tables.py`.
- Chạy PostgreSQL concurrency/restart/proxy tests. SQLite C4 không thay thế gate
  này.

## Điều kiện không được suy diễn

C4 export factory/adapter và metadata; chưa có nghĩa route đã được mount, worker
đã chạy trong deployment hoặc migration đã tồn tại. Chỉ C7 mới đóng các điểm đó.
