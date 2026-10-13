# Workforce v1: hướng dẫn nối một đối tác

Cập nhật: 13/10/2026 (phase P4; mục 8, gửi ảnh, thêm ở P5c). Viết cho **người vận hành platform** (làm các bước admin) và **người tích hợp phía đối tác** (gọi API công khai). Hợp đồng là `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md` (bản `1.3-draft`); tài liệu này chỉ nói *làm thế nào*. API cũ (`/platform/v1/intake`, webhook, khóa dịch vụ `AWP_SERVICE_KEYS`) không còn: đối tác chỉ dùng `/workforce/v1`.

Mọi bước admin dưới đây (mục 1 đến 5) cũng làm được trên console quản trị tại `$P/console` (đăng nhập bằng khóa admin; `docs/WORKFORCE_V1_VAN_HANH.md` mục 10): console gọi đúng các API này, nên các lệnh `curl` vẫn là tài liệu chuẩn. Riêng tạo và sửa hồ sơ agent bằng JSON (bước 1) chỉ có ở API; trên console, hồ sơ được tạo qua "Tạo agent qua chat".

Quy ước trong ví dụ: `$P` là địa chỉ platform (ví dụ `http://127.0.0.1:8800`), `$ADMIN` là một khóa trong `AWP_ADMIN_KEYS` (Bearer), id và bí mật trong ngoặc nhọn là giá trị trả về ở bước trước. Khóa của đối tác có dạng `dp_<id>.<secret>`, chỉ hiện **một lần** khi tạo; platform chỉ lưu băm SHA-256.

## 0. Việc phải có trước

- Chạy platform (PostgreSQL, migration, biến môi trường, sao lưu, lịch dọn dữ liệu) ở `docs/WORKFORCE_V1_VAN_HANH.md`.
- Platform chạy với `AWP_ADMIN_KEYS` và `AWP_SECRET_KEY` (khóa Fernet, để niêm bí mật ký và header MCP). Thiếu `AWP_SECRET_KEY` thì các API cần cất bí mật trả 503.
- Một **hồ sơ leader** đã công bố trong tenant của admin (bước 1) và ít nhất một model còn khóa (`GET /platform/v1/models`).
- Đối tác cho biết: `external_management_ref` của từng văn phòng (một ref = một route), có cần `residence_id` không, có cần ticket không, backend nghiệp vụ nào gửi tiến độ, MCP server nào làm tool.

## 1. Hồ sơ agent (một lần cho tenant)

```
curl -X POST $P/platform/v1/profiles -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{
  "key": "bql_leader", "name": "Trợ lý Ban quản lý", "role": "leader",
  "mission": "trợ lý của Ban quản lý, nói chuyện với cư dân.",
  "instructions": "Trả lời bằng tiếng Việt. Chỉ nói điều tool đã xác minh.",
  "tools_allow": ["partner_*"], "model_tier": "standard"}'
curl -X POST $P/platform/v1/profiles/bql_leader/versions/1/evals -H "Authorization: Bearer $ADMIN" \
  -H "Content-Type: application/json" -d '{"wait_seconds": 300}'
curl -X POST $P/platform/v1/profiles/bql_leader/versions/1/publish -H "Authorization: Bearer $ADMIN"
```

Phát hành có **cổng đánh giá**: `publish` trả `409` (`detail.code = EVAL_REQUIRED`) cho tới khi lần đánh giá gần nhất của đúng version đó đạt (`POST …/evals` chạy bộ ca của platform cộng các ca của tenant trong sandbox, không gọi MCP của đối tác). Admin có thể phát hành không qua cổng bằng `{"override_reason": "..."}`; lý do được ghi vào lịch sử (`GET /platform/v1/profiles/{key}/history`). Quay về version cũ: `POST /platform/v1/profiles/{key}/rollback {"to_version": n}`. Chi tiết: `docs/WORKFORCE_V1_VAN_HANH.md` mục 9.

`tools_allow` cấp cho leader các tool của đối tác theo tên (mẫu `fnmatch`); chuyên viên có hồ sơ riêng (`role: specialist`, liệt kê trong `team` của leader) và chỉ thấy tool mà hồ sơ của họ liệt kê.

