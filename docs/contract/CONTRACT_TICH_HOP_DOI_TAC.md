# Contract API do AI Workforce Platform cung cấp cho đối tác

Ngày ban hành: 09/10/2026. Cập nhật: 10/10/2026.

Phiên bản contract: `1.3-draft` — đồng bộ kế hoạch 1.4.3; đây là đặc tả mục tiêu, chưa xác nhận API đã triển khai.

Base path: `/workforce/v1`

## 1. Mục đích tài liệu

Tài liệu này được gửi cho đội kỹ thuật của đối tác để họ biết:

- Backend phục vụ người dùng cuối gọi API nào của platform.
- Backend nghiệp vụ/provider gọi API nào để cập nhật operation dài hạn, nếu integration có capability này.
- Request phải gửi field nào.
- Platform trả response nào.
- Backend khách hàng biết bước tiếp theo qua `next_action` và chỉ dùng SSE/history khi cần theo dõi.
- Hai bên xử lý authentication, idempotency, retry, event ordering và lỗi ra sao.

Trong contract này, **mọi API đều do AI Workforce Platform cung cấp**. Đối tác là bên chủ động kết nối và gọi platform:

```text
Backend khách hàng ──POST/GET/SSE──> AI Workforce Platform
Backend nghiệp vụ/provider ──POST/GET──> AI Workforce Platform (khi có external tracking)
```

Platform không yêu cầu đối tác xây một REST API để platform gọi ngược lại. Platform không gửi outbound webhook tới hệ thống đối tác trong contract v1.

MCP nằm ngoài phạm vi tài liệu này. Đối tác chỉ cần cung cấp MCP đã thống nhất qua quy trình onboarding; platform tự kết nối, discovery tool và dùng các tool đó để build/run agent. Cách đối tác tổ chức code/tool bên trong MCP không thuộc contract API này.

Đây chỉ là hướng dẫn tích hợp gửi cho đối tác. Tài liệu không phân công thành viên platform, không quy định folder/module/persistence nội bộ và không yêu cầu đối tác biết group chat/Leader được cài đặt như thế nào. Các ID nội bộ như `group_id`, scope, agent ID và manager account không thuộc request contract.

Các endpoint trong tài liệu là contract mục tiêu của Workforce v1. API legacy như `/partner/tickets` hiện có không được dùng thay contract này cho tích hợp mới nếu chưa qua adapter và kiểm tra scope mới.

## 2. Các hệ thống tham gia

| Hệ thống | Trách nhiệm |
|---|---|
| App người dùng cuối | Gửi thao tác tới backend khách hàng và hiển thị kết quả |
| Backend khách hàng của đối tác | Xác thực người dùng, gọi request/reply/approval/close; theo `next_action` để quyết định có đọc SSE/history hay không |
| Backend nghiệp vụ/provider của đối tác | Chỉ với operation dài hạn: xác thực actor cập nhật, lưu tiến độ thật rồi gọi Provider Event API |
| AI Workforce Platform | Mapping đúng ban quản lý, chọn agent, gọi tool MCP, lưu workflow/event và trả dữ liệu đúng audience |
| App nhân viên/provider | Nếu có: gọi backend nghiệp vụ; không giữ API key của platform |

Backend khách hàng và backend nghiệp vụ/provider có thể là cùng một hệ thống vật lý. Nếu dùng Provider Event API, credential publish event phải có purpose/quyền riêng.

## 3. Nguyên tắc lifecycle độc lập lĩnh vực

- Một HTTP `POST` chỉ nhận một command và trả một response. POST request/reply mặc định chờ kết quả lượt agent hiện tại có thời hạn rồi trả `200` kèm nội dung trả lời và IDs.
- `202` chỉ có nghĩa lượt hiện tại chưa xong trước HTTP deadline; nó không có nghĩa workflow bắt buộc chờ nhân viên/provider.
- Response/GET request luôn trả `workflow_state` và `next_action`. Backend thực hiện bước tiếp theo theo field này, không suy luận từ tên lĩnh vực hoặc nội dung text.
- Response-only: tra cứu/giải đáp read-only có thể trả `closed/none`; không cần SSE, Provider Event hoặc POST close.
- Interactive: lựa chọn, bổ sung dữ kiện, consent hoặc xác nhận dùng `awaiting_user/submit_reply`, `awaiting_approval/submit_approval`, `awaiting_confirmation/confirm_close`.
- External-tracking: chỉ khi tool trả operation pending và integration có tracking, platform dùng `waiting_external_event/watch_events`; backend provider gửi event hoặc platform dùng MCP status-query theo protocol.
- Một workflow có thể chuyển pattern trong cùng nghiệp vụ. Ví dụ booking có thể xác nhận ngay và không cần event, hoặc trả pending rồi cần tracking.
- Khi chờ user/event, platform lưu checkpoint và kết thúc lượt agent; không giữ LLM, transaction hoặc request POST mở.
- SSE là kênh tùy chọn/recovery. Chỉ `watch_request` hoặc `watch_events` yêu cầu backend theo dõi; nếu đã mở SSE thì có thể giữ khi POST tin nhắn tiếp theo.
- Mất SSE, đóng app, nhận `202` hoặc hoàn thành một lượt agent không tự đóng workflow đang mở.
- Chat tiếp dùng `workflow_reply` với workflow/hội thoại cũ, chỉ thay ID của tin nhắn; không tạo phiên chat hay ticket mới.
- Nếu một người dùng mở hai ticket/hộp chat, backend phải cấp hai `external_ticket_id` và hai `external_conversation_id` khác nhau. Mỗi tin nhắn giữ đúng bộ ID của hộp đang gửi; platform không suy đoán ticket từ nội dung.
- Workflow có side effect/explicit confirmation chỉ đóng bằng POST close hợp lệ. Read-only response-only có thể auto-close theo policy platform đã publish; đối tác không gửi cờ để tự chọn policy này.
- Nếu lượt agent chưa xong khi hết thời gian chờ, POST trả `202` kèm IDs để theo dõi qua SSE/history/GET request. `202` đã kết thúc response của POST, không có response thứ hai trên cùng request.
- Platform tự mapping request tới đúng domain, area và tài khoản ban quản lý. Đối tác không được gửi các ID nội bộ này.

`next_action` có các giá trị:

| Giá trị | Backend đối tác thực hiện |
|---|---|
| `none` | Không còn hành động bắt buộc; workflow đã terminal |
| `submit_reply` | Gửi `workflow_reply` khi người dùng chọn/bổ sung thông tin |
| `submit_approval` | Hiển thị approval và gửi decision tới approval endpoint |
| `watch_request` | Lượt trả `202`; theo dõi bằng SSE hoặc GET request/history |
| `watch_events` | Operation bên ngoài còn chạy; dùng SSE/history |
| `confirm_close` | Hỏi người dùng xác nhận rồi POST close |
| `resolve_attention` | Hiển thị trạng thái cần hỗ trợ/đối soát; không tự retry side effect |

## 4. Môi trường và version

URL minh họa:

```text
Sandbox:    https://sandbox-api.platform.example/workforce/v1
Production: https://api.platform.example/workforce/v1
```

Hai bên thay các URL minh họa bằng URL thật trong onboarding.

Quy tắc version:

- Major version nằm trong URL.
- Thay đổi additive có thể giữ `/v1`.
- Thay đổi breaking phải dùng `/v2` hoặc có giai đoạn migration được thống nhất.
- Mọi public event có `schema_version`.
- Sandbox và production dùng credential riêng.
- Timestamp dùng RFC 3339 UTC, ví dụ `2026-10-09T02:30:00Z`.
- ID do đối tác cấp là opaque string, phân biệt hoa thường. ID platform trong production dùng UUID; các nhãn `conv_001`, `wf_001`, `evt_003` trong ví dụ chỉ để dễ đọc.

## 5. Onboarding và credential

Trước khi gọi API, hai bên phải thống nhất:

