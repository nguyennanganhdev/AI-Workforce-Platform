# Hợp đồng tích hợp domain Vinhomes ⇄ platform (v1)

Trạng thái: **bản 0.2 (09/10/2026), đã làm và có test**. Mỗi mục ghi test kiểm nó. Kịch bản dùng hợp đồng này: [KICH_BAN_VANG.md](KICH_BAN_VANG.md). Kế hoạch: [KE_HOACH_TRIEN_KHAI.md](KE_HOACH_TRIEN_KHAI.md). Danh mục công cụ thật luôn lấy từ `GET /integration/v1/tools`; bảng ở §4 chỉ là ảnh chụp.

## 0. Mục đích và nguyên tắc

Domain Vinhomes là một đối tác độc lập; platform nối vào như một **khách hàng của domain**. Hợp đồng này là toàn bộ những gì platform được phép biết và làm. Khi hai nguyên tắc xung đột, nguyên tắc đứng trước thắng:

1. **Người quyết định.** Việc không đảo ngược hoặc có hiệu lực tiền bạc/pháp lý chỉ người làm (§3.3).
2. **Từ chối mặc định.** Một thao tác chỉ dùng được qua tích hợp nếu có tên trong danh mục §4. Thao tác mới của domain mặc định **không** mở cho tích hợp.
3. **Thay mặt, không thay thế.** Agent luôn hành động *thay mặt một người cụ thể* với quyền không vượt quá người đó. Domain tự kiểm quyền ở mỗi lần gọi.
4. **Domain là nguồn sự thật.** Platform không đọc database của domain. Dữ liệu platform nhận chỉ để suy luận, không để quyết định thay.
5. **Mọi thứ có dấu vết.** Mỗi thao tác ghi gắn với client, lượt ủy quyền, người được thay mặt, mã tương quan.
6. **Lặp lại được.** Mọi thao tác ghi dùng khóa idempotency.

Ngoài phạm vi v1: webhook đẩy sự kiện, đăng nhập người dùng cuối trực tiếp trên platform, thanh toán, truyền ảnh/video qua tích hợp, nhiều client nhận hồ sơ trong một tenant, và việc platform đứng ra trò chuyện với cư dân thay Reception.

## 1. Các bên

| Khái niệm | Là gì |
|---|---|
| **Client tích hợp** | Hệ thống ngoài đã đăng ký: `reception` (lễ tân của domain) hoặc `platform`. Có mã, bí mật, mức được phép theo persona, trạng thái bật/tắt, cờ `accepts_cases`. Bảng `integration_clients`. |
| **Người dùng** | Cư dân (chủ, người thuê, thành viên hộ) hoặc nhân viên (hiện trường, BQL, an ninh, quản trị). Vai trò do domain giữ. |
| **Lượt ủy quyền** | Giấy phép ngắn hạn để một client làm việc *thay mặt một người*. Bảng `delegations`. |
| **Hồ sơ (case)** | Một yêu cầu của cư dân đã bàn giao cho client nhận hồ sơ. Bảng `integration_cases`. Trường `team_id` trong thư của dây trao đổi **chính là mã hồ sơ**. |
| **Sự kiện** | Điều đã xảy ra, đọc theo con trỏ. Bảng `event_outbox`. |
| **Gói tri thức** | Tài liệu có phiên bản, kèm đối tượng được xem. |

Hai persona dùng chung một cơ chế: **cư dân** và **nhân viên**. Quyền cụ thể suy ra từ vai trò của *người được thay mặt*, không từ client.

## 2. Xác thực

*Test: `test_integration_auth.py`.*

### 2.1 Client

```
X-Client-Id: platform
Authorization: Bearer ics_…
```

Bí mật là 32 byte ngẫu nhiên; domain chỉ lưu băm SHA-256, so bằng phép so sánh thời gian cố định. Cấp hoặc xoay bí mật bằng `python -m vinhomes_api.database client --id platform --kind platform [--accepts-cases]`: lệnh in bí mật **một lần**; chạy lại là xoay, bí mật cũ hết hiệu lực ngay. Client bị tắt: 403 ở mọi nơi. Client chỉ dùng bí mật cho các điểm cuối không thay mặt ai: danh mục công cụ, hộp thư hồ sơ, nguồn sự kiện, gói tri thức, kết thúc lượt ủy quyền.

