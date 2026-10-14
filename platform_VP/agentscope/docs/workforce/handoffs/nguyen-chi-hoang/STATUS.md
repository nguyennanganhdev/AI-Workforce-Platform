# Trạng thái — Nguyễn Chí Hoàng

## Cập nhật mới nhất — D6/D7 thay toàn đội — 2026-10-12

Nguyễn Chí Hoàng đã triển khai phần code/tài liệu còn lại của D5–D7 trên working
tree sau `dev_TeamHoang@c588517`: full E2E factory, contract
`TICKET_ALREADY_BOUND`, shared provider metrics, proxy/alert/runbook,
backup-restore CI, frontend/browser gate và JUnit Release Candidate report.
Chi tiết: [PHASE_D_D6_D7.md](PHASE_D_D6_D7.md) và
[../PHASE_D_SEQUENCE.md](../PHASE_D_SEQUENCE.md).

Validation local cuối: **647 passed, 22 skipped, 313 subtests passed**, không có
failure/error; frontend lint/build pass. D7 local report trả fail đúng thiết kế
vì 22 skip hạ tầng và sandbox `NOT_VERIFIED`. CI mới cung cấp PostgreSQL 17 và
Chromium, đồng thời fail nếu thiếu report hoặc còn skip.

Trạng thái Git chính xác: **chưa tự xác nhận merge vào `develop2` và chưa có kết
quả GitHub CI của commit mới**. Sandbox đối tác chưa được cấp nên evidence phải
ghi `NOT_VERIFIED`; không tuyên bố production pass.

## Lịch sử — tích hợp cuối Phase D/D4 — 2026-10-12

Baseline đầu vào là `develop2@35cec29`: C7/D1/D2, D3 và D4 đã merge. Nguyễn
Chí Hoàng đã ghép xong phần production còn thiếu sau PR #73 gồm migration
`0011_workforce_releases`, manager API/auth, transactional release validator,
published catalog/Leader bootstrap, exact workflow/checkpoint usage reader và CI
D4/PostgreSQL. Trạng thái bàn giao: **đã commit và đã merge vào `develop2`**
qua commit/PR chứa chính cập nhật status này. Xem
[PHASE_D_D4_INTEGRATION.md](PHASE_D_D4_INTEGRATION.md) và
[../PHASE_D_SEQUENCE.md](../PHASE_D_SEQUENCE.md).

Các đoạn trạng thái cũ bên dưới được giữ làm lịch sử theo từng mốc; không được
dùng thay cho cập nhật mới nhất này.

Tên thành viên: Nguyễn Chí Hoàng. Baseline chung hiện tại:
`develop2@5e66ea0`.

**Snapshot lịch sử trước PR C7/D1/D2:** C1–C6 đã merge; C7/D1 và hai lane D2
đang được triển khai tại thời điểm ghi. Các phần này sau đó đã commit và merge
vào `develop2@278ea4a`. Chi tiết tại
[PHASE_C_C7_VA_PHASE_D_D1.md](PHASE_C_C7_VA_PHASE_D_D1.md) và trạng thái cuối
tại [../PHASE_D_SEQUENCE.md](../PHASE_D_SEQUENCE.md).

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

Live verification còn thiếu sau C7/D1: CI PostgreSQL của PR, Redis multi-process,
provider sandbox thật và browser E2E. FastAPI router mounting, SQL composition,
worker registration, SSE reconnect/replay và C6 runtime slice đã có test cục bộ.

Snapshot trình tự tại thời điểm đó: C1–C6 đã merge; C7/D1 và hai lane D2 đang
chờ merge. Mốc này đã được đóng tại `develop2@278ea4a`; xem cập nhật mới nhất ở
đầu file.

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

## Lịch sử điều phối sau khi C5 merge — 2026-10-11

- C5 đã merge qua PR #64 tại
  `830cdacd56f868d509d208b91b9a6bc29d70c935`.
- Điều kiện lịch sử là C7 chỉ mở sau C6. Điều kiện này đã được thỏa khi PR #67
  merge vào `develop2@5e66ea0`.
- Kết quả C7/D1 hiện tại được ghi riêng tại
  [PHASE_C_C7_VA_PHASE_D_D1.md](PHASE_C_C7_VA_PHASE_D_D1.md).