## 2. Tạo client và khóa

Một client = một đối tác = một tenant dữ liệu. `environment` là `sandbox` hoặc `production`; hai môi trường là hai client khác nhau, khóa không dùng chéo.

```
curl -X POST $P/platform/v1/wf/clients -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"name": "Đối tác A", "domain": "homes", "environment": "sandbox"}'
# → {"client_id": "client_…", ...}

curl -X POST $P/platform/v1/wf/clients/{client_id}/keys -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"operations": ["submit_request","reply","read_result","receive_events","submit_consent","close_workflow","confirm_route","sync_residence"]}'
# → {"key_id": "…", "api_key": "dp_<id>.<secret>", ...}   (giữ lại: không xem được lần hai)
```

Có thể thu hẹp khóa theo `operations`, theo `routes` (danh sách `route_id` thay cho `["*"]`) và đặt `expires_at`. `POST /platform/v1/wf/keys/{key_id}/revoke` thu hồi ngay; `…/rotate` cấp khóa mới cùng quyền.

## 3. Manager và route: route tạo ở trạng thái `pending`, đối tác xác nhận

Mỗi route thuộc đúng một **manager** (tài khoản ban quản lý); một client có thể có nhiều manager, mỗi `external_management_ref` thuộc đúng một manager. Tạo manager trước, rồi (tùy chọn) cấp khóa vận hành cho họ:

```
curl -X POST $P/platform/v1/wf/clients/{client_id}/managers -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"name": "Ban quản lý tòa A"}'
# → {"manager_id": "mgr_…", ...}

curl -X POST $P/platform/v1/wf/managers/{manager_id}/keys -H "Authorization: Bearer $ADMIN"
# → {"key_id": "…", "api_key": "mk_<id>.<secret>", ...}   (giữ lại: không xem được lần hai)
```

Khóa manager dùng như `Authorization: Bearer mk_<id>.<secret>` trên `/platform/v1/wf`: chỉ thấy và thao tác được route, workflow, operation, approval, receipt, `resolve`, MCP/tool của **route của chính manager đó**, và đọc được hồ sơ agent mà các route đó dùng (`GET /platform/v1/profiles`). Mọi thứ khác (client, khóa, manager, tạo/đình chỉ/thay route, sửa hồ sơ, API AgentScope) trả 403; hàng của manager khác trả 404. Khóa admin của tenant vẫn là quyền cao nhất. Thu hồi: `POST …/managers/{id}/keys/{key_id}/revoke`; tắt cả tài khoản: `POST …/managers/{id}/disable`.

`leader_profile` phải là một hồ sơ `role: leader` đã có trong tenant (nháp cũng được; chạy thì cần bản đã phát hành), nếu không `422`.

```
curl -X POST $P/platform/v1/wf/clients/{client_id}/routes -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{
  "external_management_ref": "BQL-OP1-A", "leader_profile": "bql_leader", "manager_id": "{manager_id}",
  "config": {"ticket_binding_mode": "required", "residence_required": false, "timezone": "Asia/Ho_Chi_Minh",
             "rules": {"safe_reply": "Ban quản lý sẽ liên hệ lại với bạn.", "phrase_rules": []},
             "policy": {"auto_close_read_only": true}}}'
# → {"route_id": "route_…", "revision": 1, "status": "pending", ...}
```

`rules.phrase_rules` thêm vào (không thay thế) luật chống bịa có sẵn: cụm "đã sửa/đã xong/đã đặt…" luôn cần kết quả tool đã xác minh. `safe_reply` là câu gửi cư dân khi leader không nói được điều có căn cứ. `wait_seconds` (mặc định 25) là thời gian một POST chờ lượt xong trước khi trả 202.

Đối tác xác nhận route bằng khóa của mình (lệnh này chứng minh khóa và route khớp nhau):

```
curl -X POST $P/workforce/v1/partner/routes/{route_id}/confirm -H "Authorization: ApiKey dp_<id>.<secret>" \
  -H "Content-Type: application/json" -d '{"schema_version": "1", "expected_revision": 1, "external_management_ref": "BQL-OP1-A"}'
# → {"route_id": …, "status": "active", "revision": 2, "allowed_operations": [...]}
```

