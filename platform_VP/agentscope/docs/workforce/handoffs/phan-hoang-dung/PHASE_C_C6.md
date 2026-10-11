# Phase C — C6 E2E toàn lát cắt của Phan Hoàng Dũng

Ngày **11/10/2026**, Asia/Saigon. Nhánh **`feat/wf-execution`**.
Commit đầu vào **`69e21f7`**, chứa C1–C5; C4 merge `86fa293`, C5 merge `830cdac`.
Đọc kế hoạch triển khai 1.4.3, bảng tuần tự C0–C7, bàn giao C3/C4/C5 trước khi làm.

**Đã triển khai phần kiểm tra C6 có thể làm trong owned paths. Chưa nghiệm thu
C6 toàn bộ:** còn lỗi query sau revoke thuộc C4 và các gate cần môi trường.
Xem [request C6](INTEGRATION_REQUEST_PHD_C6.md),
[trạng thái mới nhất](STATUS.md). Không tự đánh dấu mở C7.

## Phạm vi và file

- `tests/workforce/fixtures/phase_c_e2e.py`: composition test C6, kế thừa
  scripted driver C5 và dùng các adapter production đã bàn giao.
- `tests/workforce/e2e/async_tickets/test_phase_c_c6.py`: HTTP/customer/provider,
  SQL worker/Workflow/evidence, history/SSE và các tình huống lỗi.
- `tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py`: gate race
  PostgreSQL riêng, tự skip nếu không có dedicated DSN.
- `test_full_platform.py`: chỉ sửa skip reason cho đúng tình trạng C7 factory;
  không đổi assertions hoặc giả endpoints để làm gate cũ pass.
- Handoff chỉ cập nhật/tạo STATUS, PHASE và INTEGRATION_REQUEST; không tạo
  NEXT_STEPS. Request A/B/C3 ghi rõ các producer C4 đã được cung cấp.

Không sửa source/module của thành viên khác, root bootstrap, contracts,
migration, dependencies hoặc CI. C6 không có schema production mới.

## Lát cắt thực thi

```text
Customer HTTP request/reply/approval
  → C4 SQL command ledger / request / immutable ticket binding
  → C1 durable job / worker
  → C4 SQL checkpoint / continuation / Execution guard
  → C3 gateway / consent / operation intent / MCP adapter
Provider HTTP raw bytes + HMAC
  → C1 SQL credential auth
  → C3 inbox + provider job commit → 202 ACK
  → durable worker → C2 exact protocol normalization
  → operation fact + C4 Workflow/checkpoint/event log/next job, cùng UOW
  → continuation + C5 SQL committed turn evidence
  → Customer GET request / history / HTTP SSE / explicit close
```

Query fallback: durable `operation_reconcile` → `OperationReconciler` → query
port kiểm soát → exact protocol →
`WorkflowEventAdapter(query_sink=WorkflowService.apply_query_result)` →
TimerCause/continuation. Không tạo provider inbox hoặc provider cause giả.

Fixture seed membership/route đã verified bằng dữ liệu test. Customer routing
và identity dùng `SqlPartnerRoutingPort`/`SqlIdentityPort` thật. Adapter
authorization test nối các kiểm tra C4 với original SQL route/grant C1.
Customer credential dependency được inject từ header test; không phải hệ thống
customer authentication production.

Consent HTTP dùng `PartnerApprovalService`, SQL command ledger thật, và bridge
test `_ApprovalCommands`. Consent ACK và continuation result dùng hai command
ID có quan hệ deterministic, commit cùng UOW; retry trước/sau consume vẫn trả
ACK gốc và chỉ một provider create. Đây là ví dụ wiring cần C7 triển khai trong
root production, không phải module production mới của Dũng.

## Bằng chứng C6

| Tình huống | Assertion chính |
|---|---|
| Raw provider HTTP → worker → Workflow → SSE → close | ACK accepted trước worker, receipt applied sau worker; operation status events; next_action confirm_close; một create; close bằng HTTP |
| Rollback sink rồi retry | Inject lỗi sau public-event SQL insert; operation/Workflow/checkpoint/history/job/evidence không đổi; inbox accepted; worker mới xử lý lại thành công |
| HMAC / duplicate / conflicting ID / late snapshot | Body thay sau ký trả 401; duplicate cùng receipt; conflicting body 409; late version rejected/không wake model |
| Unbound correlation | Inbox quarantined; không Workflow dispatch; receipt chỉ có public fields |
| Close trước completion | Late provider fact vẫn lưu, Workflow closed/history/model không đổi |
| Route revoke / credential revoke sau ACK | Event route revoke giữ fact và suppress send; credential revoke chặn processor apply |
| Current protocol đổi rồi disable | Operation/workflow vẫn dùng exact old pin; raw event hoàn tất được, không gọi create lại |
| Hai chat cùng user | Tách workflow/conversation/group/session/approval/cursor; hai HTTP SSE đúng binding; replies xen kẽ; stop/close A không đổi B |
| C5 cùng runtime seam | Năm case response-only, interactive booking, external events, unknown reconciliation, audience isolation; raw provider và query job; SQL evidence/report/release check; replay zero model/provider calls |
| Terminal/interactive không tracking giả | Không external operations cho hai pattern này; timer IDs không được dùng làm external event ID trong inbox |
| Query sau route revoke | Strict xfail tái hiện rollback mất fact trong C4; không tính pass |
| PostgreSQL race | 8 signed HTTP deliveries + 8 concurrent applies; một fact revision/continuation; cần DSN, chưa chạy |

