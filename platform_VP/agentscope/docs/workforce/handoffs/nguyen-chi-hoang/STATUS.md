# Trạng thái — Nguyễn Chí Hoàng

Tên thành viên: Nguyễn Chí Hoàng. Baseline chung hiện tại:
`develop2@830cdacd56f868d509d208b91b9a6bc29d70c935`.

**Trạng thái mới nhất:** C1–C5 đã merge. Nguyễn Chí Hoàng là owner C7 nhưng C7
vẫn chờ C6 của Phan Hoàng Dũng hoàn thành và merge.

Task IDs đã hoàn thành theo nhịp: NCH-01; contract khởi động NCH-02/NCH-13;
Phase B độc lập của NCH-14; và output C1 thuộc NCH-03/05/06/08/12/14/15 gồm
SQL UOW, verified membership/routing, durable-job repository, provider HMAC,
migration Foundation và bootstrap opt-in. Không đánh dấu toàn bộ các task này
hoàn thành end-to-end chỉ từ output C1.

Task IDs đang làm/chưa làm: Customer/Provider HTTP routers, workflow/event
production repositories, runtime adapter/worker loop, frontend/root composition,
full migration của năm module, CI/E2E/runbook vẫn chờ C2–C6 rồi hoàn tất ở C7.

Files và thư mục đã sửa: output Phase A trước đó; Phase B thêm `foundation/event_delivery/`, `shared/event_transport/`, `tests/workforce/foundation/async_api/`, contract ports additive và `PHASE_B.md`.

Public exports, API và contract version: Python exports tại `agentscope.app.workforce.contracts`; JSON Schema và TypeScript version `1`. Chưa đăng ký FastAPI endpoint trong Phase A.

V1.4: API/protocol/event samples, invariants đã test và event IDs dùng đối soát: DTO có request/reply/close, request result, public event, provider event, operation snapshot, binding hai ticket. `event_id` và `external_event_id` tách riêng. Detailed provider protocol đang chờ Registry owner.

V1.4: inbox/checkpoint/outbox/replay/close/restart tests: chưa chạy vì Phase A chưa triển khai persistence/worker/SSE. Contract validation và multi-ticket isolation fixture đã pass.

V1.4: provider/backend đối tác thật hay mock, điều kiện onboarding còn thiếu: chưa gọi hệ thống thật; chưa có credential/route/provider sandbox. Phase A chỉ có DTO/ports và local fixtures.

Cách chạy demo hoặc test:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe scripts\workforce\export_contracts.py
```

Kết quả test: 9 contract tests pass bằng Python 3.11.15; compileall pass; schema export pass; TypeScript contract type-check pass bằng `tsc.cmd`; `git diff --check` pass. Pytest chưa chạy do `.venv` thiếu package pytest; `pnpm` chưa có trên PATH.

Schema/migration/dependency: Alembic có đúng một head
`0009_workforce_foundation`. Migration tạo membership/route/provider credential/
durable jobs và backfill tài khoản cũ ở trạng thái `pending_verification`;
không thêm dependency.

Đầu vào module khác đã dùng (fake hay thật): chưa dùng implementation module khác; các port là boundary/fake-ready.

Integration requests còn mở: xem `INTEGRATION_REQUEST_NCH_PHASE_A.md`; các yêu cầu này phục vụ phase sau và không chặn contract hiện tại.

Live verification còn thiếu: FastAPI route, PostgreSQL transaction/uniqueness, Redis server thật, provider signature, AgentScope continuation và browser UI runtime. MessageBus in-memory, SSE encoder/replay service và TypeScript transport đã có test/type/lint cục bộ.

Trình tự hiện tại: C1–C5 đã merge; Phan Hoàng Dũng thực hiện C6. Nguyễn Chí
Hoàng không bắt đầu C7 trước khi C6 merge; trong thời gian chờ chỉ review
schema/hook additive và giữ migration chain ổn định.

## Cập nhật Phase B

- `JobPort` có đường additive `enqueue_provider(...)` theo integration request của Dũng; không giả manager Scope trước khi resolve operation.
- `RequestCompletionSignalPort`, public event signal và SSE service đều chỉ đánh thức/replay; DB result/event vẫn là nguồn chuẩn.
- Job service có idempotency namespace, `not_before`, lease reclaim, fencing, heartbeat và retry; fake repository chỉ nằm trong test.
- Frontend fetch-SSE có bearer token, refresh, Last-Event-ID, 410 snapshot signal và cursor advance sau xử lý.
- Chi tiết output, lệnh kiểm tra và giới hạn Phase C: xem `PHASE_B.md`.

## Cập nhật Phase C/C1 — 2026-10-11

- Code và test: xem [PHASE_C_C1.md](PHASE_C_C1.md).
- Trình tự/gate toàn đội: xem [../PHASE_C_SEQUENCE.md](../PHASE_C_SEQUENCE.md).
- Kết quả mới: **10/10 C1**, **19/19 Foundation A/B**, **14/14 PHH
  Phase B**, **24/24 Registry**, **4/4 Auth core** pass; compileall, schema
  export và Alembic single-head pass.
- SQLite test harness đã chạy migration upgrade/downgrade và repository thật.
  PostgreSQL concurrency/Redis multi-process/provider sandbox chưa chạy vì
  không có dedicated environment trong phiên này.
- `VerifiedProviderContext` đã chốt server-only. Phase C của Dũng phải persist
  đủ context này (không rút còn dict thiếu credential/signing key) trước khi
  re-authorize provider event sau dequeue.

## Điều phối sau khi C5 merge — 2026-10-11

- C5 đã merge qua PR #64 tại
  `830cdacd56f868d509d208b91b9a6bc29d70c935`.
- C6 của Phan Hoàng Dũng hiện được mở để kiểm chứng E2E toàn lát cắt.
- C7 **chưa được bắt đầu** trước khi C6 có commit trên `develop2` và bàn giao
  metadata, handler/router factories, test evidence và danh sách seam còn mở.
- Khi gate C7 mở, Nguyễn Chí Hoàng mới gom global composition, migration additive
  của các module, worker registration, API/router mounting và CI/PostgreSQL gate
  cuối; không sửa ngược implementation thuộc owner C2–C6 nếu không có lỗi tích
  hợp được chứng minh.