| Nhóm | Dữ liệu |
|---|---|
| Partner client | `partner_client_id`, môi trường và domain được cấp |
| Ban quản lý | `external_management_ref` được mapping tới đúng tài khoản ban quản lý |
| Residence | Khi áp dụng: `residence_id` và `external_user_id` |
| Ticket binding | Chốt `ticket_binding_mode=required` nếu app có ticket/hộp chat; khi đó mỗi ticket phải có external_ticket_id và external_conversation_id riêng |
| Customer credential | Các quyền được cấp: submit_request, reply, read_result, receive_events, submit_consent, close_workflow; onboarding confirm_route/sync_residence khi được cấp riêng |
| Provider credential | `provider_integration_id`, publish_job_event và read_event_receipt |
| Event schema | Chỉ khi có external tracking: event type, state transition và version của backend nghiệp vụ/provider |
| Vận hành | Rate limit, payload limit, retention và đầu mối kỹ thuật |

API key thuộc domain không tự cấp quyền gửi request tới mọi ban quản lý trong domain. `external_management_ref` phải được hai bên xác nhận trước.

### 5.1. API key

Backend đối tác gửi:

```http
Authorization: ApiKey dp_<key-id>.<secret>
```

Plaintext secret chỉ cấp một lần và chỉ được lưu trong backend/secrets manager. Không đặt API key trong mobile app, browser, source code, log hoặc file được commit.

Mỗi credential có:

- Môi trường.
- `partner_client_id` hoặc `provider_integration_id`.
- Trạng thái và thời hạn.
- Danh sách operation được phép.
- Phạm vi domain/route liên quan.

### 5.2. Provider event signature

Request cập nhật của backend nghiệp vụ/provider cần API key và chữ ký body:

```http
Authorization: ApiKey dp_<provider-key-id>.<secret>
X-Partner-Timestamp: 1791513000
X-Partner-Key-Id: provider-signing-key-01
X-Partner-Signature: v1=<lowercase-hex-hmac-sha256>
```

Chuỗi ký:

```text
<unix_timestamp_seconds>.<raw_http_body_bytes>
```

Platform kiểm tra HMAC-SHA256 constant-time. Clock skew mặc định tối đa 5 phút. Bên gửi phải ký raw bytes trước khi request được gửi; không parse rồi serialize lại bằng format khác.

## 6. Quy ước chung

### 6.1. Header

| Header | Bắt buộc | Ý nghĩa |
|---|---|---|
| `Authorization` | Có | Machine credential |
| `Content-Type: application/json` | Có với body JSON | Dữ liệu UTF-8 |
| `Accept: application/json` | Nên | Response JSON |
| `X-Correlation-Id` | Nên | Trace kỹ thuật; không thay idempotency ID |
| `Last-Event-ID` | Khi reconnect SSE | Event cuối client đã xử lý thành công |

### 6.2. Giới hạn mặc định

| Thành phần | Giới hạn |
|---|---|
| ID do đối tác cấp | 1–200 ký tự UTF-8, không có control character |
| `external_management_ref` | 1–128 ký tự |
| Message text | 1–20.000 ký tự |
| `data` của provider event | Tối đa 64 KiB |
| Tổng JSON request | Tối đa 256 KiB |
| History page | Mặc định 100, tối đa 500 event |
| Chờ kết quả POST request/reply | Mặc định đề xuất 25 giây, chốt giá trị thật khi onboarding; timeout proxy/client phải lớn hơn giới hạn này |
| Clock skew signature | Mặc định 5 phút |

Giới hạn production được ghi trong onboarding. Vượt giới hạn trả `413` hoặc `429`.

V1 chuẩn hóa message text. Ảnh/file cần asset upload contract riêng và chỉ tham chiếu bằng `asset_id`. Platform không tải URL tùy ý nằm trong message. Gửi attachment khi chưa được cấp capability trả `422 UNSUPPORTED_MESSAGE_PART`.

### 6.3. Error response

```json
{
  "error": {
    "code": "ROUTE_NOT_AUTHORIZED",
    "message": "Request is not authorized for the configured management route.",
    "details": {},
    "request_id": "req_internal_01",
    "retryable": false
  }
}
```

| HTTP | Ý nghĩa |
|---|---|
| `400` | JSON hoặc tổ hợp field sai |
| `401` | Credential/signature sai, hết hạn hoặc revoked |
| `403` | Thiếu operation hoặc route/audience không hợp lệ |
| `404` | Không tìm thấy tài nguyên trong phạm vi caller |
| `409` | Idempotency, revision, route, correlation hoặc state conflict |
| `410` | Event cursor hết retention |
| `413` | Payload quá lớn |
| `422` | Schema hoặc giá trị nghiệp vụ sai |
| `429` | Vượt rate limit |
| `500/503` | Chưa persist/không thể xử lý; xem `retryable` |

`details` không chứa secret, prompt, trace nội bộ, danh sách manager hoặc dữ liệu của người dùng khác.

Các mã lỗi binding quan trọng:

| Code | HTTP | Khi nào xảy ra | Cách xử lý phía đối tác |
|---|---:|---|---|
| `EXTERNAL_TICKET_REQUIRED` | 422 | Route/tích hợp ticketed thiếu `external_ticket_id` | Gửi lại đúng ID ticket của hộp chat |
| `TICKET_ALREADY_BOUND` | 409 | Dùng `start_workflow` lần nữa cho external ticket đã có workflow | Dùng `workflow_reply` với workflow đã lưu; không tạo ticket mới |
| `CONVERSATION_ALREADY_BOUND` | 409 | Dùng một `external_conversation_id` cho external ticket khác | Cấp ID hộp chat mới và không trộn lịch sử |
| `WORKFLOW_BINDING_MISMATCH` | 409 | External user/ticket/conversation/workflow không cùng binding | Dừng gửi, đối chiếu mapping local; không tự retry với ID đoán |
| `WORKFLOW_REFERENCE_REQUIRED` | 422 | `workflow_reply` thiếu `workflow_id` | Dùng workflow_id platform đã trả cho ticket đó |
| `WORKFLOW_CLOSED` | 409 | Gửi reply vào workflow đã đóng | Không tự mở lại; tạo ticket mới chỉ khi người dùng thực sự tạo việc mới |

Các GET Customer API (request, snapshot, history, SSE) bắt buộc query `external_user_id` đã được backend đối tác xác thực. Platform so khớp query với audience đã lưu cùng client/grant; giá trị query không tự cấp quyền. POST Customer API lấy assertion này từ body. API key luôn nằm trong Authorization header. GET SSE/history cần cả `read_result` và `receive_events`; GET request/snapshot cần `read_result`. Các URL trong JSON response là đường dẫn cơ sở; client thêm query và URL-encode giá trị khi gọi.

HTTP `200` cho biết endpoint trả thành công representation/kết quả lượt xử lý; phải đọc `request_status`, `workflow_state`, `next_action`, result và lỗi nghiệp vụ để biết bước tiếp theo. `202` chỉ cho biết request vẫn đang xử lý, không nói operation bên ngoài thành công hay thất bại.

## 7. Định danh

| Trường | Bên tạo | Ý nghĩa |
|---|---|---|
| `external_request_id` | Backend khách hàng | Một command/message duy nhất |
| `external_user_id` | Backend khách hàng | Cư dân trong namespace partner |
| `external_ticket_id` | Backend khách hàng | Ticket nghiệp vụ phía đối tác; bắt buộc với tích hợp ticketed và ổn định suốt vòng đời ticket |
| `external_conversation_id` | Backend khách hàng | Hộp chat phía đối tác; mỗi ticket đồng thời phải có một ID riêng |
| `external_management_ref` | Hai bên xác nhận | Mã ban quản lý phía đối tác |
| `request_id` | Platform | Bản ghi nhận một command |
| `conversation_id` | Platform | Hội thoại đã bind owner/audience |
| `workflow_id` | Platform | Một yêu cầu nghiệp vụ dài hạn |
| `ticket_id` | Platform | Ticket nghiệp vụ nội bộ nếu được tạo; chỉ là output, không dùng thay external_ticket_id trong request |
| `external_job_id` | Backend nghiệp vụ/provider | Công việc/operation trong provider namespace |
| `client_reference` | Platform | Correlation platform đã lưu trước khi gọi tool |
| `external_event_id` | Backend nghiệp vụ/provider | Event duy nhất trong provider namespace |
| `receipt_id` | Platform | Biên nhận provider event |
| `event_id` | Platform | Public event duy nhất cho SSE/history |
| `sequence` | Platform | Thứ tự commit trong một conversation |

