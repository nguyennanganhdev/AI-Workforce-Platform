# Phase D — D3 lượt 1 — Phan Hoàng Dũng

Cập nhật **12/10/2026**, Asia/Saigon. Thực hiện trên working tree hiện tại theo
xác nhận của người dùng: Phase C và D2 đã xong, mở D3.

**D3 lượt 1 hoàn thành trong môi trường SQL/mock hiện có:** 8 E2E mới và
3 regression Execution mới pass, không xfail. Ba PostgreSQL crash gates đã
viết, skip do chưa có dedicated DSN. Không suy diễn sandbox hoặc production pass.

## Phạm vi

PHD-14–17 trong nhịp D: duplicate, out-of-order, crash, unknown operation,
Provider Event recovery và Scope isolation. Chỉ thay đổi tests thuộc
`tests/workforce/execution/`, `tests/workforce/e2e/`, `tests/workforce/fixtures/`
và handoff cá nhân. Chưa phát hiện lỗi production cần sửa qua các ca này.
Không sửa module/metadata/contract của owner khác, migration, CI hoặc frontend.
Không thao tác Git, không tạo NEXT_STEPS.

Đầu vào đã đọc và sử dụng:

- Kế hoạch 1.4.3, mục 5, 12, 15, 17.4–17.9.
- [C7/D1](../nguyen-chi-hoang/PHASE_C_C7_VA_PHASE_D_D1.md): SQL worker,
  lease/fence, supervisor/metrics, approval continuation và reconcile handler.
- [Registry D2](../nguyen-phuong-dong/PHASE_D_D2.md): immutable protocol pin,
  current disable, version ordering/transition validation.
- [Orchestration D2](../phan-huy-hoang/PHASE_D_D2.md): public log/replay/SSE,
  sleep/wakeup, close và ticket isolation; dùng lại implementations thật.

Tài liệu điều phối chung còn ghi D3 chưa mở; quyền thực hiện lượt này theo
chỉ dẫn mới nhất của người dùng. Không sửa trạng thái chung hoặc xác nhận merge.

## File và seam bàn giao

| File | Nội dung |
|---|---|
| `tests/workforce/fixtures/sql_ticket_slice.py` | Tách helpers HTTP ticket/reply/consent, job, history và event khỏi C6 để C6/D3 dùng chung; thêm timeout fixture option |
| `tests/workforce/fixtures/phase_d_execution.py` | `D3CaseDriver`: kế thừa SQL/HMAC C6, dùng `ApprovalContinuationCommandAdapter` và `OperationReconcileJobHandler` C7, tạo worker/job service/processor mới khi restart |
| `tests/workforce/fixtures/phase_c_fakes.py` | `c3_harness(event_mode="snapshot")` nhận lựa chọn delta; default cũ giữ nguyên |
| `tests/workforce/e2e/async_tickets/test_phase_c_c6.py` | Dùng helpers chung, giữ nguyên 11 test cases/assertions C6 |
| `tests/workforce/e2e/async_tickets/test_phase_d_d3.py` | 8 SQL/HTTP fault/recovery E2E cases |
| `tests/workforce/e2e/async_tickets/test_phase_d_d3_postgres.py` | 3 crash/reclaim gates trên PostgreSQL, schema ngẫu nhiên riêng mỗi case |
| `tests/workforce/execution/provider_events/test_phase_d_d3.py` | 3 regression dùng SQL Registry, HMAC, operation/inbox/jobs thật và typed Workflow test sink |

`D3CaseDriver.new_worker(seconds=31)` tạo service/processor mới, không mang
in-memory claim map cũ sang worker mới. Clock job tiến qua lease 30 giây;
dispose connection pool rồi reconnect cùng DB đã commit. Trigger/continuation,
checkpoint, public log và evidence vẫn do implementations SQL xử lý.

## Bằng chứng hành vi

