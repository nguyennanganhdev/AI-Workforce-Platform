# Danh sách API cho agent tools

Cập nhật: 2026-10-01. Phạm vi: HTTP endpoint dùng chung cho frontend và agent tools; không triển khai code tool hoặc agent runtime.

- Base URL demo: `http://localhost:8000`.
- Swagger: `http://localhost:8000/docs`.
- Giao diện demo: `http://localhost:8000/demo/ui`.
- Chạy bằng `services/CHAY_DEMO_API.cmd`.
- Dữ liệu mock/faker được đọc và ghi trong PostgreSQL thật.
- Demo dùng `X-Demo-Actor`: `resident`, `management`, `technical`, `security`, `admin`. Ngoài demo, API dùng danh tính người yêu cầu xác thực qua Hono và kiểm tra quyền/scope trong database.

## 1. Reception Agent

### Operation API cho Reception Agent

Agent runtime dùng một endpoint execute để gửi operation và nhận lại dữ liệu nghiệp vụ từ PostgreSQL V3:

- `POST /internal/reception/operations/execute`
- `POST /internal/reception/operations/reconcile` — chỉ tra receipt khi client không biết execute đã commit hay chưa.

Request chung gồm `operation`, `input`, `context` và `idempotency_key`. Các operation gồm `create_ticket_draft`, `get_verified_resident_context`, `update_ticket_incident`, `submit_ticket_assessment`, `resolve_management_destination`, `handoff_ticket`, `register_supervisor_wait`, `get_supervisor_event`, `append_ticket_information`, `respond_supervisor_interaction`, `request_ticket_cancellation`, `get_ticket_status`, `process_self_help` và `escalate_emergency`.

`execute` trả dữ liệu đã đọc/ghi, ticket/team/message ID, trạng thái, `missingFields` nếu có và `agentContext`; Reception runtime dựa vào response để tự chọn operation tiếp theo. API không chạy agent, không phân loại hội thoại và không tạo câu trả lời. `process_self_help` hiện trả `501` khi chưa cấu hình knowledge/RAG cư dân.

Hono proxy cho hai endpoint này có trong workspace hiện tại nhưng bị loại khỏi commit API-only theo yêu cầu; route proxy cho browser cần được tích hợp riêng. Chi tiết input/output và ví dụ bàn giao nằm trong `Endpoint cần có của reception agent.md`.

Các endpoint trực tiếp bên dưới vẫn là API nghiệp vụ nền cho frontend/runtime; chúng không thay contract operation chung ở trên.

| Tool / chức năng | API hiện có |
| --- | --- |
| `create_ticket_draft` | `POST /resident/chats/{channel_id}/ticket-drafts` |
| Đọc các draft | `GET /resident/chats/{channel_id}/ticket-drafts` |
| Chốt sự cố trong draft thành ticket | `POST /resident/chats/{channel_id}/ticket-drafts/{draft_id}/incidents/{index}/commit` |
| `load_resident_context` | `GET /resident/context` |
| `resolve_management_destination` | `GET /management-units/resolve` |

Tạo draft chưa tạo ticket chính thức. Gọi API commit khi đủ thông tin; từng sự cố trong một hội thoại có thể tạo ticket riêng.

Context trả tên, điện thoại nếu có trong database, căn hộ đã xác minh, tòa và domain. Điện thoại chưa có dữ liệu có thể trả null.

Resolve nhận bộ lọc building/domain/category theo contract Swagger và xác định đơn vị BQL phụ trách; không đồng nghĩa chọn tài khoản cá nhân hoặc tự gửi tin nhắn.

## 2. Agent kỹ thuật

| Tool / chức năng | API hiện có |
| --- | --- |
| `sop_kb.retrieve` | `GET /knowledge/search` — tìm kiếm tài liệu đã xuất bản theo từ khóa và quyền |
| `asset.read` | `GET /assets`, `GET /assets/{asset_id}` |
| `sensor.read` | `GET /assets/{asset_id}/sensor-readings` |
| `maintenance_history.read` | `GET /assets/{asset_id}/maintenance-history` |
| `technical.get_active_outage` | `GET /technical/active-outages` |
| `technical.record_measurement` | `POST /work-orders/{work_order_id}/measurements` |
| Đọc số đo | `GET /work-orders/{work_order_id}/measurements` |
| `technical.submit_executor_result` | `POST /work-orders/{work_order_id}/executor-results` |
| `maintenance_history.append` | `POST /assets/{asset_id}/maintenance-history` |
| `technical.verify_resolution` | `GET /work-orders/{work_order_id}/resolution-check` |
| `utility_isolation.request` — khóa nước | `POST /work-orders/{work_order_id}/water-shutdown-request` |
| `utility_isolation.request` — ngắt điện | `POST /work-orders/{work_order_id}/permission-requests`, `kind=utility_isolation`, `details.utility=electricity` |
| `area_restriction.request` | `POST /work-orders/{work_order_id}/permission-requests`, `kind=area_restriction` |
| `apartment_entry.request` | `POST /work-orders/{work_order_id}/permission-requests`, `kind=apartment_entry` |
| `vendor_dispatch.request` | `POST /work-orders/{work_order_id}/permission-requests`, `kind=vendor_dispatch` |
| Đọc yêu cầu quyền thao tác | `GET /work-orders/{work_order_id}/permission-requests` |
| BQL quyết định quyền thao tác | `POST /permission-requests/{request_id}/decision` |

