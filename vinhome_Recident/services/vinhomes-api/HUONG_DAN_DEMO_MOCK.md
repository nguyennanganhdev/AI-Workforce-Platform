# Chạy toàn bộ luồng API demo bằng mock

> **Hướng dẫn cũ của bản RAM.** Theo yêu cầu mới, demo đã chuyển sang PostgreSQL V3 có dữ liệu giả. Dùng [HUONG_DAN_DEMO_DATABASE_V3.md](HUONG_DAN_DEMO_DATABASE_V3.md) cho lệnh chạy, UUID và contract hiện tại. Các bước/endpoint dưới đây là lịch sử bản RAM, không áp dụng cho `main.py` hiện tại.

## 1. Khởi động

Trong PowerShell tại thư mục dự án:

```powershell
python -m pip install -e ./services/vinhomes-api
& ./services/vinhomes-api/scripts/start_demo.ps1
```

Mở **http://localhost:8000/docs**, gọi `GET /health`, kết quả phải có `mode: mock`. Không cần PostgreSQL hoặc Docker để chạy chế độ này.

Nếu chạy trực tiếp main, đặt `VINHOMES_API_DEMO_MODE=1`, `PYTHONPATH=services/vinhomes-api/src`, rồi `python -m vinhomes_api`. Script trên đặt đầy đủ biến môi trường cần thiết.

Terminal thứ hai cho gateway Hono:

```powershell
cd server
bun scripts/vinhomes-demo.ts
```

FE và client agent dùng base URL `http://localhost:3001/api/vinhomes-demo`. Ví dụ `GET /api/vinhomes-demo/catalogs` được chuyển đến FastAPI `GET /catalogs`. Gateway này chạy riêng, cần cổng 3001 trống; không khởi động đồng thời server Hono chính trên cùng cổng.

## 2. Vai trò và dữ liệu mẫu

Swagger: bấm **Try it out**, chọn `X-Demo-Actor`, nhập body rồi **Execute**. Gateway cũng nhận cùng header.

| Vai trò | Header | Thao tác |
| --- | --- | --- |
| Cư dân | `resident` | Chat, tạo ticket, xác nhận nghiệm thu |
| BQL | `management` | Nhận ticket, tạo việc, phân công, phê duyệt, báo cáo |
| Kỹ thuật | `technical` | Nhận việc, tiến độ, đề xuất khóa nước |
| An ninh | `security` | Camera, cảnh báo, đề xuất điều động/hủy |
| Admin | `admin` | Quản trị tài khoản, duyệt memory |

Chọn header rõ ràng khi chuyển vai trò. Đây là chọn nhân vật demo, không phải đăng nhập bằng phiên thật. Hono demo chuyển tiếp vai trò này; gateway ủy quyền người dùng thật chưa thuộc chế độ mock.

`GET /demo/fixtures` trả về ID mẫu: tòa `building-s201`, domain `vinhomes`, căn hộ `unit-1201`, BQL `management-s201`, room `management-room`, category `technical`/`security`.

## 3. Luồng cư dân → kỹ thuật → nghiệm thu

1. `resident`: `POST /resident/chats` với `{"title":"Rò rỉ nước"}`. Lưu `id` làm `channel_id`.
2. `resident`: gửi `POST /resident/chats/{channel_id}/messages` với `{"text":"Ống nước bị rò","client_message_id":"demo-1"}`. Reception trả lời mẫu; gửi lại cùng khóa không tạo trùng.
3. `resident`: `POST /resident/chats/{channel_id}/tickets` với `{"title":"Rò rỉ nước","description":"Rò nước dưới bồn rửa","category_id":"technical","business_severity":"P2"}`. Lưu `id` làm `ticket_id`.
4. `management`: `POST /tickets/{ticket_id}/routing/ack`, rồi `POST /tickets/{ticket_id}/work-orders`. Lưu `id` làm `order_id`.
5. `management`: xem `/staff/available`, phân công `POST /work-orders/{order_id}/assignments` với `{"staff_id":"technical"}`. Nhân viên bận khiến yêu cầu bị từ chối 409; việc vẫn nằm `/dispatch-queue`.
6. `technical`: `POST /assignments/{order_id}/response` với `{"approved":true,"note":"Nhận việc"}`, rồi `PATCH /work-orders/{order_id}/status` với `{"status":"in_progress"}`.
7. Tùy chọn luồng nước bên dưới; sau đó hoàn tất bằng `PATCH /work-orders/{order_id}/status` với `{"status":"completed","evidence":"demo-photo-01"}`. Có thể tạo metadata ảnh qua `POST /work-orders/{order_id}/evidence` với `{"file_name":"demo.jpg","description":"Đã sửa xong"}` trước bước này.
8. `resident`: lấy `/resident/approvals`, dùng `id` gọi `POST /resident/approvals/{id}/decision` với `{"approved":true,"note":"Đã kiểm tra"}`. Ticket chuyển `closed`. Từ chối (`false`) đưa việc về `in_progress` để sửa lại.
9. Xem `/my/notifications`, `/resident/tickets/{ticket_id}`, `/tickets/{ticket_id}/timeline`. `management` xem `/reports/issued-revenue`, tải `/reports/issued-revenue.docx` hoặc báo cáo `incident-frequency`.