| Tình huống | Assertions |
|---|---|
| Crash sau ACK, trước apply | Inbox accepted, job leased, operation/Workflow/history/evidence không đổi; worker mới reclaim fence/attempt mới, apply một lần |
| Crash sau public SQL insert, trước UOW commit | Rollback operation, checkpoint, Workflow, public log và continuation; inbox accepted; restart áp dụng thành công |
| Crash sau UOW commit, trước complete job | Fact/public log/continuation đã bền vững; job reclaim không tạo fact/event/turn thứ hai |
| Cả ba điểm crash | Old fence không được complete; một provider create, một continuation/model turn, một evidence mới; duplicate HTTP giữ receipt; worker idle; SSE replay khớp history |
| Lỗi enqueue job trong ingress | HTTP 500, không inbox/job/fact/event commit; retry cùng event ID nhận 202 và áp dụng thành công |
| Snapshot completed v4 → late v3 / conflicting v4 / regressive v5 | v3 rejected, hai conflict quarantined theo Registry; operation/Workflow/history/evidence/model count không đổi, không reopen |
| Timeout sau provider đã ghi | Creation unknown, replay không create lại; signed event resolve correlation và bind job thật; operation succeeded/completed, một provider create |
| Unknown → durable status query | Handler C7 đọc scoped job; canonical query hook/TimerCause cập nhật fact và continuation; không tạo inbox giả; replay terminal không gọi create |
| Delta v3 thiếu v2, current protocol bị disable | Quarantine v3; query theo exact pin xác nhận v2; processor mới áp dụng lại v3; cùng receipt replay không dispatch thêm |
| Event job-only đến trước job binding | Quarantine; sau xác minh/bind creation result, explicit recovery JobPort dispatch áp dụng receipt cũ một lần |
| Scope isolation | Bốn owner A/B cùng area, C khác area, D khác domain xử lý xen kẽ; read/query khác manager/area/domain/tenant bị chặn; job namespace giả và refs chéo bị chặn, không đổi facts khác owner |
| Supervisor gặp lỗi claim SQL | Restart counter đúng một lần, queued provider job và continuation hoàn thành, không create thêm |

Recovery của event quarantined trong test là **explicit durable recovery job**
sau khi dependency đã được xác minh/bổ sung. HTTP duplicate chỉ trả receipt cũ,
không phải API tự động scan/quarantine recovery. Không thêm scanner production
hoặc đoán owner theo payload; điều kiện vận hành ghi trong integration request.

## Kiểm thử đã chạy

Chạy từ `platform_VP/agentscope`, Python 3.11 tại test venv đã có dependency;
không đổi manifests hoặc tải thêm package.

```powershell
$env:PYTHONPATH='src;tests/workforce/fixtures'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/e2e/async_tickets/test_phase_d_d3.py `
  tests/workforce/e2e/async_tickets/test_phase_d_d3_postgres.py `
  --import-mode=importlib -q -ra --tb=short
# 8 passed, 3 skipped, 3 subtests passed

$env:PYTHONPATH='src;tests/workforce/fixtures;tests/workforce/registry/event_protocols'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/execution --import-mode=importlib -q -ra --tb=short
# 112 passed, 1 PostgreSQL skipped; đã bao gồm 3 regression D3 mới

& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/foundation/phase_d tests/workforce/foundation/phase_c `
  tests/workforce/registry/event_protocols tests/workforce/orchestration/phase_d `
  --import-mode=importlib -q --tb=short
# 44 passed, 1 PostgreSQL skipped, 76 subtests passed
```

C6: **11/11 pass**, PostgreSQL C6 skip do thiếu DSN, sau khi tách helpers chung.
Lượt ghép C6/D3 trước đó còn ba lỗi decode SSE trong test D3 mới; đã sửa cách
đọc ASGI messages và chạy lại toàn bộ D3 E2E: **8/8 pass**. Không tính các lỗi
test đã sửa hoặc test deselected là pass; không cần sửa SSE production.

Ruff E/F 79 cột: **pass** trên cả 7 file Python thay đổi.
Không có strict xfail mới hoặc giảm assertions để bỏ qua lỗi sản phẩm.

## Giới hạn và bàn giao D4

- Không có `WORKFORCE_TEST_POSTGRES_URL`; ba crash gates D3 và các PostgreSQL
  gates C6/Execution/Registry chưa chạy local. Không dùng SQLite để xác nhận
  row locks, concurrency PostgreSQL hoặc DB failover.
- Crash dùng cancellation tại fault boundaries, worker/service mới và SQL
  reconnect; chưa phải kill/restart cả application process hay DB server.
- Leader, catalog/runtime authority, quote/HITL, API-key/secret resolver và MCP
  provider là test dependencies có kiểm soát. SQL auth/routing/HMAC/jobs,
  Registry/Execution/Workflow/history/SSE/evidence là implementations thật.
- Không gọi provider/model live hoặc integration sandbox. Thiếu endpoint,
  credential và kịch bản sandbox được cấp thì không nghiệm thu gate MD/live.
- D4 có thể dùng các fixtures/tests này để kiểm tra pin và long wait; phần
  Lifecycle/publish/archive/rollback vẫn thuộc Phó Tiến Anh.

Yêu cầu CI/PostgreSQL và bàn giao D4 tại
[INTEGRATION_REQUEST_PHD_D3.md](INTEGRATION_REQUEST_PHD_D3.md).
