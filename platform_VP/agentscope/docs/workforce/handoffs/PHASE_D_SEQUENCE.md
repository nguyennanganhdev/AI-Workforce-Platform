# Trình tự Phase D và trạng thái bàn giao

Cập nhật: **2026-10-12**. Đây là tài liệu điều phối nội bộ của team platform,
không phải contract gửi đối tác.

```text
D0 — Chốt baseline Phase C và E2E C6
  ↓
D1 — Nguyễn Chí Hoàng: fault harness / worker restart / proxy SSE /
     metrics convention / test environment
  ↓
D2 ─┬─ Nguyễn Phương Đông: protocol drift / disable / ordering / pinned snapshot
    └─ Phan Huy Hoàng: SSE reconnect / replay / workflow sleep-wakeup /
       close race / hai ticket isolation
  ↓
D3 ─┬─ Phan Hoàng Dũng: fault/recovery E2E
    └─ Bùi Hữu Nghĩa: Builder regressions
  ↓
D4 — Phó Tiến Anh: publish/protocol pin / long-wait / stale evaluation /
     archive-rollback regressions
  ↓
D5 — Phan Hoàng Dũng: E2E chịu lỗi toàn lát cắt + sandbox nếu được cấp
  ↓
D6 — Nguyễn Chí Hoàng: composition cuối / migration smoke / CI / metrics /
     alert / runbook / backup-restore / release checklist
  ↓
D7 — Chốt Phase D: toàn bộ test chạy trên cùng commit develop2 → Mock E2E
     report → sandbox evidence hoặc ghi rõ chưa kiểm tra → Release Candidate
```

## Trạng thái hiện tại

- Baseline đã merge: `develop2@35cec29`, gồm C7/D1/D2, D3 và D4 qua PR #73.
- Commit `c588517` trên `dev_TeamHoang` chứa lượt integration sau D4 nhưng tại
  thời điểm cập nhật chưa có bằng chứng đã merge vào `develop2`.
- Phần code/tài liệu D5/D6 và tự động hóa D7 đã hoàn thành trong working tree
  kế tiếp `c588517`; không còn chờ output thành viên khác. Chỉ còn merge và
  chạy workflow trên chính merge commit để chốt Release Candidate.
- Sandbox thật chưa được cấp endpoint/credential/kịch bản. D7 phải ghi
  `NOT_VERIFIED`, không được đổi thành production pass từ kết quả mock.

## Gate D5

1. Customer POST → Leader/group → tool/external operation → Provider Event →
   workflow resume → event log/SSE → customer close chạy qua SQL/ASGI/worker.
2. Full-platform cases read-only, hai ticket và parallel start chạy bằng factory
   mặc định; không skip vì thiếu `WORKFORCE_E2E_FACTORY`.
3. Duplicate, out-of-order, crash, unknown recovery, route revoke, reconnect,
   close race và scope isolation tiếp tục pass.
4. PostgreSQL concurrency/fencing chạy với DSN thật trong CI, không dùng SQLite
   để thay bằng chứng race.

## Gate D6

1. Alembic có đúng một head `0011_workforce_releases`; upgrade pass.
2. CI backup bằng `pg_dump`, restore sang database tách biệt và xác nhận đúng
   Alembic head.
3. Proxy SSE, metric names, alert rules, restart/reconcile/key-rotation/restore
   runbook và release checklist tồn tại dưới `deploy/workforce/event_delivery/`.
4. Provider event accepted/duplicate/applied/ignored/quarantined dùng chung
   `MetricSink` với worker và SSE.
5. Frontend lint/build và Builder browser regression là gate bắt buộc.

## Gate D7

1. Foundation, Registry, Builder, Lifecycle, Orchestration, Execution,
   Integrations và E2E tạo JUnit report trên cùng `github.sha`.
2. Báo cáo D7 fail nếu có failure, error hoặc **bất kỳ skip nào**.
3. Workflow upload `PHASE_D_RELEASE_CANDIDATE.md` cùng toàn bộ JUnit evidence.
4. Chỉ khi PR merge vào `develop2` và workflow xanh mới đánh dấu Release
   Candidate. Sandbox thiếu vẫn phải ghi `NOT_VERIFIED` và còn chặn tuyên bố
   production-ready.

## Bằng chứng local của working tree

- Toàn bộ `tests/workforce`: **647 passed, 22 skipped, 313 subtests passed**.
  Không có failure/error; 22 skip là 12 browser và 10 PostgreSQL do máy local
  không có Playwright/DSN/Docker daemon.
- Phase A sau khi khai báo dependency RFC3339: **242 passed, 97 subtests pass**.
- Frontend lint/build: pass; lint còn 21 warning có sẵn, không có error.
- D7 local report cố ý trả `FAIL` với **982 tests, 22 skipped** và sandbox
  `NOT_VERIFIED`. CI cung cấp PostgreSQL 17 + Chromium và không cho phép skip.

CI chuẩn nằm tại `.github/workflows/workforce-phase-d.yml`. Runbook và checklist
nằm tại `deploy/workforce/event_delivery/`.
