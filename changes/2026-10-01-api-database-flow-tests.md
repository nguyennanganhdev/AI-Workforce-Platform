# Kiểm tra luồng API bằng PostgreSQL

- Ngày: 2026-10-01
- Yêu cầu: chạy test luồng API, bắt buộc kết nối database thật.

## Thay đổi
- Bổ sung migration V3 0008 cho command receipt còn thiếu, có UUID mặc định và tenant RLS.
- Sửa triage_decision_id tùy chọn và định kiểu cursor null ở hai truy vấn schema_v2.
- Upgrade seed bổ sung Supervisor version khi chưa có, giữ dữ liệu workflow.
- Thêm test PostgreSQL cho luồng Reception/idempotency, 24 API đọc, hóa đơn/thanh toán giả, alert ACK, số đo và export; cần test mới vì suite cũ chưa kiểm tra các luồng này và đã phát hiện lỗi thực.

## File/module chính
- `server/drizzle/0008_reception_command_receipt.sql`, `server/drizzle/meta/_journal.json`.
- `services/vinhomes-api/src/vinhomes_api/v3_reception_supervisor.py`.
- `services/vinhomes-api/scripts/seed_v3_remaining.sql`.
- `services/vinhomes-api/tests/test_v3_agent_database.py`.
- `my-docs/BAO_CAO_TEST_LUONG_API_DATABASE.md`.

## Quyết định & giả định
- Dùng PostgreSQL Docker cục bộ, migration/seed trên database test ngẫu nhiên với role bị giới hạn; không reset database demo.
- Dữ liệu nghiệp vụ mock được ghi/đọc database thật. API không chạy AI/runtime.

## Xác minh
- `python -m pytest tests -q --tb=short`: 39 passed; 36 case PostgreSQL và 3 case demo trong bộ nhớ.
- Ruff test mới: đạt. Supervisor module có lint tồn tại trước ở phần không sửa; không refactor ngoài phạm vi.
- Upgrade database demo thành công; restart service cổng 8000; HTTP health/ready/context/report filters đều 200.
- Diff check các file tracked đã sửa: đạt.

## Rủi ro / việc còn lại
- Chưa kiểm tra mọi endpoint/nhánh; phạm vi và các nhóm còn thiếu ghi rõ trong báo cáo.
- Chưa push các sửa lỗi/test mới.