Không được dùng bất kỳ ID nào trong bảng làm bearer credential. Namespace của ID do đối tác cấp là `partner_client_id`; backend phải bảo đảm `external_request_id` duy nhất và cặp user/ticket/conversation ổn định. `workflow_id`, `conversation_id` và `ticket_id` do platform trả phải được lưu cùng record ticket phía đối tác; đối tác không tạo hoặc đoán các ID này.

## 8. API onboarding route

### 8.1. Xác nhận route ban quản lý

Manager đã xác minh tạo pending route trên platform. Đối tác nhận `route_id` và revision qua kênh onboarding rồi xác nhận bằng backend đúng `partner_client_id`:

```http
POST /workforce/v1/partner/routes/{route_id}/confirm
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

Request:

```json
{
  "schema_version": "1",
  "external_management_ref": "BQL-OP1-A",
  "expected_revision": 1
}
```

Response:

```json
{
  "route_id": "route_001",
  "external_management_ref": "BQL-OP1-A",
  "status": "active",
  "revision": 2,
  "allowed_operations": [
    "submit_request",
    "reply",
    "read_result",
    "receive_events",
    "submit_consent",
    "close_workflow"
  ]
}
```

Response không trả domain, area hoặc manager ID nội bộ. Partner client khác không được xác nhận route này. Ref conflict trả `409 ROUTE_CONFLICT`.

### 8.2. Đồng bộ residence

Áp dụng khi request gắn với căn hộ/địa điểm đã đăng ký:

```http
PUT /workforce/v1/partner/residences/{residence_id}
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

Request:

```json
{
  "schema_version": "1",
  "external_user_id": "resident-123",
  "external_management_ref": "BQL-OP1-A",
  "status": "active",
  "expected_revision": 3
}
```

Response `200` khi cập nhật hoặc `201` khi tạo:

```json
{
  "residence_id": "S1-0205",
  "external_user_id": "resident-123",
  "external_management_ref": "BQL-OP1-A",
  "status": "active",
  "revision": 4,
  "updated_at": "2026-10-09T01:50:00Z"
}
```

`PUT` idempotent. Platform kiểm tra route thuộc đúng client/domain và còn active. Request có residence/ref/user không khớp bị từ chối. Đổi route không chuyển các workflow cũ sang manager mới.

## 9. Customer API

### 9.1. Gửi yêu cầu mới

Quyền: `submit_request` trên route đã xác nhận.

```http
POST /workforce/v1/partner/requests
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

Request:

```json
{
  "schema_version": "1",
  "command_type": "start_workflow",
  "external_request_id": "vh-message-001",
  "external_management_ref": "BQL-OP1-A",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "residence_id": "S1-0205",
  "timezone": "Asia/Ho_Chi_Minh",
  "message": {
    "type": "text",
    "text": "Hãy gọi thợ đến sửa ống nước nhà tôi bị vỡ."
  }
}
```

| Field | Quy tắc |
|---|---|
| `schema_version` | Bắt buộc, `"1"` |
| `command_type` | Bắt buộc, `start_workflow` |
| `external_request_id` | Bắt buộc, duy nhất trong partner client |
| `external_management_ref` | Bắt buộc, route active |
| `external_user_id` | Bắt buộc, người dùng/audience do backend đối tác xác thực |
| `external_ticket_id` | Bắt buộc với route/tích hợp ticketed; ID ticket phía đối tác, ổn định và không tái sử dụng cho việc khác |
| `external_conversation_id` | Bắt buộc, hộp chat phía đối tác; một ticket đồng thời dùng một conversation ID riêng |
| `message` | Bắt buộc, object text như ví dụ |
| `residence_id` | Bắt buộc khi route nghiệp vụ cần residence |
| `timezone` | IANA timezone khi có; không có thì dùng timezone đã thống nhất của route |

Đối tác không gửi `ticket_id`, `conversation_id`, `group_id`, tenant_id, domain_id, area_id, manager_account_id, route_id, agent_id, tool_id, credential, role hoặc execution mode trong body. `external_ticket_id` là ID của đối tác; `ticket_id` trong response là ID nội bộ khác.

Payload trên dùng sửa chữa làm ví dụ dữ liệu, không phải schema cố định theo lĩnh vực. Du lịch, khách sạn, vận chuyển, CSKH hoặc domain khác vẫn dùng cùng envelope; nội dung message và tool/policy đã publish quyết định workflow.

Platform lưu request/workflow/job trước, sau đó chờ kết quả lượt agent hiện tại trong giới hạn thời gian. Nếu lượt đó hoàn tất trong thời hạn, POST trả ngay nội dung trả lời đã lưu:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "request_id": "req_001",
  "request_status": "completed",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "conversation_id": "conv_001",
  "workflow_id": "wf_001",
  "workflow_state": "waiting_external_event",
  "next_action": "watch_events",
  "workflow_revision": 4,
  "ticket_id": "ticket_001",
  "result": {
    "messages": [
      {
        "message_id": "msg_003",
        "workflow_id": "wf_001",
        "sender": "assistant",
        "text": "Đã gọi thành công thợ Nguyễn Văn A đến hỗ trợ sửa ống nước.",
        "created_at": "2026-10-09T02:00:06Z"
      }
    ]
  },
  "error": null,
  "accepted_at": "2026-10-09T02:00:00Z",
  "completed_at": "2026-10-09T02:00:06Z",
  "status_url": "/workforce/v1/partner/requests/req_001",
  "conversation_url": "/workforce/v1/partner/conversations/conv_001",
  "event_stream_url": "/workforce/v1/partner/conversations/conv_001/events"
}
```

POST đã kết thúc, workflow còn mở vì response có `next_action=watch_events`; backend hiển thị result.messages rồi mở GET SSE hoặc đọc history. Với `submit_reply`, `submit_approval` hoặc `confirm_close`, backend không bắt buộc mở SSE. Với `closed/none`, không còn bước theo dõi. Cùng message khi replay giữ nguyên message_id; client chỉ hiển thị một lần.

`status_url`, `conversation_url` và `event_stream_url` là link discoverability/recovery, không phải mệnh lệnh phải gọi tất cả. `next_action` mới là chỉ dẫn điều phối phía client.

Fallback khi lượt chưa xong trước giới hạn chờ:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
```

```json
{
  "request_id": "req_001",
  "request_status": "running",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "conversation_id": "conv_001",
  "workflow_id": "wf_001",
  "workflow_state": "active",
  "next_action": "watch_request",
  "workflow_revision": 2,
  "ticket_id": null,
  "result": null,
  "error": null,
  "accepted_at": "2026-10-09T02:00:00Z",
  "completed_at": null,
  "status_url": "/workforce/v1/partner/requests/req_001",
  "conversation_url": "/workforce/v1/partner/conversations/conv_001",
  "event_stream_url": "/workforce/v1/partner/conversations/conv_001/events"
}
```

Request còn pending có thể là accepted/queued/running và trả `next_action=watch_request`. Backend dùng SSE hoặc GET request/history để nhận kết quả khi sẵn sàng; không chờ response thứ hai từ POST. Mất kết nối HTTP không tự hủy job đã lưu hoặc tạo lại workflow.

Idempotency dùng namespace chung của partner client cho request/reply/approval/close:

- Cùng external_request_id và payload chuẩn hóa: tham chiếu đúng request đã có, không chạy lượt mới.
- Pending trả 202; đã có kết luận trả 200 cùng persisted result. HTTP status có thể thay đổi theo tiến độ, IDs và nội dung kết quả đã commit không được tạo lại.
- Cùng ID nhưng khác command/resource/body/ref/user: 409 IDEMPOTENCY_CONFLICT.
- Retry sau remap chỉ truy cập request gốc nếu caller còn quyền, không tạo workflow dưới manager mới.

Kết quả terminal failed/blocked dùng HTTP 200 với request_status, workflow_state, `next_action=resolve_attention` hoặc `none` và error public; lỗi auth/schema/conflict trước tiếp nhận dùng HTTP 4xx theo mục 6.3.

#### 9.1.1. Một người dùng có hai ticket/hai hộp chat

Backend đối tác phải lưu mapping theo từng hộp chat, ví dụ:

| Hộp chat | ID đối tác gửi trong mọi POST | ID platform cần lưu sau response |
|---|---|---|
| Sửa ống nước | `external_user_id=resident-123`, `external_ticket_id=TICKET-A`, `external_conversation_id=CHAT-A` | `workflow_id=wf_A`, `conversation_id=conv_A`, `ticket_id` nếu có |
| Đặt khách sạn | `external_user_id=resident-123`, `external_ticket_id=TICKET-B`, `external_conversation_id=CHAT-B` | `workflow_id=wf_B`, `conversation_id=conv_B`, `ticket_id` nếu có |

Quy tắc phía đối tác:

1. Lần đầu người dùng tạo hộp A, gửi `start_workflow` với A; lần đầu tạo hộp B, gửi `start_workflow` với B. `external_request_id` của hai command phải khác nhau.
2. Tin nhắn tiếp theo trong hộp A gửi `workflow_reply` với TICKET-A, CHAT-A và wf_A. Hộp B luôn gửi bộ B. Không gửi `group_id`; platform tự định tuyến nội bộ.
3. Nếu cần realtime, mở SSE riêng bằng `conv_A` cho hộp A và `conv_B` cho hộp B. Event có `external_ticket_id` để backend kiểm tra phòng thủ trước khi cập nhật UI.
4. Đóng wf_A không đóng wf_B. Không tái sử dụng TICKET-A/CHAT-A cho một việc mới sau khi đóng; tạo ID mới cho ticket mới.

Platform từ chối toàn bộ command nếu các ID bị ghép chéo và không chuyển message sang một ticket “có vẻ phù hợp”.

### 9.2. Gửi reply vào workflow đang có

Dùng cùng endpoint:

```http
POST /workforce/v1/partner/requests
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

