# Nối Vinhomes với platform (Workforce v1): thiết kế đã duyệt

Cập nhật 11/10/2026 (tối). Thay cho bản kế hoạch `KE_HOACH_NOI_WORKFORCE_V1.md` (10/10). Hợp đồng của platform: `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md` bản `1.3-draft` và mã ở nhánh `feat/platform-core` (`platform_VP/core/src/awp/workforce`). Vinhomes chỉ dùng platform như một đối tác: không sửa gì bên platform.

## 1. Quyết định của chủ sản phẩm (11/10)

1. Ban quản lý **không** duyệt phương án. Reception tiếp tục tạo ticket với `plan_required=False`; luồng phương án cũ và 13 kịch bản vàng giữ nguyên.
2. Cư dân **không** phải bấm xác nhận ticket. Reception hỏi lại khi thiếu thông tin; đủ thì tạo ticket, gửi sang platform ngay và báo trạng thái trên chat.
3. Sau bàn giao, lời nói với cư dân trong hộp chat đó là của agent điều phối (leader) của platform, backend Vinhomes ghi vào đúng hộp chat. Tin nhắn tiếp theo của cư dân trong hộp chat đó đi sang platform. Vinhomes chỉ tự ghi vào hộp chat đó thẻ báo giá và vài câu cố định của cầu nối (mục 10).
4. **Báo giá:** kỹ thuật viên lập báo giá trong app nhân viên. Cư dân nhận báo giá **ngay trong chat**, là một thẻ có từng khoản vật tư, tiền công, tổng tiền, bảo hành và hai nút Đồng ý, Không đồng ý. Câu trả lời là cú bấm của chính cư dân; lời của model không bao giờ được ghi thành đồng ý hay từ chối.
5. **Nghiệm thu:** kỹ thuật viên gửi **kết quả nghiệm thu** (ảnh, ghi chú). Kỹ thuật viên không gõ tên cư dân và hệ thống không ghi rằng cư dân đã kiểm tra. Kết quả đi sang platform; cư dân nhận trên chat và tự xác nhận hoàn thành ở đó.
6. **Khẩn cấp:** Reception đánh giá mức khẩn cấp và mức đó được **gửi sang platform** cùng yêu cầu. Ticket khẩn cấp cũng được bàn giao; xử lý khẩn cấp tại chỗ của Vinhomes (leo thang, báo Ban quản lý) giữ nguyên. Tin khẩn cấp cư dân nhắn sau khi đã bàn giao cũng được báo cho platform.
7. **Ảnh gửi sau bàn giao** được gắn vào yêu cầu, để nhân viên và công cụ tra cứu của leader đều thấy.
8. **Tin cuối của leader** không được thiếu trong chat khi workflow đóng.
9. **Tri thức** lưu và tìm bằng pgvector trong chính PostgreSQL của gói: vector là cột kiểu `vector`, xếp hạng bằng khoảng cách cosine ngay trong SQL. Không có database vector riêng. Với số đoạn hiện có, lệnh tìm so đủ mọi đoạn đúng phạm vi của cư dân nên kết quả chính xác; chỉ mục HNSW đã tạo sẵn cho lúc kho lớn hơn, hiện lệnh tìm chưa đi qua nó.
10. Nhân viên vẫn nhận việc, đi, báo giá, làm trong app nhân viên. Trạng thái đi sang platform bằng sự kiện có chữ ký; platform báo lại cư dân qua chat.

## 2. Bật và tắt

Cầu nối chỉ hoạt động khi `VINHOMES_API_PLATFORM_URL` có giá trị. Để trống thì hệ thống chạy đúng như trước (mọi kiểm thử cũ không đổi).

| Biến (dịch vụ `api` và `platform-sync`) | Ý nghĩa |
|---|---|
| `VINHOMES_API_PLATFORM_URL` | Gốc của platform, ví dụ `http://host.docker.internal:8800` |
| `VINHOMES_API_PLATFORM_CUSTOMER_KEY` | Khóa khách hàng `dp_<id>.<secret>` |
| `VINHOMES_API_PLATFORM_PROVIDER_KEY` | Khóa nhà cung cấp `dp_<id>.<secret>` |
| `VINHOMES_API_PLATFORM_SIGNING_KEY_ID`, `VINHOMES_API_PLATFORM_SIGNING_SECRET` | Khóa ký sự kiện |
| `VINHOMES_API_PLATFORM_MCP_TOKEN` | Token platform phải gửi khi gọi công cụ (`Authorization: Bearer …`), 32 ký tự trở lên |

