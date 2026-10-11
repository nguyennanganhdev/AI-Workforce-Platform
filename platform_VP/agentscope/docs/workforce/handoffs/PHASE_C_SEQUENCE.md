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
- Phase B: 5/6 đã merge vào baseline đang checkout.
- Phase B của Phan Huy Hoàng: đã code/test trong working tree hiện tại, chưa có
  commit/merge trên `develop2` tại thời điểm ghi file.
- C1 của Nguyễn Chí Hoàng: đã code/test trong cùng working tree, chờ review và
  merge. C2 chưa được mở chính thức cho tới khi C0+C1 có commit chung.

## Quy tắc tiếp tục

Mỗi owner pull baseline chung, đọc file này, kế hoạch tổng và `STATUS.md` của
mình. Chỉ bắt đầu khi bước ngay trước đã có commit trên nhánh chung. C3 có hai
lane chạy song song sau C2; các bước còn lại chạy tuần tự. Mỗi PR cập nhật
`STATUS.md`, nêu commit đầu vào, exports đã dùng, test, phần giả/live và request
tích hợp còn mở. Không sửa lại migration đã merge; gửi schema additive cho C7.