```json
{
  "schema_version": "1",
  "command_type": "workflow_reply",
  "external_request_id": "vh-message-002",
  "external_management_ref": "BQL-OP1-A",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "workflow_id": "wf_001",
  "message": {
    "type": "text",
    "text": "Tôi có thể tiếp thợ trong khoảng 14 giờ đến 16 giờ."
  }
}
```

Quy tắc:

- `workflow_reply` bắt buộc có `workflow_id`.
- `start_workflow` không được có `workflow_id`.
- Reply phải cùng owner/audience/external ticket/conversation/workflow binding.
- Mỗi reply có `external_request_id` mới.
- Platform không dùng nội dung tự nhiên để đoán workflow cần cập nhật.

Response dùng cùng cấu trúc mục 9.1: `200` với kết quả lượt reply và next_action mới, hoặc `202/watch_request` khi còn pending. `request_id` mới; `external_ticket_id`, `conversation_id`, `workflow_id` và ticket giữ nguyên. Platform tiếp tục context/session đang có; một `run_id` nội bộ mới chỉ ghi nhận lượt xử lý, không phải phiên chat khác.

Thiếu workflow_id trả `422 WORKFLOW_REFERENCE_REQUIRED`; thiếu external ticket trên route ticketed trả `422 EXTERNAL_TICKET_REQUIRED`; tuple user/ticket/conversation/workflow không khớp trả `409 WORKFLOW_BINDING_MISMATCH`; workflow đã đóng trả `409 WORKFLOW_CLOSED`. Không tự tạo ticket mới nếu reply không hợp lệ. `start_workflow` là hành động chủ động tạo việc mới và phải dùng external ticket/conversation mới; không dùng cờ `create_new_workflow`. Khi SSE đã mở, tiếp tục dùng stream đó trong lúc gửi reply; response POST và event có thể đến khác thứ tự nên luôn dedupe message_id.

### 9.3. Xem trạng thái một request

```http
GET /workforce/v1/partner/requests/{request_id}?external_user_id=resident-123
Authorization: ApiKey dp_<key-id>.<secret>
```

Response:

```json
{
  "request_id": "req_001",
  "request_status": "completed",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "conversation_id": "conv_001",
  "workflow_id": "wf_001",
  "workflow_state": "waiting_external_event",
  "next_action": "watch_events",
  "ticket_id": "ticket_001",
  "accepted_at": "2026-10-09T02:00:00Z",
  "completed_at": "2026-10-09T02:00:06Z",
  "last_event_id": "evt_003",
  "workflow_revision": 4,
  "result": {
    "messages": [
      {
        "message_id": "msg_003",
        "workflow_id": "wf_001",
        "sender": "assistant",
        "text": "Đã gọi thành công thợ Nguyễn Văn A đến hỗ trợ sửa ống nước.",
        "created_at": "2026-10-09T02:00:06Z"
      }
    ]
  },
  "error": null
}
```

`request_status`:

- `accepted`
- `queued`
- `running`
- `completed`
- `failed`
- `blocked`

`workflow_state`:

- `accepted`
- `active`
- `waiting_external_event`
- `awaiting_user`
- `awaiting_approval`
- `awaiting_confirmation`
- `needs_attention`
- `blocked_authorization`
- `blocked_route_changed`
- `closed`

Request có thể `completed` trong khi workflow vẫn `waiting_external_event`. Hai trạng thái không được dùng thay nhau.

`next_action` là projection do platform tính từ state + policy + operation hiện tại. Client không gửi field này trong request và không tự suy diễn state transition. Mapping chuẩn: closed→none, awaiting_user→submit_reply, awaiting_approval→submit_approval, awaiting_confirmation→confirm_close, waiting_external_event→watch_events; request pending trước deadline response→watch_request; needs_attention→resolve_attention.

### 9.4. Lấy snapshot conversation

```http
GET /workforce/v1/partner/conversations/{conversation_id}?external_user_id=resident-123
Authorization: ApiKey dp_<key-id>.<secret>
```

Response:

```json
{
  "conversation_id": "conv_001",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "external_user_id": "resident-123",
  "workflows": [
    {
      "workflow_id": "wf_001",
      "external_ticket_id": "partner-ticket-plumbing-001",
      "ticket_id": "ticket_001",
      "state": "waiting_external_event",
      "next_action": "watch_events",
      "revision": 4
    }
  ],
  "messages": [
    {
      "message_id": "msg_003",
      "workflow_id": "wf_001",
      "sender": "assistant",
      "text": "Yêu cầu đã được tiếp nhận và đã phân công kỹ thuật viên.",
      "created_at": "2026-10-09T02:00:06Z"
    }
  ],
  "snapshot_cursor": "evt_003"
}
```

Snapshot và `snapshot_cursor` được đọc nhất quán, gồm trạng thái workflow, messages và pending approvals được phép xem. Sau snapshot, client đọc history hoặc mở SSE từ cursor này. Nếu chưa từng có event thì snapshot_cursor=null, mở SSE không cursor. Snapshot khôi phục trạng thái hiện tại; không khôi phục lịch sử đã hết retention.

### 9.5. Lấy event history

```http
GET /workforce/v1/partner/conversations/{conversation_id}/event-history?external_user_id=resident-123&after_cursor=evt_003&limit=100
Authorization: ApiKey dp_<key-id>.<secret>
```

Response:

```json
{
  "items": [
    {
      "schema_version": "1",
      "event_id": "evt_004",
      "sequence": 4,
      "event_type": "ticket.status_changed",
      "occurred_at": "2026-10-09T02:30:00Z",
      "recorded_at": "2026-10-09T02:30:01Z",
      "conversation_id": "conv_001",
      "external_ticket_id": "partner-ticket-plumbing-001",
      "external_conversation_id": "vh-chat-789",
      "external_user_id": "resident-123",
      "workflow_id": "wf_001",
      "ticket_id": "ticket_001",
      "payload": {
        "status": "technician_on_the_way",
        "estimated_arrival_minutes": 20
      }
    }
  ],
  "next_cursor": "evt_004",
  "has_more": false
}
```

Cursor thuộc conversation/audience khác bị từ chối. Cursor hết retention trả:

```http
HTTP/1.1 410 Gone
```

```json
{
  "error": {
    "code": "EVENT_CURSOR_EXPIRED",
    "message": "Load a new conversation snapshot before reconnecting.",
    "details": {
      "snapshot_url": "/workforce/v1/partner/conversations/conv_001"
    },
    "request_id": "req_internal_02",
    "retryable": false
  }
}
```

Client lấy snapshot mới rồi tiếp tục từ `snapshot_cursor`.

### 9.6. Mở SSE nhận nhiều trạng thái

