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
FINAL — Nguyễn Chí Hoàng: migration + manager API/auth + transactional
        validator + catalog/bootstrap + usage reader + CI toàn Phase D
```

## Trạng thái hiện tại

- Baseline hiện tại: `develop2@35cec29`, đã merge D4 qua PR #73.
- C7/D1/D2 implementation `bbd6d9a` đã merge vào `develop2@278ea4a`; D3
  Execution qua PR #70 (`a5366c8`) và D3 Builder qua PR #71 (`58c00f2`) đều đã
  merge.
- D4 Lifecycle đã merge qua PR #73; output không còn nằm riêng trong working
  tree của Phó Tiến Anh.
- Lượt tích hợp cuối của Nguyễn Chí Hoàng đã hoàn thành, đã commit và đã merge
  vào `develop2` qua commit/PR chứa chính tài liệu này: migration
  `0011_workforce_releases`, manager release API, server-side Scope/context,
  transactional validator, published Leader bootstrap, exact usage reader và
  gate CI D4/PostgreSQL.
- Kế hoạch chính thức kết thúc ở D4 + lượt tích hợp cuối. Các nhãn D5/D6/D7 từng
  xuất hiện trong integration request cũ không phải phase mới của kế hoạch.

## Gate đóng Phase D

1. Alembic có đúng một head `0011_workforce_releases`; migration phải
   upgrade/downgrade/upgrade được và không dùng runtime `create_all`.
2. Release endpoint chỉ nhận command/selections; Scope manager và
   `ReleaseContext` phải được resolve phía server, không tin payload client.
3. Tool, policy và current protocol head phải được đọc qua cùng canonical UOW
   của publish; protocol head được khóa khi revalidate.
4. Workflow chỉ bootstrap từ current published/enabled/non-archived leader
   version; runtime vẫn dùng exact version/protocol pin trong checkpoint.
5. Retention reader phải tìm exact workflow/checkpoint references theo đủ Scope;
   version đang được tham chiếu không được suy đoán theo tuổi record.
6. CI phải chạy C7/D1/D2, D3 Builder, D4 Lifecycle và PostgreSQL gates. Skip do
   thiếu DSN không được xem là pass.
7. Các regression SSE replay, worker restart, protocol drift, sleep/wakeup,
   close race, hai ticket isolation, publish/rollback/archive phải tiếp tục xanh.

CI tương ứng nằm tại `.github/workflows/workforce-phase-d.yml`. Chi tiết lượt
tích hợp cuối nằm tại
[PHASE_D_D4_INTEGRATION.md](nguyen-chi-hoang/PHASE_D_D4_INTEGRATION.md).