## 3. Ánh xạ định danh

| Platform | Vinhomes |
|---|---|
| `external_management_ref` | `management_units.code` |
| `external_user_id` | `users.id` |
| `external_ticket_id` | `tickets.id` |
| `external_conversation_id` | `"{channel_id}:{ticket_id}"` |
| `external_request_id` | `platform_commands.id` |
| `client_reference` | platform cấp (`cr_…`), lưu ở `platform_operations` |
| `external_job_id` | `work_orders.id`, chỉ công cụ giao việc trả về |
| `external_event_id`, `provider_version`, `occurred_at` | `ticket_events.id`, `.seq`, `.occurred_at` |
| `timezone` | `Asia/Ho_Chi_Minh` |

Route không đòi `residence_id` (`residence_required: false`).

## 4. Bảng mới (migration `0014_platform.sql`)

Mọi bảng có `tenant_id`, RLS bắt buộc như các bảng khác, `created_at`, `updated_at`.

- `platform_links`: `ticket_id` (khóa chính), `channel_id`, `user_id`, `management_ref`, `conversation_id`, `workflow_id`, `state`, `next_action`, `revision`, `cursor` (event_id cuối đã xử lý), `status` (`pending` chưa gửi được, `open`, `closed`, `failed`). `state` là trạng thái workflow bên platform; `status` chỉ sang `closed` khi cầu nối đã đọc hết sổ sự kiện của workflow đã đóng (mục 5.2).
- `platform_commands`: `id` uuid (là `external_request_id`), `ticket_id`, `kind` (`start_workflow`, `workflow_reply`, `approval_decision`, `close`), `body` jsonb, `status` (`pending`, `done`, `failed`), `attempts`, `next_attempt_at`, `last_error`, `result` jsonb. Gửi theo thứ tự tạo trong từng ticket.
- `platform_inbox`: `platform_id` (message_id hoặc event_id của platform, khóa chính cùng tenant), `ticket_id`, `chat_message_id`. Chống ghi trùng vào chat.
- `platform_approvals`: `approval_id` (khóa chính), `ticket_id`, `summary` jsonb, `arguments_hash`, `quote_ref`, `expected_revision`, `expires_at`, `status` (`pending`, `approved`, `rejected`, `expired`).
- `platform_operations`: `client_reference` (khóa chính), `ticket_id`, `tool`, `work_order_id` (chỉ với giao việc), `answer` jsonb. Gọi lại cùng `client_reference` trả lại `answer`, không làm lần hai.
- `platform_outbox`: `event_id` (= `ticket_events.id`, khóa chính), `ticket_id`, `client_reference`, `external_job_id`, `event_type`, `provider_version`, `occurred_at`, `data` jsonb, `status` (`pending`, `sent`, `rejected`), `attempts`, `next_attempt_at`, `receipt` jsonb.

Người thực hiện của agent platform trong dữ liệu Vinhomes là một dòng `integration_clients` id `platform`, kind `platform`, `accepts_cases=false`, tự tạo khi cần (như `reception_client`).

## 5. Luồng

### 5.1 Bàn giao (Reception → platform)

Trong `_handoff_draft` (`v3_reception_operations.py`), ngay sau khi ticket và snapshot đã có và **trước** nhánh "không có nơi nhận", cùng giao dịch: nếu cầu nối bật thì ghi `platform_links` (`pending`) và một `platform_commands` `start_workflow`. Ticket khẩn cấp cũng được bàn giao; phần xử lý khẩn cấp tại chỗ phía sau không đổi.

Ticket loại an ninh không khẩn cấp không gửi platform: việc an ninh do Ban quản lý điều động. Ticket an ninh **khẩn cấp** thì có gửi, để platform biết; leader chỉ báo tin cho cư dân, công cụ giao việc vẫn từ chối việc an ninh.

`message.text` của `start_workflow` là văn bản duy nhất platform nhận, gồm: dòng `ticket_id: <uuid>` (agent phải chép đúng giá trị này vào mọi công cụ), loại yêu cầu, tiêu đề, mô tả của cư dân, căn, tòa, phân khu, mức ưu tiên, dòng `Mức khẩn cấp do Lễ tân đánh giá: …`, số ảnh, giờ tạo. Không có số điện thoại, không có mã `VH-…`.