```http
GET /workforce/v1/partner/conversations/{conversation_id}/events?external_user_id=resident-123
Authorization: ApiKey dp_<key-id>.<secret>
Accept: text/event-stream
Last-Event-ID: evt_003
```

Ví dụ trên là reconnect sau khi client đã xử lý evt_003. Lần đầu mở SSE bỏ Last-Event-ID; platform replay event đã lưu từ đầu hội thoại, rồi tiếp tục live. Nếu đã có SSE, giữ stream đó cho các POST tiếp theo. Response thành công của GET là `200` với Content-Type `text/event-stream; charset=utf-8`; mỗi frame kết thúc bằng dòng trống.

Platform giữ kết nối `GET` này để gửi nhiều event:

```text
id: evt_004
event: ticket.status_changed
data: {"schema_version":"1","event_id":"evt_004","sequence":4,"event_type":"ticket.status_changed","occurred_at":"2026-10-09T02:30:00Z","recorded_at":"2026-10-09T02:30:01Z","conversation_id":"conv_001","external_ticket_id":"partner-ticket-plumbing-001","external_conversation_id":"vh-chat-789","external_user_id":"resident-123","workflow_id":"wf_001","ticket_id":"ticket_001","payload":{"status":"technician_on_the_way","estimated_arrival_minutes":20}}

id: evt_005
event: assistant.message
data: {"schema_version":"1","event_id":"evt_005","sequence":5,"event_type":"assistant.message","occurred_at":"2026-10-09T02:30:02Z","recorded_at":"2026-10-09T02:30:02Z","conversation_id":"conv_001","external_ticket_id":"partner-ticket-plumbing-001","external_conversation_id":"vh-chat-789","external_user_id":"resident-123","workflow_id":"wf_001","ticket_id":"ticket_001","payload":{"message_id":"msg_005","text":"Kỹ thuật viên đang di chuyển và dự kiến đến trong 20 phút."}}

: heartbeat

```

Quy tắc SSE:

- `POST` ban đầu đã kết thúc bằng 200 kết quả hoặc 202 pending; SSE là request `GET` riêng, là một lựa chọn khi next_action yêu cầu theo dõi. Client có thể polling GET request/history.
- Không cursor: replay từ đầu log, gồm event phát sinh trước lúc mở SSE. Nếu đầu log đã purge thì trả 410 để lấy snapshot.
- Có Last-Event-ID hoặc after_cursor: trả các event sau cursor; nếu cả hai có mặt thì phải giống nhau, không so thứ tự UUID bằng chữ.
- Khi đã hiển thị câu trả lời trong POST 200, dedupe cùng message_id khi SSE replay. Không lấy last_event_id của GET request làm cursor nếu chưa xử lý các event trước đó.
- Mỗi business event có `id`, `event` và `data`.
- Heartbeat comment mặc định 15 giây, không có business event ID, không đánh thức agent hoặc tạo lượt model.
- Client chỉ lưu cursor sau khi xử lý event thành công.
- Client dedupe bằng `event_id` và `message_id`.
- Mất kết nối thì reconnect với `Last-Event-ID`.
- Platform replay event từ database rồi tiếp tục live.
- Redis/pub-sub chỉ báo có dữ liệu mới; database là nguồn replay.
- SSE chỉ nhận dữ liệu. Reply/approval/close vẫn dùng `POST`.
- Mỗi hộp chat/ticket dùng `conversation_id` platform riêng. Không dùng cursor của conv_A để mở conv_B; backend kiểm tra `external_ticket_id` trong mọi event trước khi cập nhật hộp chat.
- Nếu không giữ SSE, backend đối tác có thể polling event history.
- Machine API key chỉ ở backend, không đặt trực tiếp trong app cư dân/browser.
- Backend dùng HTTP streaming client có hỗ trợ Authorization, retry và lưu cursor sau xử lý; không mặc định thư viện SSE tự bảo đảm xử lý bền vững.
- Platform kiểm tra auth/cursor trước khi gửi headers stream. Khi lỗi sau khi stream đã mở, ngắt kết nối để client reconnect/tra trạng thái; không thay một response SSE 200 đang mở thành JSON 410.
- Key/grant revoked làm stream dừng trong giới hạn revalidation tối đa 60 giây; reconnect phải qua auth hiện hành.

### 9.7. Public event types

| Event | Payload chính | App đối tác nên làm |
|---|---|---|
| `request.accepted` | `request_id` | Cập nhật trạng thái gửi |
| `workflow.status_changed` | state/revision | Cập nhật workflow |
| `ticket.created` | ticket ID/status | Tạo status card |
| `ticket.status_changed` | status và public details | Cập nhật status card |
| `assistant.message` | message ID/text | Thêm chat bubble |
| `approval.required` | approval summary/expiry | Hiển thị UI quyết định |
| `approval.resolved` | approval status | Khóa/cập nhật card |
| `operation.status_changed` | public operation status | Hiển thị trạng thái tích hợp |
| `workflow.awaiting_user` | reason/revision | Yêu cầu người dùng trả lời |
| `workflow.needs_attention` | public reason code | Hiển thị cần hỗ trợ |
| `workflow.closed` | state=closed/revision/reason/closed_at | Đóng đúng workflow trên UI |

`ticket.status_changed` cập nhật status card; `assistant.message` mới tạo chat bubble. Hai event khác loại không được render thành hai message giống nhau.

Public envelope bắt buộc gồm schema_version, event_id, sequence, event_type, occurred_at, recorded_at, conversation_id, external_ticket_id (nullable với tích hợp không có ticket), external_conversation_id, external_user_id, workflow_id (nullable với event cấp hội thoại), ticket_id (nullable) và payload. JSON trong SSE data giống item tương ứng của history; `id`/`event` trong SSE phải khớp event_id/event_type trong data.

Status operation là domain-specific và versioned theo integration, khác `workflow_state`. Ví dụ sửa chữa có technician_assigned/on_the_way/in_progress/completed; hotel booking có quoted/confirmation_required/confirmed/cancelled; vận chuyển có searching/driver_assigned/arriving/completed. Provider event phải map qua schema đã onboarding vào `operation.status_changed`; không đưa status tùy ý thành state mới của Workflow core.

Platform không gửi prompt, raw tool trace, credential, internal manager ID hoặc dữ liệu của audience khác.

### 9.8. Gửi approval/consent

```http
POST /workforce/v1/partner/approvals/{approval_id}/decision
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

Request:

```json
{
  "schema_version": "1",
  "external_request_id": "vh-decision-002",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "workflow_id": "wf_001",
  "decision": "approve",
  "expected_revision": 2,
  "arguments_hash": "sha256:4d7e...",
  "quote_ref": "quote_001"
}
```

Response:

```http
HTTP/1.1 202 Accepted
```

```json
{
  "approval_id": "approval_001",
  "status": "approved",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "workflow_id": "wf_001",
  "accepted_at": "2026-10-09T03:00:00Z"
}
```

Approval phải thuộc đúng audience/external ticket/conversation/workflow/run/call, chưa hết hạn và khớp arguments/quote. Credential đối tác không được approve thay cư dân khác hoặc lấy approval của hộp chat A dùng cho B. Provider status event không thay thế consent.

### 9.9. Đóng workflow

Khi cư dân xác nhận đã hoàn thành, backend khách hàng gửi command tới đúng workflow đang gắn với ticket. Quyền: `close_workflow`, đúng audience.

```http
POST /workforce/v1/partner/workflows/{workflow_id}/close
Authorization: ApiKey dp_<key-id>.<secret>
Content-Type: application/json
```

```json
{
  "schema_version": "1",
  "external_request_id": "vh-close-003",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "expected_revision": 8,
  "reason": "resident_confirmed_resolved",
  "stop_tracking_only": false
}
```

Platform xác thực, kiểm tra idempotency, CAS expected_revision, ghi state=closed và public event cùng transaction rồi trả:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "request_id": "req_close_003",
  "request_status": "completed",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "conversation_id": "conv_001",
  "workflow_id": "wf_001",
  "ticket_id": "ticket_001",
  "state": "closed",
  "next_action": "none",
  "revision": 9,
  "reason": "resident_confirmed_resolved",
  "closed_at": "2026-10-09T04:30:00Z"
}
```

