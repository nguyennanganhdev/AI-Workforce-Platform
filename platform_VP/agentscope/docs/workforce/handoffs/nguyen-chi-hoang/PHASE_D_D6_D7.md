# Phase D / D6–D7 — Vận hành và Release Candidate gate

Baseline: `dev_TeamHoang@c588517`. Phần trong tài liệu này được triển khai trong
working tree kế tiếp commit đó; chưa tự nhận là đã merge hoặc CI xanh.

## D6 đã triển khai

- Composition dùng chung một `MetricSink` cho durable worker, SSE và Provider
  Event; thêm `workforce_provider_events_total{outcome=...}`.
- Provider outcomes: `accepted`, `duplicate`, `applied`, `ignored`,
  `quarantined`.
- `deploy/workforce/event_delivery/proxy.example.conf`: tắt buffering/compress,
  chuyển `Last-Event-ID`, timeout phù hợp stream.
- `alerts.example.yml`: worker restart/failure, provider quarantine và no-progress.
- `RUNBOOK.md`: migration, restore, worker lease/fencing, unknown reconcile,
  quarantine, SSE cursor, key rotation và rollback.
- `RELEASE_CHECKLIST.md`: checklist D5–D7/production boundary.
- CI backup `pg_dump`, restore vào database tách biệt và xác nhận Alembic head.

## D7 đã tự động hóa

- Workflow chạy Foundation, Registry, Builder, Lifecycle, Orchestration,
  Execution, Integrations và E2E thành tám JUnit report trên cùng commit SHA.
- Frontend lint/build và Builder browser tests dùng Vite + Chromium.
- `write_phase_d_report.py` tổng hợp evidence; failure/error/**skip** đều làm
  gate fail.
- Artifact `PHASE_D_RELEASE_CANDIDATE.md` luôn ghi sandbox evidence hoặc
  `NOT_VERIFIED`; mock pass không được đổi thành production pass.

## Điều kiện đóng

1. Commit hiện tại phải merge vào `develop2`.
2. Workflow `Workforce Phase D Gate` trên merge commit phải xanh.
3. Tải artifact và lưu report cùng release candidate.
4. Nếu chưa có sandbox, kết luận chỉ là Release Candidate, không phải
   production-ready.

## Kết quả local trước merge

- `tests/workforce`: **647 passed, 22 skipped, 313 subtests passed** trong
  430.50 giây; không có failure/error.
- 22 skip gồm 12 browser và 10 PostgreSQL vì máy local không có Playwright,
  dedicated DSN hoặc Docker daemon. Đây không phải D7 pass.
- D7 aggregator đọc **982 tests** từ JUnit, ghi `NOT_VERIFIED` và trả exit code
  fail do 22 skip, đúng chính sách không xanh giả.
- Frontend lint/build pass; lint có 21 warning có sẵn và 0 error.
