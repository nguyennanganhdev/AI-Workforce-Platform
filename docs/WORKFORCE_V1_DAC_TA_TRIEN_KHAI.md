# Workforce v1: đặc tả triển khai bên platform

Cập nhật: 10/10/2026. Nguồn yêu cầu: `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md` (bản `1.3-draft`, gọi là "hợp đồng"; viện dẫn theo số mục, ví dụ §9.1). Tài liệu này là *cách làm* ở phía platform; hợp đồng là *cái phải đúng*. Khi hai bên mâu thuẫn, hợp đồng thắng, trừ các mục ghi "Giả định" bên dưới.

Phạm vi: `platform_VP/core` (gói `awp`). Không sửa `platform_VP/agentscope/src`. Không có mã Vinhomes trong repo platform. Vinhomes nối sau, từ `vinhome_Recident`, chỉ qua API này.

Các nghiên cứu nền (đọc trước khi làm): `docs/research/AGENTSCOPE_CHO_WORKFORCE_V1.md` (AgentScope làm được gì), `docs/research/CONTRACT_WORKFORCE_V1_GAP_2026-10-10.md` (khoảng cách với mã hiện có), `docs/WORKFORCE_V1_KE_HOACH_TRIEN_KHAI.md` (kế hoạch).

## 0. Luật làm việc cho người triển khai

1. Mọi hành vi lấy từ hợp đồng. Không thêm field, mã lỗi hay endpoint công khai ngoài hợp đồng, trừ mục "Giả định" (A1…A9) và chúng phải được ghi vào `docs/WORKFORCE_V1_QUYET_DINH.md`.
2. Đơn giản trước. Không trừu tượng cho thứ chỉ dùng một chỗ. Không thêm tính năng không được yêu cầu.
3. Mỗi hành vi có test. Test chạy bằng model giả có kịch bản (`tests/fake_llm.py`), không gọi model thật.
4. Chạy test: `cd platform_VP/core && PYTHONPATH=src ../agentscope/.venv/Scripts/python.exe -m pytest -q` (venv không có pip). Chạy cả bộ trước và sau khi sửa; không để test cũ đỏ vì thay đổi của mình.
5. Không commit, không push, không đụng `vinhome_Recident`, không đụng container Docker có sẵn của người dùng (`vp-platform-*`, `vinhomes-*`). Container thử nghiệm tự tạo phải đặt tên `awp-test-*` và xóa khi xong.
6. Báo cáo trung thực: cái gì đã chạy và qua, cái gì chỉ đọc mã, cái gì chưa kiểm. Không ghi "xong" cho thứ chưa có test chạy.
7. Giữ phong cách mã hiện có: tên ngắn, ít chú thích, docstring chỉ nói *vì sao*.

## 1. Kiến trúc

```
Backend đối tác ──ApiKey──► /workforce/v1/partner/*      ┐
Backend provider ─ApiKey+HMAC─► /workforce/v1/provider/* │  awp/workforce/ (router, auth, service)
Admin platform ───Bearer──► /platform/v1/wf/*            ┘
                                    │
          ┌─────────────────────────┴───────────────────────────────┐
          │ DB của ta: clients, keys, routes, residences,            │
          │ conversations, workflows, requests, messages, events,    │
          │ turns, jobs, approvals, operations, provider inbox,      │
          │ assets                                                   │
          └─────────────────────────┬───────────────────────────────┘
                                    │ jobs (tuần tự mỗi workflow)
                          Engine ───┴──► leader (AgentScope session sống suốt workflow)
                                            │  TeamSay / Case* tools (đã có)
                                            ├─► chuyên viên (worker)
                                            └─► PartnerTool (MCP của đối tác, bọc)
```

Một **workflow** = một vụ (`awp_cases`) + một phiên leader AgentScope sống lâu + trạng thái công khai. Vụ (case file) và cổng chống bịa, ngân sách, chi phí, hồ sơ agent giữ nguyên. Điều đổi: vụ không còn bị `CaseFinalize` đóng; vòng đời công khai do máy trạng thái ở mục 4 điều khiển, và vụ chỉ đóng khi workflow `closed`.

Lời nói với cư dân chỉ đi qua tool `CaseSay` (mục 6). Câu trả lời tự do của model **không bao giờ** thành tin nhắn công khai.

## 2. Quyết định đã chốt (người dùng, 10/10)

| # | Quyết định |
|---|---|
| D1 | Workforce v1 là API duy nhất cho đối tác. Gỡ `/platform/v1/intake`, `cases/by-ref/.../messages`, webhook, `CaseRequest`, `reply_to`, `deliver_*`, `DomainPack` (làm ở P4, ngay sau khi Workforce chạy). `/platform/v1` còn lại chỉ cho admin. |
| D2 | Không có tài liệu "kế hoạch 1.4.3". Hợp đồng là nguồn duy nhất. |
| D3 | Mọi câu chữ gửi cư dân đi qua `CaseSay` có cổng chống bịa. |
| D4 | Tool bất đồng bộ / cần cư dân đồng ý: cấu hình theo route qua API admin. |
| D5 | Một partner client = một tenant. Một `external_management_ref` = một route (hồ sơ agent, MCP, luật, chính sách riêng). |
| D6 | Cư dân xác nhận chi phí = approval (băm bảng chi phí). Xác nhận hoàn thành = `confirm_close` (rồi POST close). |
| D7 | Làm đủ P0–P5. P5 có Redis, Postgres, phục hồi sau crash, và MinIO để lưu ảnh. |
| D8 | Xóa mã cũ ngay ở P4. |
| D9 | Vụ việc chung, không chỉ sửa chữa. Reception xử lý được thì tự xử lý; cái còn lại leo thang sang platform. Platform kiểm soát cả vòng đời: liên hệ nhân viên, nhận chi phí, kiểm hóa đơn, gửi chi phí cho cư dân xác nhận, chỉ đóng khi cư dân xác nhận hoàn thành. Không có bước Ban quản lý duyệt phương án. |

## 3. Giả định (người triển khai làm theo; người dùng sẽ xem lại)