### 2.2 Lượt ủy quyền (thay mặt một người)

Người đã đăng nhập vào ứng dụng của domain cấp cho một client:

```
POST /integration/v1/delegations/self        (phiên đăng nhập của chính người đó; Idempotency-Key bắt buộc)
{ "client_id": "platform", "purpose": "resident_assistant", "ttl_seconds": 600, "channel_id": null }
→ 201 { "delegation_id": "…", "token": "dg1_…", "expires_at": "…", "persona": "resident", "scopes": ["read","draft","act_small"] }
```

- `purpose` ∈ `resident_assistant`, `staff_assistant`. Người chỉ cấp được purpose khớp vai trò (nhân viên cần vai trò `management`/`staff` hoặc là quản trị viên).
- `scopes` = giao của mức client được phép cho persona đó và trần của purpose (`resident_assistant`: read, draft, act_small; `staff_assistant`: read, draft, propose). Không bao giờ có mức cấm.
- Token chỉ hiện **một lần**; domain lưu băm. Một lượt không cấp ra lượt khác. Dùng lại cùng `Idempotency-Key`: 409.

Dùng: `Authorization: Bearer dg1_…` trên các điểm cuối trong danh mục. Mỗi lần gọi, **trong cùng giao dịch**, domain: tìm công cụ theo (method, mẫu đường dẫn) — không có → **404**; kiểm lượt còn `active`, chưa hết hạn, client còn bật, người còn `active` và còn là thành viên — hết hạn → **401** (lượt đóng `failed/expired`), client tắt hoặc người mất tư cách → **403** (lượt đóng `revoked`); persona và mức của công cụ nằm trong lượt — không → **403**; tối đa 120 lệnh gọi mỗi lượt — vượt → **429** kèm `Retry-After`; thao tác ghi thiếu `Idempotency-Key` → 400. Rồi áp **đúng các kiểm tra quyền như khi chính người đó gọi bằng phiên đăng nhập** (liên kết cư trú, phạm vi quản lý…). Không có quyền nào được lưu đệm trong token: gỡ liên kết cư trú có hiệu lực ngay ở lần gọi kế tiếp.

Kết thúc: `POST /integration/v1/delegations/{id}/finish` (bằng bí mật của client) với `{ "status": "finished"|"failed", "error_code"?, "usage"?: {"input_tokens", "output_tokens"} }`.

Cấp lượt do client chủ động cho một người (không qua phiên của người đó) **không có trong v1**.

### 2.3 Tiêu đề chung

| Tiêu đề | Ý nghĩa |
|---|---|
| `Idempotency-Key` | Bắt buộc với mọi thao tác ghi dưới ủy quyền (thiếu: 400) và với `cases/*/results|plans` (thiếu: 422). 1 đến 160 ký tự. Với đường dẫn tạo (khách, đặt tiện ích, đơn dịch vụ) gửi lại cùng khóa cùng nội dung trả bản ghi cũ; khác nội dung: 409. |
| `X-Correlation-Id` | Tùy chọn; domain trả lại (hoặc tự sinh) và ghi vào kiểm toán. |

## 3. Mức quyền

### 3.1 Bốn mức

| Mức | Nghĩa | Ví dụ |
|---|---|---|
| `read` | Chỉ đọc | công nợ, lịch tiện ích, đơn thi công |
| `draft` | Tạo bản **nháp** chưa có hiệu lực; người phải gửi/phát hành | đơn dịch vụ ở trạng thái `draft`, thông báo ở trạng thái `draft` |
| `act_small` | Làm ngay việc nhỏ, trong phạm vi của chính người đó, hủy được, có kiểm toán | đăng ký và hủy khách, đặt và hủy tiện ích, khóa thẻ mất, báo khẩn |
| `propose` | Đề xuất cho **nhân viên** duyệt; chưa đổi dữ liệu nghiệp vụ | phương án xử lý, kết quả hồ sơ |

### 3.2 Quyền client

