# Phase D / D5 — Full-platform fault E2E

Người thực hiện thay owner: **Nguyễn Chí Hoàng**. Owner nghiệp vụ gốc:
**Phan Hoàng Dũng**. Baseline: `dev_TeamHoang@c588517`; chưa ghi là đã merge
vào `develop2` cho tới khi GitHub xác nhận.

## Output

- `tests/workforce/fixtures/release_candidate_factory.py` ghép SQL repositories,
  Customer API, immutable ticket binding, durable worker và workflow
  continuation thật. Chỉ model/provider là deterministic test doubles.
- `test_full_platform.py` dùng factory này mặc định; deployment/sandbox vẫn có
  thể override bằng `WORKFORCE_E2E_FACTORY=module:function`.
- Case read-only auto-close, hai ticket độc lập và parallel start không còn skip.
- D5 phát hiện và sửa contract: start mới vào ticket đã bound trả
  `TICKET_ALREADY_BOUND`, không còn mã chung `WORKFLOW_CONFLICT`.
- CI chạy toàn bộ `tests/workforce/e2e`, gồm C6 full lifecycle, D3
  crash/recovery và PostgreSQL gates.

## Ranh giới bằng chứng

Factory D5 là **mock E2E**, không phải sandbox đối tác. SQL/HTTP/worker/workflow
là code platform; model, MCP/provider và dữ liệu là fixture. Sandbox chỉ được
đánh dấu pass nếu `WORKFORCE_SANDBOX_EVIDENCE` dẫn tới bằng chứng ngoài mock.

## Kết quả local hiện có

- `test_full_platform.py` + C4 regressions: **9 passed**.
- Toàn bộ `tests/workforce` sau D5/D6: **647 passed, 22 skipped, 313 subtests
  passed**, không có failure/error.
- 22 local skip gồm 12 browser và 10 PostgreSQL vì không có Playwright,
  dedicated DSN hoặc Docker daemon. Workflow CI cung cấp PostgreSQL 17 +
  Chromium; D7 không chấp nhận bất kỳ skip nào.