- **A1 `revision`**: `workflow_revision` bắt đầu từ 1. Tăng 1 mỗi khi một thay đổi được commit làm đổi `state`, tập approval treo, trạng thái operation, hoặc đóng. Tin nhắn không làm tăng. `expected_revision` của approval và close đều là revision của workflow (không phải của approval). `approval.required` và snapshot hiển thị revision cần gửi.
- **A2 residence**: khóa là `(partner_client, residence_id, external_user_id)`. Tạo: bỏ `expected_revision` hoặc 0 → 201, revision 1. Cập nhật: `expected_revision` phải bằng revision hiện tại, trừ khi nội dung y hệt (idempotent, 200, không tăng). Sai → 409 `REVISION_CONFLICT`. Route phải thuộc client và còn `active`; ref/user/residence không khớp → 403/422.
- **A3 tài sản (ảnh)**: hợp đồng v1 chỉ có text và nói file cần "contract riêng". Ta thêm *phần mở rộng cộng thêm* sau capability `attach_asset`: `POST /workforce/v1/partner/assets` (upload, lưu MinIO/S3) trả `asset_id`; message `{"type":"image","asset_id":...}` chỉ nhận khi key có capability này, ngược lại `422 UNSUPPORTED_MESSAGE_PART`. Ghi rõ là phần mở rộng ngoài hợp đồng, cần đối tác đồng ý.
- **A4 approval**: tool cần đồng ý phát ASK từ `on_check_permission`. Phản hồi quyết định `202` đúng hợp đồng; lượt agent tiếp tục bất đồng bộ, kết quả đọc qua SSE/history/GET request. Một reply đến khi workflow đang `awaiting_approval` trả `409 APPROVAL_PENDING` (details có `approval_id`), vì AgentScope lỗi khi nhận tin mới lúc đang đỗ.
- **A5 ticket nội bộ**: `ticket_id` được tạo (kèm event `ticket.created`) lần đầu có một operation không phải tra cứu; trước đó `null`.
- **A6 tin nhắn theo mẫu**: schema sự kiện provider (mục 7.3) có thể khai báo `message` mẫu; khi đó platform phát `assistant.message` từ mẫu mà **không gọi model** (rẻ, đúng nguồn). Sự kiện đánh dấu `wake` mới đánh thức leader.
- **A7 bí mật**: secret API chỉ lưu băm SHA-256. Secret ký HMAC của provider và header MCP phải đọc lại được, nên mã hóa Fernet bằng `AWP_SECRET_KEY` (bắt buộc ngoài chế độ dev); không bao giờ vào log, response, hoặc case file.
- **A8 giới hạn gọi MCP**: tool bọc MCP có `call_timeout` mặc định 8 giây và tối đa 9 (dưới ngưỡng 10 giây của `ToolOffloadMiddleware`, để tool có tác dụng phụ không bị đẩy xuống nền không bền).
- **A9 hết hạn**: `awaiting_user/approval/confirmation` không tự đổi trạng thái theo thời gian, trừ approval có `expires_at` (mặc định 24 giờ → `expired`, leader được báo và nói với cư dân). `active/accepted` không có lượt chạy quá `case_stall_seconds` → `needs_attention`. `waiting_external_event` quá `request_timeout_hours` (72) → `needs_attention` (mã `external_timeout`). Đây là chỉnh lại logic `expire_stalled` cũ.

## 4. Mô hình dữ liệu

Bảng mới, cùng `metadata` với `awp/db.py` (đặt trong `awp/workforce/tables.py`), tiền tố `wf_`. Kiểu cột theo cách `db.py` đang dùng (JSON, Float epoch cho thời gian). ID nền tảng: `req_`, `conv_`, `wf_`, `evt_`, `msg_`, `appr_`, `rcpt_`, `tkt_`, `route_`, `op_`, `job_`, `ast_` + uuid4 hex.

