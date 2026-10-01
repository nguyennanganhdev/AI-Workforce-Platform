# API endpoints cho Agent Tools

**Cập nhật:** 2026-10-01
**Phạm vi:** API nghiệp vụ Vinhomes Operations dùng chung cho frontend và agent tools. Danh sách này mô tả HTTP endpoint; không phải danh sách code tool hay agent runtime.

## Kết nối và xác thực

- **Base URL demo:** `http://localhost:8000`
- **Swagger/OpenAPI:** `http://localhost:8000/docs` và `http://localhost:8000/openapi.json`
- **Giao diện demo:** `http://localhost:8000/demo/ui`
- **Chạy demo:** `services/CHAY_DEMO_API.cmd`
- Demo nhận `X-Demo-Actor`: `resident`, `management`, `technical`, `security`, `admin`.
- Môi trường ngoài demo xác thực người gọi qua Hono; FastAPI kiểm tra quyền và phạm vi dữ liệu trong database. Client không tự khai role/tenant để cấp quyền.

Các path dưới đây nối trực tiếp vào Base URL. Ví dụ: `GET http://localhost:8000/resident/context`.

## 1. Reception, hội thoại và ticket

### Operation API dành cho Reception Agent

FastAPI cung cấp hai endpoint cho agent runtime:

- `POST /internal/reception/operations/execute`
- `POST /internal/reception/operations/reconcile`

Request `execute` có dạng:

```json
{
  "operation": "create_ticket_draft",
  "input": {"channel_id": "...", "incident": {"title": "Rò nước nhà vệ sinh"}},
  "context": {"bindingId": "...", "runId": "...", "requestId": "..."},
  "idempotency_key": "reception-call-001"
}
```

Principal và tenant lấy từ session/server context. `context` chỉ mang metadata truy vết và đối chiếu, không cấp quyền. Response giữ kết quả nghiệp vụ và thêm `agentContext`; Reception runtime tự quyết định operation kế tiếp. Các operation đã hỗ trợ gồm tạo/cập nhật draft, lấy resident context, ghi assessment, tìm BQL, handoff tạo ticket/team/message schema V2, polling Supervisor, bổ sung thông tin, gửi quyết định/hủy, đọc trạng thái và escalation. `process_self_help` trả `501` nếu chưa cấu hình knowledge/RAG cư dân.

Trong workspace có proxy same-origin Hono tại `/api/domains/vinhomes/resident/reception-agent/operations/{execute|reconcile}`. Proxy đó không thuộc commit API-only lần này; tài liệu này mô tả contract FastAPI, chưa tuyên bố tích hợp browser/runtime qua Hono đã được đưa lên nhánh.

| Chức năng | Endpoint |
| --- | --- |
| Context cư dân đã xác minh | `GET /resident/context` |
| Tạo/liệt kê hội thoại | `POST /resident/chats`, `GET /resident/chats` |
| Đọc/gửi tin nhắn | `GET /resident/chats/{channel_id}/messages`, `POST /resident/chats/{channel_id}/messages` |
| Tạo/đọc ticket draft | `POST /resident/chats/{channel_id}/ticket-drafts`, `GET /resident/chats/{channel_id}/ticket-drafts` |
| Chốt một sự cố trong draft thành ticket | `POST /resident/chats/{channel_id}/ticket-drafts/{draft_id}/incidents/{index}/commit` |
| Tạo ticket trực tiếp từ hội thoại | `POST /resident/chats/{channel_id}/tickets` |
| Tìm BQL phụ trách theo tòa/domain/category | `GET /management-units/resolve` |
| Xem ticket và tiến độ của cư dân | `GET /resident/tickets`, `GET /resident/tickets/{ticket_id}`, `GET /resident/tickets/{ticket_id}/progress` |
| Đọc/yêu cầu quyết định phê duyệt của cư dân | `GET /resident/approvals`, `POST /resident/approvals/{approval_id}/decision` |
| Đọc/đánh dấu đã đọc thông báo | `GET /my/notifications`, `POST /my/notifications/{notification_id}/read` |

