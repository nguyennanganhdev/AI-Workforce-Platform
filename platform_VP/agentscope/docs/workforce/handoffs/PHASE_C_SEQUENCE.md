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
- C1 của Nguyễn Chí Hoàng: đã merge trong baseline
  `dev_TeamHoang@a4c2fddac720bb155efaa01eb91266b95f7b7181`.
- C2 của Nguyễn Phương Đông, do Nguyễn Chí Hoàng thực hiện thay: đã triển khai
  SQL protocol repository/provider, exact pinned resolver và kiểm tra tích hợp
  Registry → Execution adapter trong working tree hiện tại; đang chờ review và
  merge lên nhánh chung.
- Hai lane C3 chưa bắt đầu từ working tree C2 chưa merge. Sau khi commit C2 có
  trên `develop2`, Bùi Hữu Nghĩa và Phan Hoàng Dũng pull đúng commit đó rồi mới
  triển khai song song.

## Quy tắc tiếp tục

Mỗi owner pull baseline chung, đọc file này, kế hoạch tổng và `STATUS.md` của
mình. Chỉ bắt đầu khi bước ngay trước đã có commit trên nhánh chung. C3 có hai
lane chạy song song sau C2; các bước còn lại chạy tuần tự. Mỗi PR cập nhật
`STATUS.md`, nêu commit đầu vào, exports đã dùng, test, phần giả/live và request
tích hợp còn mở. Không sửa lại migration đã merge; gửi schema additive cho C7.
