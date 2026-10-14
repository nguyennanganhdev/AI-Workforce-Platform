# Bàn giao Phase D/D2 — Phan Huy Hoàng

Người thực hiện thay: **Nguyễn Chí Hoàng**. Baseline:
`develop2@5e66ea0`. Trạng thái: đã code/test trong working tree, chưa merge.

## Phạm vi hoàn thành

- SSE reconnect dùng `Last-Event-ID` hoặc query cursor; hai nguồn cursor khác
  nhau trả `422` trước khi mở stream.
- Replay vẫn đọc DB trước khi chờ signal; signal không trở thành nguồn dữ liệu.
- Header SSE tương thích reverse proxy và metric connection/replay được phát qua
  sink inject được.
- Regression Phase B/C giữ nguyên semantics: workflow external-tracking ngủ
  không tiêu thêm model turn; external event đánh thức bằng durable trigger;
  close race fence kết quả đến muộn; hai ticket/hộp chat cùng user giữ riêng
  workflow/group/session/cursor.

Kết quả: **14/14 async workflow**, **8/8 Orchestration C4 + D2**, và **11/11 C6
E2E** pass. Không có outbound webhook sender; SSE vẫn là kênh backend khách hàng
chủ động mở tới platform.