Response này xác nhận vòng theo dõi đúng external ticket/workflow đã đóng. `workflow.closed` vẫn nằm trong event log để SSE/history đọc được. Conversation/lịch sử vẫn tồn tại; workflow/ticket khác của cùng người dùng không bị đóng.

- Khác revision: `409 REVISION_CONFLICT`; lấy snapshot hiện hành và kiểm tra lại quyết định trước khi gửi command mới.
- Retry cùng external_request_id/body: trả cùng kết quả đã lưu, không đóng lần hai hoặc tạo lượt agent mới. Idempotency được kiểm tra trước CAS trên revision cũ.
- Công việc ngoài chưa terminal: yêu cầu `stop_tracking_only=true` và reason=`resident_requested_stop_tracking`; nếu thiếu trả `409 WORKFLOW_NOT_READY_TO_CLOSE`. API này không tự gọi tool hủy.
- Tin nhắn “đã sửa xong” qua workflow_reply có thể dẫn tới hỏi xác nhận; backend phải gửi close command để ghi nhận đóng một cách rõ ràng.
- Sau close, workflow_reply mới bị từ chối với `409 WORKFLOW_CLOSED`. Event nhân viên đến muộn chỉ được audit/lưu sự thật công việc theo quyền, không tự mở lại ticket hoặc đánh thức agent.

Việc hủy công việc bên nhà cung cấp là hành động nghiệp vụ riêng, không được suy ra từ close.

## 10. Provider Event API dành cho operation bất đồng bộ

Phần này chỉ áp dụng khi tool/protocol trả operation còn pending và integration đã được cấp capability publish event. Nghiệp vụ đồng bộ trả kết quả terminal ngay không cần triển khai hoặc gọi các endpoint này.

### 10.1. Gửi cập nhật trạng thái

```http
POST /workforce/v1/provider/job-events
Authorization: ApiKey dp_<provider-key-id>.<secret>
X-Partner-Timestamp: 1791513000
X-Partner-Key-Id: provider-signing-key-01
X-Partner-Signature: v1=<signature>
Content-Type: application/json
```

Request:

```json
{
  "schema_version": "1",
  "external_event_id": "technician-event-009",
  "external_job_id": "JOB-123",
  "client_reference": "platform-correlation-001",
  "event_type": "repair.technician_on_the_way",
  "provider_version": 3,
  "occurred_at": "2026-10-09T02:30:00Z",
  "data": {
    "estimated_arrival_minutes": 20
  }
}
```

Field rules:

| Field | Quy tắc |
|---|---|
| `external_event_id` | Bắt buộc, duy nhất trong provider integration |
| `external_job_id` | Job ID phía provider; ít nhất job ID hoặc client reference phải có |
| `client_reference` | Correlation do platform đã đưa vào tool call |
| `event_type` | Thuộc schema đã thống nhất |
| `provider_version` | Số tăng dần theo job nếu provider hỗ trợ |
| `occurred_at` | Thời điểm nghiệp vụ xảy ra |
| `data` | Dữ liệu theo event schema, không chứa instruction cho agent |

Không gửi `manager_account_id`, `domain_id`, `area_id`, `conversation_id`, `workflow_id`, `agent_id` hoặc credential khác. Platform tự tra từ job/correlation đã lưu.

Nếu cả `external_job_id` và `client_reference` có mặt, chúng phải trỏ cùng một operation.

Response sau khi inbox và processing job đã commit:

```http
HTTP/1.1 202 Accepted
```

```json
{
  "receipt_id": "receipt_009",
  "ingestion_status": "accepted",
  "duplicate": false,
  "received_at": "2026-10-09T02:30:01Z",
  "status_url": "/workforce/v1/provider/event-receipts/receipt_009"
}
```

`accepted` chỉ xác nhận event đã được lưu. Nó chưa có nghĩa agent đã xử lý hoặc backend khách hàng đã đọc event qua SSE.

Event gửi lại cùng ID và cùng payload trả receipt cũ với `duplicate: true`. Cùng ID khác payload trả `409 EVENT_ID_CONFLICT`.

Event hợp lệ nhưng chưa nối được job có thể trả `ingestion_status: quarantined`; worker đối soát bằng correlation. Platform không đoán workflow dựa trên tên người dùng hoặc note.

### 10.2. Xem receipt

```http
GET /workforce/v1/provider/event-receipts/{receipt_id}
Authorization: ApiKey dp_<provider-key-id>.<secret>
```

Response:

```json
{
  "receipt_id": "receipt_009",
  "external_event_id": "technician-event-009",
  "ingestion_status": "applied",
  "normalized_status": "technician_on_the_way",
  "received_at": "2026-10-09T02:30:01Z",
  "applied_at": "2026-10-09T02:30:02Z",
  "error": null
}
```

Receipt states:

- `accepted`
- `processing`
- `applied`
- `duplicate`
- `quarantined`
- `rejected`
- `needs_attention`

Receipt response không trả manager, người dùng, nội dung chat hoặc prompt.

### 10.3. Ordering

- Có `provider_version`: version thấp hơn/equal đã xử lý không được làm lùi state.
- Cùng version nhưng khác payload là conflict.
- Delta event bị thiếu version giữa phải chờ reconcile.
- Không có version: `occurred_at` không đủ đảm bảo thứ tự; platform chỉ áp transition hợp lệ.
- `completed` không bị `on_the_way` đến muộn đẩy lùi.
- Correction/reopen cần event type riêng đã thống nhất.
- Event đến sau close có thể được lưu để audit nhưng không tự reopen workflow hoặc đánh thức agent.

State chuẩn minh họa:

```text
pending → assigned → on_the_way → arrived → in_progress → completed
                  ↘ failed / cancelled
```

## 11. Retry và idempotency

### 11.1. Customer API

- Retry network error/`5xx` với cùng `external_request_id` và body, theo backoff có jitter. Retry phải tham chiếu cùng command đã lưu.
- `429`: theo `Retry-After`.
- Không đổi request ID chỉ để né `409`.
- `400/401/403/404/409/410/422` chỉ retry sau khi nguyên nhân được xử lý.
- Nếu response `200` hoặc `202` bị mất, gửi lại đúng request để đọc kết quả/trạng thái của cùng request. Pending có thể trả 202; đã xong trả 200, không chạy lại tool.

### 11.2. Provider Event API

- Backend nghiệp vụ/provider lưu event/outbox trước khi gửi.
- Retry với cùng `external_event_id` và business payload.
- Mỗi lần retry tạo timestamp/signature transport mới.
- `202` kết thúc retry gửi event; dùng receipt endpoint để theo dõi xử lý.
- `5xx`/network error retry exponential backoff + jitter; `429` tuân Retry-After. `401/403/409/422` cần xử lý nguyên nhân trước khi gửi lại, không retry vô hạn.
- Cùng event ID khác payload tuyệt đối không được retry như cùng event.

### 11.3. SSE/history

- SSE reconnect tự động với `Last-Event-ID`.
- Client dedupe public event ID.
- Nếu cursor hết retention, lấy snapshot mới.
- Nếu backend đối tác không duy trì SSE, polling history bằng cursor.
- Không gọi request-status liên tục với tần suất cao thay cho event stream.

## 12. Retention và bảo mật dữ liệu

- Public event history được giữ trong toàn bộ thời gian workflow mở và tối thiểu 90 ngày sau close, trừ thỏa thuận khác.
- Dedupe provider event giữ tối thiểu 180 ngày hoặc không ngắn hơn retry window đã cam kết.
- Không purge workflow mở, event đang xử lý, operation unknown hoặc checkpoint còn tham chiếu.
- API luôn filter theo partner client, route, external user, external ticket và conversation/workflow binding khi tích hợp có ticket.
- Trạng thái workflow/ticket được giữ khi SSE offline. Cursor của client là vị trí replay, không phải lệnh đóng hoặc xác nhận người dùng đã đọc.
- Cùng manager nhưng hai người dùng/audience không dùng chung chat, approval hoặc transaction state.
- Nội dung message/event là dữ liệu không tin cậy, không thể đổi scope, policy hoặc credential.
- Không log API secret, Authorization header, signing secret hoặc dữ liệu nhạy cảm không cần thiết.

## 13. Case hoàn chỉnh đa lĩnh vực