Mỗi client có `levels` theo persona, ví dụ `platform`: `{"resident": ["read","draft","act_small"], "staff": ["read","draft","propose"]}`. Quyền của một lượt = giao của quyền client, trần của purpose và quyền của chính người được thay mặt.

### 3.3 Cấm tuyệt đối (luôn là người)

Không thao tác nào dưới đây có trong danh mục, bất kể client:

- duyệt hoặc từ chối phương án (BQL), đồng ý hoặc từ chối phương án và chi phí (cư dân);
- **gửi** một đơn nháp thành chính thức (cư dân), **phát hành** thông báo (BQL);
- thanh toán, hoàn tiền, phát hành hoặc hủy hóa đơn và thông báo phí;
- nghiệm thu, đóng yêu cầu, xác nhận hoàn tất, kết luận chất lượng;
- duyệt ngân sách, duyệt điều động/hủy điều động an ninh, duyệt khóa nước;
- cấp, đổi, thu hồi vai trò và phạm vi, duyệt tài khoản, xác minh cư trú;
- xử lý đơn ở bàn lễ tân (chuyển trạng thái, cấp thẻ), xóa dữ liệu.

*Test: `test_every_tool_is_a_real_operation_and_none_decides_for_a_person`; trong `test_golden.py` mỗi kịch bản thử đúng các thao tác cấm bằng token và nhận 404.*

### 3.4 Trường không trả cho agent

Mã QR/token cổng (khách, tiện ích), số thẻ đầy đủ (chỉ 4 số cuối), số giấy tờ tùy thân, ảnh khuôn mặt, token thẻ thanh toán, bí mật, số tài khoản hoàn tiền. Số điện thoại chỉ cho chính chủ và nhân viên trong phạm vi. *Test: G04, G05.*

## 4. Danh mục công cụ

`GET /integration/v1/tools` (client hoặc lượt) trả các công cụ mà bên gọi được dùng, kèm `input_schema`/`output_schema` lấy từ OpenAPI thật để platform sinh công cụ MCP. Kiểm tra bằng (method, mẫu đường dẫn). `GET /integration/v1/openapi.json` trả lát cắt OpenAPI chỉ gồm các điểm cuối này. Ảnh chụp danh mục (45 công cụ):

**Cư dân**

| Công cụ | Mức | Điểm cuối | Làm gì |
|---|---|---|---|
| `resident.me` | read | `GET /resident/me` | Cư dân là ai |
| `resident.context` | read | `GET /resident/context` | Các căn đã xác minh |
| `resident.homes` | read | `GET /resident/homes` | Các căn để chọn (không gộp ngầm) |
| `resident.tickets.list` / `.get` / `.progress` | read | `GET /resident/tickets`, `/{ticket_id}`, `/{ticket_id}/progress` | Yêu cầu của cư dân |
| `resident.plans.list` | read | `GET /resident/plans` | Phương án chờ cư dân quyết |
| `resident.notifications.list` | read | `GET /my/notifications` | Thông báo cá nhân |
| `resident.emergency.raise` | act_small | `POST /resident/tickets/{ticket_id}/emergency` | Báo khẩn: yêu cầu thành `critical`, BQL được báo một lần |
| `resident.debit_notes.list` / `.get` / `.balance` | read | `GET /resident/units/{unit_id}/debit-notes`, `/{note_id}`, `/balance` | Công nợ (chủ và người thuê) |
| `resident.visitors.list` / `.create` / `.cancel` | read / act_small | `/resident/units/{unit_id}/visitor-passes`, `POST /resident/visitor-passes/{pass_id}/cancel` | Khách đến thăm |
| `resident.cards.list` | read | `GET /resident/units/{unit_id}/cards` | Thẻ của căn |
| `resident.cards.report_lost` | act_small | `POST /resident/cards/{card_id}/report-lost` | Khóa thẻ mất ngay |
| `resident.service_requests.list` / `.draft` | read / draft | `/resident/units/{unit_id}/service-requests` | Đơn lễ tân; cư dân tự gửi |
| `resident.amenities.list` / `.availability` | read | `GET /resident/amenities`, `/{amenity_id}/availability?date=` | Tiện ích và khung giờ trống |
| `resident.amenity_bookings.list` / `.create` / `.cancel` | read / act_small | `/resident/amenity-bookings`, `…/{booking_id}/cancel` | Đặt và hủy tiện ích |
| `resident.construction.policy` / `.permits` | read | `GET /resident/units/{unit_id}/construction-policy`, `/construction-permits` | Quy định và đơn thi công (chủ và người thuê) |
| `resident.announcements.list` | read | `GET /resident/announcements` | Thông báo cho tòa của cư dân |

