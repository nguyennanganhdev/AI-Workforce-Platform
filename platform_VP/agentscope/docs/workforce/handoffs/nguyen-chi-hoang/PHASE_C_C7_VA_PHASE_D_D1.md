# Bàn giao C7 và Phase D/D1 — Nguyễn Chí Hoàng

Ngày thực hiện: **2026-10-12**. Baseline đầu vào:
`develop2@5e66ea0` (PR #67/C6 đã merge).

## C7 đã triển khai

- Migration additive `0010_workforce_runtime` đóng băng đủ 19 bảng do Registry,
  Execution, Orchestration và Lifecycle bàn giao; không import metadata runtime
  từ migration đã phát hành.
- `WorkforceBootstrap` tạo đúng một `foundation.uows` dùng chung, cho phép
  `runtime_factory` lắp graph thật trước startup, mount router ổn định trước
  OpenAPI và quản lý SQL/worker trong cùng lifespan.
- `build_phase_c_runtime` dựng graph production Registry → Execution →
  Orchestration → Lifecycle từ các port deployment inject; không dùng fixture
  C6. Các dependency Leader/MCP/auth/quote/query vẫn được fail-fast yêu cầu rõ.
- `compose_phase_c_runtime` kiểm tra hai router và đăng ký đủ handler
  `provider_event`, `operation_reconcile`, `workforce.workflow.continue`,
  `workforce.lifecycle.evaluate`.
- `OperationReconcileJobHandler` lấy `Scope`, `operation_id`, `timer_id` từ
  durable job; không tạo inbox provider giả.
- `ApprovalContinuationCommandAdapter` ghi kết quả consent và enqueue một
  approval continuation có idempotency key riêng trong cùng UOW; restart không
  làm mất wakeup và retry không dùng lại request ID của lệnh consent.
- `create_app` mount router của runtime assembly đúng một lần trước lifespan.
- CI PostgreSQL/migration/C7–D2 được thêm tại
  `.github/workflows/workforce-phase-d.yml`.

`runtime_factory` chỉ nhận các dependency production do deployment cung cấp
(Leader, MCP transport, quote/HITL, auth dependencies, query adapter). C7 không
đưa fake/scripted Leader hoặc MCP trong test C6 vào production.

## D1 đã triển khai

- `DurableWorkerSupervisor` restart vòng poll khi repository/transport lỗi,
  shutdown có kiểm soát và không can thiệp retry/fencing của từng durable job.
- Metric convention ổn định: `workforce_worker_iterations_total`,
  `workforce_worker_restarts_total`, `workforce_sse_connections_total`,
  `workforce_sse_replays_total`; có null sink và in-memory sink cho test.
- SSE thêm `Connection: keep-alive`, `Content-Encoding: identity`, giữ
  `Cache-Control: no-cache` và `X-Accel-Buffering: no`; cursor mâu thuẫn bị chặn
  trước khi mở stream.
- `scripts/workforce/check_phase_d_environment.py` kiểm tra Python/dependency,
  Alembic single head và DSN PostgreSQL test.
- Fault harness chứng minh worker phục hồi sau simulated database restart.

## Bằng chứng kiểm tra cục bộ

- C7 + D1: **8 pass**.
- Foundation: **31 pass**.
- C6 E2E: **11 pass**.
- Migration SQLite: upgrade → downgrade `0009` → upgrade head pass.
- `compileall`, environment check và `git diff --check` pass.

Đây là snapshot kiểm thử tại thời điểm bàn giao ban đầu. C7/D1 và hai lane D2
sau đó đã commit và merge vào `develop2@278ea4a`; PostgreSQL/Phase D gates và
trạng thái cuối được ghi tại `../PHASE_D_SEQUENCE.md`.
