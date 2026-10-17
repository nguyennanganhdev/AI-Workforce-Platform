# Bàn giao Phase B — Nguyễn Chí Hoàng

Ngày cập nhật: 2026-10-10. Baseline triển khai: `develop2@254ec21`.

## Phạm vi đã thực hiện

Phase B bổ sung của Chí Hoàng là **Jobs/SSE signal/transport + fake event
refs**, thuộc phần độc lập của NCH-14. Không triển khai hộ workflow/event log
của Huy Hoàng, provider inbox của Dũng hoặc protocol normalizer của Đông.

### Backend

- `foundation/event_delivery/_jobs.py`: model job nội bộ, repository protocol,
  enqueue scoped/provider, idempotency, schedule, lease, fencing và retry.
- `foundation/event_delivery/_worker.py`: claim một job, heartbeat, dispatch
  handler và fenced complete/fail; lỗi handler chỉ lưu loại lỗi đã sanitize.
- `foundation/event_delivery/_signals.py`: signal completion và public event
  trên MessageBus, namespace bằng đủ Scope và resource ID.
- `foundation/event_delivery/_sse.py`: replay event bền vững trước, signal chỉ
  đánh thức, heartbeat/catch-up và SSE encoder.
- Contract additive: `JobPort.enqueue_provider(...)` và
  `RequestCompletionSignalPort`.

### Frontend

- `shared/event_transport/sseClient.ts`: fetch-SSE có bearer token, refresh,
  cursor, reconnect/backoff, kiểm tra envelope và lỗi cursor hết hạn.
- `shared/event_transport/cursor.ts`: cursor store abstraction; chưa gắn vào
  localStorage để shell quyết định lifecycle theo đăng nhập.

### Test doubles

- `tests/workforce/foundation/async_api/fakes.py`: repository/event port fake
  cho module test. Đây không phải production persistence.

## Output cho thành viên khác

- Dũng có thể gọi `JobPort.enqueue_provider(verified_context, ...)` đúng yêu
  cầu trong `INTEGRATION_REQUEST_PHD-01_PHASE_A.md`; context phải do auth
  server xác minh và chứa `tenant_id`, `provider_integration_id`.
- Huy Hoàng inject `ConversationEventPort` vào `ConversationSseService`; event
  log của Huy vẫn là nguồn chuẩn, signal không thay persistence.
- Partner ingress có thể dùng `RequestCompletionSignalPort` để bounded-wait;
  sau wake phải đọc lại persisted `InboundReceipt`.
- Shell/UI import `streamConversationEvents` từ `shared/event_transport`;
  410 phải chuyển sang snapshot recovery, không tự bỏ cursor rồi tiếp tục.

## Kiểm chứng

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.async_api.test_phase_b tests.workforce.foundation.test_contracts -v
& '.\examples\web_ui\frontend\node_modules\.bin\tsc.cmd' -b
& '.\examples\web_ui\frontend\node_modules\.bin\eslint.cmd' 'src/features/workforce/shared/event_transport/*.ts'
```

Kết quả: 19 Python tests pass; compileall pass; TypeScript build và ESLint
pass; `git diff --check` pass. Full pytest Workforce chưa chạy vì `.venv`
không có `pytest`; một số suite Execution/E2E còn yêu cầu fixture path riêng.

## Chưa làm — chuyển Phase C

- PostgreSQL repository, bảng `wf_jobs`/`wf_outbox`, Alembic và recovery scan.
- Bootstrap worker, FastAPI SSE/history endpoints và proxy headers.
- Provider signature/replay-window/rate-limit auth.
- Retention watermark, snapshot transaction và HTTP 410 từ event repository.
- Nối handler thật của Execution/Orchestration và kiểm thử restart/race.

Phase C cần metadata/public exports của Huy Hoàng và Dũng. Nếu chưa sẵn sàng,
tiếp tục bằng repository/ports hiện có, không import private service của họ.
