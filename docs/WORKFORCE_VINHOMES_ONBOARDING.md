# Nối Reception Vinhomes với Workforce v1

## Chuyển tiếp có kiểm soát

Không bật trên database/dịch vụ Vinhomes đang chạy chỉ vì merge source. Backup trước khi migrate. Chạy migration domain `0013_workforce.sql` và cập nhật `schema/roles.sql` bằng quy trình migration hiện có. Runtime role phải không có BYPASSRLS; các bảng Workforce bật FORCE RLS theo tenant. Không gỡ unique index một integration nhận case đang active: phải chuyển `accepts_cases` khỏi integration cũ trong transaction onboarding, rồi mới bật integration mới. Case cũ không tự đổi chủ; generation mới có binding riêng.

Platform phải có supervisor và các chuyên viên đã công bố, credential customer/provider, event_map, MCP integration và route theo **management unit UUID thực tế**. Backend xác nhận route revision; route mới mặc định pending. `external_user_id` lấy từ actor đã xác thực; `residence_id` là unit UUID. External ticket là `<ticket UUID>:g<reopen_count>`; external conversation là `<resident channel UUID>:<ticket UUID>:g<generation>`. Không tìm workflow gần nhất của cư dân.

## Cấu hình backend

Chỉ lưu ở secret store hoặc `.env` ignored của backend:

```dotenv
VINHOMES_WORKFORCE_ENABLED=1
VINHOMES_WORKFORCE_URL=http://workforce-api:8800
VINHOMES_WORKFORCE_CUSTOMER_KEY=<customer ApiKey value without prefix>
VINHOMES_WORKFORCE_PROVIDER_KEY=<provider ApiKey value without prefix>
VINHOMES_WORKFORCE_SIGNING_KEY_ID=<provider signing key ID>
VINHOMES_WORKFORCE_SIGNING_SECRET=<provider signing secret>
VINHOMES_WORKFORCE_INTEGRATION_CLIENT_ID=<registered Vinhomes integration client ID>
VINHOMES_WORKFORCE_MCP_SERVICE_KEY=<random secret at least 32 characters>
VINHOMES_WORKFORCE_MCP_CONTEXT_KEY=<random signing key at least 32 characters>
VINHOMES_WORKFORCE_MCP_AUDIENCE=<platform MCP integration ID matching provider ID>
```

Cài optional dependency `vinhomes-api[workforce]`. Chạy MCP như service riêng bằng `python -m vinhomes_api.workforce_mcp`, port mặc định 8810, bind mặc định localhost. Trong Docker phải đặt `VINHOMES_WORKFORCE_MCP_HOST=0.0.0.0` và chỉ mở mạng nội bộ. Danh sách host hợp lệ do `VINHOMES_WORKFORCE_MCP_HOSTS` cấu hình (xem module); dùng bearer service key từ platform MCP headers và cùng context key/audience. Không truyền những khóa này ra resident app.

Mỗi BQL cần service actor có quyền nghiệp vụ thực tế. DBA cấp bản ghi trong `vh_workforce_management_grants`: tenant_id, management_unit_id, service_actor, danh sách tools, active; **auto_categories mặc định rỗng**. Grant không thay RBAC/domain access của service actor. Không dùng cư dân như tài khoản quản trị, không bật is_admin bypass. Chưa có danh sách loại việc tự giao được người dùng xác nhận, nên giữ cơ chế tự động này tắt.

## MCP và event policy

Allowlist MCP: `get_ticket`, `get_staff_availability` (read_only=true, requires_consent=false); `propose_plan`, `create_work_order`, `offer_assignment` (requires_consent=true). Propose/offer cần `tracks_events=true`. Provider client phải có `publish_job_event/read_event_receipt` và cùng ID với integration tracking.

Event map: `job.progress`→pending, `job.completed`→completed, `job.failed`→failed, `job.cancelled`→cancelled. Dữ liệu có schema object đóng, chỉ `business_status` string và `business_version` integer, required cả hai; public_fields chỉ hai trường này. Mode snapshot, provider_version tăng độc lập theo job tracking. Transition map phải chấp nhận pending/offered/assigned/accepted/in_progress → pending/completed/failed/cancelled; pending → pending cũng cần để nhận snapshot phiên bản mới. Có thể nhận terminal→terminal khi nghiệp vụ cập nhật phiên bản; không tự cho terminal→pending nếu chưa có quy tắc mở lại. Onboarding phải xác nhận schema/transition phù hợp loại job.

Ảnh chuyển bởi backend: đọc file đã ready/scan clean, kiểm ownership/checksum, xin upload platform, POST MinIO và finalize, rồi attach asset ID trong request. `AWP_MINIO_UPLOAD_ORIGIN` phải truy cập được từ **backend Vinhomes**, không chỉ từ máy người dùng; ví dụ host.docker.internal trong mạng Docker Desktop. Bucket private; browser vẫn xem ảnh qua API Vinhomes.

## Nhận/trả và nhân viên

Reception gọi `submit_reception_message` như cũ. Khi bật, lệnh ghi outbox trong transaction cư dân rồi trả queued; không gọi HTTP trong transaction đó. Adapter có lease/heartbeat, xử lý tối đa 20 outbox song song, giữ thứ tự command theo binding. Retry dùng external ID/body cũ. Tra cứu quyền cư dân/ticket/BQL lại trước gửi và trước trả kết quả. Binding/cursor ghi có CAS chống poller lùi cursor.

Kết quả public được đưa về đúng resident channel với source `platform_supervisor`, dedupe public message ID. Resident UI lấy snapshot qua API backend `/resident/workforce/tickets/{ticket_id}`; quyết định consent gửi structured API approval. Phê duyệt phương án sửa chữa/chi phí và nghiệm thu Vinhomes vẫn dùng API domain tương ứng. Không dùng chat text để thay consent hoặc phê duyệt nghiệp vụ.

Supervisor đọc ticket/nhân lực qua MCP, đề xuất kế hoạch hoặc work order, rồi offer_assignment. Vinhomes kiểm phê duyệt, chuyên môn, ca, tải, phiên bản; nhân viên nhận việc qua API assignment hiện có. Provider outbox trả tiến độ; platform không cần LLM cho mỗi thay đổi trạng thái. Hoàn tất plan approval/job không thay QC hay đóng ticket. Yêu cầu hủy công việc cần luồng nghiệp vụ riêng; bộ tool hiện tại không tự hủy business job hoặc đóng ticket.

## Nghiệm thu trước bật trên dữ liệu thật

Đã có test sandbox PostgreSQL với runtime RLS, API Reception, MCP HTTP thật, consent, tạo order, offer và nhân viên accept qua API thật, provider progress, tracking close giữ business job và late event không mở lại. Phần trạng thái hoàn tất cuối test được mô phỏng bằng SQL; không coi là nghiệm thu toàn bộ staff thi công/QC/resident acceptance bằng UI.

Chạy lại các test contract/core/load, đo model thật trên dữ liệu giả/ẩn danh, kiểm luồng ảnh xuyên backend, fault/restart, frontend bằng trình duyệt và SOP đối soát/backup/khôi phục. Chọn thời điểm cutover và service actor/BQL thật trước bật. Không đưa thông tin mật/PII của cư dân vào bài test model khi chưa có cấu hình dữ liệu và provider phù hợp.