Draft chưa tạo ticket chính thức. Commit tạo ticket cho từng sự cố đủ thông tin; retry được chống trùng theo draft/index. API resolve xác định đơn vị BQL phụ trách, không tự chọn người nhận hoặc gửi tin nhắn.

## 2. Phương án, điều phối và work order

| Chức năng | Endpoint |
| --- | --- |
| Đọc danh sách/chi tiết ticket và triage | `GET /tickets`, `GET /tickets/{ticket_id}`, `GET /tickets/{ticket_id}/triage` |
| Tạo ticket, cập nhật trạng thái, ghi assessment | `POST /tickets`, `PATCH /tickets/{ticket_id}/status`, `POST /tickets/{ticket_id}/assessments` |
| Tạo/đọc phương án | `POST /tickets/{ticket_id}/plans`, `GET /tickets/{ticket_id}/plans`, `GET /plans` |
| BQL duyệt phương án | `POST /plans/{plan_id}/management-decision` |
| Cư dân đọc/duyệt phương án | `GET /resident/plans`, `POST /resident/plans/{plan_id}/decision` |
| Đọc danh sách/chi tiết work order và hàng đợi điều phối | `GET /work-orders`, `GET /work-orders/{work_order_id}`, `GET /dispatch-queue` |
| Tạo work order, chuyển trạng thái | `POST /tickets/{ticket_id}/work-orders`, `PATCH /work-orders/{work_order_id}/status` |
| Tra nhân viên phù hợp, phân công | `GET /staff/available`, `POST /work-orders/{work_order_id}/assignments` |
| Nhân viên nhận/từ chối việc | `POST /assignments/{assignment_id}/response` |
| Đọc timeline/bằng chứng ticket | `GET /tickets/{ticket_id}/timeline`, `GET /tickets/{ticket_id}/evidence` |
| BQL xác nhận đã nhận ticket được định tuyến | `POST /tickets/{ticket_id}/routing/ack` |
| Đọc hàng đợi và quyết định phê duyệt work | `GET /approvals`, `POST /approvals/{approval_id}/decision` |

Các thao tác thay đổi có thể cần `version` và/hoặc `idempotency_key` theo contract. Nếu version cũ, tải lại trạng thái trước khi quyết định; khi retry cùng request, giữ nguyên idempotency key.

## 3. Agent kỹ thuật

| Chức năng | Endpoint |
| --- | --- |
| Tìm tài liệu đã xuất bản trong phạm vi được cấp | `GET /knowledge/search` |
| Đọc danh sách/chi tiết thiết bị | `GET /assets`, `GET /assets/{asset_id}` |
| Đọc/ghi số liệu sensor | `GET /assets/{asset_id}/sensor-readings`, `POST /assets/{asset_id}/sensor-readings` |
| Đọc lịch sử bảo trì | `GET /assets/{asset_id}/maintenance-history` |
| Đọc sự cố đang gián đoạn | `GET /technical/active-outages` |
| Đọc/ghi số đo work order | `GET /work-orders/{work_order_id}/measurements`, `POST /work-orders/{work_order_id}/measurements` |
| Gửi kết quả thực hiện | `POST /work-orders/{work_order_id}/executor-results` |
| Kiểm tra điều kiện hoàn tất | `GET /work-orders/{work_order_id}/resolution-check` |
| Ghi lịch sử bảo trì sau khi xác minh | `POST /assets/{asset_id}/maintenance-history` |
| Tạo/đọc yêu cầu quyền thao tác | `POST /work-orders/{work_order_id}/permission-requests`, `GET /work-orders/{work_order_id}/permission-requests` |
| BQL quyết định yêu cầu quyền thao tác | `POST /permission-requests/{request_id}/decision` |
| Đề nghị ngừng nước, đọc gián đoạn nước | `POST /work-orders/{work_order_id}/water-shutdown-request`, `GET /work-orders/{work_order_id}/water-interruptions` |
| Thông báo/bắt đầu/khôi phục cấp nước | `POST /water-interruptions/{interruption_id}/notify`, `POST /water-interruptions/{interruption_id}/start`, `POST /water-interruptions/{interruption_id}/restore` |