Dòng mức khẩn cấp lấy từ ticket: `KHẨN CẤP` kèm loại nguy hiểm khi nhận ra được (cháy hoặc khói, rò khí gas, chập điện hoặc giật điện, kẹt thang máy, ngập nước hoặc vỡ ống nước, sập trần) hoặc `không khẩn cấp`, rồi mức độ nghiêm trọng (nhẹ, vừa, nặng, nghiêm trọng) khi đã đánh giá.

### 5.2 Tiến trình đồng bộ (`python -m vinhomes_api.platform_sync`, dịch vụ compose `platform-sync`)

Vòng lặp khoảng 1 giây, dùng vai trò database hạn chế của API, an toàn khi chạy lặp. Mỗi vòng theo thứ tự:

1. **Tạo sự kiện tiến độ:** quét `ticket_events` mới của các ticket có link, ánh xạ theo bảng mục 7 vào `platform_outbox`. Gặp báo giá mới (`work_order.repair_proposed`) thì ghi luôn **thẻ báo giá** vào hộp chat (mục 5.4), một lần cho mỗi báo giá.
2. **Đóng theo ticket:** link của ticket đã `closed` hoặc `cancelled` bằng đường khác (Ban quản lý, an ninh) được ghi một lệnh `close` kèm `stop_tracking_only` (lý do cố định của platform `resident_requested_stop_tracking`), vì platform có thể còn theo dõi việc.
3. **Gửi lệnh:** `POST /workforce/v1/partner/requests` (hoặc `approvals/{id}/decision`, `workflows/{id}/close`). Lỗi mạng hoặc 5xx, 429: thử lại cùng `external_request_id`, giãn dần. Lỗi 4xx không thử lại được: `failed`, ghi `last_error`. Kết quả cập nhật `platform_links` (ids, `state`, `next_action`, `revision`); `result.messages` ghi vào chat. `approval_decision` và `close` gửi lại giữ nguyên `expected_revision` đã gửi lần đầu; chỉ đổi khi chính platform từ chối lần gửi đó. Lệnh `close` thường bị từ chối `WORKFLOW_NOT_READY_TO_CLOSE` 5 lần liên tiếp thì gửi ở dạng `stop_tracking_only`.
4. **Đọc sự kiện:** với mỗi link `open`, `GET …/conversations/{id}/event-history?after_cursor=` (không dùng SSE: đơn giản hơn, chịu được khởi động lại), đọc tới hết sổ. Theo từng sự kiện:
   - `assistant.message` → ghi vào chat bằng `append_agent_message` (người gửi là client `platform`), chống trùng theo `message_id` ở `platform_inbox`.
   - `workflow.*` → cập nhật `state`, `next_action`, `revision`.
   - `approval.required` / `approval.resolved` → `platform_approvals` và một tin chat có `body.platform = {kind: "approval", …}` kèm `text`.
   - Các loại khác chỉ cập nhật cursor.
5. **Gửi sự kiện tiến độ:** `POST /workforce/v1/provider/job-events`, ký HMAC-SHA256 trên `<timestamp>.<byte thô của body>`; gửi lại giữ nguyên body. Sự kiện của một ticket chỉ một tiến trình gửi tại một thời điểm.

**Khi workflow đóng.** Câu trả lời của lệnh `close` (hoặc lỗi `WORKFLOW_CLOSED`) chỉ ghi `state = closed`; link vẫn `open`. Bước đọc sự kiện đọc tới hết sổ rồi mới chuyển link sang `closed`. Nhờ vậy mọi thứ platform đã ghi trước lúc đóng (tin cuối của leader, kết cục của một thẻ đồng ý) đều vào chat. Lần đọc lỗi thì vòng sau đọc lại. Trong lúc đó hộp chat đã trở lại với Reception.

**Khi platform không xử lý được.** Câu trả lời 200 có `request_status` là `failed` hoặc `blocked`, sự kiện `workflow.needs_attention` với lý do `engine_error`, và trạng thái `blocked_*`: link sang `failed`, cư dân nhận một câu báo, hộp chat trở lại với Reception, ticket do người xử lý. `needs_attention` vì lý do khác thì link vẫn mở (tin nhắn tiếp theo của cư dân đánh thức lại leader).

### 5.3 Tin nhắn tiếp theo của cư dân

