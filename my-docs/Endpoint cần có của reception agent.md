# Endpoint cần có của Reception Agent

## Trạng thái

FastAPI cung cấp hai endpoint dùng chung cho các operation của Reception Agent:

- `POST /internal/reception/operations/execute`
- `POST /internal/reception/operations/reconcile`

### URL gọi qua Hono

Workspace hiện tại có proxy để frontend/runtime gọi cùng operation qua Hono và dùng session của người yêu cầu:

- `POST http://localhost:3001/api/domains/vinhomes/resident/reception-agent/operations/execute`
- `POST http://localhost:3001/api/domains/vinhomes/resident/reception-agent/operations/reconcile`

Hono proxy chỉ cho phép hai hậu tố `/execute` và `/reconcile`, chỉ nhận `POST`, yêu cầu cùng origin, rồi chuyển tiếp cookie phiên đến FastAPI. **Proxy Hono này bị loại khỏi commit API-only hiện tại**; việc nối browser/runtime qua Hono cần được đưa lên riêng. Backend FastAPI xác thực principal và tenant từ session/server context; không lấy quyền từ `context` do caller gửi. Trong chế độ demo loopback, gateway mới được cấu hình mới thêm header actor demo.

Các endpoint chỉ xác thực, kiểm tra quyền và trạng thái nghiệp vụ, đọc/ghi PostgreSQL rồi trả dữ liệu có cấu trúc cho Reception xử lý tiếp. Endpoint không gọi model, không phân loại nội dung, không chọn tool và không tự viết câu trả lời cho cư dân.

## Xác thực và request chung

Request dùng session cư dân đã đăng nhập. Backend lấy tenant và principal từ session/server context. `context.tenantId` và `context.principalId`, nếu được gửi, phải khớp dữ liệu đã xác thực. `bindingId`, `runId`, `requestId` chỉ dùng truy vết, không cấp quyền.

```json
{
  "operation": "create_ticket_draft",
  "input": {},
  "context": {
    "tenantId": "tenant-uuid",
    "principalId": "resident-user-id",
    "bindingId": "reception-binding-id",
    "runId": "run-id",
    "requestId": "request-id"
  },
  "idempotency_key": "unique-operation-key"
}
```

`idempotency_key` dài tối đa 128 ký tự. Backend lưu receipt cùng transaction nghiệp vụ. Gửi lại cùng operation, key và input sẽ nhận response đã lưu với `replayed: true`; dùng lại key với input khác trả `409 IDEMPOTENCY_KEY_REUSED`.

Response thành công giữ dữ liệu nghiệp vụ và có thêm `agentContext` gồm operation, facts, missing fields và resource context. Reception tự chọn bước tiếp theo dựa trên response.

## Luồng tạo ticket và bàn giao Supervisor

### 1. `create_ticket_draft`

```json
{
  "operation": "create_ticket_draft",
  "input": {
    "channel_id": "channel-uuid",
    "client_message_id": "resident-message-uuid",
    "incident": {
      "title": "Rò nước nhà vệ sinh",
      "description": "Nước rò dưới bồn rửa",
      "domain_id": "domain-uuid",
      "building_id": "building-uuid",
      "unit_id": "unit-uuid",
      "category_id": "category-uuid",
      "contact_name": "Nguyễn Văn A",
      "contact_phone": "+84900000000",
      "request_kind": "incident",
      "source_message_id": "message-uuid",
      "facts": [],
      "file_ids": []
    }
  },
  "context": {},
  "idempotency_key": "draft-channel-01"
}
```

Draft được lưu vào message của chat và trả `draftId`, `channelId`, các incident, `missingFields` và `ready`. Đây là bản nháp trong chat; ticket ID/code chỉ được cấp khi bàn giao tạo ticket thành công.

`contact_name` và `contact_phone` được lấy từ hồ sơ cư dân đã xác thực; giá trị do caller tự gửi không được dùng làm danh tính.

### 2. `get_verified_resident_context`