### Giới hạn

- Sensor đọc dữ liệu đã lưu trong database; chưa nối BMS/IoT.
- Các yêu cầu khóa nước, ngắt điện, vào căn hộ hoặc điều nhà thầu là workflow phê duyệt; chưa điều khiển thiết bị hoặc gọi hệ thống ngoài.
- `/knowledge/search` là tìm kiếm từ khóa có kiểm tra quyền; chưa phải pipeline RAG/vector retrieval và chưa bảo đảm đã seed đủ SOP/tiêu chí nghiệm thu.
- Executor result kiểm tra trạng thái, evidence và điều kiện hoàn tất trước khi ghi kết quả; lịch sử bảo trì chỉ ghi công việc hoàn thành đã được xác minh.

## 3. Agent bảo vệ

| Chức năng | API hiện có |
| --- | --- |
| Metadata camera | `GET /security/cameras` |
| Liên hệ khẩn cấp | `GET /security/emergency-contacts` |
| Tạo cảnh báo khẩn cấp | `POST /tickets/{ticket_id}/emergency-alerts` |
| Danh sách cảnh báo | `GET /security/alerts` |
| Xác nhận nhận cảnh báo | `POST /security/alerts/{alert_id}/ack` |
| Chuyển cấp cảnh báo | `POST /security/alerts/{alert_id}/escalate` |
| Đề nghị điều động bảo vệ | `POST /work-orders/{work_order_id}/security/dispatch-request` |
| Đề nghị hủy điều động | `POST /work-orders/{work_order_id}/security/cancel-request` |
| BQL phê duyệt | `POST /approvals/{approval_id}/decision` |

Camera/contact hiện là dữ liệu seed. Chuyển cấp được thực hiện qua API; chưa có worker tự động hoặc tích hợp cuộc gọi/SMS/camera ngoài.

## 4. Report Agent

| Tool / chức năng | API hiện có |
| --- | --- |
| `get_report_filter_options` | `GET /reports/filter-options` |
| `get_employee_performance_summary` | `GET /reports/employee-performance` |
| `get_employee_feedback_details` | `GET /reports/employee-feedback` |
| `get_repair_revenue_summary` | `GET /reports/repair-revenue` |
| `get_incident_frequency_summary` | `GET /reports/incident-frequency-summary` |
| `get_report_supporting_records` | `GET /reports/supporting-records` |
| `create_report_export` | `POST /reports/exports` |
| `get_report_export_status` | `GET /reports/exports/{export_id}` |
| Tải báo cáo | `GET /reports/exports/{export_id}/content` |

### Giới hạn

- Filter options trả tòa, nhóm sự cố và nhân viên; chưa trả danh sách phân khu riêng.
- Supporting records hỗ trợ ticket, công việc và hóa đơn, có phân trang; chưa có danh sách giao dịch thanh toán riêng hoặc liên kết tự động đến mọi bộ lọc của một chỉ số.
- Tần suất lọc một tòa mỗi lần, hỗ trợ query `interval=day/week/month`.
- Doanh thu tính theo hóa đơn đã phát hành; thực thu và còn phải thu được tách riêng. Chưa tách tiền công/vật tư vì schema chưa có trường phân loại.
- Export hỗ trợ DOCX đồng bộ; chưa có PDF/XLSX hoặc worker xuất báo cáo nền. Download kiểm tra người tạo và quyền hiện tại.

## 5. Ảnh trong hội thoại Reception

| Tool / chức năng | API hiện có |
| --- | --- |
| `initiate_image_upload` | `POST /resident/chats/{channel_id}/image-uploads` |
| Upload bytes | `PUT /image-uploads/{upload_id}/content` |
| `complete_image_upload` | `POST /image-uploads/{upload_id}/complete` |
| `get_conversation_images` | `GET /resident/chats/{channel_id}/images` |
| `attach_images_to_ticket` | `POST /tickets/{ticket_id}/conversation-images` |
| `get_image_read_access` | `GET /conversation-images/{file_id}/read-access` |
| Đọc nội dung ảnh | `GET /conversation-images/{file_id}/content` |

Luồng: initiate → upload bytes → complete → gửi message có `file_ids` → đọc lại ảnh từ hội thoại → liên kết vào ticket khi ticket được tạo.

Backend kiểm tra bytes thực tế, kích thước/checksum và chữ ký định dạng trước khi đánh dấu ready. API liên kết ảnh vào ticket kiểm tra nguồn hội thoại/quyền và không tạo liên kết trùng khi gọi lại.