| Bảng | Cột chính |
|---|---|
| `wf_clients` | `id` (partner_client_id), `tenant`, `domain`, `environment`, `name`, `status`, `capabilities` JSON, `created_at` |
| `wf_keys` | `key_id` (PK, phần giữa `dp_` và `.`), `client_id` hoặc `integration_id`, `kind` customer\|provider, `secret_hash`, `operations` JSON, `routes` JSON (`["*"]` hoặc id), `status`, `expires_at`, `created_at`, `revoked_at` |
| `wf_signing_keys` | `key_id`, `integration_id`, `secret_enc`, `status` |
| `wf_integrations` | `id`, `client_id`, `status`, `event_schema` JSON (mục 7.3) |
| `wf_routes` | `id`, `client_id`, `external_management_ref`, `status` pending\|active\|suspended\|replaced, `revision`, `leader_profile`, `config` JSON (`ticket_binding_mode`, `residence_required`, `timezone`, `wait_seconds`, `rules` {safe_reply, phrase rules}, `policy` {`auto_close_read_only`, `approval_ttl_seconds`}), `created_at`. Duy nhất `(client_id, external_management_ref)` khi `active`. |
| `wf_mcp_servers` | `route_id`, `name`, `url`, `transport`, `headers_enc`, `timeout` |
| `wf_tools` | `route_id`, `name` (tên model thấy), `server`, `mcp_tool`, `kind` lookup\|action, `read_only`, `requires_consent`, `tracking` none\|events\|status_query, `client_reference_arg`, `idempotency_arg`, `consent_summary`, `call_timeout`, `description_override` |
| `wf_residences` | `client_id`, `residence_id`, `external_user_id`, `route_id`, `status`, `revision`, `updated_at` |
| `wf_conversations` | `id`, `client_id`, `route_id`, `external_user_id`, `external_conversation_id`, `external_ticket_id` (null được), `last_sequence`, `purged_through`, `created_at`. Duy nhất `(client_id, external_conversation_id)` |
| `wf_workflows` | `id`, `conversation_id`, `client_id`, `route_id`, `case_id`, `external_user_id`, `external_ticket_id`, `ticket_id`, `state`, `revision`, `expects` (reply\|confirmation\|null), `current_request_id`, `close_reason`, `attention_reason`, `last_activity_at`, `created_at`, `closed_at`. Duy nhất `(client_id, external_ticket_id)` khi không null |
| `wf_requests` | `id`, `client_id`, `external_request_id`, `command_type`, `fingerprint`, `route_id`, `conversation_id`, `workflow_id`, `status`, `response` JSON (kết quả đã đóng băng), `error` JSON, `accepted_at`, `completed_at`. Duy nhất `(client_id, external_request_id)` |
| `wf_messages` | `id`, `conversation_id`, `workflow_id`, `request_id` (null nếu hệ thống), `sender` user\|assistant\|system, `text`, `asset_ids` JSON, `created_at` |
| `wf_events` | `event_id` (PK), `conversation_id`, `sequence`, `event_type`, `workflow_id`, `ticket_id`, `external_ticket_id`, `payload` JSON, `occurred_at`, `recorded_at`. Duy nhất `(conversation_id, sequence)` |
| `wf_event_tombstones` | `event_id`, `conversation_id`, `sequence` (để trả 410 sau khi dọn) |
| `wf_turns` | `id`, `workflow_id`, `job_id`, `status` running\|completed\|parked\|error\|interrupted, `started_at`, `ended_at` |
| `wf_jobs` | `id`, `workflow_id`, `kind` resident_message\|provider_wake\|approval_resume\|nudge\|recover, `request_id`, `payload` JSON, `status` queued\|dispatched\|done\|failed, `lease_owner`, `lease_until`, `attempts`, `created_at` |
| `wf_approvals` | `id`, `workflow_id`, `conversation_id`, `client_id`, `external_user_id`, `session_id`, `agent_id`, `tool_call_id`, `tool_name`, `arguments` (chuỗi JSON chuẩn hóa), `arguments_hash`, `quote_ref`, `summary` JSON, `status` pending\|approved\|rejected\|expired\|cancelled, `workflow_revision`, `expires_at`, `decided_at`, `decision_request_id`, `created_at` |
| `wf_operations` | `id`, `workflow_id`, `route_id`, `integration_id`, `tool_name`, `tool_call_id`, `args_hash`, `client_reference` (duy nhất), `external_job_id`, `status` intent\|sent\|pending\|completed\|failed\|unknown, `normalized_status`, `last_rank`, `provider_version`, `result` JSON, `created_at`, `updated_at` |
| `wf_provider_inbox` | `receipt_id`, `integration_id`, `external_event_id`, `payload_hash`, `event_type`, `payload` JSON, `operation_id`, `workflow_id`, `ingestion_status`, `normalized_status`, `error` JSON, `provider_version`, `received_at`, `applied_at`. Duy nhất `(integration_id, external_event_id)` |
| `wf_assets` | `id`, `client_id`, `conversation_id`, `object_key`, `content_type`, `size`, `sha256`, `created_at` |

`sequence` của event được cấp trong cùng giao dịch ghi event (tăng `wf_conversations.last_sequence`), nên thứ tự commit = thứ tự sequence. Event và thay đổi trạng thái luôn cùng một giao dịch (hàm `emit(conn, ...)` nhận connection của giao dịch).

## 5. Máy trạng thái và `next_action`

`workflow_state` (§9.3): `accepted, active, waiting_external_event, awaiting_user, awaiting_approval, awaiting_confirmation, needs_attention, blocked_authorization, blocked_route_changed, closed`.

| state | next_action |
|---|---|
| closed | none |
| awaiting_user | submit_reply |
| awaiting_approval | submit_approval |
| awaiting_confirmation | confirm_close |
| waiting_external_event | watch_events |
| needs_attention, blocked_* | resolve_attention |
| accepted, active (có request đang chạy) | watch_request |

`request_status`: accepted → queued → running → completed | failed | blocked. Request `completed` khi workflow đã vào trạng thái nghỉ (mọi state trừ accepted/active) sau chuỗi lượt do request đó khởi phát. Request `failed/blocked` trả HTTP 200 với `next_action` resolve_attention hoặc none và `error` công khai (§9.1, cuối).

Chuyển trạng thái sau khi một lượt của leader kết thúc (hàm thuần `settle(workflow, facts)` để test riêng):

1. Còn approval `pending` → `awaiting_approval`.
2. Chuyên viên còn chưa báo cáo, hoặc còn câu hỏi/phản biện mở → vẫn `active` (lượt tiếp do báo cáo của họ đánh thức leader; không đóng request).
3. `CaseSay` cuối của lượt có `expects=reply` → `awaiting_user`; `expects=confirmation` → `awaiting_confirmation`.
4. Còn operation theo dõi chưa kết thúc → `waiting_external_event`.
5. Leader đã `CaseFinalize(resolved)`: chỉ tra cứu (không operation hành động, không approval) và `policy.auto_close_read_only` → `closed` (lý do `answered`); ngược lại → `awaiting_confirmation`. `needs_human/cannot_resolve` → `needs_attention`.
6. Lượt kết thúc không rơi vào mục nào: watchdog nhắc tối đa 2 lần ("hãy dùng CaseSay hoặc CaseFinalize"), sau đó `needs_attention` (mã `leader_silent`) kèm tin nhắn an toàn công khai.

Chuyển bởi API/sự kiện: close hợp lệ → `closed`; tin reply của cư dân vào workflow không đóng → `active`; route bị đình chỉ hoặc key hết quyền → `blocked_authorization`; route bị thay thế → `blocked_route_changed` (workflow cũ giữ route cũ, không chuyển lịch sử sang route mới).

## 6. Phần đối diện agent

Giữ nguyên: hồ sơ, case file, `CaseFact/Gap/Ask/Answer/Challenge/Read/Decide`, digest, chống bịa, ngân sách, `calc_sum`, tầng model, cắt tool theo vai, Jev tùy chọn.

Thêm hoặc đổi (chỉ leader dùng các tool này; cổng tool theo hồ sơ/vai như hiện nay):