**Nhân viên**

| Công cụ | Mức | Điểm cuối |
|---|---|---|
| `staff.me` | read | `GET /operations/me` |
| `staff.tickets.list` (có `overdue=true`) / `.get` / `.timeline` / `.plans` | read | `GET /tickets`, `/{ticket_id}`, `/{ticket_id}/timeline`, `/{ticket_id}/plans` |
| `staff.work_orders.mine` / `.list` / `.get` | read | `GET /my-work-orders`, `/work-orders`, `/work-orders/{work_order_id}` |
| `staff.available` | read | `GET /staff/available` |
| `staff.plans.queue` | read | `GET /plans` |
| `staff.catalogs` | read | `GET /catalogs` |
| `staff.reports.incident_frequency` / `.incident_summary` / `.repair_revenue` / `.filter_options` | read | `GET /reports/…` |
| `staff.service_requests.list` | read | `GET /operations/service-requests` |
| `staff.announcements.list` | read | `GET /operations/announcements` |
| `staff.announcements.draft` | draft | `POST /operations/announcements` (luôn ở `draft`, ghi `drafted_by='agent'` và client) |

Nhân viên không có `act_small` qua tích hợp trong v1: đổi trạng thái phiếu việc, ghi bằng chứng, phân công, xử lý đơn lễ tân, phát hành thông báo, đóng tiện ích đều là thao tác của người.

## 5. Hộp thư hồ sơ (case)

*Test: `test_golden.py::test_G02…`, `test_request_presentation.py`.*

Hồ sơ là yêu cầu đã bàn giao cho client có `accepts_cases` (tối đa một client đang bật mỗi tenant — ràng buộc ở cơ sở dữ liệu). **Không có client nhận hồ sơ → yêu cầu vẫn tới BQL xử lý tay**, cư dân không thấy lỗi. Hợp đồng dùng lại **dây `schema_v2`** Reception ⇄ Supervisor (idempotent theo `message_id`, phân trang theo con trỏ); tên `Supervisor` trong thân thư chỉ là tên của dây.

| Hướng | Điểm cuối | Thân |
|---|---|---|
| Domain → client | `GET /integration/v1/cases/inbox?cursor=&limit=` | thư `ReceptionToSupervisorMessage`: `ticket_submitted`, `information_provided`, `plan_approved`, `plan_rejected`, `plan_change_requested`, `cancel_requested` |
| Client → domain | `POST /integration/v1/cases/{ticket_id}/results` (+`Idempotency-Key`) | thư `SupervisorToReceptionResult`: `accepted`, `in_progress`, `information_requested`, `plan_approval_requested`, `completed`, `failed`, `cancelled` |
| Client → domain | `POST /integration/v1/cases/{ticket_id}/plans` (+`Idempotency-Key`) | đề xuất phương án (§5.1) |
| Đọc | `GET /integration/v1/cases/{ticket_id}` | trạng thái hồ sơ, yêu cầu (không có thông tin cá nhân của cư dân), phương án mới nhất |

### 5.1 Đề xuất phương án

```
POST /integration/v1/cases/{ticket_id}/plans
{ "ticket_version": 7, "summary": "Thay gioăng vòi bếp", "steps": ["Khóa van", "Thay gioăng", "Kiểm tra rò rỉ"],   // 1 đến 4 bước
  "performer_staff_id": "…", "appointment_at": "2026-10-10T09:00:00+07:00",
  "estimated_amount": 150000, "estimated_duration_min": 60, "cost_bearer": "resident", "requires_outage": false }
→ 201 { "id": "…", "status": "management_pending", "proposed_by_client_id": "platform", … }
```

