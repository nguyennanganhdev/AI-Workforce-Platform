# Kế hoạch: ba phần còn thiếu của API đối tác và sandbox

14/10/2026 · Người đọc: PM · Trạng thái: **đề xuất, chờ duyệt** (chưa code)

## Tóm tắt

- Ba phần còn thiếu (đối tác tự duyệt, sự kiện provider, theo dõi thao tác
  ngoài) **đã có code của team ở Phase C**. Chế độ hợp nhất chưa nối vào vì
  Leader console gọi thẳng tool MCP, không đi qua `ExecutionGateway`. Vì vậy
  việc cần làm là **nối**, không phải viết lại.
- Sandbox: không có sản phẩm bên ngoài nào cung cấp sẵn, vì hợp đồng
  `/workforce/v1` là của dự án mình. Đề xuất: **tự dựng môi trường sandbox
  bằng chính gói Docker**, và dùng **gói Vinhome** (nhánh `dev_Vinhome`) làm
  đối tác thật đầu tiên. Cầu nối của gói Vinhome đã gọi đúng các endpoint của
  hợp đồng, kể cả ba phần trên.
- Ước lượng: phần A khoảng 4–5 ngày làm việc, phần B khoảng 1–2 ngày (sau A).
- Cần anh/chị chốt 5 quyết định ở cuối tài liệu.

## A. Ba phần còn thiếu ở chế độ hợp nhất

### A.0 Hiện trạng

| Phần | Code có sẵn (Phase C) | Chế độ hợp nhất hiện nay |
|---|---|---|
| Đối tác duyệt (approval) | `ApprovalService`, `PartnerApprovalService`, `ApprovalContinuationCommandAdapter`, route `POST /partner/approvals/{id}/decision` | Không gắn. Tool có tác động hỏi xác nhận **trong chat** (chỉ hợp với console) |
| Sự kiện provider | `ProviderEventIngress`, `ProviderEventProcessor`, `WorkflowEventAdapter`, route `/provider/job-events`, `/provider/event-receipts/{id}`, xác thực HMAC `HmacProviderAuth` | Không gắn; `main.py` không truyền bộ xác thực provider nên `provider_auth = None` |
| Theo dõi thao tác ngoài | `ExternalOperationService`, `OperationReconciler`, job `operation_reconcile`, trạng thái `waiting_external_event` | Không gắn |

Điểm nghẽn chung: ở Phase C, mọi lần gọi tool đều đi qua `ExecutionGateway`
(chính sách → giao dịch idempotent → duyệt → thực thi → thao tác ngoài). Còn
ChatService của console gọi thẳng `MCPClient`.

### A.1 Cổng thực thi cho ticket đối tác (nền cho cả ba phần)

- Chỉ áp dụng cho session Leader/agent **thuộc một workflow đối tác** (session
  có `workflow_id`). Ticket console giữ nguyên xác nhận trong chat.
- Tool **chỉ đọc** chạy như cũ. Tool có tác động (spec `requires_consent` hoặc
  MCP `readOnlyHint=false`) đi qua `ExecutionGateway`.
- Viết các adapter mà gateway cần, lấy dữ liệu từ Agent Studio:
  `tool_registry` (tool đã gắn cho agent và cờ chỉ đọc/cần duyệt/chạy dài),
  `runtime_authority` (agent nào được gọi tool nào, theo phiên bản đã ghim),
  `quote_provider` (tóm tắt tham số thành "phiếu" có hash), `mcp` (MCP của
  workspace quản lý).

### A.2 Đối tác tự duyệt

1. Agent định gọi tool cần duyệt → gateway tạo approval + phiếu → lượt Leader
   kết thúc với `workflow_state=awaiting_approval`, `next_action=approve`, kèm
   `approval_id` và nội dung phiếu.
2. Đối tác hỏi người dùng (ví dụ: thẻ báo giá cư dân bấm, như gói Vinhome đang
   làm) rồi gọi `POST /partner/approvals/{id}/decision`.
3. `ApprovalContinuationCommandAdapter` đánh thức workflow → runner chạy tiếp
   lượt Leader: **đồng ý** thì gateway thực thi đúng phiếu đã duyệt (hash phải
   khớp); **từ chối** thì báo cho Leader để đổi phương án.

### A.3 Theo dõi thao tác ngoài

Tool khai báo là "chạy dài" (ví dụ: tạo lệnh sửa chữa, chờ thợ nhận) sẽ được
`ExternalOperationService` tạo intent **trước** khi gọi, rồi chuyển mã thao
tác cho provider. Workflow chuyển sang `waiting_external_event`. Job
`operation_reconcile` hỏi lại trạng thái nếu quá hạn mà không có sự kiện.

### A.4 Sự kiện provider

- Gắn router provider và hai job `provider_event`, `operation_reconcile` vào
  chế độ hợp nhất.
- Cấp khoá provider (bảng `wf_provider_credentials` có sẵn) theo cùng cách
  cấp khoá đối tác: endpoint admin có `X-Provisioning-Secret`. Thêm
  `secret_resolver` cho HMAC.
- Khi có sự kiện, `WorkflowEventAdapter` đánh thức workflow → Leader nhận
  tóm tắt sự kiện → nhắn khách ("thợ đã nhận việc, đến lúc 09:00").

### A.5 Thứ tự làm và kiểm thử