- **`CaseSay(text, expects="none"|"reply"|"confirmation", cites=[])`**: kiểm `check_text(text, sources, rules, trusted)` như `CaseFinalize`; sai thì trả lỗi để model sửa. Thành công ghi `wf_messages` (gắn `request_id` của chuỗi lượt đang chạy) + event `assistant.message` trong một giao dịch, và đặt `expects`. Không gọi được khi workflow đã đóng.
- **`CaseAskConsent(summary, items=[{label, amount}], total, quote_ref?, cites=[])`**: dành cho xin cư dân đồng ý chi phí (D6). Kiểm `total` bằng tổng `items` (Decimal, dùng `calc_sum`) và mọi con số có trong bằng chứng được dẫn; sai thì trả lỗi (đây là kiểm thử "tổng sai bị từ chối"). Công cụ luôn bị cổng approval chặn bằng ASK (mục 6.1). Khi được duyệt: ghi bằng chứng "cư dân đã đồng ý ..." vào case file và trả kết quả cho agent; khi từ chối: kết quả DENIED.
- **`CaseFinalize`**: giữ kiểm tra như cũ (cite, challenge mở, số liệu, Jev), nhưng thay vì đóng vụ thì: ghi `final`, phát `answer` như một `assistant.message` (qua cùng đường với `CaseSay`), rồi gọi `settle`. Bỏ `confirm_with`, `open_requests`, `CaseRequest`.
- **`PartnerTool`** (mục 8): mỗi dòng `wf_tools` của route thành một `ToolBase`.
- Prompt leader (trong `profiles/compile.py`): cư dân chỉ thấy `CaseSay`; hỏi khi thiếu dữ kiện; không nói "đã làm" nếu chưa có kết quả tool xác minh; chờ `pending` thay vì bịa; dùng `CaseAskConsent` trước khi chốt chi phí; khi nhận sự kiện hoàn thành, hỏi cư dân xác nhận bằng `CaseSay(expects="confirmation")`.
- **Bối cảnh mỗi lượt** (mở rộng `DigestMiddleware`): tiêm từ DB của ta — trạng thái workflow, operation đang theo dõi (`client_reference`, `external_job_id`, trạng thái chuẩn hóa), approval đang treo/vừa quyết, tin cư dân gần nhất. Dữ kiện nghiệp vụ không được chỉ nằm trong ngữ cảnh (nén ngữ cảnh có thể mất).
- **Tin cư dân và nội dung provider là dữ liệu không tin cậy**: bọc trong `<resident-message id=...>` / `<provider-event ...>`, ghi làm bằng chứng đúng loại (`intake` cho lời cư dân, `provider:<event_type>` cho provider), làm sạch ký tự điều khiển, cắt độ dài.

### 6.1 Cổng approval

Trong `ToolGateMiddleware.on_check_permission`: nếu tool thuộc tập "cần đồng ý" (`CaseAskConsent` và `wf_tools.requires_consent`) và `tool_call.state != ALLOWED`:
1. Chuẩn hóa `tool_call.input` (JSON canonical, khóa sắp xếp), băm `sha256:<hex>`.
2. Ghi `wf_approvals` (pending, `workflow_revision`, `expires_at`), event `approval.required` và tăng revision, trong một giao dịch; khóa theo `(session_id, tool_call.id)` để ghi lại không tạo bản thứ hai.
3. Trả `PermissionDecision(ASK)`; lượt đỗ (không có `ReplyEndEvent`, coi `RequireUserConfirmEvent` là điểm kết thúc lượt).
Khi cư dân quyết định (API §9.8): kiểm audience/ticket/conversation/workflow, chưa hết hạn, `expected_revision`, `arguments_hash` khớp bản đã lưu và `quote_ref`; **ta tự dựng** `UserConfirmResultEvent` từ bản đã lưu (không lấy gì từ client), không bao giờ truyền `rules`; xếp lượt resume; `approve` chạy tool, `reject` trả DENIED.
Đã xác minh bằng test ở P0 (mục 13): ASK từ middleware đỗ được ngay cả khi phiên ở `dont_ask`.

## 7. API

### 7.1 Chung (§5, §6)
- Mount ở `/workforce/v1`. `SecurityMiddleware` cho các đường `/workforce/` đi thẳng (xác thực nằm trong router); các đường khác giữ như cũ.
- `Authorization: ApiKey dp_<id>.<secret>`; so sánh hằng thời gian trên băm; kiểm trạng thái, hạn, operation, phạm vi route/domain. Sai → 401; thiếu quyền hoặc route/audience sai → 403.
- Lỗi theo §6.3: `{"error": {"code", "message", "details", "request_id", "retryable"}}`; không lộ secret, prompt, trace, id nội bộ, dữ liệu người khác. Dùng `APIRoute` riêng cho router này để không đổi handler lỗi toàn cục của AgentScope: JSON hỏng/field chồng chéo → 400 `INVALID_REQUEST`; sai schema/giá trị → 422 `VALIDATION_FAILED`.
- Giới hạn: body 256 KiB (413), text 1–20000 ký tự, id đối tác 1–200 ký tự không có ký tự điều khiển, `external_management_ref` 1–128, `data` provider ≤ 64 KiB, history mặc định 100 tối đa 500. Rate limit theo key (429 + `Retry-After`).
- Mọi thời gian RFC 3339 UTC (`...Z`). `X-Correlation-Id` được ghi lại, không thay idempotency.

### 7.2 Customer API (§8, §9)
Làm đủ: `POST partner/routes/{id}/confirm`, `PUT partner/residences/{id}`, `POST partner/requests` (`start_workflow`, `workflow_reply`), `GET partner/requests/{id}`, `GET partner/conversations/{id}`, `GET .../event-history`, `GET .../events` (SSE), `POST partner/approvals/{id}/decision`, `POST partner/workflows/{id}/close`. Chi tiết field, mã lỗi, thứ tự kiểm tra: theo hợp đồng. Các điểm cần chú ý:

