# Vinhomes Operations FastAPI

## Demo mock

Chạy `setup_demo_database.ps1`, rồi `start_demo.ps1` trong `scripts/` từ thư mục dự án, mở `http://localhost:8000/docs`. Xem [hướng dẫn demo database V3](HUONG_DAN_DEMO_DATABASE_V3.md). Demo dùng PostgreSQL với dữ liệu faker, không dùng RAM; chọn vai trò bằng `X-Demo-Actor`, quyền vẫn kiểm tra từ database.

Active HTTP routes query the canonical V3 PostgreSQL tables (`tickets`, `ticket_events`, `ticket_assessments`, `ticket_triage_decisions`, `work_orders`, `work_assignments`, `work_approvals`). The restored `vh_*` modules and Alembic migrations are retained as legacy reference and are not mounted by `main.py`. Do not run those migrations on a V3 database.

Run `python -m vinhomes_api` from this directory. The default bind address is `127.0.0.1:8000`; Swagger is at `/docs` and the OpenAPI document at `/openapi.json`.

Business endpoints require `VINHOMES_API_DATABASE_URL` (`postgresql+asyncpg://...`), a V3 tenant (`VINHOMES_API_TENANT_ID` or `VINHOMES_API_TENANT_KEY`), and server verified identity. Set `VINHOMES_API_AUTH_URL` to the platform's `/api/me` endpoint to forward the browser session cookie. For local loopback development, `VINHOMES_API_DEV_USER_ID` can select an existing active user; database grants are still checked. This development setting is rejected when binding to a non-loopback host.

`GET /health` checks the process. `GET /ready` checks required V3 tables. Business queries use a transaction with `SET LOCAL app.tenant_id` and `app.user_id`. Operations routes require active management/staff grants; `/resident/*` and `/my/notifications` require an active tenant membership and check ownership of each chat, ticket or notification. Room routes require room membership. Report, knowledge and admin routes apply additional management scope, document ACL or admin checks.

The API includes V3 read and write routes for tickets, assessment/review triage,
work orders, assignments, approvals, evidence, QC, cleaning, security, contractor
progress and budget requests. The complete route contract is visible at `/docs`.
New endpoints also cover resident chat/ticket tracking, in-app notifications,
management room messages, scoped knowledge search, available staff, water
interruptions, admin memory review, and JSON/DOCX incident or issued-invoice
reports. Security incident creation accepts `business_severity` P0–P3 and stores
the corresponding `p1`–`p4` value.
`POST /resident/chats/{channel_id}/tickets` creates one ticket for a verified
resident unit in an existing chat, resolves the active management coverage and
notifies scoped managers. `POST /tickets/{ticket_id}/routing/ack` records BQL
acceptance and notifies the requester.
The V3 extension tables for field operations are in
`server/drizzle/0001_vinhomes_operations.sql` and
`server/drizzle/0002_vinhomes_qc_redo.sql`; apply the server Drizzle migrations
before starting this service. The old `vh_*` write routes remain unmounted.

For the local Docker fixture, `scripts/seed_v3_local.sql` creates a tenant, user,
building, management coverage, published triage policy and local evidence storage
location. The local file API accepts JPEG, PNG and WebP images of at most 10 MB and
stores them in the ignored `.local-v3-files` directory. It is available only with
`VINHOMES_API_DEV_USER_ID` on a loopback host. Deployments need a verified object
store and malware scanning before enabling production uploads.

The runtime database role needs `SELECT` on V3 tables and `INSERT`/`UPDATE` on
`channels`, `channel_memberships`, `messages`, `message_mentions`, `tickets`,
`ticket_events`, `ticket_assessments`, `ticket_triage_decisions`,
`ticket_triage_reviews`, `work_orders`, `work_assignments`, `work_approvals`,
`service_interruptions`, `interruption_scopes`, `notification_deliveries`,
`memory_candidates`, `knowledge_reviews`, `evidence_items`, `execution_principals`,
`files`, `file_objects`, `ticket_files` and the seven `vh_*` extension tables.
It must not have `BYPASSRLS`. Data changes run inside a tenant scoped transaction.

