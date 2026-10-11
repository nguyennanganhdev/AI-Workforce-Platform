# Bàn giao Phase C4 — Phan Huy Hoàng

Ngày hoàn thành code: **2026-10-11**. Baseline đầu vào:
`develop2@7bfdc6097fbbd8a5cfeddaf8f84f60b2ddf798c3`, đã có C1, C2 và hai lane C3.

## Kết quả

C4 đã nối lát cắt backend:

```text
Customer POST
  → xác thực actor + resolve/revalidate route
  → command idempotency + ticket/conversation binding
  → workflow/checkpoint/public event + durable job cùng UOW
  → commit
  → bounded wait (không giữ transaction)
  → Foundation worker claim job
  → LeaderTurnRunner thật được inject
  → CAS + lease/fence + checkpoint/result/event/evidence cùng UOW
  → completion signal sau commit
  → 200 nếu lượt đã xong, 202 nếu hết thời hạn chờ
```

Không có outbound webhook. SSE là một GET riêng do backend khách hàng mở và có
thể reconnect/replay. Runtime không giữ model/tool sống trong thời gian workflow
đang chờ user, approval, timer hoặc provider event.

## Code và public exports

- `_tables.py`: metadata additive cho workflow, immutable binding, input,
  checkpoint, partner command/request và public event log.
- `_repository.py`: `SqlWorkflowRepository`, `SqlPartnerRequestRepository`,
  `SqlCheckpointRepository`, `SqlEventRepository`; tất cả dùng UOW được inject,
  không tự tạo schema hoặc commit UOW của caller.
- `_runtime.py`: `LeaderWorkflowBootstrap`, `SqlRuntimeContinuation`,
  `WorkflowContinuationJobHandler` và các port/seed cho Leader/team runtime thật.
- `_execution.py`: `ExecutionOperationReader` đọc operation đã persist của
  Execution, gồm trạng thái `pending` thật.
- `_router.py`: factory route Customer API cho POST request/reply, GET result,
  snapshot, history, SSE và POST close. C7 chịu trách nhiệm mount factory.
- `orchestration.get_metadata()`: metadata C4 để C7 đưa vào migration additive.
- `WorkflowService.apply_query_result(...)`: hook canonical cho status-query nội
  bộ dùng `TimerCause`; không giả provider inbox/event ID.
- `CommittedTurnEvidence` + `RuntimeEvidenceWriter`: evidence đã lọc, ghi trong
  cùng UOW với turn; C5 dùng để nối evaluation vào runtime thật.

`LeaderBootstrapResolver` phải trả một `group_id`, session/shared-state và
published Leader version đã materialize thật. C4 không cung cấp fake mặc định;
composition thiếu dependency phải fail khi khởi động.

## Bất biến đã giữ

- Một external ticket/conversation chỉ bind một workflow/conversation/group;
  hai hộp chat của cùng người dùng vẫn tách group, session và checkpoint.
- Retry cùng `(tenant, partner_client, external_request_id)` trả resource cũ và
  được đọc trước khi resolve route mới; remap không tạo workflow/group thứ hai.
- Reply/close dùng owner, audience, ticket, conversation và route pin ban đầu.
- HTTP handler không chạy Leader trong transaction. Worker chạy ngoài
  transaction rồi commit kết quả bằng revision CAS + workflow lease fence.
- External event/query hook join UOW của Execution. Closed/revoked workflow
  không bị mở lại. Query result dedupe bằng `timer_id + source_hash`.
- Public event chỉ phát signal sau commit; history/SSE kiểm tra audience và
  cursor trước khi stream. Cursor không còn hợp lệ được map thành HTTP 410.
- Command thất bại ở lần retry cuối được ghi trạng thái/error đã sanitize;
  không lưu exception/provider secret vào response công khai.

## Kiểm thử

```powershell
$env:PYTHONPATH=(Resolve-Path src)
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests\workforce\orchestration\phase_c -p "test_*.py" -v
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests\workforce\orchestration\async_workflows -p "test_*.py" -v
```

Kết quả tại lúc bàn giao:

- C4 SQL/HTTP integration: **5/5 pass**.
- Workflow Phase B regression: **14/14 pass**.
- Python compileall vùng Orchestration: pass.

Test C4 dùng SQLite/aiosqlite nhưng chạy repository/UOW/job worker/Leader
adapter/event log thật. PostgreSQL lock/race, app composition và Alembic vẫn là
gate C7; không coi SQLite là bằng chứng PostgreSQL production.

## Không thuộc C4

- Không thêm/sửa Alembic revision, global app bootstrap, worker deployment,
  compose hoặc CI; C7 thực hiện sau C6.
- Không hard-code model/agent/team giả. Concrete Leader/team engine và
  published catalog được inject qua `LeaderBootstrapResolver` và
  `LeaderTurnRunner`.
- Không triển khai eval/grader; C5 tiêu thụ runtime/evidence C4.
- Không thực hiện E2E provider-event toàn nền tảng; C6 thực hiện sau C5.

Các dependency tiếp theo nằm tại
[INTEGRATION_REQUEST_PHH_C4.md](INTEGRATION_REQUEST_PHH_C4.md).
