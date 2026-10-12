# Workforce v1: kế hoạch triển khai bên platform và nối Vinhomes

Cập nhật: 10/10/2026. Nguồn: `CONTRACT_TICH_HOP_DOI_TAC.md` bản `1.3-draft` (ngoài repo) và `docs/research/AGENTSCOPE_CHO_WORKFORCE_V1.md`. Kế hoạch này **chưa được duyệt**; mục 7 là các câu cần chốt trước khi làm.

## 1. Hợp đồng đòi hỏi gì

Đối tác (Vinhomes) là **bên gọi**. Platform chỉ phục vụ API và **không gọi ngược webhook**:

| Hướng | Cách |
|---|---|
| Đối tác → platform | `POST /partner/requests` (`start_workflow`, `workflow_reply`), approval, close, `PUT residences`, confirm route |
| Platform → đối tác | Không có webhook. Platform gọi công cụ của đối tác qua **MCP** |
| Tiến độ → đối tác | SSE, history, snapshot, GET request. Mỗi workflow trả `workflow_state` và `next_action` để đối tác biết bước tiếp |
| Nhân viên → platform | `POST /provider/job-events` (ký HMAC), platform trả receipt |

Điểm khó của hợp đồng: POST **chờ tối đa khoảng 25 giây** kết quả của lượt agent rồi trả 200 (kèm tin nhắn) hoặc 202; mỗi cư dân có thể mở nhiều ticket song song, mỗi ticket có bộ ID riêng; mọi lệnh idempotent; event có thứ tự, cursor và hạn lưu.

## 2. Cái đã có và cái phải đổi

| Phần của hợp đồng | Hiện trạng trong lõi | Việc |
|---|---|---|
| Hồ sơ agent, chi phí, ngân sách, tầng model, chống bịa, case file | Có | Giữ nguyên |
| Workflow | Có "vụ" (`open/finalized/failed`) | Thêm `workflow_state` (9 trạng thái) và `next_action`, tính từ trạng thái vụ |
| Hội thoại với cư dân | Chưa có | Bảng tin nhắn và công cụ `CaseSay` |
| Event công khai, SSE, history, snapshot, cursor, 410 | Chưa có | Bảng event riêng (AgentScope không tái dùng được) |
| POST chờ 25 giây, 200/202 | Chưa có | Bảng lượt chạy và cơ chế chờ |
| Approval có `arguments_hash` | Chưa có | Phát ASK từ `on_check_permission`, tự làm bản ghi approval |
| Close có CAS revision | Đóng bằng `CaseFinalize` | Thêm close do đối tác, `stop_tracking_only` |
| Provider events | Có `reply_to` ở follow-up (tự đặt) | Thay bằng Provider Event API đúng hợp đồng |
| Công cụ của đối tác | Có `CaseRequest` + webhook (tự đặt) | **Bỏ**; thay bằng công cụ bọc MCP |
| Xác thực | Khóa env | `ApiKey dp_<id>.<secret>` lưu băm, có quyền theo operation, HMAC cho provider |
| Route, residence | Chưa có | Bảng và hai endpoint |
| Lỗi, idempotency, 12 mã binding | Một phần | Làm đủ theo mục 6.3 |

Hệ quả cần nói rõ: **`/platform/v1/intake`, webhook callback, `CaseRequest` và `DomainPack.deliver_*` mà tôi viết trước đó đều bị thay thế** bởi hợp đồng này. Phần quản trị `/platform/v1` (hồ sơ agent, chi phí, vụ) giữ lại cho admin.

## 3. Các quyết định thiết kế đề xuất

1. **Workflow = vụ hiện có.** Thêm `ticket binding` (user, ticket, conversation đối tác) làm khóa, đúng các mã lỗi `WORKFLOW_BINDING_MISMATCH`, `TICKET_ALREADY_BOUND`...
2. **Lời gửi cư dân đi qua `CaseSay(text, expects)`**, không phải câu trả lời tự do của model. Nhờ đó cổng chống bịa kiểm từng con số trước khi cư dân thấy, và `expects` (`reply`, `approval`, `confirmation`, `none`) quyết định `next_action`.
3. **Công cụ đối tác = MCP bọc trong tool của platform.** Tool ghi `client_reference` và operation vào DB **trước** khi gọi, trả `pending` ngay, rồi chờ Provider Event. Lý do: AgentScope tự đẩy tool chạy quá 10 giây xuống nền và mất khi khởi động lại, nên không dùng cho thao tác có tác dụng phụ như đặt thợ.
4. **Approval:** tool được khai báo "cần cư dân đồng ý" thì `on_check_permission` phát ASK, tạo bản ghi approval (băm tham số), lượt đỗ lại. Quyết định của cư dân dựng lại sự kiện từ bản đã lưu rồi chạy tiếp.
5. **Event công khai là bảng riêng**, ghi cùng giao dịch với thay đổi trạng thái. SSE đọc bảng này; bus chỉ là tín hiệu "có dữ liệu mới".
6. **Chờ 25 giây:** mỗi POST tạo một dòng "lượt", `on_reply` đánh dấu xong; handler chờ có hạn rồi trả 200 hoặc 202.
7. **Chặn lỗi đã biết của AgentScope:** reply mới vào phiên đang đỗ approval sẽ lỗi, nên API phải kiểm trước và trả lỗi trạng thái.

## 4. Lộ trình, mỗi bước có tiêu chí kiểm