`/permission-requests` dùng cho utility isolation (ví dụ ngắt điện), hạn chế khu vực, vào căn hộ hoặc điều nhà thầu; gửi `kind` và dữ liệu chi tiết tương ứng. Đây là quy trình yêu cầu/phê duyệt, không trực tiếp điều khiển van, điện, cửa hoặc gọi nhà cung cấp ngoài.

## 4. Agent bảo vệ

| Chức năng | Endpoint |
| --- | --- |
| Đọc metadata camera/liên hệ khẩn cấp | `GET /security/cameras`, `GET /security/emergency-contacts` |
| Tạo cảnh báo khẩn cấp gắn ticket | `POST /tickets/{ticket_id}/emergency-alerts` |
| Liệt kê cảnh báo | `GET /security/alerts` |
| ACK/chuyển cấp cảnh báo | `POST /security/alerts/{alert_id}/ack`, `POST /security/alerts/{alert_id}/escalate` |
| Đề nghị điều động/hủy điều động bảo vệ | `POST /work-orders/{work_order_id}/security/dispatch-request`, `POST /work-orders/{work_order_id}/security/cancel-request` |
| BQL quyết định phê duyệt liên quan | `POST /approvals/{approval_id}/decision` |

Camera và liên hệ hiện là dữ liệu seed. Chuyển cấp được ghi nhận qua API; chưa có worker tự gọi điện/SMS hoặc tích hợp camera bên ngoài.

## 5. Report Agent và hóa đơn

| Chức năng | Endpoint |
| --- | --- |
| Lấy tùy chọn bộ lọc | `GET /reports/filter-options` |
| Tổng hợp hiệu suất nhân viên/chi tiết phản hồi | `GET /reports/employee-performance`, `GET /reports/employee-feedback` |
| Tổng hợp doanh thu sửa chữa/tần suất sự cố | `GET /reports/repair-revenue`, `GET /reports/incident-frequency-summary` |
| Đọc bản ghi hỗ trợ báo cáo | `GET /reports/supporting-records` |
| Tạo export, xem trạng thái và tải nội dung | `POST /reports/exports`, `GET /reports/exports/{export_id}`, `GET /reports/exports/{export_id}/content` |
| Tóm tắt tài chính ticket, tạo/đọc hóa đơn | `GET /tickets/{ticket_id}/financial-summary`, `POST /tickets/{ticket_id}/invoices`, `GET /invoices/{invoice_id}` |
| Phát hành hóa đơn/ghi thanh toán demo | `POST /invoices/{invoice_id}/issue`, `POST /invoices/{invoice_id}/demo-payments` |

Các endpoint báo cáo trực tiếp bổ sung hiện có:

- `GET /reports/incident-frequency` và `GET /reports/incident-frequency.docx`
- `GET /reports/issued-revenue` và `GET /reports/issued-revenue.docx`

Export agent hiện hỗ trợ DOCX đồng bộ; chưa có PDF/XLSX hoặc worker xuất nền. Doanh thu theo hóa đơn `issued`; tiền thực thu và còn phải thu được tính riêng. `demo-payments` chỉ dành cho demo local.

## 6. Ảnh hội thoại Reception

| Bước | Endpoint |
| --- | --- |
| Khởi tạo upload | `POST /resident/chats/{channel_id}/image-uploads` |
| Tải bytes | `PUT /image-uploads/{upload_id}/content` |
| Hoàn tất upload | `POST /image-uploads/{upload_id}/complete` |
| Liệt kê ảnh hội thoại | `GET /resident/chats/{channel_id}/images` |
| Liên kết ảnh với ticket | `POST /tickets/{ticket_id}/conversation-images` |
| Xin quyền đọc/đọc nội dung ảnh | `GET /conversation-images/{file_id}/read-access`, `GET /conversation-images/{file_id}/content` |