Route `pending` chưa nhận tin. Đổi văn phòng: `POST /platform/v1/wf/routes/{id}/replace` (route cũ thành `replaced`, workflow cũ giữ route cũ và chuyển `blocked_route_changed`, route mới lại `pending` chờ xác nhận, thuộc cùng manager và mang theo bản sao MCP server và tool của route cũ, nguyên trạng thái); tạm dừng: `…/suspend`.

Nếu route đòi `residence_required`, đối tác đồng bộ cư dân trước: `PUT $P/workforce/v1/partner/residences/{residence_id}` với `{"schema_version":"1","external_user_id":…,"external_management_ref":…,"status":"active"}`.

## 4. MCP server và tool của route (phía admin)

Tool của đối tác là MCP (streamable HTTP). Header (token) được niêm Fernet, `GET` chỉ trả *tên* header. URL bị kiểm SSRF khi ghi và khi nối (chặn địa chỉ nội bộ, trừ khi `AWP_MCP_ALLOW_PRIVATE=1` ở môi trường kín).

Có hai cách. **Cách 1, kho tool (khuyến nghị):** thêm server (đang tắt), bật nó để platform tự đọc `tools/list`, rồi kích hoạt từng tool.

```
curl -X POST $P/platform/v1/wf/routes/{route_id}/mcp -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"name": "bql", "url": "https://mcp.doitac.example/mcp", "headers": {"Authorization": "Bearer <token>"}}'
curl -X POST $P/platform/v1/wf/routes/{route_id}/mcp/bql/enable -H "Authorization: Bearer $ADMIN"
# → {"server": {...,"enabled": true}, "tools": [...], "added": [...], "changed": [], "gone": [], "rejected": []}
curl -X PATCH $P/platform/v1/wf/routes/{route_id}/tools/book_repair -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"status": "active", "tracking": "events", "client_reference_arg": "client_reference", "integration_id": "{integration_id}"}'
```

Mặc định an toàn khi phát hiện: tool có `readOnlyHint` → tra cứu (`lookup`), `active` ngay; mọi tool khác → hành động (`action`) cần cư dân đồng ý, ở trạng thái `proposed` và **không agent nào dùng được** cho tới khi một người kích hoạt bằng PATCH và nói rõ `tracking`. Tool trùng tên tool của platform bị từ chối (xem `rejected`). `…/refresh` so lại với server (tool mới, tool biến mất → `gone`, schema đổi → lưu bản mới và ghi `schema_changed_at`; tra cứu mất `readOnlyHint` → thành hành động `proposed`); `…/disable` tắt server (tool của nó biến mất khỏi agent, dòng giữ nguyên). Mỗi tool giữ ảnh chụp schema lúc phát hiện, nên khi server MCP tắt (kể cả lúc platform khởi động lại) agent vẫn thấy tool và lời gọi báo lỗi rõ ràng. `GET …/tools?status=proposed` liệt kê tool chờ kích hoạt. Tool phát hiện được mà server **không** đánh dấu `readOnlyHint` chỉ thành tra cứu (`"kind": "lookup", "read_only": true`) khi gửi kèm lý do ở `consent_waiver` (lý do được lưu; thiếu → `422`). Tool có input schema lớn hơn 32 KiB không được nhận (`rejected`: "its schema is too large"). `enable`/`refresh` trả `409` khi server bị tắt, sửa hoặc xóa trong lúc platform đang đọc danh sách tool: không có gì được ghi, gọi lại là được.

**Cách 2, khai cả bộ (cũ, vẫn chạy):** PUT thay toàn bộ; server khai theo cách này bật sẵn, tool `active` ngay.

```
curl -X PUT $P/platform/v1/wf/routes/{route_id}/mcp -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{
  "servers": [{"name": "bql", "url": "https://mcp.doitac.example/mcp", "headers": {"Authorization": "Bearer <token>"}}]}'

curl -X PUT $P/platform/v1/wf/routes/{route_id}/tools -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{
  "tools": [
    {"name": "partner_lookup_ticket", "server": "bql", "mcp_tool": "lookup_ticket", "kind": "lookup", "read_only": true},
    {"name": "partner_book_repair", "server": "bql", "mcp_tool": "book_repair", "kind": "action",
     "tracking": "events", "client_reference_arg": "client_reference", "integration_id": "{integration_id}",
     "requires_consent": true, "consent_summary": "Đặt lịch sửa chữa lúc {slot}", "call_timeout": 8}]}'
```

