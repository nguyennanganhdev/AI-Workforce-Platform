# Phase C — C6 E2E toàn lát cắt của Phan Hoàng Dũng

Ngày cập nhật **12/10/2026**, Asia/Saigon. Nhánh **`feat/wf-execution`**.
Commit đầu vào **`69e21f7`**, chứa C1–C5; C4 merge `86fa293`, C5 merge `830cdac`.
Đọc kế hoạch triển khai 1.4.3, bảng tuần tự C0–C7, bàn giao C3/C4/C5 trước khi làm.

**C6 hoàn thành trong môi trường kiểm thử hiện có: 11 passed, zero xfail.**
Query-after-revoke và binding mismatch đã được kiểm chứng sau sửa C4.
PostgreSQL gate chưa chạy vì không có dedicated DSN; không tính skip là pass.
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

Output Orchestration mô tả tại [PHH C4](../phan-huy-hoang/PHASE_C_C4.md).
Root bootstrap, contracts, migration, dependencies và CI không thay đổi.
C6 không có schema production mới.

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
| Query sau route revoke | Fact commit, Workflow/history/evidence không đổi, worker idle, không thêm model call; không còn xfail |
| Reply sai immutable tuple | Caller có quyền nhận 409/WORKFLOW_BINDING_MISMATCH; sai user hoặc grant bị revoke vẫn 403/AUTHORIZATION_DENIED; không dispatch |
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
  tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py -q -ra

$env:PYTHONPATH='src;tests/workforce/fixtures;tests/workforce/registry/event_protocols'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/execution tests/workforce/e2e tests/workforce/foundation `
  tests/workforce/registry tests/workforce/lifecycle tests/workforce/builder `
  --ignore=tests/workforce/e2e/async_tickets/test_phase_c_c6.py `
  --ignore=tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py `
  --import-mode=importlib -q

$env:PYTHONPATH='src;tests/workforce/orchestration/async_workflows;tests/workforce/orchestration/phase_a'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/orchestration --import-mode=importlib -q
```

Các suite có module `fakes`/`fixtures` trùng tên nên chạy Orchestration riêng;
không sửa root conftest của đội. Một lượt collect tất cả cùng PYTHONPATH tối
thiểu lỗi import legacy; không phải kết quả regression code.

Kết quả ngày 12/10/2026:

- C6: **11 passed, 0 xfail, 1 skipped** trong 96.97 giây. Skip duy nhất của
  lượt C6 là PostgreSQL do không có `WORKFORCE_TEST_POSTGRES_URL`.
- Regression ngoài C6: **274 passed, 9 skipped, 178 subtests passed**.
- Orchestration: **262 passed, 97 subtests passed** sau cập nhật assertion
  regression ingress theo exception binding mismatch mới.
- Kiểm thử C4 SQL/HTTP tập trung: **6 passed**. Bounded-wait kiểm tra worker
  succeeded và receipt completed; chi tiết sửa test trong handoff C4.
- Ruff E/F: **pass** trên năm file source Orchestration (88 cột) và ba file
  test thay đổi (79 cột).

Strict xfail đã bỏ, assertion binding mismatch đổi từ 403 sang 409 và kiểm tra
đúng error code. Assertion route revoke đọc kết quả vẫn là 403.
Không có `WORKFORCE_E2E_FACTORY`; các gate factory cũ vẫn cần composition C7.
PostgreSQL locks/race và deployment không nằm trong kết luận pass SQLite này.

## Bàn giao

[INTEGRATION_REQUEST_PHD_C6.md](INTEGRATION_REQUEST_PHD_C6.md) ghi C4 đã xử lý,
approval bridge, handler/router map, metadata và các điều kiện môi trường.
C6 không còn blocker query-after-revoke/binding mismatch. Điều phối mở C7 theo
baseline tích hợp của đội là bước riêng. Không thực hiện thao tác Git trong lượt này.