Luồng: initiate → upload bytes → complete → gửi message có `file_ids` → đọc lại ảnh → gắn ảnh vào ticket. Backend kiểm tra bytes, kích thước, checksum và chữ ký định dạng. Storage hiện là local demo; link đọc có hạn, gắn với danh tính và vẫn cần xác thực.

## 7. Tạo agent và phối hợp nhóm

| Chức năng | Endpoint |
| --- | --- |
| Liệt kê/tạo agent trong room | `GET /rooms/{room_id}/agents`, `POST /rooms/{room_id}/agents` |
| Cập nhật cấu hình agent | `PUT /rooms/{room_id}/agents/{agent_id}/configuration` |
| Gửi kết quả đánh giá, xem hàng chờ admin | `POST /rooms/{room_id}/agents/{agent_id}/review-submissions`, `GET /admin/agent-reviews` |
| Admin duyệt/từ chối, đọc version agent | `POST /admin/agent-reviews/{review_id}/decision`, `GET /rooms/{room_id}/agents/{agent_id}/versions` |
| Tạo team, đọc team | `POST /rooms/{room_id}/teams`, `GET /rooms/{room_id}/teams`, `GET /teams/{team_id}` |
| Tạo/đọc/cập nhật task | `POST /teams/{team_id}/tasks`, `GET /teams/{team_id}/tasks`, `PATCH /teams/{team_id}/tasks/{task_id}` |
| Gửi/đọc mailbox | `POST /teams/{team_id}/mailbox`, `GET /teams/{team_id}/mailbox` |
| Cập nhật trạng thái team, lấy context room | `PATCH /teams/{team_id}/state`, `GET /rooms/{room_id}/context` |
| Đọc namespace/tạo đề xuất memory | `GET /memory/namespaces`, `POST /tickets/{ticket_id}/memory-candidates` |
| Admin xem/duyệt đề xuất memory | `GET /admin/memory-candidates`, `POST /admin/memory-candidates/{candidate_id}/review` |

Các API này lưu cấu hình, bản ghi đánh giá, version, task, mailbox và memory candidate. Chúng không thực thi AgentScope/LLM hay tự chạy đánh giá agent.

## 8. Response, quyền và ranh giới tích hợp

- Tài liệu hiện ghi nhận **49 endpoint JSON** dùng schema response chung `AgentBusinessResponse`. Con số này là số endpoint dùng schema, không phải số tool runtime; download ảnh/DOCX trả bytes.
- `agentContext` là metadata kỹ thuật (`operation`, `facts`, `missingFields`, `resourceContext`, `source`). API vẫn trả các field nghiệp vụ đầy đủ; không tự sinh câu trả lời, câu hỏi, khuyến nghị hay bước tiếp theo cho agent.
- `GET /knowledge/search` là tìm kiếm từ khóa có kiểm tra quyền; chưa phải pipeline RAG/vector retrieval. API `answer_or_escalate` chưa được triển khai.
- Sensor và camera là dữ liệu seed/database; chưa kết nối BMS/IoT/camera ngoài. Yêu cầu khóa nước, ngắt điện, vào căn hộ và điều nhà thầu là workflow phê duyệt.
- Bản ghi đánh giá agent không đồng nghĩa API đã chạy LLM hoặc sandbox. Agent runtime/provider vẫn do hệ thống gọi bên ngoài đảm nhiệm.

## Tài liệu và mã nguồn

- [Danh sách API cho agent tools](API_CHO_AGENT_TOOLS.md)
- [Mapping nghiệp vụ và database V3](API_NGHIEP_VU_MOI_DATABASE.md)
- [FastAPI entry point](../services/vinhomes-api/src/vinhomes_api/main.py)
- Các router triển khai nằm trong `services/vinhomes-api/src/vinhomes_api/v3_*.py`.
