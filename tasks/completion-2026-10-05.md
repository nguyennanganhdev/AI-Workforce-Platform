# Hoàn thiện sáu khoảng trống — 05/10/2026

Nhánh `dev_teamChien_HuyDo`, điểm đầu `04a5131`. Người dùng cho phép Docker local trước, bật CI/merge #31 khi checks đạt,
Playwright headless; giữ MCP cho phiên khác. Không commit credentials.

- [ ] 1. Model/UI/MCP: UI nghiệp vụ đạt; model mới chưa đạt. Reception key 401, Factory key 429 hết credit;
  chưa tìm khóa Gemini/DeepSeek/Claude. Đã hỏi file/key hợp lệ, chờ người dùng.
- [x] 2. Docker local/restore/monitor/CI: restore hai DB/8 object, alert/recovery đạt; CI đạt và PR #31 đã gộp
  vào `develop` tại `d5d5b2e`. Domain/chứng chỉ public hoãn; chưa kiểm webhook thật hay khởi động app từ dữ liệu restore.
- [x] 3. Admin tạo đơn vị UI: transaction/RBAC/tenant/input/overlap, phòng/Supervisor; Playwright đạt.
- [ ] 4. Preset báo cáo: đóng gói/cài nháp tự động/idempotent; publish qua real evaluation còn chờ key/quota.
- [x] 5. Một đăng nhập: account host cùng identity, role riêng, không fallback dev-admin, logout cả hai;
  UI kết nối theo user. OAuth vendor/MCP caller cá nhân chưa nghiệm thu.
- [x] 6. Upload browser → MinIO: actual POST 204, complete/ticket; replay/hash/size/image/isolation đạt.

84 API tests, 175 TS tests Linux, 17 resident tests; typecheck bốn package đạt. 7 API opt-in test bỏ qua không thay bằng chứng live.
[Biên bản/giới hạn](../docs/teams/chien/COMPLETION_ACCEPTANCE_2026-10-05.md).
[Nhánh remote](../docs/teams/chien/BRANCH_AUDIT_2026-10-05.md).