| Bước | Việc | Kiểm thử (tự động) |
|---|---|---|
| A1 | Adapter registry/authority/quote/mcp + nhánh gateway trong ChatService | Unit test từng adapter; ticket console không đổi hành vi |
| A2 | Gắn approval + runner tiếp tục sau duyệt | E2E: hỏi duyệt → đồng ý → tool chạy đúng một lần; từ chối; gửi lại cùng quyết định (idempotent) |
| A3+A4 | Thao tác ngoài + router/job provider + cấp khoá provider | E2E: tool chạy dài → sự kiện HMAC → Leader báo khách; chữ ký sai bị từ chối; sự kiện trùng bị bỏ qua; reconcile khi mất sự kiện |
| A5 | Chạy lại bộ E2E Phase C (C6, D3, D5) trên assembly hợp nhất | Toàn bộ `tests/workforce` |

Rủi ro: ChatService là đường chạy chính của console, nên A1 phải được rào
bằng điều kiện "session thuộc workflow đối tác".

## B. Sandbox đối tác

### B.1 Có thể lấy sẵn ở đâu không?

Không. Sandbox kiểu Stripe/PayPal là môi trường thử **do chính nhà cung cấp
API dựng**. Ở đây platform là bên cung cấp API, nên mình phải tự dựng. Các
công cụ ngoài chỉ hỗ trợ một phần:

| Công cụ | Dùng để | Có cần không |
|---|---|---|
| Prism / Microcks (mock từ OpenAPI) | Đối tác viết code trước khi có sandbox | Không bắt buộc; đối tác đầu tiên là gói nội bộ |
| cloudflared / ngrok | Mở sandbox ra Internet cho đối tác bên ngoài | Chỉ khi có đối tác ngoài và chưa có VPS |
| Giới hạn chi tiêu của OpenAI project | Chặn tiền model khi chạy sandbox | **Nên có** |

### B.2 Đề xuất

1. **Môi trường sandbox = gói Docker vừa đóng** (compose `awp-develop2`), chạy
   thành một project riêng `awp-sandbox`, với DB/volume và secret riêng, và
   `WORKFORCE_PARTNER_API=true`. Dùng key OpenAI của một project có giới hạn
   chi tiêu. Chạy local trước; khi có VPS thì dùng cùng file compose.
2. **Script khởi tạo sandbox:** tạo quản lý khu vực, xác minh, cấp key đối
   tác, cấp tuyến, đăng ký MCP demo hoặc MCP Vinhome. Một lệnh, chạy lại
   không tạo trùng.
3. **Đối tác thật đầu tiên = gói Vinhome.** Cầu nối
   `vinhome_Recident/services/vinhomes-api/src/vinhomes_api/platform.py` đã gọi
   `partner/requests`, `partner/approvals/{id}/decision`,
   `partner/workflows/{id}/close`, `event-history`, `routes/{id}/confirm`,
   `provider/job-events`, `provider/event-receipts`, xác thực
   `Authorization: ApiKey …` và ký HMAC đúng hợp đồng. Gói này cũng có MCP 23
   tool và 13 kịch bản vàng G01–G13.
   - Đã sửa ở vòng này: chế độ hợp nhất từng đòi header `X-External-User-Id`
     không có trong hợp đồng, nên sẽ từ chối cầu nối Vinhome. Giờ đã đọc
     `external_user_id` từ query/body như hợp đồng.
   - Cầu nối được viết theo snapshot `feat/platform-core`, nên cần một lượt
     chạy đối chiếu với develop2. Các luồng duyệt và sự kiện provider cần
     phần A xong trước.
4. **Bằng chứng:** `partner_sandbox_check.py` (kiểm hợp đồng chung) và các
   kịch bản Vinhome chạy qua cầu nối, rồi người duyệt theo
   `SANDBOX_DOI_TAC_CHECKLIST.md` → biến `WORKFORCE_SANDBOX_EVIDENCE`.

### B.3 Thứ tự

| Bước | Việc | Phụ thuộc |
|---|---|---|
| B1 | Script khởi tạo sandbox + compose project `awp-sandbox` | Gói Docker (đã xong) |
| B2 | Chạy `partner_sandbox_check.py` trên sandbox (luồng hỏi–đáp–đóng) | B1, key model có giới hạn |
| B3 | Trỏ cầu nối Vinhome vào sandbox, chạy kịch bản hỏi–đáp–đóng | B1 |
| B4 | Chạy kịch bản có duyệt và có sự kiện provider | Phần A |
| B5 | Người duyệt ký bằng chứng | B2–B4 |

## Quyết định cần anh/chị chốt

| # | Câu hỏi | Đề xuất |
|---|---|---|
| D1 | Ticket đối tác cần duyệt thì ai duyệt? | Người dùng cuối qua đối tác (đúng hợp đồng và đúng cách gói Vinhome đang làm: cư dân tự bấm) |
| D2 | Đánh dấu tool "chạy dài, chờ sự kiện" ở đâu? | Một ô mới trong tab Công cụ của Agent Studio |
| D3 | Cấp khoá provider thế nào? | Endpoint admin + `X-Provisioning-Secret`, giống khoá đối tác |
| D4 | Sandbox chạy ở đâu? | Local trước; VPS khi có |
| D5 | Đối tác sandbox đầu tiên? | Gói Vinhome (nội bộ, đã theo hợp đồng) |