`input` để trống. Response trả hồ sơ cư dân và các căn hộ đã xác minh, gồm ID căn hộ, tòa nhà, site và domain. Backend chỉ lấy các membership còn hiệu lực của principal trong session.

### 3. `update_ticket_incident`

```json
{
  "operation": "update_ticket_incident",
  "input": {
    "channel_id": "channel-uuid",
    "draft_id": "draft-uuid",
    "index": 0,
    "fields": {
      "title": "Rò nước nhà vệ sinh",
      "description": "Nước rò dưới bồn rửa",
      "facts": [],
      "file_ids": []
    }
  },
  "context": {},
  "idempotency_key": "update-incident-01"
}
```

Chỉ cập nhật field trong allowlist của incident. `facts` tham chiếu message nguồn; `file_ids` dùng ID ảnh đã upload, không nhận bucket hoặc object key. Response trả bản draft mới cùng các field còn thiếu.

### 4. `submit_ticket_assessment`

Input gồm `channel_id`, `draft_id`, `index` và `assessment`:

```json
{
  "priority": "high",
  "severity": "major",
  "is_emergency": false,
  "reason": "Caller assessment reason"
}
```

Backend kiểm tra enum và quy tắc `is_emergency=true` phải có priority `critical`, rồi lưu assessment vào draft. Đây là dữ liệu do caller gửi, không phải backend tự triage. Khi handoff, assessment được lưu vào ticket và ticket event.

### 5. `resolve_management_destination`

Input gồm `channel_id`, `draft_id`, `index`. Backend kiểm tra căn hộ xác minh, domain, tòa, category và coverage đang hiệu lực. Response trả `managementUnitId`, `workspaceId`, `channelId`, Supervisor agent/version. Nếu dữ liệu chưa đủ hoặc BQL chưa có workspace, group chat hay Supervisor version, response trả `available: false` và `missingFields`; API không tự chọn một BQL khác.

### 6. `handoff_ticket`

Với draft, input gồm `channel_id`, `draft_id`, `index`, `handoff_reason` (`needs_staff`, `self_help_declined`, `self_help_failed` hoặc `emergency`). Backend kiểm tra draft, assessment, cư dân, coverage và Supervisor destination; trong cùng transaction, backend tạo ticket, tạo hoặc dùng team Supervisor hiện hành, lưu message schema_v2 vào mailbox và trả:

- snapshot ticket gồm ID/code, trạng thái, vị trí, category, BQL, assessment và ảnh;
- `team.id`, workspace và group chat;
- response handoff schema_v2, gồm trạng thái replay và business effect.

Reception dùng `ticket.id` để tiếp tục polling Supervisor, `team.id` để đối chiếu team và `handoff.business_effect` để biết backend đã ghi nhận gì; Reception runtime tự quyết định có chờ, hỏi thêm cư dân hay gửi bước khác.

Nếu thiếu field hoặc destination, response trả `accepted: false` cùng `missingFields`, không tạo ticket. Nếu gửi sẵn `input.message` hoặc `input.schema_v2`, operation sẽ kiểm tra và lưu message schema_v2 cho ticket/team đã tồn tại.

Supervisor nhận message qua inbox API schema_v2 và cần tự xử lý tiếp. Handoff chỉ xác nhận message đã được backend lưu; không xác nhận Supervisor đã đọc hay đã giải quyết ticket.

### 7. `register_supervisor_wait`

Input gồm `ticket_id` và tùy chọn `cursor`. Backend xác nhận ticket thuộc cư dân và có team Supervisor hiện hành, rồi trả `teamId`, `ticketGeneration`, `waitMode: "poll"` và `resultsPath`. Đây là thông tin polling; agent runtime quản lý vòng chờ.

### 8. `get_supervisor_event`

Input gồm `ticket_id`, tùy chọn `cursor` và `limit` (1–100). Response trả các result schema_v2 của Supervisor và `next_cursor`. Backend không resume hoặc chạy Reception thay runtime.

## Operation cho tin nhắn tiếp theo