### 13.1. Lập kế hoạch và booking đồng bộ, không cần Provider Event

```mermaid
sequenceDiagram
    participant C as Backend khách hàng
    participant P as AI Workforce Platform
    C->>P: POST start_workflow: lên kế hoạch hotel và xe
    P->>P: Leader chọn Plan/Hotel/Car/Calculator, gọi tool tra cứu
    P-->>C: 200 phương án + awaiting_user + submit_reply
    C->>P: POST workflow_reply + workflow_id: chọn phương án 2
    P-->>C: 200 approval.required + awaiting_approval + submit_approval
    C->>P: POST approval decision
    P->>P: Gọi tool booking một lần; tool trả confirmed
    P-->>C: 200 booking thành công + awaiting_confirmation + confirm_close
    C->>P: POST close sau khi người dùng xác nhận
    P-->>C: 200 closed + none
```

Response phương án đầu tiên minh họa:

```json
{
  "request_id": "req_trip_001",
  "request_status": "completed",
  "external_ticket_id": "partner-ticket-trip-001",
  "conversation_id": "conv_trip_001",
  "workflow_id": "wf_trip_001",
  "workflow_state": "awaiting_user",
  "next_action": "submit_reply",
  "workflow_revision": 3,
  "ticket_id": null,
  "result": {
    "messages": [
      {
        "message_id": "msg_trip_001",
        "workflow_id": "wf_trip_001",
        "sender": "assistant",
        "text": "Tôi đã chuẩn bị ba phương án khách sạn và xe trong ngân sách. Bạn muốn chọn phương án nào?",
        "created_at": "2026-10-10T02:00:06Z"
      }
    ]
  },
  "error": null
}
```

Backend hiển thị phương án và chỉ gửi `workflow_reply` khi người dùng chọn. Không phải mở SSE, không có backend nhân viên/provider POST trạng thái và không tạo `waiting_external_event`. Sau approval, nếu tool booking trả `confirmed` ngay, platform trả `awaiting_confirmation/confirm_close`; người dùng xác nhận thì backend POST close.

### 13.2. Khi nào cùng nghiệp vụ booking phải dùng external tracking

Tên “booking” không quyết định lifecycle:

| Kết quả tool đã xác minh | Workflow | next_action | Provider Event/SSE |
|---|---|---|---|
| Báo giá/phương án, chưa chọn | awaiting_user | submit_reply | Không bắt buộc |
| Cần consent trước giao dịch | awaiting_approval | submit_approval | Không bắt buộc |
| Booking đã confirmed | awaiting_confirmation | confirm_close | Không bắt buộc |
| Booking pending và có operation ID + event/status-query | waiting_external_event | watch_events | Có |
| Read-only đã đủ kết quả và policy auto-close | closed | none | Không |
| Chưa có kết quả trước HTTP deadline | state hiện hành | watch_request | SSE hoặc GET request/history |

Nếu một provider hotel trả pending rồi gửi `hotel_booking.confirmed`, luồng đó dùng cùng cơ chế external-tracking như sửa chữa nhưng event schema của hotel; core không dùng trạng thái kỹ thuật viên. Nếu provider khác trả confirmed ngay, tuyệt đối không tạo event channel/timer giả chỉ vì đó là “booking”.

### 13.3. Một khách hàng mở hai ticket/hộp chat đồng thời

Cư dân `resident-123` mở hộp A để sửa ống nước và hộp B để đặt khách sạn:

```mermaid
sequenceDiagram
    participant C as Backend khách hàng
    participant P as AI Workforce Platform
    C->>P: start_workflow (TICKET-A, CHAT-A, request-A1)
    P-->>C: wf_A, conv_A, ticket_A
    C->>P: start_workflow (TICKET-B, CHAT-B, request-B1)
    P-->>C: wf_B, conv_B, ticket_B hoặc null
    C->>P: workflow_reply (TICKET-A, CHAT-A, wf_A, request-A2)
    P-->>C: Kết quả chỉ của hộp A
    C->>P: workflow_reply (TICKET-B, CHAT-B, wf_B, request-B2)
    P-->>C: Kết quả chỉ của hộp B
    C->>P: GET SSE conv_A
    C->>P: GET SSE conv_B
    P-->>C: Stream A chỉ có event external_ticket_id=TICKET-A
    P-->>C: Stream B chỉ có event external_ticket_id=TICKET-B
    C->>P: close wf_A + TICKET-A + CHAT-A
    P-->>C: wf_A closed; wf_B giữ nguyên
```

Backend đối tác nên có một record local cho mỗi ticket với các cột tối thiểu: external_user_id, external_ticket_id, external_conversation_id, workflow_id, conversation_id, platform ticket_id nullable, workflow_revision, last_event_id và lifecycle status. Mọi thao tác lấy ID từ record của chính hộp chat đang tương tác; không dùng biến “workflow gần nhất của user”.

Nếu backend ghép `TICKET-A + CHAT-B`, `TICKET-A + wf_B` hoặc dùng lại CHAT-A để tạo TICKET-B, platform trả lỗi binding và không xử lý message. Đây là lỗi cần sửa mapping phía đối tác, không phải lỗi để retry tự động.

### 13.4. External-tracking: gọi thợ sửa ống nước

Đây là ví dụ của pattern external-tracking, không phải cấu hình mặc định của platform.

```mermaid
sequenceDiagram
    participant C as Backend khách hàng
    participant P as AI Workforce Platform
    participant T as Backend nghiệp vụ/provider
    C->>P: POST start_workflow: gọi thợ sửa ống nước
    P->>P: Lưu request, Leader chọn agent, gọi MCP tool
    P->>P: Tool trả JOB-123 và thợ Nguyễn Văn A; lưu kết quả/context/event
    P-->>C: 200 kết quả lượt đầu + conv_001 + wf_001 + ticket_001
    Note over C,P: POST kết thúc; ticket vẫn mở, agent chờ bằng checkpoint
    C->>P: GET SSE cho conv_001
    P-->>C: Replay event đã lưu; dedupe message đã nhận từ POST
    T->>P: POST job-events: thợ đang di chuyển
    P-->>T: 202 receipt sau persist
    P->>P: Nối JOB-123 tới wf_001, xử lý một lượt cần thiết
    P-->>C: SSE status và lời nhắn mới
    C->>P: POST workflow_reply + wf_001: hãy đi cổng B
    P->>P: Tiếp tục cùng ticket và context
    P-->>C: 200 kết quả lượt reply
    Note over C,P: SSE vẫn mở; message từ POST/SSE có cùng message_id
    T->>P: POST job-events: completed
    P-->>T: 202 receipt
    P-->>C: SSE hỏi cư dân xác nhận hoàn tất
    C->>P: POST /partner/workflows/wf_001/close
    P-->>C: 200 state=closed sau commit
    P-->>C: SSE workflow.closed
```

SSE có thể tới trước response POST ở các lượt chat tiếp. Client dedupe theo message_id; thứ tự hai đường mạng không làm phát sinh hai câu trả lời.

### 13.5. Kết quả POST đầu tiên và mở SSE

POST đầu tiên dùng payload mục 9.1. Khi tool xác nhận thành công, response 200 có câu “Đã gọi thành công thợ Nguyễn Văn A đến hỗ trợ sửa ống nước”, `conversation_id=conv_001`, `workflow_id=wf_001`, `ticket_id=ticket_001`, `workflow_state=waiting_external_event`.

Backend hiển thị message `msg_003`, rồi mở:

```http
GET /workforce/v1/partner/conversations/conv_001/events?external_user_id=resident-123
Authorization: ApiKey dp_<key-id>.<secret>
Accept: text/event-stream
```

Không đặt cursor trong lần đầu này. Platform phát lại event đã lưu rồi tiếp tục live, nên status phát sinh giữa POST và GET không bị bỏ sót. Message msg_003 được replay thì chỉ ghi nhận event/cursor, không thêm chat bubble.

Nếu lượt đầu chưa xong trước giới hạn chờ, POST trả 202 với cùng IDs và result=null. Backend mở SSE ngay để nhận kết quả lượt đầu về sau. Đây là nhánh fallback, không có bước “202 rồi trả thêm 200 trên cùng POST”.

### 13.6. Backend nghiệp vụ gửi tiến độ