- **Thứ tự kiểm tra** `POST requests`: xác thực → quyền → schema → route (thuộc client, `active`, key được phép) → idempotency (§9.1) → residence → binding vé (`EXTERNAL_TICKET_REQUIRED`, `TICKET_ALREADY_BOUND`, `CONVERSATION_ALREADY_BOUND`, `WORKFLOW_REFERENCE_REQUIRED`, `WORKFLOW_BINDING_MISMATCH`, `WORKFLOW_CLOSED`) → trạng thái (`APPROVAL_PENDING`) → ghi request/workflow/job trong một giao dịch → chờ.
- **Idempotency chung** cho request/reply/approval/close theo `(client, external_request_id)`; vân tay = băm JSON chuẩn hóa của phần có nghĩa (command, ref, user, ticket, conversation, workflow, message, decision...). Cùng id + cùng vân tay → trả đúng bản đã lưu (200 nếu xong, 202 nếu còn chạy, và nếu còn chạy thì chờ lại tới hạn); khác → 409 `IDEMPOTENCY_CONFLICT`. Phản hồi đã xong là bản **đóng băng** (`wf_requests.response`), không dựng lại, nên `message_id` giữ nguyên khi phát lại. Idempotency kiểm trước CAS (§9.9).
- **Chờ lượt** (§3, §9.1): sau khi ghi, handler chờ `wait_seconds` (route; mặc định 25, test đặt nhỏ) trên DB (thăm dò 100–250 ms) cộng tín hiệu bus để dậy sớm; request xong → 200 kèm `result.messages` (các `wf_messages` có `request_id` này), hết hạn → 202. Ngắt kết nối HTTP không hủy gì.
- **SSE** (§9.6): xác thực và kiểm con trỏ *trước* khi gửi header; không cursor → phát lại từ đầu log; có cursor → các event sau nó; cả `Last-Event-ID` và `after_cursor` mà khác nhau → 400; con trỏ của hội thoại/audience khác → từ chối; con trỏ trong `wf_event_tombstones` hoặc dưới `purged_through` → 410 `EVENT_CURSOR_EXPIRED` kèm `snapshot_url`. Khung: `id:`, `event:`, `data:` (JSON y hệt phần tử history), dòng trống; heartbeat comment `: heartbeat` mỗi 15 giây không tạo event; đọc DB rồi mới nghe tín hiệu (tránh khe hở); thăm dò DB dự phòng để chạy được khi không có Redis; xác thực lại key/grant tối đa 60 giây, mất quyền thì ngắt. Lỗi sau khi stream mở → ngắt kết nối.
- **Snapshot** (§9.4): đọc nhất quán một giao dịch: workflows (state, next_action, revision), messages, pending approvals được phép xem, `snapshot_cursor` (null nếu chưa có event). Phân trang messages: 200 gần nhất, `messages_before` để lùi.
- **GET** customer bắt buộc `external_user_id` khớp audience đã lưu; không khớp → 404 (không lộ tồn tại).
- **Close** (§9.9): kiểm quyền, idempotency, CAS `expected_revision` (409 `REVISION_CONFLICT`), nếu còn operation chưa terminal mà không có `stop_tracking_only=true` + reason `resident_requested_stop_tracking` → 409 `WORKFLOW_NOT_READY_TO_CLOSE`; ghi `state=closed`, event `workflow.closed`, đóng vụ trong một giao dịch; không gọi tool hủy. `close` không do model quyết định.

### 7.3 Provider Event API (§10)
- `POST provider/job-events`: ApiKey (`publish_job_event`) + `X-Partner-Timestamp/Key-Id/Signature` trên **raw bytes** (`<ts>.<body>`), HMAC-SHA256 hằng thời gian, lệch tối đa 5 phút. Lưu hộp thư + lệnh xử lý trong một giao dịch rồi mới trả `202` với `receipt_id`, `ingestion_status`, `duplicate`, `received_at`, `status_url`.
- Trùng `(integration, external_event_id)` cùng nội dung → receipt cũ, `duplicate: true`; khác nội dung → 409 `EVENT_ID_CONFLICT`. Có cả `external_job_id` và `client_reference` mà trỏ khác operation → 422 `JOB_CORRELATION_MISMATCH`. Không nối được → `quarantined` (job đối soát chạy lại khi có operation mới khớp; không đoán theo tên/ghi chú).
- `event_schema` của integration: `{"version","version_mode":"snapshot"|"delta","events":{"<event_type>":{"status","rank","terminal","outcome","public_status","public_fields":[...],"message":"mẫu có {field}","wake":bool,"evidence":bool}}}`. `event_type` không có trong schema → 422 `UNKNOWN_EVENT_TYPE`. Thứ tự: `provider_version` thấp hơn hoặc bằng đã xử lý và `rank` thấp hơn không làm lùi trạng thái (receipt `rejected`, mã `STALE_EVENT`, vẫn lưu); cùng version khác nội dung → conflict; `delta` thiếu version giữa → giữ `processing` đến khi đủ hoặc hết hạn thì `needs_attention`. Sự kiện đến sau khi workflow đóng: lưu để audit (`applied` với ghi chú `after_close`), không mở lại, không đánh thức.
- Áp sự kiện (một giao dịch): cập nhật operation, event `operation.status_changed` (+ `ticket.status_changed` nếu có `public_status`), tin nhắn mẫu nếu có, ghi bằng chứng vào case file nếu `evidence`, rồi nếu `wake` thì xếp job `provider_wake`. Nội dung provider vào ngữ cảnh model chỉ qua trường đã nằm trong schema.
- `GET provider/event-receipts/{id}` (§10.2): chỉ receipt của chính integration; không trả manager, người dùng, nội dung chat.

### 7.4 Admin (Bearer admin, `/platform/v1/wf`)
Tạo client; tạo/thu hồi/xoay key (trả `dp_<id>.<secret>` đúng một lần; key provider kèm signing key); tạo route `pending` (trả `route_id`, `revision`), đình chỉ, thay thế; khai báo MCP server và tool cho route; khai báo integration và `event_schema`; xem workflows, operations, receipts, approvals; `resolve` cho `needs_attention` (`resume` hoặc `close`). Admin không bao giờ nhìn thấy secret đã lưu.

## 8. Công cụ đối tác qua MCP