- `append_ticket_information`: nhận message schema_v2 `information_provided`; kiểm tra pending request, message nguồn và file.
- `respond_supervisor_interaction`: nhận một message schema_v2 hợp lệ như `plan_approved`, `plan_rejected`, `plan_change_requested` hoặc `information_provided`; backend áp dụng đúng kiểm tra pending/version của schema_v2.
- `request_ticket_cancellation`: nhận message schema_v2 `cancel_requested`. Đây chỉ là yêu cầu hủy, không tự chuyển ticket sang cancelled.
- `get_ticket_status`: input `ticket_id`; trả snapshot trạng thái công khai và timeline của ticket thuộc cư dân.
- `escalate_emergency`: với draft, lưu assessment critical do caller gửi. Với ticket hiện hữu, yêu cầu `ticket_id`, `reason`, `source_message_id`; backend đánh dấu critical/emergency, ghi event và xếp notification in-app cho BQL. Response chỉ xác nhận notification đang pending trong database, không xác nhận có người đã nhận hoặc dịch vụ khẩn cấp bên ngoài đã được gọi.
- `process_self_help`: hiện trả `501` đến khi có dịch vụ knowledge/RAG cho phạm vi cư dân. Endpoint không tự sinh hướng dẫn.

Với `respond_supervisor_interaction` và các operation gửi Supervisor, input `message` (hoặc `schema_v2`) phải đầy đủ theo schema_v2; backend kiểm tra ticket, team, generation, version, source message, file và pending state trước khi lưu.

## Reconcile khi timeout

`POST /internal/reception/operations/reconcile` nhận cùng `operation`, `input`, `context` và `idempotency_key` đã dùng trong execute. Endpoint chỉ đọc receipt, không chạy lại operation:

```json
{
  "operation": "create_ticket_draft",
  "input": {"channel_id": "channel-uuid", "incident": {}},
  "context": {},
  "idempotency_key": "draft-channel-01"
}
```

Response có `found`, `status` (`completed`, `in_progress` hoặc `not_found`) và `result` đã lưu nếu operation hoàn tất. Cùng key nhưng operation/input khác trả `409`.

## Upload ảnh hội thoại

Reception chỉ chuyển `file_id` vào draft/schema_v2. API upload hiện có:

1. `POST /resident/chats/{channel_id}/image-uploads` — kiểm tra metadata file và cấp thông tin upload.
2. `PUT /image-uploads/{upload_id}/content` — gửi bytes file.
3. `POST /image-uploads/{upload_id}/complete` — xác nhận file đã sẵn sàng.
4. `GET /resident/chats/{channel_id}/images` — đọc ảnh của hội thoại.
5. `POST /tickets/{ticket_id}/conversation-images` — gắn các file ID được chọn vào ticket. `handoff_ticket` tự gắn các `file_ids` đã chọn trong draft trước khi gửi message Supervisor.

Backend kiểm tra quyền sở hữu, trạng thái, loại/kích thước và checksum; agent không truyền bucket hoặc object key.

## Lỗi nghiệp vụ chính

- `401/403`: session không hợp lệ, principal/tenant mismatch hoặc không có quyền trên tài nguyên.
- `404`: chat, draft, ticket hoặc Supervisor result không thuộc scope của cư dân.
- `409`: idempotency key bị dùng với payload khác, ticket/team/version/pending state đã đổi hoặc destination bị mơ hồ.
- `422`: input sai schema, enum, field bắt buộc, source message hoặc file reference.
- `501` của `process_self_help`: resident knowledge/RAG chưa được cấu hình.

## Phân định trách nhiệm

```text
Reception Agent
  → execute(operation, input, context, idempotency_key)
  → PostgreSQL V3: draft / ticket / assessment / team / schema_v2 message
  → response nghiệp vụ + agentContext
  → Reception Agent chọn và gọi bước kế tiếp
  → reconcile khi không rõ request trước đã commit hay chưa
```

Backend không gọi AI, không phân loại mô tả cư dân và không tự quyết định câu trả lời. Backend chịu trách nhiệm xác thực session, phạm vi dữ liệu, kiểm tra schema/state, ghi dữ liệu và trả kết quả đã lưu.