Trong `send_message` (`v3_resident.py`): nếu hộp chat có link đang chạy (link `pending` hoặc `open`, workflow chưa đóng, ticket chưa `closed` hay `cancelled`) thì ghi lệnh `workflow_reply` và **không** gọi Reception. Khi platform đang chờ approval (`APPROVAL_PENDING`), lệnh thử lại sau. Lệnh `workflow_reply` còn chờ khi workflow đã đóng thì bị bỏ, không báo lỗi cho cư dân.

**Ảnh.** Ảnh trong tin nhắn được gắn vào ticket (cùng cách Reception gắn ảnh bổ sung: bảng `ticket_files`, sự kiện `ticket.conversation_images_attached`), nên nhân viên thấy trong yêu cầu và `vh_ticket_get` đếm được. Ticket đang `resolved` (chờ cư dân xác nhận kết quả) cũng gắn: ảnh chụp chỗ chưa đạt là thứ người làm lại cần. Platform chỉ nhận chữ: lệnh gửi đi có thêm câu "Cư dân gửi thêm N ảnh.", N là số ảnh vừa gắn thêm (ảnh ticket đã có thì không tính); tin chỉ có ảnh thì lệnh chỉ gồm câu đó.

**Khẩn cấp.** Tin có dấu hiệu khẩn cấp (`emergency_kind`) đi **cả hai đường**: Reception xử lý tại chỗ như cũ (leo thang ticket, báo Ban quản lý), và một lệnh `workflow_reply` báo cho leader bằng một câu cố định: "Cư dân vừa báo tình huống khẩn cấp (<loại>). Lời cư dân:" rồi nguyên văn lời cư dân. Câu này không nói Ban quản lý đã nhận tin: lúc ghi lệnh, lượt của Reception chưa chạy và có thể không báo được. Ticket đang `resolved` vẫn leo thang khẩn cấp được.

"Bóng đèn bị cháy", "cầu chì bị cháy" là đồ hỏng, không phải cháy. Chỉ coi là đồ hỏng khi cả vế câu chỉ nói về cái đèn hay cầu chì đó: tên đèn, chỗ đặt, "bị cháy", "rồi", lời nhờ thay. Có thêm từ nào khác ("bắt cháy", "cháy lan", "cháy dữ dội", "cạnh cột đèn có xe máy cháy") hoặc trong tin có lửa, khói thì vẫn là cháy. Đoán sai thì sai về phía coi là cháy.

Sau khi workflow đóng, hộp chat trở lại với Reception.

### 5.4 Báo giá: cư dân trả lời trên thẻ

1. Kỹ thuật viên lập báo giá (`POST /work-orders/{id}/repair-proposal`): một `work_approvals` loại `customer_repair`, trạng thái `pending`.
2. Tiến trình đồng bộ ghi vào hộp chat **một** tin của client `platform`: `body = {text, platform}`. `text` là báo giá bằng chữ (từng khoản, tiền công, tổng, bảo hành) cho ứng dụng không vẽ được thẻ. `platform = {kind: "quote", approval_id, lines: [{name, quantity, unit, unit_price, amount}], labor_cost, warranty_months, total, expires_at}`; `approval_id` là id của `work_approvals`, tiền là số nguyên đồng, `expires_at` có thể là `null`. Ghi chú riêng của kỹ thuật viên không nằm trong thẻ.
3. `GET /resident/chats/{id}/messages` trả thêm `platform.status` cho thẻ báo giá: `pending`, `approved`, `rejected` hoặc `expired`, tính từ `work_approvals` lúc đọc, không lưu trong tin nhắn. Báo giá bị rút hoặc quá hạn đọc là `expired`.
4. Cư dân bấm trên thẻ; ứng dụng gọi đường có sẵn `POST /resident/approvals/{approval_id}/decision` bằng phiên của chính cư dân. Không có công cụ nào để leader ghi thay. Kỹ thuật viên cũng không ghi thay được: với ticket đã bàn giao, đường "cư dân đồng ý tại chỗ" trên máy nhân viên (`POST /work-orders/{id}/repair-proposal/onsite-decision`) trả 409 và app nhân viên không hiện hai nút đó (`GET /work-orders/{id}` trả `quoteInChat: true`). Ticket không bàn giao thì đường này vẫn như cũ.
5. Platform được báo bằng sự kiện: `job.quote_ready` (chỉ làm bằng chứng, không đánh thức leader), rồi `job.quote_approved` hoặc `job.quote_rejected` (mỗi loại có một câu mẫu cho cư dân; chỉ lần từ chối đánh thức leader).