Quy tắc đáng nhớ: `lookup` không có tác dụng phụ, phải `read_only` (cấu hình hoặc `readOnlyHint` của MCP), không dùng được `requires_consent`/`tracking`. `action` có tác dụng phụ: nền tảng ghi một dòng operation *trước khi* gọi, đưa `client_reference` (và khóa idempotency) vào tham số theo `client_reference_arg`/`idempotency_arg` (đối tác phải idempotent theo khóa đó: "đúng một lần" chỉ đúng khi đối tác làm vậy), và không bao giờ gọi lần hai khi gặp lại cùng lời gọi. `tracking`: `none` (kết quả xong ngay, ví dụ `confirmed`), `events` (kết quả `pending`, tiến độ về qua Provider Event API ở bước 5, cần `client_reference_arg` hoặc `idempotency_arg`), `status_query` (platform tự hỏi lại bằng `status_tool`). `call_timeout` tối đa 9 giây. Đặt tên tool tránh `Case*`, `Team*`, `Agent*`, `calc_sum`. `requires_consent` buộc cư dân đồng ý (approval) trước khi tool chạy; với `action` đây là **mặc định**. Muốn một hành động chạy không cần hỏi phải gửi `"requires_consent": false` kèm `"consent_waiver": "<lý do>"` (lý do được lưu lại); thiếu lý do → `422`.

## 5. Integration, schema sự kiện và khóa provider

Chỉ cần khi đối tác có tool `tracking: events`. Schema nói với platform *mỗi loại sự kiện nghĩa là gì*; platform không có tên trạng thái của ngành nào trong mã.

```
curl -X POST $P/platform/v1/wf/clients/{client_id}/integrations -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{
  "event_schema": {"version": "1", "version_mode": "snapshot", "events": {
    "repair.assigned":  {"status": "assigned", "rank": 10, "public_status": "assigned",
                         "public_fields": ["worker_name", "eta_minutes"], "field_types": {"eta_minutes": "count"},
                         "message": "Thợ {worker_name} sẽ đến sau khoảng {eta_minutes} phút."},
    "repair.completed": {"status": "completed", "rank": 90, "terminal": true, "outcome": "completed",
                         "public_status": "completed", "public_fields": ["summary"], "wake": true, "evidence": true}}}}'
# → {"integration_id": "intg_…"}

curl -X POST $P/platform/v1/wf/integrations/{integration_id}/keys -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{}'
# → {"api_key": "dp_….…", "signing_key": {"key_id": "…", "secret": "…"}}   (hiện một lần)
```

Ý nghĩa: `rank` cao hơn là tiến xa hơn (sự kiện hạng thấp đến muộn bị `STALE_EVENT`, không lùi trạng thái); `terminal` + `outcome` (`completed`, `cancelled`, …) là kết thúc; `public_fields` là những trường *duy nhất* ra khỏi hộp thư vào event công khai, tin nhắn và ngữ cảnh model; `message` là tin mẫu gửi cư dân **không gọi model**; `wake: true` mới đánh thức leader; `reopen: true` cho loại sự kiện sửa/mở lại. Gắn integration vào tool bằng `integration_id` ở bước 4. Xoay/thu hồi khóa ký: `POST …/integrations/{id}/signing-keys` và `…/signing-keys/{key_id}/revoke`.

Backend nghiệp vụ gửi sự kiện (chữ ký HMAC-SHA256 trên **byte thô** của body, chuỗi ký là `<timestamp>.<body>`, lệch giờ tối đa 5 phút):

