# MCP Vinhomes v2 — bàn giao cho backend platform

## 1. Phạm vi đã chốt

Domain xác thực cư dân, xác minh căn hộ, tiếp nhận và tạo ticket. Khi đủ thông tin, domain gửi `start_workflow`; platform tạo session/workflow cho ticket và quản lý điều phối, tiến độ cùng ngoại lệ. **Không có bước BQL duyệt yêu cầu, màn hình tiếp nhận BQL hoặc tool chuyển sang một hàng đợi BQL tại domain.** Quyết định này thay đề xuất escalation trong bản nghiên cứu ngày 13/10.

Nhân viên vẫn nhận việc, đi hiện trường, lập báo giá và gửi kết quả qua domain. Cư dân tự bấm thẻ báo giá và xác nhận kết quả. Các gate an ninh/QC/báo giá đang có không bị bỏ qua vì platform quản lý session.

Mọi loại ticket đi qua điểm bàn giao hiện tại đều được xếp lệnh `start_workflow` khi bridge bật, kể cả incident an ninh thông thường. Domain không lọc ticket khỏi Platform chỉ vì Platform chưa có quyền thực thi một thao tác. Mỗi ticket chỉ tạo một link/lệnh start khi bàn giao lại; worker retry cùng `external_request_id`. Cấu hình/ủy quyền route giữa hai hệ thống là bước onboarding một lần, không phải BQL duyệt từng yêu cầu. Các thao tác booking/thẻ/khách đang xử lý ngoài điểm bàn giao ticket chưa tự trở thành session; mở rộng các route đó cần adapter riêng.

MCP v2 là version hợp đồng nghiệp vụ, không phải tuyên bố đã nâng MCP protocol lên bản mới nhất. SDK/dependency giữ nguyên; handshake đã test dùng `2025-03-26`. Hai bên chốt protocol thực tế trước onboarding.

## 2. Catalog đúng 7 tool

| Tool | Mục đích sau bàn giao |
|---|---|
| `vh_ticket_get` | Đọc snapshot mới nhất, version, công việc, báo giá, xác nhận cư dân, SLA và các thao tác được phép |
| `vh_knowledge_search` | Tra đoạn tài liệu trong scope ticket, kèm document/version/chunk references |
| `vh_staff_available` | Tra nhân viên theo chuyên môn/đơn vị và ca ở thời điểm yêu cầu; không phải giữ chỗ lịch |
| `vh_work_order_dispatch` | Tạo/giao work order cho ticket hiện hữu; pending là chờ nhận, queued là chờ nguồn lực |
| `vh_work_order_reschedule` | Đổi lịch trước khi nhân viên lên đường, dựa trên yêu cầu có nguồn từ cư dân |
| `vh_ticket_cancel` | Hủy theo luật hiện có; chặn việc đã đến nơi/đang làm/đã xong và điều động an ninh |
| `vh_ticket_add_note` | Bổ sung nội dung cho người xử lý |

Không cấp tool tạo lại ticket, chọn/xác định lại căn hộ/cư dân, khách/thẻ/booking/công nợ toàn hộ, approve quote/plan, QC pass, thanh toán hoặc đóng thay cư dân. Catalog/declaration/profile dùng allowlist từng tên, không dùng `vh_*`.

## 3. Credential: control-plane khác runtime theo session

`VINHOMES_API_PLATFORM_MCP_TOKEN` là Bearer do **backend platform** giữ riêng: dùng discovery và gọi API cấp grant. Nó không trực tiếp gọi tool nghiệp vụ. Token không vào browser, prompt hay tham số tool.

Khi xử lý `start_workflow`, backend platform đã biết `external_request_id`, `external_ticket_id` và workflow vừa tạo. Backend tự gọi:

```http
POST /api/business/platform/mcp-grants
Authorization: Bearer <CONTROL_PLANE_TOKEN>
Content-Type: application/json
```

