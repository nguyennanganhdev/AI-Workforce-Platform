# Workforce integration scripts

Chủ sở hữu: **Nguyễn Chí Hoàng**.

Các script dùng cho gate tích hợp và phát hành:

- `check_phase_d_environment.py`: kiểm tra dependency, PostgreSQL và Alembic
  head trước khi chạy gate Phase D.
- `write_phase_d_report.py`: tổng hợp các JUnit report của cùng một commit,
  fail nếu thiếu report bắt buộc hoặc có failure/error/skip, đồng thời ghi rõ
  bằng chứng sandbox là đã xác minh hay `NOT_VERIFIED`.

Không đặt secret trong tham số lệnh, source hoặc artifact CI. Script báo cáo
chỉ tổng hợp bằng chứng; trạng thái Release Candidate vẫn phải đáp ứng
`deploy/workforce/event_delivery/RELEASE_CHECKLIST.md`.