```python
import hashlib, hmac, json, time, httpx
body = json.dumps({"schema_version": "1", "external_event_id": "evt-009", "client_reference": "cr_…",
                   "event_type": "repair.assigned", "provider_version": 1, "occurred_at": "2026-10-10T02:30:00Z",
                   "data": {"worker_name": "An", "eta_minutes": 20}}).encode()
ts = str(int(time.time()))
sig = "v1=" + hmac.new(SIGNING_SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
httpx.post(f"{P}/workforce/v1/provider/job-events", content=body, headers={
    "Authorization": f"ApiKey {PROVIDER_API_KEY}", "Content-Type": "application/json",
    "X-Partner-Timestamp": ts, "X-Partner-Key-Id": SIGNING_KEY_ID, "X-Partner-Signature": sig})   # → 202 + receipt_id
```

Gửi lại phải giữ nguyên `external_event_id` và nội dung (trùng cùng nội dung → 202 `duplicate: true`; khác nội dung → 409 `EVENT_ID_CONFLICT`). Không gửi manager, conversation hay workflow id: platform tự nối bằng `client_reference`/`external_job_id`. Xem biên nhận: `GET /workforce/v1/provider/event-receipts/{receipt_id}`; admin xem `GET /platform/v1/wf/receipts`.

## 6. Kiểm thử trước khi mở

1. `POST /workforce/v1/partner/requests` với `command_type: start_workflow` (xem hợp đồng 9.1: `external_request_id`, `external_management_ref`, `external_user_id`, `external_ticket_id`, `external_conversation_id`, `message`). Gửi lại *y hệt* phải ra cùng kết quả (idempotency) và không gọi tool lần hai.
2. Đọc `workflow_state` và `next_action` trong phản hồi: `submit_reply` → `workflow_reply`; `submit_approval` → `POST approvals/{id}/decision` (kèm `arguments_hash` và `expected_revision` lấy từ snapshot); `watch_events` → mở SSE `GET …/conversations/{id}/events` (không cursor lần đầu, nối lại bằng `Last-Event-ID`); `confirm_close` → hỏi cư dân rồi `POST workflows/{id}/close`; `resolve_attention` → người vận hành xem `GET /platform/v1/wf/workflows` và `POST …/workflows/{id}/resolve` (`resume` hoặc `close`).
3. Chạy bộ kiểm tuân thủ phía platform (mô phỏng, không phải bằng chứng production): `pytest tests/workforce/test_compliance.py`; bảng từng dòng ở `docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md`. Bằng chứng sandbox ghi riêng, không ghi mock là production pass (hợp đồng 14.3).

## 7. Lỗi thường gặp

| Triệu chứng | Nguyên nhân |
|---|---|
| 401 `UNAUTHENTICATED` với `details.reason` | `revoked`, `expired`, `client_disabled` (khóa đúng nhưng không còn dùng được); sai bí mật thì không có `reason`. Khóa admin không dùng ở `/workforce`, khóa `dp_…` không dùng ở `/platform`. |
| 403 `ROUTE_NOT_AUTHORIZED` | Route chưa `active` (quên `confirm`), khóa không phủ route, route bị đình chỉ/thay thế (`details.reason`). |
| 409 `WORKFLOW_BINDING_MISMATCH` / `TICKET_ALREADY_BOUND` / `CONVERSATION_ALREADY_BOUND` | Ghép sai ticket, conversation, workflow. Một hộp chat = một ticket = một workflow; sửa ánh xạ phía đối tác, không retry. |
| 409 `APPROVAL_PENDING` | Đang chờ cư dân quyết định approval; gửi quyết định trước, không gửi reply. |
| 409 `REVISION_CONFLICT` | `expected_revision` cũ: lấy lại từ snapshot. |
| 202 thay vì 200 | Lượt chưa xong trong `wait_seconds`: đọc `GET requests/{id}`, history hoặc SSE; không có "202 rồi 200" trên cùng POST. |
| Sự kiện provider `quarantined` | Chưa nối được operation (tool chưa lưu mã job, `client_reference` sai, key không phủ route); quá `AWP_WF_QUARANTINE_SECONDS` (3600) thì `UNMATCHED_EVENT`. |
| Workflow `needs_attention` | `GET /platform/v1/wf/workflows/{id}` cho `attention_reason`: `leader_silent`, `engine_error`, `operation_unknown`, `external_timeout`, `stalled`, `provider_gap`… Người vận hành `resolve`. |