Thẻ đồng ý của platform (`body.platform.kind = "approval"`, trả lời qua `POST /resident/platform/approvals/{approval_id}/decision {approve: bool}`, lệnh `approval_decision` với `arguments_hash`, `expected_revision`, `quote_ref` đã lưu) vẫn được hỗ trợ cho việc khác mà leader cần cư dân đồng ý. Leader không dùng nó cho báo giá.

### 5.5 Nghiệm thu và hoàn thành

1. Nhân viên chuyển việc sang `completed` (cần ảnh trước và sau như hiện nay).
2. Màn hình **Nghiệm thu** ở app nhân viên: chụp thêm ảnh nghiệm thu (bằng chứng loại `verification`) và gửi kết quả. `POST /work-orders/{id}/onsite-acceptance {version, note?}`: chỉ nhân viên đã nhận việc, việc đã `completed`, ticket không có `requiresPlan`, có ít nhất một ảnh `after` hoặc `verification`. Hệ thống ghi đây là **báo cáo nghiệm thu của kỹ thuật viên** (người ghi là chính kỹ thuật viên, kèm ghi chú và số ảnh kết quả); không có gì ghi rằng cư dân đã xem hay đồng ý. Rồi chạy `publish_completion`: ticket sang `resolved`, tạo yêu cầu xác nhận hoàn thành cho cư dân. Trả 201 `{id, work_order_id, outcome, checked_at, ticket_status: "resolved"}`. Mỗi việc chỉ gửi được một lần, và không gửi được khi việc đã có kết quả nghiệm thu (Ban quản lý đánh trượt, hoặc cư dân đã từ chối kết quả): khi đó cần việc mới hoặc nghiệm thu của Ban quản lý. Nghiệm thu của Ban quản lý (QC) vẫn dùng được như cũ.
3. Tiến trình đồng bộ ghi vào hộp chat **một** tin của cầu nối nêu kết quả: tóm tắt (có ghi chú của kỹ thuật viên), người gửi, số ảnh kết quả (ảnh sau và ảnh nghiệm thu). Cư dân nhận kết quả mà không phụ thuộc lượt của leader. Cùng lúc, sự kiện `job.result_published` (kết thúc, đánh thức leader) sang platform với đúng các số liệu đó. Leader soát bằng `vh_ticket_get` rồi mời cư dân xác nhận; workflow sang `awaiting_confirmation`.
4. Chat hiện thẻ xác nhận khi ticket có link đang mở và có yêu cầu xác nhận hoàn thành đang chờ (`GET /resident/chats` trả `confirm_close`), kể cả khi leader chưa nói gì. Cư dân trả lời qua đường có sẵn `POST /resident/approvals/{id}/decision`:
   - Đồng ý: ticket `closed` (như cũ) và ghi lệnh `close` cho workflow.
   - Không đồng ý: ticket mở lại (như cũ) và ghi lệnh `workflow_reply` nêu lý do để leader giao việc lại.

## 6. Công cụ MCP (`/mcp` trên API, streamable HTTP, không trạng thái)

Platform không cho công cụ biết cư dân hay ticket. Vì vậy mọi công cụ nhận `ticket_id` do agent điền; máy chủ chỉ chấp nhận ticket có link `pending` hoặc `open` (leader giao việc ngay trong lượt đầu, trước khi cầu nối nhận được câu trả lời của lệnh `start_workflow`), và mọi thông tin cư dân, căn hộ đều suy từ ticket. Không bao giờ trả mã `VH-…`, số điện thoại, ghi chú nội bộ. Giờ in theo giờ Việt Nam dạng `HH:MM dd/MM/yyyy`. Mỗi lời gọi dưới 8 giây, dưới 256 KiB. `/mcp` chỉ mở ở địa chỉ của dịch vụ `api`; cổng chung trả 404 cho `/api/business/mcp`.

Hành động nhận thêm tham số ẩn `client_reference` (platform điền) và trả một đối tượng JSON có `status`. Một `client_reference` chỉ trả lại câu trả lời đã lưu cho đúng công cụ và đúng ticket đã dùng nó; dùng cho lời gọi khác thì bị từ chối, không làm gì.