- Mỗi route có `wf_mcp_servers` và `wf_tools`. Factory tool (`extra_agent_tools`) tạo `PartnerTool` cho mọi agent của route đó, kể cả worker; **không** dùng `/workspace/mcp` của AgentScope. URL MCP kiểm SSRF (chặn nội bộ trừ khi cấu hình cho phép), header lấy từ secret đã mã hóa. Dùng SDK `mcp` (có sẵn trong venv); giữ kết nối/stateless, cache danh sách tool, không `list_tools` ở mỗi bước; `structuredContent` được ghép vào text kết quả.
- **Tra cứu** (`kind=lookup`): gọi đồng bộ, kết quả thành bằng chứng như mọi tool.
- **Hành động** (`kind=action`): *trước khi gọi* ghi `wf_operations` (`intent`, `client_reference`, `args_hash`) và `ticket` nếu cần (A5), commit, rồi mới gọi MCP với `client_reference` (và khóa idempotency) chèn vào tham số theo cấu hình. Gặp lại cùng `(workflow, tool, args_hash, tool_call_id)` sau crash thì trả kết quả đã lưu hoặc kiểm tra trạng thái, **không gọi lần hai**.
- Kết quả MCP chuẩn hóa: `confirmed|completed` → operation xong đồng bộ (không theo dõi); `pending|accepted|queued` + `tracking != none` → `pending`, lưu `external_job_id` nếu có, tool trả cho agent "đang chờ, tham chiếu X, bạn sẽ được báo, chỉ nói điều đã xác minh"; lỗi rõ → `failed`; hết giờ/không rõ → `unknown`: không thử lại, agent được báo, workflow `needs_attention` nếu không có cách tra trạng thái (`status_query`).
- `requires_consent` → đi qua cổng approval (6.1) trước khi gọi.
- Tool có tác dụng phụ không bao giờ chạy ngoài quyền: quyền của profile + `on_check_permission`; tra cứu phải có `readOnlyHint` hoặc cấu hình `read_only`.

## 9. Bền bỉ và nhiều tiến trình (P5)

- **Hàng đợi `wf_jobs`**: mỗi workflow tối đa một job `dispatched`. Dispatch = nhận quyền (UPDATE có điều kiện, `FOR UPDATE SKIP LOCKED` trên Postgres), gọi `AgentScopeClient.say`/resume; xong khi lượt kết thúc và `settle` chạy. Job có `lease_until`, gia hạn khi còn chạy; quá hạn → xếp lại (tối đa 3 lần rồi `needs_attention`).
- **Phục hồi khi khởi động**: quét job `dispatched` hết lease; workflow `waiting_external_event`/`awaiting_approval` không cần làm gì (trạng thái ở DB của ta); approval đỗ mà `wf_approvals` mồ côi thì đối soát với phiên; không tạo operation mới (khóa `client_reference` + `tool_call_id`).
- **Bus**: `AWP_REDIS_URL` → `RedisMessageBus`; không có thì `InMemoryMessageBus`. Mọi thứ đúng khi không có tín hiệu bus (thăm dò DB). **Postgres**: `AWP_DB_URL` và `AWP_AGENTSCOPE_DB_URL` đổi sang `postgresql+asyncpg://`; có Alembic cho bảng `awp`/`wf` (bước triển khai riêng, `python -m awp migrate`).
- **Retention** (§12): dọn event cũ hơn 90 ngày sau khi workflow đóng (ghi tombstone, cập nhật `purged_through`), inbox provider 180 ngày; không bao giờ dọn workflow mở / event đang xử lý / operation `unknown`/`pending`.
- **Tài sản (A3)**: `awp/assets.py`, backend `local` và `s3` (MinIO). Client S3 tự ký SigV4 bằng `httpx` (không thêm phụ thuộc), kiểm bằng máy chủ giả trong test và MinIO thật bằng Docker (`cgr.dev/chainguard/minio` có sẵn). Giới hạn loại (`image/png|jpeg|webp|gif`), kích thước, quét magic bytes; không bao giờ tải URL tùy ý từ message; URL tải xuống ký có hạn, chỉ cho phía nhân viên qua tham số tool.
- **Chi phí/ngân sách**: giữ như hiện nay; thêm đặt trước (reservation) trong DB để nhiều agent song song không vượt ngân sách (bước tùy chọn của P5 nếu còn thời gian).

## 10. Các pha và tiêu chí nghiệm thu

| Pha | Việc | Nghiệm thu |
|---|---|---|
| P0 | Sửa test nền bị đỏ theo thứ tự chạy; kiểm 4 điểm chưa xác minh bằng test ngắn: ASK từ middleware trong `dont_ask`; `POST /chat` khi phiên đang chạy; `call_tool` MCP qua SDK với timeout; offload 10 giây với tool bọc; ghi `docs/research/KIEM_CHUNG_P0.md` | Mỗi điểm một test và kết luận ghi lại; bộ test nền xanh ổn định (chạy 3 lần) |
| P1 | S1: cấu hình, bảng, lỗi công khai, auth ApiKey, giới hạn, admin (client/key/route/integration), confirm route, residences. S2: conversation/workflow/request, idempotency, binding, events, history, snapshot, SSE, với *engine giả* | Test hợp đồng: các mã lỗi binding, idempotency (cùng id khác body → 409), SSE nối lại không mất event, replay trước lần mở SSE đầu, cursor cũ → 410, hai hội thoại không lẫn, thiếu quyền → 403 |
| P2 | S3: engine thật (job, turn, `CaseSay`, `settle`, chờ 25 giây, watchdog). S4: approval + close + `CaseAskConsent` | Luồng §13.1 (tra cứu → chọn → approval → đặt xác nhận ngay → confirm_close → close) và read-only → closed/none, bằng model giả; hai ticket song song không lẫn; reply khi chờ approval → 409 |
| P3 | S5: `PartnerTool`/operation + Provider Event API | Luồng §13.4 hoàn chỉnh; phát lại POST không gọi thợ lần hai; event trùng, sai thứ tự, đến sớm, đến sau close; tổng chi phí sai bị từ chối; không đóng khi chờ thợ |
| P4 | S6: gỡ mã cũ (D1); chuyển test cũ sang API mới; bộ kiểm tuân thủ ánh xạ từng dòng §13.9 và §14.3 | Không còn tham chiếu `intake`/webhook/`CaseRequest`/`DomainPack`; mỗi dòng §13.9 có một test tên rõ; toàn bộ test xanh |
| P5 | S7: Redis bus, Postgres (Docker `awp-test-*`), lease/phục hồi, retention, Alembic, tài sản MinIO, tải 20 workflow song song | Toàn bộ bộ test chạy trên Postgres; crash giả lập giữa lượt chờ không tạo job/operation mới; SSE đa tiến trình qua Redis; 20 workflow đồng thời không lẫn; ảnh lưu/đọc từ MinIO thật |