## 8. Gửi ảnh: PHẦN MỞ RỘNG NGOÀI HỢP ĐỒNG V1 (chỉ dùng khi đối tác đã đồng ý)

**Đọc trước.** Hợp đồng `1.3-draft` chỉ chuẩn hóa tin nhắn chữ; mục 6.2 của nó nói: "Ảnh/file cần asset upload contract riêng và chỉ tham chiếu bằng `asset_id`... Gửi attachment khi chưa được cấp capability trả `422 UNSUPPORTED_MESSAGE_PART`". Mục này mô tả phần "contract riêng" đó **như platform đang làm**. Nó **không nằm trong hợp đồng**, tắt với mọi client cho tới khi người vận hành bật, và hình dạng của nó (tên trường, mã lỗi, giới hạn) có thể đổi khi hai bên chốt contract ảnh chính thức. Với client chưa bật, không gì khác hợp đồng: tin `type: image` nhận `422 UNSUPPORTED_MESSAGE_PART`.

**Bật (người vận hành).** Platform phải có kho ảnh (`docs/WORKFORCE_V1_VAN_HANH.md` mục 12). Rồi cấp capability cho client và cấp quyền cho khóa:

```
curl -X PATCH $P/platform/v1/wf/clients/{client_id} -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"capabilities": ["attach_asset"]}'                       # tắt lại: {"capabilities": []}  (có hiệu lực ngay)
curl -X POST $P/platform/v1/wf/clients/{client_id}/keys -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" \
  -d '{"operations": ["submit_request","reply","read_result","receive_events","submit_consent","close_workflow","attach_asset"]}'
```

Cần **cả hai**: capability trên client và operation `attach_asset` trên khóa. Trên console: màn Đối tác, dòng "Gửi ảnh" của client, và ô `attach_asset` khi tạo khóa.

**Bước 1, đối tác tải ảnh lên** (thân request là chính các byte của ảnh, không phải JSON, không phải multipart; ba id nằm trong query):

```
curl -X POST "$P/workforce/v1/partner/assets?external_request_id=up-0001&external_user_id=resident-123&external_conversation_id=vh-chat-789" \
  -H "Authorization: ApiKey dp_<id>.<secret>" -H "Content-Type: image/jpeg" --data-binary @anh.jpg
# → 201 {"asset_id": "ast_…", "content_type": "image/jpeg", "size": 183422, "sha256": "…",
#        "external_user_id": "resident-123", "external_conversation_id": "vh-chat-789", "created_at": "…Z"}
```

**Bước 2, gửi tin nhắn mang ảnh** (trong `start_workflow` hoặc `workflow_reply`, mọi trường khác y như hợp đồng 9.1/9.2):

```
"message": {"type": "image", "asset_id": "ast_…", "text": "Nước rò ở chỗ này."}        # text là tùy chọn
```

Quy tắc:

- **Ảnh thuộc về đúng bộ ba đã khai lúc tải lên**: client của khóa, `external_user_id`, `external_conversation_id`. Tin nhắn chỉ mang được ảnh khi cả ba trùng. Ảnh của cư dân khác, của hộp chat khác, của client khác, hay mã không tồn tại đều nhận **cùng một** `404 NOT_FOUND` (không lộ ảnh có tồn tại hay không). Một ảnh dùng lại được trong nhiều tin của cùng hộp chat, không dùng được ở hộp chat khác: tải lại.
- **Loại ảnh xét theo các byte đầu của tệp**, không theo header `Content-Type` (header bị bỏ qua): PNG, JPEG, WebP, GIF. Thứ khác → `422 VALIDATION_FAILED` (`errors[0].field = body`). Platform không giải mã, không thu nhỏ, không quét nội dung ảnh.
- **Tối đa 5 MiB** (`AWP_ASSET_MAX_BYTES`) → `413 PAYLOAD_TOO_LARGE`, cắt ngay khi đang đọc. Khóa, quyền và capability được xét **trước** khi đọc byte nào của thân.
- **Idempotent** theo `(client, external_request_id)`, chung không gian id với mọi lệnh khác của hợp đồng 9.1: gửi lại đúng upload đó (cùng byte, cùng bộ id) trả `201` với đúng `asset_id` cũ; cùng id mà khác byte hoặc khác bộ id, hoặc id đã dùng cho một request/quyết định/close → `409 IDEMPOTENCY_CONFLICT`.
- **Một tin nhắn mang một ảnh.** Nhiều ảnh là nhiều tin. Không có `asset_ids`, không có `url`: trường lạ → `422`. **Platform không bao giờ tải một địa chỉ**: ảnh chỉ vào bằng upload, và một URL viết trong `text` chỉ là chữ.
- **Câu trả lời không bao giờ nói ảnh nằm ở đâu.** Snapshot (`messages[].asset_ids`, chỉ có ở tin mang ảnh) và history (`request.accepted` có `payload.asset_ids`) chỉ nêu `asset_id`. Không có API cho đối tác tải ảnh về: họ đã có ảnh.
- **Agent không nhìn thấy ảnh.** Leader được báo "cư dân gửi N ảnh" kèm `asset_id`, loại và kích thước; nó không mô tả được nội dung ảnh. Điều nó làm được là chuyển ảnh cho phía đối tác: gọi `CaseAssetLink(asset_id)` lấy một link GET ký sẵn, sống `AWP_ASSET_URL_TTL` giây (mặc định 900), cho đúng một ảnh của chính workflow đó, và đặt link vào **tham số một tool MCP của đối tác** (ví dụ `note` hay `photo_url` của tool gọi thợ). **MCP server của đối tác nên tải ảnh ngay khi nhận lời gọi** rồi tự lưu, đừng chuyển link đi tiếp: link hết hạn. Link mang tên máy kho ảnh mà platform được cấu hình (`AWP_S3_PUBLIC_ENDPOINT`); hai bên phải thống nhất địa chỉ đó tới được từ MCP server của đối tác.
- Cư dân không bao giờ nhận link: tin nhắn của agent có link bị cổng chặn, và bản xin đồng ý (`approval.summary.arguments`) ghi `[image link]` ở chỗ có link.
- **Giữ bao lâu**: ảnh bị xóa khỏi kho `AWP_CLOSED_RETENTION_DAYS` (90) ngày sau khi workflow của hộp chat đó đóng (không bao giờ khi workflow còn mở, và không khi còn operation chưa kết thúc); ảnh tải lên mà không gửi trong tin nào bị xóa sau cùng số ngày đó. Tin nhắn vẫn giữ `asset_id`.

| Lỗi | Khi nào |
|---|---|
| `403 PERMISSION_DENIED`, `details.operation = attach_asset` | Khóa không có operation `attach_asset` |
| `403 PERMISSION_DENIED`, `details.capability = attach_asset` | Client chưa được bật gửi ảnh (upload) |
| `422 UNSUPPORTED_MESSAGE_PART`, `details.part_type = image` | Tin `type: image` của client chưa được bật; mọi `type` khác `text`/`image` luôn nhận mã này |
| `422 VALIDATION_FAILED` | Thiếu/sai một trong ba id của query; thân không phải một trong bốn loại ảnh; phần `message` sai dạng (`asset_id` không đúng `ast_` + 32 ký tự hex, có trường lạ) |
| `413 PAYLOAD_TOO_LARGE` | Ảnh lớn hơn giới hạn |
| `404 NOT_FOUND`, `details.field = message.asset_id` | `asset_id` không phải ảnh của đúng client + cư dân + hộp chat này |
| `409 IDEMPOTENCY_CONFLICT` | `external_request_id` đã dùng cho một upload khác hoặc một lệnh khác |
| `503 INTERNAL_ERROR`, `details.reason = asset_store_unavailable` (`retryable: true`) | Kho ảnh tạm không trả lời: gửi lại cùng `external_request_id` |
| `503 INTERNAL_ERROR`, `details.reason = asset_store_not_configured` | Platform này không có kho ảnh: hỏi người vận hành |

Thứ tự kiểm của upload: khóa → operation → capability → ba id → có kho → kích thước (khi đọc) → loại ảnh → idempotency → ghi. Một upload bị từ chối không để lại gì.

Mẫu mã chạy được cho cả hai bước: `platform_VP/deploy/smoke.py` (hàm `upload`, `assets`, `start_body`).