| Công cụ | Loại | Tham số agent điền | Trả về |
|---|---|---|---|
| `vh_ticket_get` | tra cứu | `ticket_id` | ticket (`ticket_status`), mức khẩn cấp (`is_emergency`, `severity`, `priority`), việc, người nhận, lịch hẹn, báo giá đang chờ cư dân trả lời, báo cáo nghiệm thu (`acceptance_report`: kết quả, người gửi, giờ gửi, ghi chú), số ảnh (`resident_photos`: chỉ ảnh do chính cư dân gửi; ảnh của nhân viên theo loại trước, sau, nghiệm thu), mốc tiến độ |
| `vh_resident_context` | tra cứu | `ticket_id` | tên gọi, cách xưng hô, quan hệ với căn, căn, tòa, phân khu |
| `vh_knowledge_search` | tra cứu | `ticket_id`, `query` | các đoạn tài liệu đúng phân khu của cư dân, kèm tên tài liệu; tìm bằng pgvector trong PostgreSQL của gói (khoảng cách cosine trong SQL) |
| `vh_home_rules` | tra cứu | `ticket_id` | hạn mức theo phân khu |
| `vh_debit_notes` | tra cứu | `ticket_id`, `view` | công nợ của căn (chỉ chủ hộ, người thuê) |
| `vh_staff_available` | tra cứu | `ticket_id` | nhân viên đúng chuyên môn, đang trong ca, còn chỗ |
| `vh_work_order_dispatch` | hành động, `tracking: events` | `ticket_id`, `description`, `staff_id?`, `appointment_at?` | `pending` + `external_job_id`; không ai rảnh: `queued`; từ chối: `failed` + lý do (việc an ninh, ticket theo phương án, đang có việc chưa xong) |
| `vh_work_order_reschedule` | hành động | `ticket_id`, `appointment_at`, `reason` | `confirmed` |
| `vh_ticket_cancel` | hành động | `ticket_id`, `reason` | `confirmed` hoặc `failed` |
| `vh_ticket_add_note` | hành động | `ticket_id`, `note` | `confirmed` |
| `vh_visitor_register` | hành động | `ticket_id`, `guest_name`, `visit_from`, `visit_to`, `purpose`, `guest_count?`, `vehicle_plate_no?` | `confirmed` kèm đã duyệt hay chờ quầy lễ tân duyệt; hoặc `failed` + lý do |
| `vh_announcements` | tra cứu | `ticket_id` | thông báo của Ban quản lý cho tòa và phân khu của cư dân |
| `vh_visitor_list` | tra cứu | `ticket_id` | các lượt khách của căn, kèm `visit_ref` |
| `vh_visitor_cancel` | hành động | `ticket_id`, `visit_ref` | `confirmed` hoặc `failed` + lý do |
| `vh_cards` | tra cứu | `ticket_id` | thẻ ra vào và thẻ xe của căn (số thẻ chỉ hiện bốn số cuối), kèm `card_ref` |
| `vh_card_report_lost` | hành động | `ticket_id`, `card_ref` | `confirmed` (thẻ bị khóa) hoặc `failed` + lý do |
| `vh_amenities` | tra cứu | `ticket_id` | tiện ích đặt được (giá, giờ mở, luật) và các lượt căn đã đặt, kèm `amenity_ref`, `booking_ref` |
| `vh_amenity_availability` | tra cứu | `ticket_id`, `amenity_ref`, `date` | lượt còn trống trong ngày, theo khu vực |
| `vh_amenity_book` | hành động | `ticket_id`, `amenity_ref`, `start_at`, `end_at`, `area?`, `people?` | `confirmed` nghĩa là **đã gửi thẻ**, chưa đặt chỗ (xem dưới) |
| `vh_amenity_cancel` | hành động | `ticket_id`, `booking_ref` | `confirmed` hoặc `failed` + lý do |
| `vh_service_requests` | tra cứu | `ticket_id` | các yêu cầu căn đã gửi quầy lễ tân và tình trạng |
| `vh_construction` | tra cứu | `ticket_id` | quy định và giấy phép thi công của căn (chỉ chủ hộ, người thuê) |
| `vh_my_requests` | tra cứu | `ticket_id` | các yêu cầu khác của cư dân và tình trạng, không kèm mã |