| Bước | Nội dung | Kiểm bằng |
|---|---|---|
| P0 | Kiểm 5 điểm "chưa xác minh" trong ghi chú nghiên cứu bằng test ngắn (ASK trong `dont_ask`; POST khi phiên bận; timeout MCP; Postgres; tắt offload) | Mỗi điểm một test, kết quả ghi lại |
| P1 | Khung API: xác thực `ApiKey`, route/residence, `POST /partner/requests`, 200/202, bảng hội thoại, event, history, snapshot, SSE có `Last-Event-ID`, idempotency, mã lỗi | POST lặp ra cùng kết quả; mất kết nối SSE rồi nối lại không mất event; cursor cũ trả 410 |
| P2 | Luồng với cư dân: `CaseSay`, `awaiting_user/approval/confirmation`, approval, close CAS | Một ticket đi hết: hỏi, chọn, đồng ý, xác nhận, đóng; hai ticket song song không lẫn |
| P3 | Công cụ đối tác qua MCP + Provider Event API (HMAC, receipt, dedupe, thứ tự, quarantine) | Gọi thợ trả pending, event tới sau đánh thức đúng workflow; event trùng, sai thứ tự, đến sau khi đóng đều đúng hợp đồng |
| P4 | Gỡ phần cũ bị thay thế; bộ kiểm tuân thủ theo mục 13.9 của hợp đồng; một client mẫu và một MCP giả kiểu Vinhomes | Toàn bộ kịch bản mục 13.9 chạy xanh bằng model giả |
| P5 | Độ bền: Redis bus, Postgres, phục hồi sau crash, dọn dữ liệu theo retention | Khởi động lại giữa lúc chờ thợ không tạo job mới |

Mốc demo 22/10, đóng băng 19–21/10: P0–P3 vừa khít, P4 rút gọn, P5 sau demo. Demo chạy một tiến trình với SQLite.

## 5. Nối với Vinhomes (làm ở `vinhome_Recident`, sau)

Platform không chứa mã Vinhomes. Vinhomes là "backend khách hàng" nên cần:

| Thứ Vinhomes cần có | Nối với |
|---|---|
| Khi Reception không tự xử lý được, backend gọi `start_workflow` | Thay hộp thư `integration_cases` kiểu kéo hiện có. `external_ticket_id` = mã ticket Vinhomes, `external_conversation_id` = hộp chat của cư dân |
| Tin của cư dân sau đó | `workflow_reply` |
| Hiển thị tiến độ cho cư dân | Đọc SSE hoặc history, rồi hiển thị `assistant.message`, `ticket.status_changed`, `approval.required` |
| Cư dân đồng ý chi phí, xác nhận hoàn thành | Approval decision, rồi close |
| Một MCP server của Vinhomes (đặt thợ, tra ticket, tra tri thức, biểu mẫu chi phí) | Platform gọi qua MCP |
| App nhân viên báo tiến độ và chi phí | Backend Vinhomes gọi Provider Event API |
| Khai báo một lần | Khóa API, xác nhận route, đồng bộ residence |

Ánh xạ từ `schema_v2` hiện có: `ticket_submitted` → `start_workflow`; `information_provided` → `workflow_reply`; `plan_approved/rejected` → approval decision; `cancel_requested` → close với `stop_tracking_only`.

## 6. Rủi ro đã biết (từ nghiên cứu mã AgentScope)

- Crash giữa một lượt mất toàn bộ thay đổi của lượt đó và có thể gọi tool lần hai; vì thế phải ghi `client_reference` trước khi gọi MCP.
- MCP chỉ có header tĩnh, không OAuth; tên tool thành `mcp__{mcp}__{tool}`; không có khái niệm route nên ta tự giữ cấu hình theo route.
- Nén ngữ cảnh do model tóm tắt và có thể cắt phần cũ, nên dữ kiện nghiệp vụ nằm ở DB của ta và được tiêm lại mỗi lượt.
- Postgres và nhiều tiến trình chưa kiểm; mọi kết luận trên đọc từ mã, chưa chạy.
- Hợp đồng là bản nháp, nó tự ghi chưa xác nhận API nào đã triển khai.

## 7. Cần bạn xác nhận

1. **Workforce v1 là API duy nhất cho đối tác?** Tôi hiểu là thay `/platform/v1/intake`, webhook và hợp đồng kéo hộp thư của Vinhomes. `/platform/v1` chỉ còn cho admin.
2. **Có tài liệu "kế hoạch 1.4.3" mà hợp đồng nói đã đồng bộ không?** Tôi chưa thấy nó trong repo. Nó có thể định nghĩa route, manager, domain.
3. **Mọi câu chữ gửi cư dân đi qua `CaseSay` có kiểm chống bịa**, không dùng câu trả lời tự do của model. Đồng ý?
4. **Công cụ đối tác:** tool bọc MCP trả `pending` ngay cho thao tác có tác dụng phụ (đặt thợ), còn tra cứu thì gọi đồng bộ. Ai khai báo tool nào là bất đồng bộ hay cần cư dân đồng ý: tôi đề xuất cấu hình theo route qua API admin.
5. **Route là gì trong mô hình của ta?** Đề xuất: một partner client là một tenant; một `external_management_ref` là một route có bộ hồ sơ agent, MCP và luật riêng.
6. **Cư dân xác nhận chi phí** là approval (có băm bảng chi phí), còn xác nhận hoàn thành là `confirm_close`. Đúng không?
7. **Phạm vi demo 22/10** là P0–P3 trên một tiến trình, Redis và Postgres sau. Chấp nhận?
8. **Xóa mã cũ** (`CaseRequest`, webhook, `reply_to`, `deliver_*`) ở P4, sau khi Workforce chạy được, để không có hai đường song song?