```json
{
  "ticket_id": "<external_ticket_id>",
  "external_request_id": "<ID start_workflow domain đã gửi>",
  "workflow_id": "<workflow vừa tạo>",
  "grant_request_id": "<UUID do backend platform cấp và giữ nguyên khi retry>",
  "tools": ["vh_ticket_get", "vh_knowledge_search", "vh_staff_available", "vh_work_order_dispatch", "vh_work_order_reschedule", "vh_ticket_cancel", "vh_ticket_add_note"],
  "ttl_seconds": 3600
}
```

Response: `grant_id`, `ticket_id`, `workflow_id`, `bearer_token`, `expires_at`, `tools`; `Cache-Control: no-store`. Gọi lại cùng grant_request_id/nội dung trả cùng token và expiry, không gia hạn âm thầm; đổi nội dung, grant revoked/hết hạn trả 409. Gia hạn bằng một grant_request_id mới khi workflow vẫn active.

Backend gắn `Authorization: Bearer <bearer_token>` vào MCP transport **riêng của workflow đó**, không để model chọn key. `POST /mcp` vẫn là MCP endpoint. Token có hash trong DB, expiry/revocation, ticket/management/tool scope; workflow được đối chiếu khi domain nhận được ID từ response start. Pending handover không bị deadlock vì domain chưa kịp lưu workflow_id.

**Không có thao tác người dùng/BQL duyệt grant.** Endpoint cấp grant là control-plane extension domain đã chuẩn bị; nhóm platform phải tích hợp lời gọi và credential theo workflow. Chưa nghiệm thu platform thật thì không được nói cơ chế này đã chạy end-to-end. Nếu platform chỉ có một header chung cho mọi workflow, phải bổ sung adapter trước khi bật bridge v2.

Operator có thể issue/revoke grant riêng cho pilot bằng `python -m vinhomes_api.platform_access` với owner `DATABASE_URL`; CLI ghi credential vào `--output`, không in token. Đây là công cụ vận hành, không phải luồng duyệt ticket hằng ngày. Không cấp quyền DB/CLI owner cho model.

## 4. Tool calls, CAS và receipt

- Mọi tool nhận ticket_id từ bàn giao. Server không coi ID là bằng chứng quyền.
- Trước **lệnh ghi mới**, đọc `vh_ticket_get`, truyền `expected_ticket_version`. Thiếu hoặc stale version bị từ chối. Trạng thái/policy vẫn kiểm lại trong transaction.
- Lệnh ghi có client_reference do backend platform cấp. Timeout/mất response: retry cùng reference và nội dung; không cấp reference mới để thử side effect.
- Receipt hợp lệ replay ngay cả sau link đóng, với grant còn hiệu lực và đúng ticket/tool/payload. Reference đổi payload/tool/ticket bị chặn. Receipt lịch sử chưa có request_hash giữ quy tắc replay cũ.
- Đổi lịch/hủy nhận source_message_id do domain gắn vào tin nhắn sau bàn giao. Server kiểm đúng người gửi, chat/ticket, membership active và khoảng thời gian hiệu lực. Đây là bằng chứng nguồn lời yêu cầu; không biến text thành quyết định báo giá hoặc xác nhận hoàn thành.

Grant có thể chỉ cho read; `policy.actions` phản ánh cả nghiệp vụ và danh sách tool của grant. Policy snapshot không thay thế kiểm tra khi ghi.

## 5. Kết quả/lỗi máy đọc được

Tool trả JSON text để client cũ dễ chuyển đổi, cùng `structuredContent` theo outputSchema. Có `schema_version: vinhomes-mcp-v2`, `correlation_id` và các trường nghiệp vụ. Lỗi thực thi `isError=true`, ví dụ:

```json
{
  "schema_version": "vinhomes-mcp-v2",
  "correlation_id": "<uuid>",
  "status": "failed",
  "error": {"code": "STALE_TICKET_VERSION", "message": "Ticket đã thay đổi.", "retryable": false}
}
```

Các mã quan trọng: `TICKET_GRANT_REQUIRED`, `TICKET_SCOPE_FORBIDDEN`, `TICKET_VERSION_REQUIRED`, `STALE_TICKET_VERSION`, `REFERENCE_CONFLICT`, `RESIDENT_SOURCE_REQUIRED`, `RESIDENT_SOURCE_FORBIDDEN`, `BUSINESS_RULE_REFUSED`, `TEMPORARILY_UNAVAILABLE`, `OUTCOME_UNKNOWN`, `OUTPUT_LIMIT`. Không suy ra “chưa có side effect” từ mất kết nối/commit acknowledgement; đối soát bằng receipt.