**Đặt tiện ích cần cư dân tự bấm.** Một lượt đặt có thể mất phí, nên `vh_amenity_book` không đặt gì: nó ghi vào hộp chat một thẻ (tiện ích, khu vực, giờ, số người, phí) có nút "Xác nhận đặt chỗ", dùng được trong 15 phút. Cư dân bấm thì `POST /resident/platform/bookings/{card_id}/confirm` mới tạo lượt đặt, bằng đúng luật của tiện ích như khi đặt trong ứng dụng; bấm lại không tạo lượt thứ hai. Sau đó agent điều phối nhận một tin cho biết cư dân đã xác nhận và lượt đặt đang ở trạng thái nào (đã xác nhận, hoặc chờ thanh toán). Trạng thái của thẻ được đọc từ lượt đặt mỗi lần mở hộp chat, không lưu trong tin nhắn.

Các công cụ hành động khác trong nhóm này (hủy lượt khách, hủy lượt đặt, báo mất thẻ) làm việc như chính cư dân làm trong ứng dụng: cùng một luật, và chỉ trên những thứ thuộc căn của cư dân đó.

Chưa có công cụ tạo yêu cầu dịch vụ mới ở quầy (cấp thẻ, đăng ký xe): cư dân tự tạo trong ứng dụng, hoặc nói trong hộp chat để Lễ tân lập yêu cầu.

`vh_ticket_get` có thêm khóa `status: "completed"` **chỉ khi** ticket đã `resolved` hoặc `closed`: platform coi khóa `status` ở tầng trên cùng là bằng chứng việc đã xong.

`vh_ticket_cancel` hủy xong thì ghi luôn lệnh `close` (lý do `resident_cancelled`) để hộp chat trở lại với Reception. Nó từ chối khi việc đã đến nơi, đang làm hoặc đã làm xong: việc đã làm không bị bỏ bằng một câu trong chat, Ban quản lý xử lý.

Không có công cụ nào về báo giá. Báo giá do kỹ thuật viên lập trong app nhân viên; cư dân trả lời trên thẻ báo giá (mục 5.4); platform chỉ được báo bằng sự kiện.

Khi nhân viên từ chối hoặc lời mời hết hạn, Vinhomes tự mời người kế tiếp; hết người thì báo `job.unassigned`.

**Lời dặn leader** (trong `deploy/platform/vinhomes-declaration.json`), những điểm chính: chép đúng `ticket_id`; giao việc ngay ở lượt đầu; mọi lượt kết thúc bằng một tin cho cư dân; không ghi nhận, không hỏi xin đồng ý báo giá bằng lời và không dùng công cụ xin đồng ý của platform cho báo giá, chỉ giải thích và nhắc cư dân bấm trên thẻ; kết quả nghiệm thu là báo cáo của nhân viên, cư dân chưa kiểm tra, và cư dân đã có tin kết quả của cầu nối nên leader chỉ mời xác nhận, không nhắc lại con số; với yêu cầu khẩn cấp thì câu đầu tiên nói cư dân cần làm gì ngay, chỉ bằng điều tìm được trong tài liệu (số hotline), giao việc ngay, không bảo cư dân chờ và không nói Ban quản lý đã nhận tin.

## 7. Sự kiện tiến độ (`version_mode: snapshot`)

Mọi sự kiện gửi kèm `client_reference` của lần giao việc tạo ra việc đó. Việc không do leader giao thì không có sự kiện.

| Sự kiện | Hạng | Phát khi | Trường cư dân được thấy | Cờ |
|---|---|---|---|---|
| `job.offered` | 10 | mời nhân viên | | |
| `job.declined` | 10 | nhân viên từ chối | | |
| `job.offer_expired` | 10 | lời mời hết hạn | | |
| `job.unassigned` | 10 | không còn ai để mời | | đánh thức |
| `job.accepted` | 20 | nhân viên nhận | `staff_name`, `eta` | tin mẫu |
| `job.rescheduled` | 20 | đổi lịch | `appointment` | tin mẫu |
| `job.en_route` | 30 | đang đến | `staff_name` | tin mẫu |
| `job.arrived` | 40 | đã đến | `staff_name` | tin mẫu |
| `job.quote_ready` | 50 | có báo giá | `items`, `total`, `warranty_months` | bằng chứng |
| `job.quote_approved` | 50 | cư dân bấm Đồng ý trên thẻ | | tin mẫu, bằng chứng |
| `job.quote_rejected` | 50 | cư dân bấm Không đồng ý trên thẻ | | tin mẫu, đánh thức |
| `job.started` | 60 | bắt đầu làm | | tin mẫu |
| `job.completed` | 70 | nhân viên báo xong | | tin mẫu |
| `job.result_published` | 90 | kỹ thuật viên gửi kết quả nghiệm thu (hoặc Ban quản lý nghiệm thu), chờ cư dân xác nhận | `summary`, `photo_count`, `reported_by` | kết thúc `completed`, đánh thức, bằng chứng |
| `job.cancelled` | 90 | việc bị hủy | `reason` | kết thúc `cancelled`, đánh thức |