An agent running without a browser session cannot yet call protected port 8000
routes. The planned Hono delegation path must pass a verified requesting user
identity to FastAPI; no route accepts a client supplied user ID as authority.

## Giao diện chạy thử API V3

Mở `services/CHAY_DEMO_API.cmd` hoặc chạy `scripts/start_demo.ps1`, rồi mở **http://localhost:8000/demo/ui**.
Trang là giao diện nghiệp vụ: cư dân gửi yêu cầu, BQL điều phối/phê duyệt, nhân viên nhận việc,
upload bằng chứng, an ninh, trao đổi phòng và báo cáo. Không cần nhập endpoint hoặc JSON.
Hướng dẫn thao tác demo được gộp ngay bên dưới. Luồng sản phẩm và điểm cần tích hợp xem ở [tài liệu tổng thể](../../docs/teams/chien/SYSTEM_FLOW_AND_MAINTENANCE_2026-10-04/README.md).

### Hướng dẫn giao diện demo V3

#### Mở hệ thống

Double-click **`services/CHAY_DEMO_API.cmd`**.
File khởi động Docker, PostgreSQL V3, FastAPI và mở **http://localhost:8000/demo/ui**.
Giao diện chạy cùng API nên không cần frontend hoặc Hono riêng.

Launcher bổ sung scope site demo cho BQL/bảo vệ để chạy màn hình An ninh trên database faker đã có; không seed lại hoặc reset nghiệp vụ. Bước này chỉ chấp nhận database cục bộ `vinhomes_v3` chứa tenant demo duy nhất.

Nếu API cũ đang chạy, dừng bằng Ctrl+C ở cửa sổ API rồi mở CMD lại. Launcher chỉ mở trình duyệt khi database và giao diện nghiệp vụ đã sẵn sàng. Khi launcher tạo API ẩn, log nằm ở `services/vinhomes-api/.local-v3-faker/demo-api.stderr.log`.

#### Cách sử dụng

Chọn vai trò ở góc trên. Chọn mục trong thanh điều hướng, chọn yêu cầu hoặc công việc rồi thao tác bằng form và nút. Không cần nhập ID, endpoint, version hoặc JSON. Quyền và điều kiện thực hiện vẫn do API kiểm tra.

##### 1. Cư dân gửi yêu cầu

1. Chọn **Cư dân → Yêu cầu → Gửi yêu cầu mới**.
2. Điền tiêu đề, mô tả, khu vực dịch vụ, tòa nhà, căn hộ, loại dịch vụ và thông tin liên hệ.
3. Lưu để tạo yêu cầu gửi đến BQL phụ trách.
4. Xem chi tiết yêu cầu và lịch sử xử lý.

Có thể vào **Trao đổi với lễ tân**, tạo cuộc trao đổi, gửi tin nhắn và tạo yêu cầu từ cuộc trao đổi đó. Agent lễ tân ở chế độ demo phản hồi mẫu trong database.

##### 2. Ban quản lý tiếp nhận và điều phối

1. Chọn **Ban quản lý → Yêu cầu**, mở yêu cầu vừa tạo.
2. **Tiếp nhận yêu cầu**, **Đánh giá sự cố** nếu cần.
3. **Đánh giá & duyệt triage**: chọn assessment, đề xuất phân loại; trong cùng màn hình có nút duyệt đề xuất đang chờ.
4. **Tạo công việc** khi ticket còn chờ điều phối.
5. Trong chi tiết công việc, chọn **Phân công nhân viên**. Danh sách lấy từ nhân viên đang rảnh, đúng chuyên môn và trong ca làm việc.

##### 3. Nhân viên nhận việc và xử lý