401 là Bearer sai/hết hạn/revoked; 429 có Retry-After; 413 vượt request limit. JSON-RPC/SDK validation errors là lớp protocol, không giả thành business success.

## 6. Trạng thái và giới hạn

`ticket_get` bổ sung ticket_version/snapshot_seq/read_at, work_order_id/version, policy, confirmation, SLA và phân trang milestones. `history_before_seq` lấy từ `history_page.next_before_seq`; tối đa 100 event/page. Snapshot tối đa 50 work orders gần nhất, có work_orders_truncated để không coi đây là toàn bộ lịch sử.

`status=completed` giữ làm alias tương thích kết quả operation. **Không dùng nó để nói cư dân đã đồng ý hoặc ticket đã đóng.** Đọc:

- `confirmation.result_published`: đã có kết quả được công bố trong trạng thái hiện tại.
- `confirmation.waiting_for_resident`: đang chờ quyết định cư dân.
- `confirmation.resident_accepted`: có quyết định đồng ý và ticket đã đóng.
- `confirmation.ticket_closed`: trạng thái ticket closed.

Giờ phục vụ tại appointment_at được tra theo ca; current load không phải reservation tương lai được bảo đảm. Khi offer, domain kiểm cả ca hiện tại và ca của thời điểm hẹn. Không hứa ETA/giờ hoàn tất khi domain chưa xác nhận.

Request/output MCP tối đa 256 KiB; phần thực thi tool có timeout 7 giây; quota hiện tại 120 request/phút/grant/process. Host/Origin có allowlist; host public lấy từ allowed origins, tên DNS nội bộ bổ sung bằng MCP_ALLOWED_HOSTS. Điều chỉnh quota/timeout chỉ sau chốt production limits với platform.

## 7. Handover và sự kiện

Outer request giữ contract partner hiện có. Text bàn giao v1.1 bổ sung handover_version, ticket_version, category_code và deadlines khi có. Không thêm JSON metadata/attachment không được partner hỗ trợ. Identity/căn hộ đã có; không xác định lại bằng tool.

Staff progress vẫn dùng 15 event types hiện hữu, HMAC raw bytes, provider_version và receipt. Không tự thêm event type chưa đăng ký. SLA warning/breach dùng workflow_reply text do domain tạo, `own=true` và domain_notice_key chống trùng. Platform quản lý attention/session; domain không tạo hàng đợi BQL.

Work order BQL tạo mới ngoài MCP chưa tự thành operation do platform đăng ký. Chưa mở một luồng “adopt job” hay bịa client_reference. Nếu muốn theo dõi nhánh này bằng provider events, hai bên phải chốt binding/adoption; `ticket_get` vẫn đọc được trạng thái công việc trong ticket.

## 8. Acceptance pack và vận hành

Test domain dùng PostgreSQL riêng: token/route/ticket/workflow/tool scope, expiry/revoke, control-plane retry, CAS/reference conflict, source cư dân, pagination, quota/Host, HTTP báo giá → bằng chứng → QC → resolved → cư dân đóng hoặc rework. Không gọi Agent/provider/embedding.

Khi onboarding cần cung cấp: URL/version partner thực tế, supported MCP protocol, route mapping, credential từng purpose, adapter grant theo workflow, schema/events/retention, knowledge pack đang hiệu lực và đầu mối kỹ thuật. Không gửi DB dump, account export, source private hoặc token trong tài liệu Git.

Các tài liệu đi kèm: [NOI_WORKFORCE_V1.md](NOI_WORKFORCE_V1.md), `deploy/platform/vinhomes-declaration.json`, `deploy/platform/README.md`, [deploy/HTTPS.md](../../deploy/HTTPS.md), báo cáo release cuối và evidence riêng đã ẩn credential. Phần Agent do chủ dự án tự nghiệm thu.