Quy tắc: yêu cầu thuộc hồ sơ của client; `ticket_version` bằng `version` hiện tại của yêu cầu và yêu cầu chưa ở trạng thái cuối (409); yêu cầu đã phân loại (422); chưa có phương án đang chờ (409); người thực hiện thuộc đơn vị, có chuyên môn và **đang trong ca đúng giờ hẹn** (422); `appointment_at` có múi giờ và ở tương lai (422). Cùng khóa cùng nội dung trả phương án cũ; khác nội dung 409. Sau đó đi đúng đường có sẵn: BQL duyệt (`/plans/{id}/management-decision`) → cư dân đồng ý (`/resident/plans/{id}/decision`) → tạo phiếu việc và chào việc cho người thực hiện. Client và mọi lượt ủy quyền gọi các điểm cuối quyết định: 404.

## 6. Nguồn sự kiện

*Test: `test_golden.py::test_G12…`.*

```
GET /integration/v1/events?after=<seq>&topics=ticket.*,plan.*&limit=100        (bí mật của client)
→ { "items": [ { "seq": 1042, "event_id": "…", "topic": "ticket.sla_breached", "occurred_at": "…", "schema_version": 1, "payload": {…} } ],
    "next_cursor": "1042" }
```

- **Ít nhất một lần**, theo thứ tự `seq`; client giữ con trỏ và loại trùng theo `event_id`. Đọc lại từ một con trỏ cũ trả đúng chuỗi cũ.
- Sự kiện chỉ được phục vụ sau `VINHOMES_API_EVENT_SETTLE_SECONDS` (mặc định 2) kể từ lúc ghi, để một giao dịch chậm cam kết không xuất hiện sau con trỏ đã giao.
- Chỉ mang mã và trạng thái, **không** mang dữ liệu cá nhân.
- Chủ đề có thật trong v1: mọi sự kiện của yêu cầu mang tiền tố `ticket.` / `plan.` / `work_order.` / `work_assignment.` / `water.` / `triage.` (ví dụ `ticket.created`, `ticket.status_changed`, `ticket.emergency_escalated`, `plan.proposed`, `plan.management_decided`, `plan.resident_decided`, `work_order.offered`), cộng `ticket.sla_warning`, `ticket.sla_breached`, `announcement.published`, `visitor_pass.created`, `amenity_booking.cancelled_by_closure`. Mỗi cảnh báo hạn chỉ phát một lần mỗi yêu cầu.
- Cảnh báo hạn do tác vụ `python -m vinhomes_api.jobs sweep` (compose có sẵn dịch vụ `scheduler` chạy mỗi phút) phát khi đã qua 80% thời gian xử lý (`warning`) và khi quá hạn (`breached`). Hạn do cơ sở dữ liệu gán khi yêu cầu tạo ra theo chính sách `sla_policies` đang hiệu lực.

## 7. Gói tri thức

*Test: `test_golden.py::test_the_knowledge_pack…`.*

```
GET /integration/v1/knowledge/pack?audience=resident|staff|management&since=<version>        (bí mật của client)
→ { "version": "sha256:…", "generated_at": "…", "audience": "resident", "unchanged": false,
    "documents": [ { "id": "handbook:…", "kind": "handbook|policy|announcement|fee_table|faq", "title": "…", "body_md": "…",
                     "language": "vi", "scope": {"zone_codes": [], "unit_kinds": []}, "audience": ["resident"],
                     "effective_from": "…", "effective_to": null, "checksum": "sha256:…", "source": "handbook_articles/…" } ] }
```

- Nguồn: cẩm nang, văn bản quy định (kèm biểu phí và hỏi đáp), thông báo đã phát hành còn hiệu lực.
- Tài liệu chỉ nằm trong gói của đối tượng nó khai báo: gói `resident` **không bao giờ** có tài liệu chỉ dành cho nhân viên hoặc BQL (kiểm trong test).
- Client chỉ lấy gói `resident` khi quyền client có persona cư dân, gói `staff`/`management` khi có persona nhân viên.
- `since=<version>` bằng phiên bản hiện tại trả `unchanged: true` và danh sách rỗng; khác thì trả cả gói. (Chưa có phần chênh lệch theo từng tài liệu.)

## 8. Nạp dữ liệu, dựng thế giới mẫu, đặt lại