## 11. Bốn kiểm thử người dùng đã duyệt, viết lại theo Workforce v1

1. **Chờ nhân viên 20 phút không bị đóng nhầm**: workflow `waiting_external_event` qua `case_stall_seconds` vẫn nguyên; chỉ `needs_attention` sau `request_timeout_hours`.
2. **Yêu cầu thi công nhận lại sự kiện chi phí**: tool hành động trả `pending`, provider gửi `repair.cost_reported` (đánh thức), leader xử lý và hỏi cư dân.
3. **Tổng chi phí sai bị từ chối**: `CaseAskConsent` với tổng sai trả lỗi, không tạo approval.
4. **Chỉ đóng khi cư dân xác nhận**: không có đường nào đóng trừ POST close hợp lệ (hoặc auto-close tra cứu); leader nói "xong" không đóng được.

## 12. Ngoài phạm vi / chưa kiểm (phải nói thẳng trong báo cáo cuối)

Model thật và chất lượng tiếng Việt; MCP thật của Vinhomes; Postgres/Redis chỉ kiểm trong Docker cục bộ; chất lượng nén ngữ cảnh với workflow nhiều ngày; giao diện quản trị và SDK; khai báo thật của Vinhomes (hồ sơ agent, MCP, schema sự kiện) làm sau ở `vinhome_Recident`.

## 13. Kết quả P0 (bắt buộc, ghi đè các mục trên khi mâu thuẫn)

Đã chạy test thật (thư mục `tests/probes/`, ghi chú ở `docs/research/KIEM_CHUNG_P0_*.md`; đọc các ghi chú đó, có mã mẫu dùng lại được). Baseline: đã sửa một race thật trong `CaseFinalize` (leader chốt khi còn câu hỏi đồng nghiệp chưa trả lời); bộ test nền 35 xanh.

**Approval (mục 6.1, A4, A9)**
1. `ToolGateMiddleware.on_check_permission` hiện trả ALLOW sớm cho tool tiền tố `Case/Team/AgentCreate/AgentInvite` mà không gọi `next_handler`. Kiểm tra "cần đồng ý" phải nằm **sau** kiểm `allowed(name)` và **trước** nhánh `OWN_TOOLS`, nếu không `CaseAskConsent` lọt qua cổng.
2. Ở lượt `ALLOWED` khi resume, AgentScope chép `input` của sự kiện vào lời gọi. Cổng phải yêu cầu hàng approval `approved` **và** `sha256(canonical(input)) == arguments_hash` đã lưu, nếu không DENY.
3. Một lượt resume có thể đỗ lại lần nữa (hai tool cần đồng ý trong một reply) và không có `ReplyEndEvent`. Mọi lượt, kể cả `approval_resume`, kết thúc mà thấy `RequireUserConfirmEvent` và không có `ReplyEndEvent` → `awaiting_approval` với approval mới và revision+1.
4. A4 chỉnh lại: AgentScope **không** báo lỗi cho `POST /chat` khi phiên đang đỗ (trả 200, lưu tin lạc + khung assistant rỗng + `REPLY_END(error,'setup')` trên kênh phiên). Vì vậy `409 APPROVAL_PENDING` do API của ta quyết định **trước khi** xếp job, và không bao giờ chuyển tiếp kênh phiên AgentScope ra ngoài.
5. `POST /chat` không mang được `UserInterruptEvent`. Hủy/hết hạn approval dùng `enqueue_run_trigger(kind="resume", inputs=UserInterruptEvent(reply_id))` (module `agentscope.app._bus_ops`, tiền tố gạch dưới: ghi là phụ thuộc nội bộ). Lượt interrupt không gọi model, nên cần job sau đó để leader báo cư dân.
6. Lưu `agent_id`/`session_id` của agent đã hỏi (kể cả worker) và resume thẳng vào đó. Không bao giờ truyền `ConfirmResult.rules`. Idempotency theo trạng thái hàng approval vẫn bắt buộc (sự kiện resume gửi lại chỉ là lưới đỡ cuối).
7. Sau crash, sự kiện duyệt gửi lại có thể chạy tool lần nữa, nên tool `requires_consent` cũng phải qua khóa chống trùng operation (mục 8).