Storage hiện là local demo, metadata lưu PostgreSQL; chưa upload S3/MinIO. Link đọc có hạn, gắn danh tính người yêu cầu, vẫn cần xác thực và hết hiệu lực sau restart; chưa dùng trực tiếp cho model bên ngoài.

## 6. RAG

`answer_or_escalate`: chưa viết API, theo yêu cầu loại phần gọi RAG khỏi phạm vi triển khai.

Các API nghiệp vụ cho agent tools trong các bảng trên vẫn được triển khai; không có code tool hoặc model runtime trong phần này.

## 7. Response để agent tiếp tục xử lý

Các endpoint này là API nghiệp vụ viết bằng code. API xác thực người gọi, kiểm tra quyền/phạm vi, kiểm tra input và điều kiện nghiệp vụ, đọc/ghi PostgreSQL, rồi trả response cho caller. Không có AI/LLM, prompt, phân tích ngôn ngữ tự nhiên, chọn tool hay quyết định câu trả lời trong các endpoint này. Agent/runtime bên ngoài chịu trách nhiệm hiểu hội thoại và quyết định xử lý tiếp.

49 endpoint JSON có schema response chung `AgentBusinessResponse`; đây là schema response, không phải 49 tool được cài trong API. Response giữ nguyên field nghiệp vụ và thêm `agentContext` với metadata có giới hạn:

| Trường | Nội dung |
| --- | --- |
| `operation` | Tên endpoint/nghiệp vụ đã gọi |
| `facts` | Một số ID, code, status, version hoặc kết quả kiểm tra đã có sẵn trong response; không phân tích nguyên nhân |
| `missingFields` | Field thiếu do validator hiện có xác định; không tạo câu hỏi để hỏi người dùng |
| `resourceContext` | ID hoặc bộ lọc được truyền vào endpoint |
| `source` | `business_api` |

Các field nghiệp vụ đầy đủ vẫn nằm ở response gốc, ví dụ `ticket`, `location`, `category`, `managementDestination`, `items`, `checks`, `status` và `version`. API không sinh `outcome`, `summary`, `questionsToAsk`, `nextActions` hoặc khuyến nghị. `agentContext` chỉ là metadata kỹ thuật, không phải nội dung agent phải trả lời. Endpoint tải bytes ảnh/DOCX tiếp tục trả file.

### Ví dụ tạo ticket

Caller gửi các field có cấu trúc đã được runtime/caller xác định. API kiểm tra và ghi ticket vào database, sau đó trả snapshot dữ liệu. Ví dụ rút gọn:

```json
{
  "id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
  "code": "VH-AAAAAAAAAAAA",
  "status": "open",
  "version": 1,
  "creationOutcome": "created",
  "ticket": {
    "id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
    "title": "Tràn nước nhà vệ sinh",
    "status": "open",
    "version": 1
  },
  "location": {
    "unitCode": "A-1201",
    "buildingName": "Tòa A"
  },
  "managementDestination": {
    "name": "Ban quản lý tòa A"
  },
  "agentContext": {
    "operation": "create_ticket",
    "facts": {
      "id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
      "code": "VH-AAAAAAAAAAAA",
      "status": "open",
      "version": 1,
      "creationOutcome": "created"
    },
    "missingFields": [],
    "resourceContext": {
      "ticket_id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    },
    "source": "business_api"
  }
}
```

Agent dùng snapshot này để tự quyết định cách phản hồi hoặc gọi endpoint tiếp theo. Nếu draft thiếu field, API trả HTTP 422 cùng `missingFields` được tính từ dữ liệu draft; agent tự diễn giải và quyết định có hỏi cư dân hay không. API không tạo câu hỏi. Nếu điều kiện kỹ thuật không đạt, API trả các check thất bại đã xác định; agent tự xử lý thông tin đó. Mọi request tiếp theo vẫn qua kiểm tra quyền và trạng thái ở server.

Các API ghi nhận hành động nghiệp vụ như duyệt yêu cầu, ACK cảnh báo hay gửi kết quả kỹ thuật vẫn thực hiện đúng thao tác endpoint được gọi. Việc quyết định có gọi endpoint đó hay trả lời hội thoại thuộc caller/agent bên ngoài API.

### Trạng thái xác minh response mới

Đã kiểm tra cú pháp và lint trước đó; thay đổi hiện tại chưa chạy lại các scenario HTTP nghiệp vụ. Ví dụ trên minh họa contract, không phải response vừa được gọi trên database.

## 8. Tài liệu liên quan

- [Mapping input/output và luồng nghiệp vụ](API_NGHIEP_VU_MOI_DATABASE.md).
- [Báo cáo thay đổi và giới hạn xác minh](../changes/2026-10-01-v3-database-business-apis.md).

Danh sách endpoint hiện có không đồng nghĩa mọi nhánh nghiệp vụ hoặc tích hợp bên ngoài đã được kiểm chứng. Payload, query parameters và response chi tiết xem Swagger.