Công cụ vận hành của domain, không phải điểm cuối cho platform. Chi tiết định dạng: [NAP_DU_LIEU.md](NAP_DU_LIEU.md). *Test: `test_import.py`, `test_database_tool.py`, `test_golden.py` (chạy trên thế giới mẫu).*

| Lệnh (`python -m vinhomes_api.database …`) | Việc |
|---|---|
| `mock --profile test\|standard --seed 42` | dựng thế giới mẫu của [KICH_BAN_VANG.md §3](KICH_BAN_VANG.md); chạy lại không thêm gì; đi qua trigger và ràng buộc thật |
| `import --dir DIR [--dry-run]` | nạp dữ liệu thật (CSV/JSON) theo mã; một giao dịch, sai dòng nào báo dòng đó và không ghi gì |
| `client --id … --kind … [--accepts-cases]` | đăng ký client, in bí mật một lần |
| `reset --confirm TEN_DATABASE` | xóa sạch và dựng lại schema trống; chỉ chạy khi nhắc đúng tên database |

## 9. Lỗi, phiên bản, giới hạn

### 9.1 Lỗi của `/integration/v1/*`

```json
{ "error": { "code": "VALIDATION_FAILED", "message": "…", "retryable": false, "correlation_id": "…", "details": [ { "loc": ["body","purpose"], "msg": "…" } ] } }
```

| HTTP | `code` | Thử lại |
|---|---|---|
| 400 | `BAD_REQUEST` | không |
| 401 | `UNAUTHENTICATED` | không (cấp lại) |
| 403 | `FORBIDDEN` | không |
| 404 | `NOT_FOUND` (kể cả thao tác không có trong danh mục) | không |
| 409 | `CONFLICT` | sau khi đọc lại |
| 422 | `VALIDATION_FAILED` | không |
| 429 | `RATE_LIMITED` | có, sau `Retry-After` |
| 503 | `UNAVAILABLE` | có |

Các điểm cuối nghiệp vụ gọi dưới ủy quyền giữ dạng lỗi vốn có của chúng (`{"detail": …}`); client xử lý theo mã HTTP.

### 9.2 Phiên bản và giới hạn

Đường dẫn mang `v1`. Thêm trường tùy chọn hoặc điểm cuối không đổi phiên bản; client bỏ qua trường lạ. Đổi nghĩa hoặc siết kiểm tra → `v2`, chạy song song tối thiểu 90 ngày. Phân trang theo con trỏ, `limit` tối đa 100. Mỗi lượt tối đa 120 lệnh gọi.

## 10. Kiểm toán và quyền riêng tư

- Mọi thao tác ghi dưới ủy quyền tạo `audit_events` với `initiator_kind='agent'`, `initiator_id=<client>`, `actor_user_id=<người được thay mặt>`, payload có `delegationId`, `onBehalfOf`, `idempotencyKey`, `tool`. Sự kiện của yêu cầu ghi `actor_kind='agent'` và `actor_client_id`. Hành động của client không thay mặt ai (đề xuất phương án) ghi client là người khởi tạo.
- Nhật ký chỉ thêm, không sửa.
- Dữ liệu cá nhân chỉ ra khỏi domain khi một lượt ủy quyền đang hiệu lực cần; gói tri thức và sự kiện không chứa dữ liệu cá nhân (kiểm trong test).

## 11. Còn mở

Danh sách dưới đây đã được duyệt ngày 09/10/2026 là **phần ngoài phiên bản 1**: không làm trong v1, mỗi mục sẽ được quyết định riêng khi đến lượt.

1. Lượt ủy quyền do client chủ động (cần đồng ý rõ của người dùng và liên kết tài khoản).
2. Nhiều client nhận hồ sơ trong một tenant (chọn theo nhóm dịch vụ).
3. Webhook đẩy sự kiện thay cho kéo (ký, thử lại, hộp thư chết).
4. Phần chênh lệch theo từng tài liệu trong gói tri thức.
5. Nháp yêu cầu sự cố qua tích hợp (hiện chỉ có qua Reception trong trò chuyện của domain): cần quyết định có để platform tiếp quản trò chuyện không.