**Lượt, job, đánh thức (mục 5, 9, A6)**
8. Job chỉ `done` khi mọi lượt nó khởi phát đã kết thúc **và** phiên rảnh (`bus.is_locked(session_lock)` sai, hoặc `GET /sessions/{id}/status == idle`). Gửi ngay sau khi `on_reply` kết thúc luôn trả 409.
9. `AgentScopeClient.say` hiện ném `RuntimeError` khi status ≥ 300: thêm lỗi có kiểu `SessionBusy` cho 409 (không mất tin, retry an toàn); dispatcher chờ rảnh rồi gửi, và vẫn phải có vòng retry vì AgentScope tự bắt đầu một lượt (TeamSay của worker) giữa lúc kiểm và gửi.
10. HTTP 200 của `/chat` **không** có nghĩa đã nhận: có hai đường mất tin (dựng agent lỗi; khóa đang bị giữ). Job chỉ coi là đã nhận khi thấy hàng `wf_turns` mang `Msg.id` của job trong thời hạn; nếu không thì gửi lại cùng `Msg.id` hoặc `needs_attention`.
11. `provider_wake` và nudge của watchdog là **job gửi bằng `say()`** (Msg bọc `<provider-event job=...>`), không dùng `deliver_to_inbox`/`Runtime.deliver` (cho lượt rỗng thừa, không có khóa tương quan). Chỉ giữ inbox cho đánh thức nội bộ của AgentScope (worker TeamSay, AgentCreate, báo lỗi worker). Sửa `LeaderWatchdog._after` thành job nudge. Không dùng `enqueue_run_trigger(kind="message")` làm hàng đợi (đảo thứ tự).
12. `wf_turns.job_id` cho phép null (lượt do báo cáo worker đánh thức); thêm cột `trigger` (message|continue) và `msg_id` nullable. Tại `on_reply` end không biết còn lượt kế tiếp trong cùng run hay không, nên: ghi lượt ngay, còn `settle` và chuyển request sang `completed` chạy khi phiên rảnh, idempotent, và chạy lại ở lần rảnh sau nếu lại có lượt mới.
13. `TurnRecorder` phải bắt exception: lỗi model là exception trong `on_reply`, không phải `ReplyEndEvent(ERROR)`; mất ~8–9 giây qua ~12 HTTP call (cân nhắc giảm retry của SDK), là chặn trên cho chờ 25 giây. Interrupt thì có `ReplyEndEvent(interrupted)`.
14. Khi tạo phiên luôn truyền `name` (nếu không có thêm một lần gọi model đặt tiêu đề dưới khóa phiên).

**MCP (mục 8, A8)**
15. Không giữ session MCP: mỗi lần gọi mở phiên mới trên một `httpx` client dùng chung (13 ms cục bộ); phiên dùng chung chỉ là tối ưu tùy chọn cho tra cứu. Dùng `streamable_http_client` + `create_mcp_http_client` (`streamablehttp_client` đã deprecated) và `send_request(CallToolRequest ...)`; **không** dùng `ClientSession.call_tool` (nó gọi ngầm `tools/list` và ném `RuntimeError` sau khi lệnh đã chạy).
16. `timeout` là ngân sách cả lần gọi (connect + call + đóng), bọc ngoài bằng `asyncio.timeout(timeout + ~0.5)`; mặc định 8 s, tối đa 9 s; đặt `read_timeout_seconds` và `httpx.Timeout(read >= timeout+5)`.
17. Bảng ánh xạ: `failed` khi lỗi trước khi gửi (connect, 401/403, 404 session terminated) hoặc `isError`/status `failed|rejected`. `unknown` (không bao giờ thử lại) khi hết giờ, rơi kết nối giữa chừng, 5xx trên `tools/call`, hoặc hành động trả không có `status` đọc được. Tra cứu read-only được thử lại **một** lần và chỉ khi phiên chết. `pending|accepted|queued` + `tracking != none` → `pending`; `confirmed|completed` → ok.
18. `ToolChunk` SUCCESS cho ok và pending (thành bằng chứng, có tham chiếu); ERROR cho failed và unknown (không thành bằng chứng; dấu vết ở `wf_operations`). Văn bản cho agent: `PENDING: ... Say only that it is pending`, `FAILED: ...`, `UNKNOWN: ... Do not retry`. Lọc text lỗi của server MCP trước khi đưa cho agent. Bắt `CancelledError` lạ (`current_task().cancelling()==0`) và đổi thành kết quả.
19. Tool tra cứu phải cấu hình `read_only` khi đối tác không đặt `readOnlyHint` (nếu không bị DENY dưới `dont_ask`). Tool hành động phải được ALLOW bởi `on_check_permission` (sau cổng approval).
20. SSRF và chuyển hướng: kiểm ở httpx client của ta (chặn redirect hoặc kiểm lại từng bước).

**Offload (A8)**
21. Hạn chót phải bọc **toàn bộ thân tool** (chuẩn bị + ghi operation + gọi đối tác) bằng một `asyncio.timeout` ngoài từ lúc vào tool (đồng hồ 10 s bắt đầu từ `on_acting`). Hết giờ: hủy lời gọi, ghi operation `unknown`, không bao giờ `failed`. Tool tự ghi kết quả vào bảng operation trong thân tool (kể cả nhánh timeout), vì ngắt lượt trong 10 giây đầu không hủy tool và không ai đọc giá trị trả về.
22. Phòng thủ chiều sâu: mọi `PartnerTool` khai `allow_offload=False` và `build_app` truyền `custom_agent_cls` dùng `OffloadPolicy/agent_cls_with` (mẫu ở `tests/probes/p0_offload_stack.py`); không dùng `is_state_injected`. Test: ngữ cảnh leader không bao giờ chứa "running in background".

**Chống trùng và phục hồi (mục 8, 9)**
23. Khóa chống trùng operation là `(workflow, tool, args_hash)` với `client_reference` dẫn xuất xác định, **không** có `tool_call_id` (id này không ổn định qua crash). Chèn dòng nguyên tử (INSERT với khóa duy nhất rồi rẽ nhánh). Gặp dòng cũ chưa terminal (`intent|sent|pending|unknown`) thì trả dòng cũ, không gọi mới. Một lời gọi *cố ý* lặp lại cùng tham số (ví dụ gọi thợ lần hai) phải khác ở tham số hoặc có `idempotency_nonce` do agent cấp, và chỉ được phép khi dòng cũ đã terminal.
24. Dòng `intent` sau restart (không biết đã gửi chưa): nếu có `idempotency_arg` thì gửi lại cùng `client_reference`; nếu có `status_query` thì tra; nếu không thì `unknown` + `needs_attention`, không retry. "Đúng một lần" cần provider idempotent theo `client_reference`.
25. Phục hồi khi khởi động: xếp lại job hết lease với payload gốc (AgentScope không khôi phục lượt đã mất); với Redis chỉ `DEL agentscope:session:lock:<sid>` sau khi lease job/node đã hết hạn; đối soát `wf_approvals` với trạng thái phiên (approval pending mà phiên không `awaiting_permission` → hủy hàng hoặc xếp lại job; phiên `awaiting_permission` mà ta không có approval pending → gửi `UserInterruptEvent`); chặn `expire_stalled` cho workflow đang chờ khôi phục. Tiêu chí P5 thêm ca "khóa Redis kẹt".
