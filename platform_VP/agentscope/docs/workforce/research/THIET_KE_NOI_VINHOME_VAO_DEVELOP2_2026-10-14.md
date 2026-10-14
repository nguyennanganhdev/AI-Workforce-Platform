# Thiết kế: nối Vinhome (đối tác thật) vào develop2

14/10/2026 · Người đọc: PM và team platform · Quyết định của PM: Vinhome nối vào
**develop2**; platform chạy **cùng VPS** với Vinhome; D1–D5 theo đề xuất.

## Mục tiêu

Gói Vinhome trên VPS (`https://vinhome-platform.duckdns.org`) nối vào develop2
**mà không sửa gì bên Vinhome**:

- Bộ khai báo `deploy/platform/vinhomes-declaration.json` của Vinhome là đầu vào.
- Platform cấp ra `platform.env` đúng định dạng Vinhome đang dán vào
  `deployment.env`.

## Những gì đã có và đã khớp hợp đồng

| Phần | Trạng thái |
|---|---|
| Customer API `/workforce/v1/partner/*` (request, reply, kết quả, history, snapshot, close, xác nhận route) | Có (chế độ hợp nhất) |
| Envelope sự kiện provider, header ký `X-Partner-*`, HMAC `v1=` trên `ts.raw` | Có (`HmacProviderAuth`) |
| Payload `assistant.message`, `workflow.status_changed`, `workflow.closed` | Khớp với cách cầu nối Vinhome đọc |

## Phần làm mới (chỉ trong chế độ hợp nhất)

1. **Leader của route là một agent Agent Studio.** Onboarding dựng agent từ
   `profiles[]` của bộ khai báo và gắn với route. Ticket mới dùng phiên bản
   đang phát hành; ticket đang mở giữ phiên bản lúc bắt đầu.
2. **Middleware cho session đối tác** (gắn qua `extra_agent_middlewares`):
   - `CaseSay(text, expects, cites)` và `CaseFinalize(answer, outcome, cites,
     unknowns)` là đường duy nhất để lời của leader tới người dùng. `expects`
     = `none` / `reply` / `confirmation`.
   - Mỗi tool của route được bọc lại: đúng tên trong khai báo (`vh_*`), dùng
     `description_override`, ẩn tham số `client_reference` khỏi model rồi
     platform tự điền (cùng lượt, cùng tham số thì cùng giá trị). Kết quả được
     gắn nhãn bằng chứng `E1, E2…`. Tool có `tracking: events` thì ghi thành
     operation (`client_reference`, `external_job_id`).
   - Bộ kiểm câu (`CaseSay`): cụm từ cấm trong `route.config.rules` (có
     `unless`), con số/giờ/tiền phải có trong bằng chứng được trích dẫn hoặc
     lời người dùng, một tin mỗi lượt. Bị từ chối thì trả lý do để model sửa;
     cả lượt không có tin hợp lệ thì gửi `safe_reply`.
3. **Trạng thái sau lượt:**
   - `reply` → `awaiting_user`;
   - `confirmation` → `awaiting_confirmation`;
   - `none` → `waiting_external_event` khi còn việc đang theo dõi, nếu không thì
     `awaiting_user`;
   - tool cần đồng ý đang chờ → `awaiting_approval`.
4. **Sự kiện provider** (`POST /provider/job-events`,
   `GET /provider/event-receipts/{id}`): bảng sự kiện của integration lấy từ
   khai báo. Mỗi sự kiện được xử lý như sau:
   - kiểm `event_type`, trường bắt buộc và kiểu số;
   - chống trùng theo `external_event_id`;
   - nối với operation qua `client_reference` và `external_job_id`;
   - bỏ qua sự kiện có hạng thấp hơn (`STALE_EVENT`);
   - có tin mẫu thì gửi thẳng cho người dùng, không qua model;
   - có cờ `evidence` thì ghi bằng chứng;
   - có cờ `wake` thì đánh thức leader;
   - sự kiện kết thúc thì đóng operation.
5. **Duyệt của đối tác (D1):** tool cần đồng ý trong session đối tác đi như sau:
   - platform phát `approval.required`, kèm `arguments_hash`,
     `expected_revision` và `summary`;
   - đối tác gọi `POST /partner/approvals/{id}/decision`;
   - platform đánh thức leader để chạy hoặc bỏ thao tác đó.
6. **Onboarding:** `POST /workforce/v1/admin/partner-onboarding` (cần
   `X-Provisioning-Secret`) và script `scripts/workforce/onboard_partner.py`.
   - Lần đầu, endpoint tạo:
     - client, khoá khách hàng, khoá provider và khoá ký (bí mật mã hoá khi lưu);
     - MCP của đối tác cho tài khoản quản lý;
     - agent leader;
     - route (mỗi `management_ref` một route) và bảng sự kiện.
   - Chạy lại thì chỉ cập nhật agent, tool và MCP; `--new-keys` mới cấp khoá mới.
7. **Sửa chỗ lệch hợp đồng (dùng chung):**
   - mã lỗi của close: `REVISION_CONFLICT`, `WORKFLOW_NOT_READY_TO_CLOSE`,
     `WORKFLOW_CLOSED`;
   - snapshot thêm `sender`;
   - payload `approval.required` có đủ trường để đối tác gửi quyết định;
   - xem biên nhận chỉ cần API key.

## Vì sao không dùng nguyên đường Phase C

Phase C xử lý sự kiện provider xoay quanh các operation do `ExecutionGateway`
tạo, được ghim vào checkpoint. Leader của chế độ hợp nhất gọi tool qua
ChatService, không qua gateway. Vì vậy phần mới dùng lại những gì đã có:
xác thực HMAC, job bền, workflow, public event, `claim_or_read` và trigger. Nó có
bảng riêng `wf_unified_*`, và không đụng tới đường Phase C.

## Giới hạn đã biết

- Trigger sự kiện bị engine dùng chung **hoãn** khi workflow đang chờ người dùng.
  Sự kiện đánh thức bị hoãn sẽ được đưa vào lượt kế tiếp, khi người dùng nhắn.
- Không làm `/partner/approvals/{id}/chat` (Vinhome không dùng).
- Snapshot vẫn trả `pending_approvals` (Vinhome đọc `approvals`, chỉ dùng khi
  cursor hết hạn).