App nhân viên gọi backend nhân viên. Sau xác thực và lưu trạng thái, backend gửi body dưới đây tới `POST /workforce/v1/provider/job-events`, với API key và signature ở mục 10:

```json
{
  "schema_version": "1",
  "external_event_id": "technician-event-009",
  "external_job_id": "JOB-123",
  "client_reference": "platform-correlation-001",
  "event_type": "repair.technician_on_the_way",
  "provider_version": 3,
  "occurred_at": "2026-10-09T02:30:00Z",
  "data": {
    "estimated_arrival_minutes": 20
  }
}
```

Platform trả 202 sau khi lưu event. Platform dùng integration + job/correlation để tìm đúng ticket và phiên chat đã lưu; worker tiếp tục đúng workflow. Backend khách hàng nhận `ticket.status_changed` và `assistant.message` như mục 9.6.

Nếu SSE mất mạng sau evt_004, reconnect GET với `Last-Event-ID: evt_004`; platform replay evt_005 và các event sau, giữ nguyên workflow.

### 13.7. Khách chat thêm trong ticket cũ

```json
{
  "schema_version": "1",
  "command_type": "workflow_reply",
  "external_request_id": "vh-message-002",
  "external_management_ref": "BQL-OP1-A",
  "external_user_id": "resident-123",
  "external_ticket_id": "partner-ticket-plumbing-001",
  "external_conversation_id": "vh-chat-789",
  "workflow_id": "wf_001",
  "message": {
    "type": "text",
    "text": "Nhờ báo thợ đi vào cổng B giúp tôi."
  }
}
```

Gửi tới POST /partner/requests. Response là kết quả lượt mới qua 200, hoặc 202 nếu chưa xong trong thời hạn. Giữ ticket_001/conv_001/wf_001 và context; platform không tự tạo ticket khác. Có chuyển được lời nhắn cho thợ hay không phụ thuộc tool/capability đã có; chỉ báo “đã chuyển” khi có kết quả xác minh. SSE hiện tại tiếp tục hoạt động.

### 13.8. Xác nhận đóng

Backend nghiệp vụ gửi `repair.completed`. Platform cập nhật tiến độ và hỏi người dùng xác nhận, workflow chuyển `awaiting_confirmation/confirm_close`.

Cư dân xác nhận; backend khách hàng gửi POST close ở mục 9.9 với workflow_id=wf_001 và revision hiện hành. Nhận 200 state=closed nghĩa vòng theo dõi đã đóng. Event đến muộn không tự reopen; conversation và lịch sử vẫn đọc được.

### 13.9. Các tình huống phải kiểm tra

| Tình huống | Hành vi |
|---|---|
| Retry POST vì mất response | Cùng request/result, không gọi tạo thợ lần hai |
| Lượt đầu vượt thời gian chờ | 202 + IDs, kết quả sau qua SSE/history/GET request |
| Event tới trước GET SSE đầu tiên | Replay từ log bền vững |
| Cùng message qua POST và SSE | Cùng message_id, một chat bubble |
| Khách POST reply | Cùng workflow/ticket/conversation/context |
| Cùng user có hai hộp chat | Hai external ticket/conversation/workflow riêng; message và SSE không đi chéo |
| Ghép sai ticket/conversation/workflow | 409 binding error; không dispatch Leader/tool và không tự đoán ticket |
| Provider gửi trùng/sai thứ tự | Dedupe, không lùi trạng thái |
| Worker restart khi chờ | Khôi phục checkpoint và pin, không tạo job mới |
| Route remap A sang B | Ticket cũ vẫn gắn A; revalidate quyền, không chuyển lịch sử sang B |
| Close đồng thời với reply/event | CAS/state check; không mở lại hoặc tạo chat sau close |
| Event đến sau close | Audit/dedupe; không tự reopen |

## 14. Checklist phía đối tác

### 14.1. Backend khách hàng

- [ ] API key chỉ nằm ở backend.
- [ ] `external_request_id` ổn định và duy nhất.
- [ ] `external_user_id` đã được đối tác xác thực.
- [ ] `external_ticket_id` ổn định suốt vòng đời; không dùng lại cho ticket mới.
- [ ] Mỗi ticket/hộp chat đồng thời có `external_conversation_id` riêng và ổn định.
- [ ] Lưu `workflow_id`, `conversation_id`, platform `ticket_id` nullable, revision và cursor theo đúng external ticket; không dùng “workflow gần nhất của user”.
- [ ] Route/residence được đồng bộ trước request.
- [ ] Hiển thị kết quả lượt đầu từ POST 200; đọc workflow_state + next_action, không mặc định mọi workflow còn mở hoặc cần SSE.
- [ ] Xử lý fallback 202 bằng SSE/history/GET request, không đợi response thứ hai của POST.
- [ ] workflow_reply giữ đúng external user/ticket/conversation/workflow, không dùng start_workflow cho mỗi tin nhắn.
- [ ] GET customer có external_user_id và kiểm tra audience.
- [ ] Dedupe cùng message nhận từ POST và SSE, kể cả SSE tới trước.
- [ ] Chỉ mở SSE khi next_action=watch_request/watch_events hoặc UX cần realtime; nếu không mở thì polling GET request/history. Khi dùng SSE, reconnect bằng `Last-Event-ID`.
- [ ] Dedupe `event_id` và `message_id`.
- [ ] Có fallback event history/snapshot.
- [ ] Approval và close gắn đúng workflow/user/revision.
- [ ] Hai SSE của hai hộp chat lưu cursor riêng và kiểm tra external_ticket_id trước khi cập nhật UI.

### 14.2. Backend nghiệp vụ/provider khi có external tracking

- [ ] Không triển khai/gọi Provider Event chỉ cho đủ mẫu nếu operation luôn trả terminal.
- [ ] Khi có event: credential publish riêng với backend khách hàng.
- [ ] Actor cập nhật được xác thực và có quyền trên operation.
- [ ] Event được lưu trước khi gửi.
- [ ] `external_event_id` duy nhất và retry giữ nguyên ID/payload.
- [ ] Gửi `external_job_id` và `client_reference` khi có.
- [ ] Provider version tăng theo job hoặc có transition/reconcile rule.
- [ ] Signature được tính trên raw body.
- [ ] Không gửi manager/conversation/workflow ID tự khai.

### 14.3. Kiểm thử chung trước production

- [ ] Read-only → 200 closed/none, không SSE/Provider Event/close.
- [ ] Plan hotel/xe → 200 awaiting_user/submit_reply → reply cùng workflow → approval → booking confirmed → confirm_close → close 200.
- [ ] Booking confirmed ngay không tạo external tracking; booking pending mới chuyển waiting_external_event/watch_events.
- [ ] POST → gọi thợ → 200 kết quả → GET SSE → status updates → reply cùng ticket → resident close 200.
- [ ] Nhánh fallback 202, response POST bị mất và event trước GET SSE đầu tiên.
- [ ] Duplicate customer request và provider event.
- [ ] Event sai thứ tự và callback đến sớm.
- [ ] Worker/platform/backend đối tác restart.
- [ ] SSE reconnect và cursor hết retention.
- [ ] Sai signature, revoked key và wrong route/audience.
- [ ] Hai manager cùng area và hai người dùng/audience không lẫn dữ liệu.
- [ ] Hai integration có status schema khác nhau không làm Workflow core hardcode trạng thái của một ngành.
- [ ] Evidence sandbox được ghi riêng; mock pass không được ghi là production pass.

## 15. Thông tin cần điền khi onboarding

```text
Tên đối tác:
Môi trường:
Base URL platform:
Partner client ID:
Provider integration ID:
External management ref:
Residence mapping: Có/Không
Customer API operations:
POST result wait timeout:
Proxy/client timeout:
Provider API operations:
Customer credential key ID:
Provider credential key ID:
Provider signing key ID:
Rate limit:
Payload limit:
Retention:
Event schema/version:
Đầu mối kỹ thuật phía đối tác:
Đầu mối kỹ thuật phía platform:
Ngày sandbox pass:
Ngày production enable:
Contract exception/addendum:
```

Mọi exception phải ghi rõ endpoint/field/event bị ảnh hưởng, thời hạn, owner hai bên và test bù. Không thỏa thuận thay đổi contract bằng nội dung chatbot hoặc prompt agent.
