# Trình tự Phase D và trạng thái bàn giao

Cập nhật: **2026-10-12**. Đây là tài liệu điều phối nội bộ của team platform,
không phải contract gửi đối tác.

```text
D0 — Baseline develop2 đã có đủ output C1–C6; E2E C6 pass
  ↓
D1 — Nguyễn Chí Hoàng: fault harness / worker restart / proxy SSE /
     metric convention / test environment
  ↓
D2 ─┬─ Nguyễn Phương Đông: protocol drift / disable / ordering / pinned snapshot
    └─ Phan Huy Hoàng: SSE reconnect / replay / workflow sleep-wakeup /
       close race / hai ticket isolation
  ↓
D3 — Chỉ mở sau khi D2 được review và merge
```

## Trạng thái hiện tại

- Baseline đầu vào: `develop2@5e66ea0` (merge PR #67, đủ output C1–C6).
- C7, D1 và cả hai lane D2 đã được Nguyễn Chí Hoàng triển khai thay trong
  working tree hiện tại; **chưa commit/push/merge**.
- D0 đã được kiểm chứng bằng lát cắt C6: **11/11 pass**.
- Hai lane D2 không phụ thuộc output của nhau, nhưng đều phụ thuộc C7/D1 trong
  cùng PR này và phải được review cùng migration `0010_workforce_runtime`.
- D3 chưa được mở trong lượt này.

## Gate merge C7/D0–D2

1. Alembic có đúng một head `0010_workforce_runtime`; upgrade/downgrade/upgrade
   phải pass trên SQLite và CI PostgreSQL.
2. Composition phải dùng đúng `foundation.uows`, mount đủ workflow/execution
   router và đăng ký đủ bốn job type: provider event, operation reconcile,
   workflow continuation, lifecycle evaluation.
3. Worker phải tự khởi động lại sau lỗi repository/transport; durable DB và
   lease/fencing vẫn là nguồn chuẩn, không retry side effect mù.
4. SSE phải hỗ trợ `Last-Event-ID`, replay từ DB và header chống proxy buffering.
5. Protocol bị revise/disable không được làm đổi normalizer của operation đã pin.
6. Sleep/wakeup, close race và hai ticket cùng user phải tiếp tục pass các suite
   Orchestration/C6 hiện có.

CI tương ứng nằm tại `.github/workflows/workforce-phase-d.yml`. CI tách các
owner suite thành các lệnh pytest riêng để tránh trùng tên module test cũ.