`items` là danh sách `{label, amount}` (tiền công là một dòng riêng), `total` bằng tổng các `amount`, số nguyên đồng. `job.quote_ready` không có tin mẫu và không đánh thức leader: cư dân đã có thẻ báo giá. Câu trả lời báo giá là hai loại sự kiện vì tin mẫu của platform không rẽ nhánh được. `reported_by` là tên kỹ thuật viên gửi kết quả, hoặc "Ban quản lý" khi Ban quản lý tự nghiệm thu; `summary` có ghi chú của kỹ thuật viên, tối đa 200 ký tự, một dòng; `photo_count` là số ảnh kết quả (ảnh sau và ảnh nghiệm thu), không tính ảnh trước khi làm.

Platform không sửa được bảng sự kiện đã lưu: đổi bảng này là tạo một integration mới với khóa nhà cung cấp và khóa ký mới (xem `deploy/platform/README.md`).

## 8. Thứ Vinhomes giao cho nhóm platform

`deploy/platform/vinhomes-declaration.json`: hồ sơ agent, cấu hình route (câu trả lời an toàn, cụm từ cấm), máy chủ MCP và bảng công cụ, bảng sự kiện. `deploy/platform/apply.py` đưa bộ này vào một platform qua API quản trị của nó và in ra các khóa để điền vào `deployment.env`; sau đó `python -m vinhomes_api.platform confirm-routes` xác nhận route bằng khóa khách hàng.

## 9. Ngoài phạm vi

Ảnh không đi qua platform (hợp đồng chỉ nhận chữ): ảnh nằm ở kho ảnh của Vinhomes và gắn vào ticket, platform chỉ biết số ảnh. Đồng bộ danh sách căn hộ (`residences`), SSE, nhiều ban quản lý cùng lúc có khóa riêng, và thanh toán không làm ở bản này.

## 10. Câu của cầu nối và việc còn mở

Cầu nối tự ghi vào hộp chat đã bàn giao những thứ sau, không phải lời leader:

- thẻ báo giá (mục 5.4);
- tin kết quả nghiệm thu (mục 5.5 bước 3);
- câu trên thẻ đồng ý của platform và câu ghi nhận kết cục của thẻ đó;
- một câu khi platform không xử lý được yêu cầu (mục 5.2): "Hệ thống điều phối chưa xử lý được yêu cầu này. Ban quản lý sẽ liên hệ trực tiếp với bạn.";
- một câu khi leader kết thúc lượt mà không trả lời tin nhắn cư dân vừa gõ: "Trợ lý chưa có câu trả lời cho tin nhắn này…". Câu này không ghi cho lệnh do cầu nối tự tạo (cư dân bấm "Chưa đạt", tin báo khẩn cấp mà Reception đã trả lời).

Việc còn mở:

- Leader là model của platform: có lượt nó kết thúc mà không nói gì hoặc nói lỏng. Lời dặn và câu dự phòng của cầu nối giảm được, không hết. Model mạnh hơn cho leader là việc của nhóm platform.
- Một lượt của leader hỏng hẳn (`engine_error`) thì việc điều phối ticket đó kết thúc, workflow bên platform nằm ở `needs_attention` cho tới khi người vận hành platform đóng.
- Sau khi cư dân từ chối báo giá, việc trở về "đã đến nơi"; kỹ thuật viên lập báo giá mới thì cư dân nhận thẻ mới. Leader không hủy được yêu cầu ở bước này (việc đã đến nơi), Ban quản lý xử lý.
- Lệnh `close` gửi ở dạng "ngừng theo dõi" hiện bên platform với lý do `resident_requested_stop_tracking` kể cả khi Ban quản lý hủy: đó là lý do duy nhất platform nhận khi còn việc đang theo dõi.
