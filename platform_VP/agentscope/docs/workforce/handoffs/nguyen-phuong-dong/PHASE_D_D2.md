# Bàn giao Phase D/D2 — Nguyễn Phương Đông

Người thực hiện thay: **Nguyễn Chí Hoàng**. Baseline:
`develop2@5e66ea0`. Trạng thái: đã code/test trong working tree, chưa merge.

## Phạm vi hoàn thành

- Giữ immutable protocol version và current/enabled head tách biệt.
- Thêm acceptance chứng minh khi protocol v2 đổi mapping rồi bị disable:
  call mới bị chặn nhưng operation đang chạy với exact v1 pin vẫn normalize
  theo mapping v1.
- Schema hash giữa v1/v2 khác nhau và resolver không được tự chuyển old pin sang
  current head.
- Regression Registry tiếp tục kiểm tra full Scope isolation, revision CAS,
  forged ref, ordering metadata và provider event context.

Kết quả: **30 pass, 1 PostgreSQL gate skip, 76 subtests pass**. PostgreSQL gate
được bật trong workflow Phase D qua `WORKFORCE_TEST_POSTGRES_URL`.