SSE test gọi router HTTP thực và gửi ASGI `http.disconnect` sau số frame giới
hạn; không mock stream. Reconnect với Last-Event-ID khớp durable history;
disconnect không close workflow. Đây là test ASGI in-process, chưa kiểm chứng
reverse proxy, mạng thật hoặc browser.

## Thật / dữ liệu kiểm soát / chưa kiểm chứng

| Thành phần | Mức kiểm chứng |
|---|---|
| DB/UOW/jobs/worker/signals | Foundation implementation thật, DB SQLite file riêng mỗi test, cùng UOW factory |
| Manager identity / partner route | SQL membership/route/identity adapters thật, seed dữ liệu test |
| Provider auth | HMAC + SQL credential repository thật; API-key authenticator/secret resolver là test ports |
| Registry / Execution / Workflow | Implementations SQL và router/processor/continuation/query hook thật |
| C5 evidence / evaluation / release check | SQL writer/repository/runner/service thật, giữ Scope/version/hash pins |
| Leader/model / catalog/runtime authority / quote/HITL | Scripted test dependencies từ fixture C5; không kết luận concrete AgentScope Leader production |
| MCP/provider | MCP adapter creation thật với fake backend; query port đọc dữ liệu backend kiểm soát, không live MCP status transport |
| PostgreSQL / global composition / migrations / CI | Chưa nghiệm thu; gate và yêu cầu C7 ghi trong request C6 |

Không coi SQLite là bằng chứng row locks, fencing/race PostgreSQL. Worker restart
ở đây là tạo lại dispatcher trên DB đã commit; không phải crash/restart cả
application process hoặc phục hồi backend/model state.

## Validation

Chạy từ `platform_VP/agentscope`. Python 3.11 test venv có SQLAlchemy,
aiosqlite, asyncpg, httpx, pytest; không đổi dependency manifests.

```powershell
$env:PYTHONPATH='src;tests/workforce/fixtures'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/e2e/async_tickets/test_phase_c_c6.py `
  tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py -q -rx -rs

$env:PYTHONPATH='src;tests/workforce/fixtures;tests/workforce/registry/event_protocols'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/execution tests/workforce/e2e tests/workforce/foundation `
  tests/workforce/registry tests/workforce/lifecycle tests/workforce/builder `
  --import-mode=importlib -q

$env:PYTHONPATH='src;tests/workforce/orchestration/async_workflows;tests/workforce/orchestration/phase_a'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/orchestration --import-mode=importlib -q
```

Các suite có module `fakes`/`fixtures` trùng tên nên chạy Orchestration riêng;
không sửa root conftest của đội. Một lượt collect tất cả cùng PYTHONPATH tối
thiểu lỗi import legacy; không phải kết quả regression code.

Kết quả C6 cuối lượt: **10 tests đạt, 1 strict xfail, 1 PostgreSQL skip**.
Trong lượt suite cuối có 9 tests đạt; test grading sau chỉnh assertion đọc
`aggregate.pattern` đã chạy lại riêng: **1 passed, 10 deselected**. Không cộng
test deselected vào pass; strict xfail là lỗi baseline còn mở.

Regression rộng ngoài các tests C6 mới: **274 passed, 9 skipped,
178 subtests passed**. Lượt rộng ban đầu
còn lỗi trong test C6 đóng chat đang pending approval; đã sửa test dùng
`stop_tracking_only=True` đúng contract, kiểm tra lại bằng suite C6.

Orchestration chạy riêng: **260 passed, 1 failed, 97 subtests passed**. Failure
là test sẵn có `C4SqlSliceTests.test_bounded_wait_observes_committed_worker_result`:
deadline 1 giây, kết quả 202 thay vì 200. Đã tái hiện ở hai lượt, không sửa
module/test của PHH; không báo suite này xanh.
Chạy riêng test này cũng fail. Kịch bản chẩn đoán tương đương chạy riêng có
worker `succeeded`, receipt `completed`, không job error; chưa kết luận lỗi
sản phẩm từ deadline 1 giây nhạy timing. PHH cần kiểm tra test/đồng bộ worker.

Ruff E/F, line length 79: pass cho bốn file Python thay đổi. Không thay source
nên không tuyên bố có lượt mypy production mới.

Không có `WORKFORCE_TEST_POSTGRES_URL` hoặc `WORKFORCE_E2E_FACTORY`. Docker CLI
có nhưng `dockerDesktopLinuxEngine` không chạy. PostgreSQL gate mới và các gate
factory cũ cần môi trường riêng; không dùng credentials production để chạy.

## Bàn giao

[INTEGRATION_REQUEST_PHD_C6.md](INTEGRATION_REQUEST_PHD_C6.md) nêu blocker C4,
approval bridge, handler/router map, metadata và các điều kiện môi trường.
Chỉ sau xử lý blocker và merge C6 vào develop2 mới đối chiếu mở C7 theo bảng
tuần tự của đội. Không tự commit, push hoặc tạo PR trong lượt này.
