# Integration request — D3 lượt 1 → D4 / gate môi trường

Cập nhật **12/10/2026**. Người gửi: **Phan Hoàng Dũng**.
D3 SQL/mock local đã pass; không yêu cầu sửa lại output D1/D2.
Chi tiết: [PHASE_D_D3.md](PHASE_D_D3.md).

## PHD-D3-01 — Đưa D3 và PostgreSQL gates vào CI

**Owner: Nguyễn Chí Hoàng**, file chung `.github/workflows/workforce-phase-d.yml`.

CI hiện chỉ gọi C7/D1/D2 và C6 SQLite, chưa gọi các files D3 mới.
Đề nghị thêm các lệnh sau với `WORKFORCE_TEST_POSTGRES_URL` trỏ DB test riêng;
chạy từ `platform_VP/agentscope`, không dùng credential production:

```bash
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols \
python -m pytest tests/workforce/execution --import-mode=importlib -q -ra

PYTHONPATH=src:tests/workforce/fixtures \
python -m pytest \
  tests/workforce/e2e/async_tickets/test_phase_d_d3.py \
  tests/workforce/e2e/async_tickets/test_phase_d_d3_postgres.py \
  tests/workforce/e2e/async_tickets/test_phase_c_c6.py \
  tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py \
  --import-mode=importlib -q -ra
```

Hai files D3 trùng basename ở hai owner test roots nên dùng `--import-mode=importlib`.
PostgreSQL tests tạo schema ngẫu nhiên, cleanup đúng schema đó; migration gate
của C7 vẫn chạy riêng. D3 không đổi migration hoặc CI ngoài quyền sở hữu.

Điều kiện đóng: CI PostgreSQL thực sự chạy và pass cả ba crash boundaries D3
cùng duplicate/concurrency C6/Execution. Local skip chưa phải bằng chứng pass.

## PHD-D3-02 — Output cho D4 của Phó Tiến Anh

**Owner nhận: Phó Tiến Anh**, phối hợp Registry/Builder/Orchestration theo D4.

- Fixture `D3CaseDriver` nối approval continuation/query job adapters C7.
  `SqlTicketSliceSupport` dùng cùng customer HTTP/consent flow với C6.
- D3 chứng minh protocol pin vẫn giữ qua disable, delta gap query và worker
  restart; không đưa current protocol hash thay exact pin vào evidence/eval.
- Timeout sau write tạo creation unknown; replay giữ một provider create.
  Event/query đã xác minh cập nhật operation fact; call result ban đầu không
  bị giả thành một create mới thành công. Không dùng unknown làm lý do retry write.
- Crash sau commit không phát thêm public event/continuation/evidence; history
  và SSE replay vẫn đọc dữ liệu đã commit, old worker fence không ghi đè.
- Các case publish pin, long wait, stale evaluation, archive/rollback tiếp tục
  thực hiện trong Lifecycle; không import scripted model/fake MCP vào production.

D4 không cần sửa lại các assertions C6/D3 để làm consumer pass. Khi phát hiện
thiếu seam Execution, bàn giao signature/repro về folder PHD.

## Điều kiện recovery vận hành và live verification

Quarantine recovery đã kiểm chứng bằng JobPort dispatch tường minh sau khi job
binding hoặc predecessor/query fact được xác minh. Duplicate HTTP không tạo
recovery job mới. Không suy diễn đã có periodic quarantine scanner hoặc TTL
cleanup deployment; nếu rollout cần chúng, composition/runbook phải chỉ rõ
ai enqueue recovery, quyền provider namespace, giới hạn retry/TTL và audit.

Chưa có dedicated PostgreSQL DSN hoặc sandbox provider được cấp trong lượt này.
Gate MD/live còn cần endpoint, credentials, provider protocol/query support và
kịch bản sandbox được cho phép. Không mở rộng sang dịch vụ thật trong D3 lượt 1.
