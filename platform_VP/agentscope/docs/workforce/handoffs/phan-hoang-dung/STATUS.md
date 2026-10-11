# Trạng thái — Phan Hoàng Dũng

Ngày: **11/10/2026**, Asia/Saigon. Nhánh: **feat/wf-execution**.
Baseline: **67ff871**, đã chứa C1 `a4c2fdd` và C2 `b9feee2` trên
`develop2`. Thay đổi C3 lần này chưa commit/push.

## Kết luận phạm vi

- Phase A/B đã bàn giao; tài liệu lịch sử:
  [PHASE_A.md](PHASE_A.md), [PHASE_B.md](PHASE_B.md).
- **Lane C3 của Dũng đã hoàn thiện:** Provider ingress ↔ Operation ↔ Protocol
  dùng auth/UOW/jobs C1 và Registry SQL C2 thật; chi tiết
  [PHASE_C_C3.md](PHASE_C_C3.md).
- Chỉ kết luận lane Dũng; không đánh dấu C3 Builder của Nghĩa hoàn thành.
  C4 Workflow/POST/Leader/event log/SSE, C6 E2E toàn lát cắt và C7
  composition/migration/CI chưa được nghiệm thu trong lượt này.
- Verified context, exact resolver và canonical UOW consumer đã được nối;
  không còn báo thiếu output C1/C2 này.

## Tasks C3 và đầu ra

| Tasks | Đã thực hiện trong C3 | Giới hạn |
|---|---|---|
| PHD-14 | Dùng Registry SQL exact detail pin cho operation/create result; bind theo đủ Scope | Runtime/tool catalog/MCP trong test vẫn là dependencies giả |
| PHD-15 | Persist full VerifiedProviderContext; request-local loader đọc inbox thật; re-authorize credential; worker handler kiểm tra provider namespace | Workflow apply sink thật thuộc C4 |
| PHD-16 | Query/transition dùng exact pin kể cả current bị đổi hoặc disable; scoped durable query timer, giữ TimerCause | MCP query transport và canonical query hook chưa phải live integration |
| PHD-17, kiểm tra C3 | Signed provider HTTP, durable worker thật, rollback/retry, early correlation, hai manager xen kẽ | Chưa làm C6 full-platform E2E |

## Owned paths và exports

Chỉ thay đổi:
`src/agentscope/app/workforce/execution/**`,
`tests/workforce/{execution,fixtures}/**`,
`docs/workforce/handoffs/phan-hoang-dung/**`.
Không sửa contracts/Foundation/Registry/Orchestration, migration, root bootstrap
hoặc dependency manifests.

- `create_repository(session_factory=None, *, uow_factory=None)`: C3 dùng
  canonical UOW factory C1; giữ compatibility với session factory cũ.
- Mới `external_operations.RegistryExecutionProtocols`: bind public Registry
  service/resolver theo Scope; không query trực tiếp bảng Registry.
- Mới loader nội bộ `provider_events/_context.py`: đối chiếu stored
  context/envelope/receipt/time/Scope/pin, re-authorize trong apply UOW.
- Ingress persist full server-only verified context; job payload chỉ tham chiếu
  receipt, không mang provider-controlled Scope hoặc signing secret.
- `ProviderEventProcessor.handle_job(job)`: callable Foundation JobHandler,
  kiểm tra namespace với inbox rồi trả receipt/outcome.
- HTTP sanitize PermissionError từ C1: authentication sai trả 401,
  thiếu operation trả 403.
- Tests mới `test_execution_c3.py`, fixture `phase_c_fakes.py`; fixture cũ thêm
  tùy chọn canonical UOW và nhận normalization UOW.

Không thêm bảng/cột: provider_ref nằm trong JSON payload của inbox hiện có.
Metadata sáu bảng Execution bàn giao cho C7 qua `execution.get_metadata()`.

## Producer thật và test dependencies

| Thành phần | Trạng thái kiểm chứng |
|---|---|
| C1 auth | HmacProviderAuth + SQL credential repository thật; API-key authenticator/secret resolver là test dependencies |
| C1 UOW/jobs/worker | Canonical UOW + SQL job repository + service + worker thật, cùng DB test |
| C2 Registry | SqlAsyncProtocolRepository/Provider/service thật; publish/current/old-pin lookup bằng SQLite |
| Execution | HTTP/ingress/repository/operation/processor/reconciler/adapters thật |
| Workflow | Fake sink của Dũng dùng shared DTO/PHH schemas, ghi SQL trong caller UOW; không thay implementation C4 |
| Provider/MCP/runtime/catalog | Fake backend/ports của owned tests; không có sandbox/model/booking thật |

## Bằng chứng kiểm tra ngày 11/10/2026

- Execution/E2E slice + Foundation contracts + Registry:
  **150 passed, 5 skipped, 76 subtests passed**, gồm **22 tests C3** mới.
- Foundation Phase B + C1: **20 passed**.
- Workflow Phase B: **14 passed** bằng unittest discover.
- Ruff E/F 79 cột: pass. Mypy: **28 source files**, pass.
- Các lệnh chạy lại, test collection notes và invariants tại
  [PHASE_C_C3.md](PHASE_C_C3.md). Frontend không thay đổi.

Hai skip PostgreSQL cần dedicated `WORKFORCE_TEST_POSTGRES_URL`; ba skip
full-platform cần `WORKFORCE_E2E_FACTORY`. Không tính skip là pass hoặc coi
SQLite là bằng chứng PostgreSQL locks/races.

Đã kiểm tra signature/timestamp/body Scope sai, duplicate receipt, revoke trước
apply, enqueue failure sau SQL insert, sink rollback + after-commit callback,
loader metadata forgery, exact old pin sau drift/disable, hai manager xen kẽ,
early event và query timer không tạo provider inbox giả.

## Integration requests còn cần owner

- [C3 → C4/C7](INTEGRATION_REQUEST_PHD_C3.md): Workflow sink/hooks trong caller
  UOW; đăng ký worker/router bằng dependencies thật; gom metadata vào migration
  additive và quyết định xử lý inbox legacy thiếu verified context.
- [Contract Phase A/B](INTEGRATION_REQUEST_PHD-01_PHASE_A.md): chỉ giữ các
  quyết định shared còn mở; đã cập nhật phần context/resolver/UOW được giải quyết.

Không tự backfill credential/signing-key/authentication time cho inbox cũ,
không triển khai thay C4/C7 hoặc bắt đầu C6 khi các bước trước chưa bàn giao.

## Tín hiệu từ C4 — 2026-10-11

C4 đã nhận seam C3 và cung cấp Workflow sink thật trong caller UOW, gồm
`apply_external_event` hiện có và `apply_query_result` canonical cho TimerCause.
C4 đã kiểm tra query hook qua `WorkflowEventAdapter` + Execution SQL repository
thật. C6 chưa bắt đầu: vẫn phải chờ C4 merge và C5 hoàn thành. Hướng dẫn nối C6
nằm tại `../phan-huy-hoang/INTEGRATION_REQUEST_PHH_C4.md`.

