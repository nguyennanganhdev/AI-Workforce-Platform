# Demo API bằng database V3 với dữ liệu giả

API dùng PostgreSQL V3 thật; cư dân, BQL, nhân viên, ticket và hóa đơn là dữ liệu tổng hợp phục vụ demo. Ghi bằng API được lưu trong database và giữ lại khi restart FastAPI.

## Khởi động

Từ thư mục gốc dự án, mở PowerShell:

```powershell
python -m venv ./services/vinhomes-api/.venv
& ./services/vinhomes-api/.venv/Scripts/python.exe -m pip install -e ./services/vinhomes-api
& ./services/vinhomes-api/scripts/setup_demo_database.ps1
& ./services/vinhomes-api/scripts/start_demo.ps1
```

Script setup tạo PostgreSQL Docker riêng trên `127.0.0.1:5544`, áp dụng migration của gói (`python -m vinhomes_api.database migrate`) và nạp dữ liệu mẫu. Cần Docker Linux engine hoạt động.

Thông tin kết nối được sinh trong `.local-v3-faker/*.env`, đã bỏ qua trong Git. Không cần gửi mật khẩu qua chat. Volume Docker giữ dữ liệu; chạy setup lại chỉ bổ sung fixture còn thiếu, không xóa trạng thái xử lý ticket. Không chạy `docker compose down -v` nếu muốn giữ dữ liệu.

## Swagger

- Swagger: **http://localhost:8000/docs**.
- `/health` phải trả `schema: v3`, `dataMode: faker-database`.
- `/ready` phải trả `status: ready`; lỗi 503 nghĩa database chưa sẵn sàng, API không tự chuyển về RAM.
- Chọn header `X-Demo-Actor`: `resident`, `management`, `technical`, `security`, `admin`. Vai trò ánh xạ đến user fixture; quyền và scope vẫn truy vấn từ database. Cách chọn này chỉ bật trên loopback và tenant demo.
- `/demo/fixtures` trả UUID thực tế trong database, danh mục và căn hộ của nhân vật đang chọn.

Giao diện cư dân và nhân viên gọi API qua proxy `/api/business` (xem [chạy Resident / Operations](../resident-web/07-connected-runtime.md)).

## Dữ liệu seed

| Dữ liệu | ID |
| --- | --- |
| Tenant | `11111111-1111-5111-a111-111111111111` |
| Domain | `22222222-2222-5222-a222-222222222222` |
| Tòa | `77777777-7777-5777-a777-777777777777` |
| BQL | `88888888-8888-5888-a888-888888888888` |
| Category kỹ thuật | `33333333-3333-5333-a333-333333333333` |
| Category an ninh | `33333333-3333-5333-a333-333333333334` |
| Nhân viên kỹ thuật | `eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee1` |
| Nhân viên an ninh | `eeeeeeee-eeee-5eee-aeee-eeeeeeeeeee2` |
| Scope tòa | `99999999-9999-5999-a999-999999999999` |
| Room BQL | `management-room` |

Seed có 20 căn hộ/cư dân, 21 ticket mẫu, 20 hóa đơn `issued` và dòng hóa đơn, membership/quyền, ca trực, chuyên môn, coverage BQL, policy triage, storage local và agent mẫu. Căn hộ cư dân chính lấy tại `GET /demo/fixtures` → `myUnits`.

## Luồng tạo ticket → hoàn tất

1. `resident`: `POST /resident/chats` với `{"title":"Rò nước demo"}`.
2. Gửi message với `text`, `client_message_id`. Phản hồi Reception mẫu cũng được ghi vào bảng `messages`; gửi lại cùng khóa không tạo trùng.
3. `POST /resident/chats/{channel_id}/tickets`: nhập UUID từ fixture cho `domain_id`, `building_id`, `unit_id`, `category_id`; thêm `title`, `description`, `contact_name`, `contact_phone`, `request_kind: incident`.
4. `management`: nhận ticket qua `/tickets/{ticket_id}/routing/ack`. Lấy chi tiết ticket để đọc `version` mới.
5. Tạo work order qua `/tickets/{ticket_id}/work-orders` với `category_id`, `required_specialty_id` (UUID category kỹ thuật), `description`, `ticket_version`.
6. Tra `/staff/available?managementUnitId=...&categoryId=...`. Phân công `/work-orders/{work_order_id}/assignments` với `staff_id`, `offer_expires_at` (ISO UTC tương lai), `work_order_version` lấy từ GET gần nhất.
7. `technical`: dùng **assignment ID** từ bước 6 gọi `/assignments/{assignment_id}/response`, body `{"status":"accepted","eta_at":"ISO UTC tương lai"}`. Từ chối dùng `status: rejected`, `rejection_reason`.
8. Đọc `workOrder.version` qua GET; chuyển lần lượt `accepted → en_route → arrived → in_progress` qua PATCH status, mỗi bước có `version`, `status`, `note`. Luôn dùng version mới trả về.
9. Nếu khóa nước: đề xuất với `reason`, `affected_scope_id`, `planned_start`, `planned_end`. BQL duyệt `/approvals/{id}/decision` với `status: approved`, `note`; sau đó `/notify`, kỹ thuật `/start`, `/restore`.
10. Upload ảnh `/tickets/{ticket_id}/files` bằng raw bytes, query `filename`, `mimeType`, `purpose`. Gắn bằng chứng qua `/tickets/{ticket_id}/evidence` với `file_id`, `work_order_id`, `assignment_id`, `purpose: after`.
11. Kỹ thuật chuyển work order sang `completed`: API yêu cầu bằng chứng và nước đã khôi phục; tạo `work_approvals.customer_completion`, ticket chuyển `resolved`.
12. Cư dân lấy `/resident/approvals`, quyết định bằng `approved`, `note`. Đồng ý chuyển ticket `closed`; từ chối đưa ticket/work order về `in_progress`.

## Báo cáo và room

- Báo cáo yêu cầu `buildingId`, `fromDate`, `toDate`; doanh thu thêm `categoryId`. Dùng `/reports/issued-revenue` hoặc `.docx`, `/reports/incident-frequency` hoặc `.docx`. Giá trị dựa trên hóa đơn đã seed trong database; chưa tự phát hành hóa đơn cho mọi việc mới.
- V3 còn có triage, QC, vệ sinh, nhà thầu, ngân sách, checkpoint/sự cố/bàn giao an ninh. Xem contract trong Swagger; dữ liệu các nhóm chưa seed sẽ rỗng đến khi tạo bằng API.

## Phạm vi hiện tại

Chế độ RAM cũ không còn được chọn bởi `main.py`. Demo và chế độ kết nối dữ liệu thật dùng cùng các router/schema V3; khác nguồn dữ liệu và cách chọn user cục bộ. Mặc định khi tắt demo, danh tính vẫn xác thực qua Hono hoặc user phát triển được cấu hình.

Các chức năng trước chỉ có trong RAM nhưng chưa có router V3 tương ứng không tự được chuyển thành API database: camera/contact ngoài, chuỗi cảnh báo/ACK, phê duyệt điều động/hủy an ninh, quản trị account trên FastAPI, tạo agent trong room, đề xuất memory. Chúng cần nối vào schema/chức năng sở hữu tương ứng; `work_approvals.kind` hiện chưa có loại điều động/hủy. Không trả dữ liệu RAM cho các route đó trong chế độ V3.