Hóa đơn mock trị giá 150.000 VND được phát hành một lần khi việc kỹ thuật hoàn tất; báo cáo dựa trên các hóa đơn `issued`, kể cả trước khi cư dân nghiệm thu.

## 4. Khóa và mở nước

Khi việc kỹ thuật `in_progress`:

1. `technical`: `POST /work-orders/{order_id}/water-shutdown-request`, lưu `id` và `approval_id`.
2. `management`: `POST /approvals/{approval_id}/decision` với `{"approved":true,"note":"Đồng ý khóa nước"}`.
3. `management`: `POST /water-interruptions/{id}/notify`.
4. `technical`: `POST /water-interruptions/{id}/start`, rồi `/restore`.
5. Hoàn tất việc. API chặn hoàn tất nếu nước chưa khôi phục; yêu cầu bị BQL từ chối không chặn hoàn tất.

## 5. An ninh, điều động và cảnh báo

Tạo ticket như luồng kỹ thuật nhưng category `security`, mức `P0` hoặc `P1`. Ánh xạ database được giữ: P0→p1, P1→p2, P2→p3, P3→p4.

1. BQL nhận ticket và tạo work order.
2. `security`: `POST /work-orders/{order_id}/security/dispatch-request`.
3. `management`: phê duyệt qua `/approvals/{id}/decision`; phân công `staff_id: security`.
4. `security`: nhận việc và bắt đầu như luồng kỹ thuật.
5. Xem `/security/cameras`, `/security/emergency-contacts`; tạo `POST /tickets/{ticket_id}/emergency-alerts`.
6. `security`: ACK qua `POST /security/alerts/{id}/ack`; hoặc `/escalate` chuyển cho BQL rồi `management` ACK. API chặn hoàn tất ticket khẩn cấp khi chưa có ACK.
7. Hoàn tất có bằng chứng và cư dân xác nhận như trên.
8. Muốn hủy việc đang mở: `security` gọi `/work-orders/{order_id}/security/cancel-request`, BQL quyết định. Duyệt hủy đưa việc và ticket về `cancelled`.

## 6. Room, memory và tài khoản

- BQL: `/rooms`, `/rooms/management-room/agents`, tạo agent bằng `POST .../agents` với `{"name":"Agent demo"}`.
- Gửi `POST /rooms/management-room/messages` với `{"text":"Tổng hợp ticket","client_message_id":"room-1","mention_agent_id":"report"}`. Lấy messages hoặc `/mentions/{message_id}` để xem kết quả mẫu.
- BQL: `POST /memory-candidates` với `{"text":"Quy trình demo"}`. Admin lấy `/admin/memory-candidates`, duyệt qua `POST /admin/memory-candidates/{id}/review` với body quyết định.
- Admin: `/admin/accounts`, tạo account bằng POST với `name`, `role`; khóa/mở/xóa mềm qua `PATCH /admin/accounts/{id}/access` với `{"status":"suspended"}` / `active` / `deleted`. Khóa các ID vai trò mẫu sẽ chặn header tương ứng.
- Tra tri thức mẫu: `/knowledge/search?query=nước`.

## 7. Phạm vi mock

Dữ liệu lưu trong RAM, khởi động lại FastAPI sẽ xóa dữ liệu và khôi phục nhân vật mẫu. Phản hồi agent, camera, thông báo, metadata bằng chứng và hóa đơn là mô phỏng; không gọi LLM, camera, gửi SMS hoặc lưu ảnh thật. DOCX là file tải được thực tế. API trả header `X-Vinhomes-Data-Mode: mock`.

Contract mock dùng ID dễ đọc, có một cư dân/tòa/BQL mẫu và chưa thay thế contract UUID, cookie, tenant của chế độ database V3. Khi nối FE thật, dùng OpenAPI của chế độ đang chạy để đối chiếu input/output. Chế độ V3 được giữ khi `VINHOMES_API_DEMO_MODE` không bật.