1. Chọn **Nhân viên kỹ thuật** hoặc **Nhân viên bảo vệ → Công việc của tôi**.
2. Mở công việc, **Nhận công việc** và đặt giờ dự kiến đến; hoặc **Từ chối nhận** kèm lý do.
3. Cập nhật lần lượt **Bắt đầu di chuyển → Đã đến hiện trường → Bắt đầu xử lý**.
4. **Thêm ảnh bằng chứng**, chọn loại ảnh và ghi chú. Hoàn công cần bằng chứng phù hợp theo API.
5. **Hoàn thành** khi đủ điều kiện.
6. Đổi sang **Cư dân → Chờ xác nhận**, đồng ý kết quả hoặc yêu cầu xử lý lại.

##### 4. Khóa nước

1. Nhân viên đã nhận công việc chọn **Đề nghị khóa nước**, điền lý do, phạm vi và thời gian.
2. **Ban quản lý → Phê duyệt**, duyệt hoặc từ chối.
3. Trong chi tiết công việc, BQL chọn **Thông báo cư dân** sau khi được duyệt.
4. Nhân viên chọn **Bắt đầu khóa nước**, sau đó **Mở lại nước**.
5. Hoàn thành công việc sau khi nước đã được mở lại và có bằng chứng.

##### 5. QC, vệ sinh, nhà thầu và ngân sách

- Trong chi tiết công việc: **Kế hoạch vệ sinh**, **Tiến độ nhà thầu**, **Đề nghị ngân sách**.
- BQL vào **Phê duyệt** để duyệt ngân sách được giao.
- Công việc đã hoàn thành: BQL **Kiểm tra chất lượng**.
- QC không đạt và có yêu cầu làm lại: BQL **Tạo công việc làm lại**, sau đó tiếp tục phân công công việc mới.

##### 6. An ninh

- Chọn khu vực trong **An ninh**.
- Quản trị viên tạo điểm tuần tra; người có quyền khu vực ghi nhận kiểm tra.
- **Báo cáo sự cố**, chọn mức nghiệp vụ P0–P3, ghi diễn biến; API ánh xạ sang p1–p4 trong database.
- **Cập nhật xử lý** sự cố. Chuyển cấp chỉ ghi nhận trạng thái demo, không gọi hoặc gửi tin cho hệ thống bên ngoài.
- **Bàn giao ca** cho người nhận; người nhận hoặc admin **Nhận bàn giao**.

##### 7. Phòng, tri thức, báo cáo và bộ nhớ

- **Phòng ban quản lý**: mở phòng, gửi tin nhắn, chọn agent thuộc phòng nếu muốn mention.
- **Tra cứu tri thức**: chọn phạm vi dịch vụ và từ khóa, xem tài liệu được phép truy cập.
- **Báo cáo**: chọn tòa nhà, loại dịch vụ nếu báo cáo doanh thu, và kỳ; xem bảng và **Tải Word**. Doanh thu tính theo hóa đơn đã phát hành.
- **Quản trị viên → Duyệt bộ nhớ**: đọc nội dung và duyệt/từ chối có lý do.
- **Thông báo**: xem cập nhật của vai trò hiện tại và đánh dấu đã đọc.

#### Lưu ý khi demo

- Dữ liệu ghi qua API vào PostgreSQL; đóng hoặc tải lại trang không xóa nghiệp vụ.
- Giao diện chỉ có chức năng được backend hiện tại hỗ trợ. Không tự tạo kết quả cho endpoint chưa triển khai.
- Mỗi lần lưu xong, trang tải lại dữ liệu để lấy trạng thái/version mới. Khi có xung đột, đóng form và **Làm mới** trước khi thao tác tiếp.
- Lỗi quyền/phạm vi cần đổi đúng vai trò hoặc chọn tài nguyên thuộc phạm vi phụ trách. Các danh mục demo không tự cấp quyền cho người chọn.
- Mất kết nối lúc lưu có thể xảy ra sau khi server đã xử lý: kiểm tra dữ liệu trước khi thử lại.
- Danh sách yêu cầu/công việc hiển thị tối đa 100 bản ghi để demo. Đây là UI tạm, chưa thay toàn bộ frontend sản phẩm.
- Giao diện console cũ còn là asset tham khảo; luồng chính tại `/demo/ui` không dùng console hoặc Swagger.
