# Trình tự Phase C và trạng thái bàn giao

Cập nhật: **2026-10-11**. File này là bảng điều phối nội bộ, không phải contract
gửi đối tác và không thay đổi `KE_HOACH_TRIEN_KHAI.md`.

```text
C0 — Merge đủ Phase B và chốt một baseline chung
  ↓
C1 — Nguyễn Chí Hoàng: DB/UOW/Auth/Job/Signal/Bootstrap nền
  ↓
C2 — Nguyễn Phương Đông: Registry protocol thật ↔ Execution
  ↓
C3 ─┬─ Bùi Hữu Nghĩa: Protocol validation ↔ Builder
    └─ Phan Hoàng Dũng: Provider ingress ↔ Operation ↔ Protocol
  ↓
C4 — Phan Huy Hoàng: POST → Workflow → Event → Leader → Event log/SSE
  ↓
C5 — Phó Tiến Anh: Eval đa lượt ↔ runtime thật
  ↓
C6 — Phan Hoàng Dũng: E2E toàn lát cắt
  ↓
C7 — Nguyễn Chí Hoàng: composition/migration/CI cuối
```

## Trạng thái hiện tại

- Phase A: 6/6 đã hoàn thành và merge.
- Phase B: 6/6 đã hoàn thành; C0 đã chốt trong baseline chung.
- C1, C2 và cả hai lane C3 đã merge vào baseline chung
  `develop2@7bfdc6097fbbd8a5cfeddaf8f84f60b2ddf798c3`.
- C4 của Phan Huy Hoàng đang nằm trong working tree kế tiếp trên đúng baseline
  đó; code và kiểm thử đã hoàn tất, chờ review/commit/merge.
- C5 chỉ bắt đầu sau khi commit C4 xuất hiện trên `develop2`; C6 và C7 tiếp tục
  theo đúng thứ tự của sơ đồ.

## Quy tắc tiếp tục

Mỗi owner pull baseline chung, đọc file này, kế hoạch tổng và `STATUS.md` của
mình. Chỉ bắt đầu khi bước ngay trước đã có commit trên nhánh chung. C3 có hai
lane chạy song song sau C2; các bước còn lại chạy tuần tự. Mỗi PR cập nhật
`STATUS.md`, nêu commit đầu vào, exports đã dùng, test, phần giả/live và request
tích hợp còn mở. Không sửa lại migration đã merge; gửi schema additive cho C7.

## Cập nhật mới nhất — C4 ngày 2026-10-11

- Baseline đầu vào C4: `develop2@7bfdc6097fbbd8a5cfeddaf8f84f60b2ddf798c3`;
  C1, C2 và cả hai lane C3 đã có trên nhánh chung.
- C4 của Phan Huy Hoàng đã hoàn thành code và test trong working tree; chờ commit,
  review và merge vào `develop2`.
- Sau khi commit C4 xuất hiện trên `develop2`, Phó Tiến Anh pull commit đó và bắt
  đầu C5. C6 và C7 vẫn chưa được bắt đầu trước khi các gate ngay trước hoàn tất.
- Handoff authoritative của C4:
  `phan-huy-hoang/PHASE_C_C4.md` và
  `phan-huy-hoang/INTEGRATION_REQUEST_PHH_C4.md`.
