# Báo cáo kiểm tra luồng API với database

Ngày: 2026-10-01.

## Môi trường và cách chạy

- PostgreSQL thật trong Docker `vinhomes-faker-v3-postgres-1`, cổng 5544.
- Suite integration tạo database `resident_contract_test_<UUID>` riêng, áp dụng toàn bộ migration V3 và bốn file seed, dùng role runtime không có superuser/BYPASSRLS. Database test được xóa sau mỗi lượt; database demo không bị reset.
- FastAPI được gọi bằng TestClient cho phần lớn test. Test adapter cư dân có khởi động HTTP server thật và gọi adapter bằng Bun. Kiểm tra riêng HTTP cổng 8000 sau khi cập nhật database demo.
- Tại thư mục `services/vinhomes-api`, chạy:

```powershell
$env:PYTHONPATH = 'src'
./.venv/Scripts/python.exe -m pytest tests -q --tb=short
```

## Kết quả đã chạy

Suite đạt **39 test**: **36 test dùng PostgreSQL thật**, **3 test demo trong bộ nhớ**. Đây là tổng số test case, không phải số endpoint hoặc độ bao phủ toàn bộ nhánh.

| Nhóm | Kiểm tra và kết quả |
| --- | --- |
| Cư dân và ảnh | Upload ảnh, đọc ảnh, retry, tạo Case, phân trang, timeline, quyền căn hộ, validation, origin, giới hạn dung lượng: đạt trên PostgreSQL. |
| Luồng xử lý hoàn chỉnh | Cư dân tạo yêu cầu → BQL duyệt kế hoạch → cư dân duyệt → tạo work order → mời kỹ thuật viên → nhận việc → en_route/arrived/in_progress → ảnh trước/sau → hoàn tất → QC → công bố kết quả → cư dân xác nhận: đạt trên PostgreSQL. Kiểm tra bản ghi Case/ticket/work order sau luồng. |
| Xác nhận và sửa lại | Retry, concurrent confirm/reopen, version/revision và quyền QC: đạt trên PostgreSQL. |
| Reception | Lấy context đã xác minh → cư dân gửi tin nhắn → tạo draft chưa tạo ticket → bổ sung thông tin → lưu assessment → tìm BQL/Supervisor → handoff tạo ticket/team/message schema_v2 → đăng ký poll → đọc kết quả và trạng thái: đạt trên PostgreSQL. |
| Retry Reception | Execute lại trả cùng ticket, reconcile lấy kết quả đã lưu, đổi payload cùng key trả 409, giả principal/tenant trả 403, lỗi rollback không lưu receipt: đạt trên PostgreSQL. |
| Hóa đơn và tiền mock | Tạo hóa đơn/retry → phát hành → ghi thanh toán tổng hợp 50.000 → retry không trùng → còn phải thu 100.000; chặn thanh toán trước phát hành và vượt số dư: đạt trên PostgreSQL. Không gọi cổng thanh toán. |
| Cảnh báo bảo vệ | Tạo/retry → tạo danh sách người nhận → chặn ACK sai người và chuyển cấp quá sớm → người nhận ACK/retry; trạng thái DB acknowledged: đạt trên PostgreSQL. |
| Dữ liệu kỹ thuật | Lấy tài sản, ghi số đo giả có thời gian/mã nguồn, đọc số đo và lịch sử bảo trì: đạt trên PostgreSQL. |
| Báo cáo | Bộ lọc, hiệu suất, phản hồi, doanh thu, tần suất; tạo export/retry → kiểm tra trạng thái → tải DOCX; cư dân không được tải export của BQL: đạt trên PostgreSQL. |
| Các API đọc | 24 test có tham số cho catalogs/dashboard/identity/tickets/work orders/queue/tasks/approvals/triage/plans/rooms/assets/outages/security alerts/report aggregates/memory/accounts/agent reviews/notifications: đạt trên PostgreSQL. |
| Adapter cư dân | Adapter thực gửi ảnh, tạo/retry, lấy danh sách/chi tiết/ảnh bằng HTTP và đối chiếu database: đạt. |
| Khóa nước và điều động bảo vệ demo | Ba test demo kiểm tra khóa nước/khôi phục/hoàn tất, điều động/cảnh báo và quyền/tài khoản/chống trùng: đạt trong bộ nhớ; không dùng kết quả này để khẳng định luồng khóa nước trên PostgreSQL. |

## Lỗi phát hiện và đã sửa

1. Migration V3 thiếu `vh_command_receipt` trong khi grants và Reception đã dùng bảng: bổ sung migration 0008, UUID mặc định, unique key và tenant RLS.
2. `request.triage_decision_id` khai báo UUID với default null nhưng không nhận null khi truyền tường minh: sửa thành UUID tùy chọn đúng contract.
3. Hai truy vấn đọc message/results không định kiểu parameter cursor null khiến PostgreSQL lỗi: cast timestamp ở điều kiện null.
4. Upgrade database demo không seed Supervisor version mới: bổ sung seed version khi chưa tồn tại, giữ version và workflow đã có.

## Database demo và HTTP cổng 8000

- Đã chạy `scripts/upgrade_demo_database.ps1`, migration và seed/grants thành công.
- Khởi động lại đúng tiến trình `python -m vinhomes_api` cổng 8000 để nạp code sửa.
- `GET /health`: 200, `schema=v3`, `dataMode=faker-database`.
- `GET /ready`: 200, ready.
- `POST /internal/reception/operations/execute`, operation `get_verified_resident_context`, actor cư dân: 200 và một nơi cư trú.
- `GET /reports/filter-options`, actor BQL: 200 và một tòa nhà.
- Không ghi secret hoặc thông tin cá nhân trả về vào báo cáo.

## Giới hạn kiểm tra

- Chưa đạt kiểm tra toàn bộ endpoint và mọi nhánh. Các nhóm ghi khác như yêu cầu cách ly điện/rào chắn/vào căn hộ/nhà thầu, vòng đời team/task/mailbox, duyệt cấu hình agent và memory, hủy/timeout Supervisor, sự cố storage và lỗi đồng thời ở mọi nhóm chưa được chạy đầy đủ trong lượt này.
- Luồng khóa nước đầy đủ mới chạy bằng bộ demo trong bộ nhớ; cần test PostgreSQL riêng trước khi khẳng định luồng đó đạt.
- `process_self_help` trả 501 theo phạm vi hiện tại: chưa tích hợp RAG. Test kiểm tra rollback đúng; không có AI trong API.
- Camera/BMS/payment là nguồn seed/mock trong database, chưa kiểm tra kết nối nhà cung cấp ngoài.
- Có cảnh báo thư viện Starlette/httpx và Pydantic trong suite; không làm test thất bại. Lint module Supervisor còn báo các vấn đề có sẵn ngoài ba dòng logic sửa.
- Các sửa lỗi và test mới đang ở workspace, chưa push trong lượt này.
