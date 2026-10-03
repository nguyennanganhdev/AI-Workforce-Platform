# Bàn giao bốn luồng FE/UI — 01/10/2026

**Dành cho BE bắt đầu tích hợp:** đọc [06 — Hướng dẫn API, dữ liệu, phân quyền và nghiệm thu liên app](06-backend-integration-guide.md). Tài liệu này mô tả hiện trạng UI; tài liệu 06 chỉ rõ phần cần nối và các khác biệt giữa mock với production.

Đây là UI có dữ liệu mẫu, chưa phải hệ thống nghiệp vụ production. Hai frontend vẫn độc lập: `resident-app` không import component, CSS hoặc state của `app`. Tài liệu này cập nhật phần trạng thái UI trong các tài liệu 01–04; endpoint bên dưới là đề xuất cần thống nhất với BE.

## 1. Cư dân: nhiều hội thoại, một ticket mỗi hội thoại

- Entry: `http://localhost:3011/login` → **Khám phá bản trải nghiệm**.
- Hai tab chính vẫn là Trợ lý và Tiện ích. Thanh **Hội thoại / Chat mới** nằm trong Trợ lý, không thêm tab chính.
- `#/chat/:conversationId`: chọn hội thoại; nội dung và bản nháp phản ánh tách riêng.
- Chỉ **Gửi phản ánh** tạo ticket. Sau đó chat trong phòng chỉ bổ sung cho ticket đó; sự cố khác dùng Chat mới.
- `#/requests/:id`: tiến trình, ảnh, cư dân xác nhận hoặc đề nghị kiểm tra lại.
- Khu vực sự kiện mẫu ở chi tiết ticket mô phỏng được điều phối / chờ xác nhận. Cập nhật đúng phòng, tăng số tin chưa đọc; mở phòng xóa số chưa đọc. Ticket hoàn tất không tự mở lại.
- `#/notifications`: truy cập hội thoại có tin chưa đọc và thông báo trạng thái ticket.
- `src/services/conversations.ts` là ranh giới logic hội thoại, bọc lại adapter cũ. `ResidentState.messages/draft` là dữ liệu của phòng đang mở để giữ tương thích component hiện hữu.
- `nha.resident.demo.v1` giữ lịch sử khi reload. Snapshot cũ được chuyển thành phòng lịch sử và một phòng riêng cho mỗi ticket; không xóa transcript cũ.
- Nội dung đang gõ và ảnh chưa gửi được giữ khi đổi phòng trong lần mở app hiện tại; chưa lưu qua reload. Bản nháp phản ánh đã gửi vào hội thoại được lưu cùng phòng.

BE cần cung cấp conversation ownership, quan hệ unique `conversation.ticket_id`, message cursor, public ticket events, read cursor theo user và realtime/reconnect. Cập nhật trạng thái và append message cần cùng version để tránh ghi đè khi có nhiều thiết bị. Event thật cần `eventId` để dedupe; hàm mô phỏng hiện tại không phải bộ nhận realtime.

## 2. Tài khoản và vai trò Operations

Entry: `http://localhost:3020/operations/login`. Phần **Tài khoản để xem giao diện mẫu** chỉ dùng review; đăng nhập thật không cho chọn quyền. Chọn tài khoản mẫu rồi bấm **Xem bản trải nghiệm**.

| Mã mẫu | Vai trò | Màn hình chính |
|---|---|---|
| ADMIN-01 | Admin | `/operations/accounts` |
| BQL-01 / BQL-02 | BQL S2.01 / S2.02 | `/operations/team` |
| KT-01 | Kỹ thuật | `/operations/my-tasks` — danh sách chung và xử lý hiện trường |
| AN-01 | An ninh | `/operations/my-tasks` — danh sách chung và xử lý hiện trường |
| VS-01 | Vệ sinh | Màn nghiệp vụ vệ sinh hiện hữu |

Admin tạo hồ sơ nhân viên/BQL/admin, duyệt hồ sơ cư dân pending, kích hoạt, khóa và xóa. Form không lưu mật khẩu. Không tự khóa/xóa chính mình, không xóa nhân viên có công việc đang mở, xóa cần nhập đúng định danh. Có nhật ký thao tác mẫu. Hồ sơ cư dân pending là seed; đăng ký resident chưa đẩy dữ liệu vào bảng admin.

Menu và direct URL giới hạn theo role trong `workspace/model.ts`. Bỏ bộ chọn persona trong sidebar. Khóa tài khoản ở tab khác được phát hiện bằng storage event. Đây là điều hướng FE, không phải kiểm quyền bảo mật; BE phải xác thực và kiểm tra role/scope từng request.

`operations.ui-preview` và `operations.preview-account` chỉ là cờ tab, không phải token. Phiên thật, gửi lời mời/kích hoạt, mật khẩu lần đầu, OTP và reset do BE cung cấp. Role `manager` trong view model FE cần map sang `management` của actor BE hiện tại, không truyền thẳng như role claim.

## 3. BQL: nhóm, agent và bảng ticket

`/operations/team` chỉ hiển thị phòng cùng scope của BQL. Tạo agent mẫu sẽ tự thêm agent vào nhóm. Chọn **@Nhắc agent**, tùy chọn ticket cùng tòa nhà, rồi gửi nội dung. Context mẫu gồm room, scope, tối đa tám message ID gần nhất và ticket/stage. Không cho đính kèm ticket hoặc gọi agent ngoài phòng.

Phản hồi agent được gắn nhãn mô phỏng. AgentScope, Context Builder, interrupt và thực thi agent thuộc BE; FE không giả lập các thao tác này thành công. Bảng công việc và ticket trong tin nhắn mở `/operations/kanban?ticket=...`, dùng cùng chi tiết và cùng record với nhân viên tại `/operations/my-tasks?ticket=...`.

## 4. Điều phối, hiện trường và báo cáo

Các ticket `DEMO-*` dùng chung giữa nhóm BQL, Phân công công việc, Việc của tôi và báo cáo. BQL xem trong scope; nhân viên chỉ thấy ticket được giao cho mình. Bộ chọn nhân viên kiểm tra bộ phận, phạm vi, trạng thái và công việc đang mở trong workflow ticket. Nhân viên bận đưa ticket vào hàng chờ, timeline ghi thông báo mẫu cho cư dân.

### Gộp màn công việc

- Bỏ menu “Ticket & hiện trường”. Nhân viên dùng **Việc của tôi**; BQL dùng **Phân công công việc**.
- `WorkPage.tsx` dùng một danh sách, bộ lọc nội dung/bộ phận/tiến độ và lịch sử; BQL có thêm chế độ bảng tiến độ. Mỗi thẻ mở đúng hồ sơ gốc, không tạo bản sao.
- `work-items.ts` là read model chung, ghép tham chiếu tới ticket mới và Task/WorkOrder hiện hữu. BQL thấy một dòng/task, chi tiết chứa các lần thi công; nhân viên thấy các phiếu được giao. Mọi dòng giới hạn theo tòa nhà. Hồ sơ ngoài phạm vi bị ẩn, không bị xóa.
- `TicketDetail.tsx` được dùng chung giữa BQL và nhân viên; nút thao tác theo role/assignment/stage. Phiếu cũ tiếp tục mở component hiện hữu, giữ checklist, báo giá, ảnh trước/sau và bàn giao cư dân.
- **Đang mở** và **Lịch sử** lấy từ cùng read model. Chờ cư dân xác nhận/BQL phê duyệt vẫn là việc đang mở; đóng ticket chuyển cùng record sang lịch sử.
- `?ticket=` chọn workflow ticket, `?job=` chọn phiếu nhân viên, `?task=` chọn nhiệm vụ BQL, `?view=history` giữ lịch sử khi mở/đóng chi tiết. Link ngoài phạm vi hiển thị không tìm thấy, không tự mở một ticket khác.
- `/operations/dispatch?ticket=...` là redirect tương thích, giữ ticket ID và chuyển theo role. `/operations/completed-tasks` chuyển về tab lịch sử của màn tương ứng.
- Nút **Sẵn sàng nhận thêm việc** cập nhật availability của tài khoản mẫu; không tự bỏ phân công đang có.

| Nhánh | Trình tự UI |
|---|---|
| Điện / nước nhỏ | Phân công → đến hiện trường → đề nghị cư dân đồng ý → xử lý → ảnh → gửi kết quả → cư dân xác nhận |
| Nước lớn | Khảo sát → cư dân đồng ý → đề nghị BQL khóa nước → BQL duyệt → thông báo cắt nước → khóa van → xử lý, ảnh → mở nước/thông báo khôi phục → cư dân xác nhận |
| An ninh thường P2/P3 | Camera metadata → phân công/hàng chờ → khảo sát → xử lý, bằng chứng → xác nhận; quá hạn có chuyển trưởng ca, hủy cần BQL duyệt |
| An ninh khẩn P0/P1 | Người trực xác nhận cảnh báo → xử lý, bằng chứng → đã kiểm soát → BQL đóng; thiếu xác nhận có chuyển cấp, không tự hoàn tất |

Nút xác nhận thay cư dân nằm riêng trong khung **Sự kiện cư dân · chỉ để kiểm thử UI**. Production bỏ khung này và nhận event từ BE. Ảnh FE tối đa ba ảnh/ticket, thu nhỏ về cạnh dài tối đa 1000px; private storage, quyền đọc file và upload thật thuộc BE.

Mức ưu tiên FE đã thống nhất P0–P3. Snapshot legacy `vhm_operations_data_v9_*` chỉ chuyển các field `severity`: P1→P0, P2→P1, P3→P2, P4→P3. Snapshot mới dùng v10; dữ liệu v9 giữ nguyên, không tự đổi mã ticket hoặc nội dung ghi chú. Không áp dụng phép đổi này cho payload API mới. `VinhomesTicketSummary.severity` hiện là string; cần chốt enum/schema ở producer trước tích hợp.

`/operations/reports` cho BQL chọn ngày và loại báo cáo, scope cố định theo tài khoản. Có queued, failed/thử lại, ready, xem trước và tải DOCX hợp lệ. Tần suất thống kê ticket theo ngày tạo, tòa nhà, nhóm điện/nước/an ninh. Doanh thu mẫu cộng `amount` của ticket kỹ thuật hoàn tất; **chưa phải tổng hóa đơn thực**. BE cần chốt ngày hạch toán, trạng thái hóa đơn, thuế/hoàn tiền, currency và quyền xuất báo cáo. File tải luôn ghi BÁO CÁO MẪU.

## Dữ liệu và điểm tích hợp

- Operations mới: `app/src/features/vinhomes-operations/workspace/`, local key `vinhomes.frontend-workspace.v1`; reducer thuần ở `service.ts`, đọc/lưu và báo lỗi ở `use-workspace.ts`.
- Danh sách công việc đã hợp nhất qua `work-items.ts`, nhưng persistence mock vẫn giữ schema cũ và mới để bảo toàn checklist, báo giá, ảnh và lịch sử. Read model không sao chép ticket giữa hai store. Các thao tác ghi về reducer gốc tương ứng. Đây chưa phải migration dữ liệu production: BE cần cung cấp quan hệ ticket → task → các lần thi công và tải nhân viên chung; báo cáo/nhắc agent hiện vẫn áp dụng workflow ticket mẫu `DEMO-*`. Resident vẫn cần API để đồng bộ với Operations.
- Mapping identity legacy chỉ dành cho ba tài khoản seed, không cấp hồ sơ cũ cho một tài khoản mới chỉ vì cùng role. Khi nối BE bỏ mapping seed và dùng user ID/assignment do server xác nhận.
- Backend đã có đọc ticket tại [ticket-routes.ts](../../server/src/business/ticket-routes.ts), DTO tại [vinhomes-ticket.ts](../../shared/vinhomes-ticket.ts). Không được coi các đường dẫn `server/src/domains/vinhomes/` trong tài liệu cũ là file đang tồn tại ở checkout này.
- Các API nghiệp vụ mới bên dưới **chưa được triển khai bởi thay đổi FE này**. Tên path mang tính đề xuất, không gọi thử như API thật.

| Nhu cầu adapter | Hợp đồng cần BE chốt |
|---|---|
| Bootstrap tài khoản | `GET /api/session`: user, role, scopes, accountStatus; 401 khác lỗi mạng |
| Cấp/duyệt/khóa tài khoản | `GET/POST /api/admin/accounts`, `POST /:id/approve`, `/suspend`, `/activate`, `DELETE /:id`; audit và dependency/version |
| Hội thoại cư dân | `GET/POST /api/resident/conversations`, `POST /:id/messages`, `POST /:id/read`; conversationId/ticketId/readCursor |
| Nhóm BQL / agent | `GET /api/management/rooms`, `POST /:id/messages`, `POST /:id/agents`; scope lấy từ session, mention IDs có kiểm quyền |
| Ticket / hiện trường | List/detail theo actor; command phân công, đồng ý, phê duyệt, ảnh, khôi phục, xác nhận; expectedVersion, idempotencyKey, public events |
| Báo cáo | Tạo job kind/from/to/scope → jobId/status → polling hoặc event → fileId/download có auth, expiry và filename |

Ví dụ envelope event đề xuất:

```json
{
  "eventId": "evt-unique",
  "type": "ticket.awaiting_resident_confirmation",
  "conversationId": "conversation-id",
  "ticketId": "ticket-id",
  "version": 12,
  "occurredAt": "2026-10-01T08:00:00Z",
  "publicMessage": "Nhân viên đã xử lý, mời bạn kiểm tra kết quả."
}
```

Không đưa thông tin nội bộ, prompt hoặc toàn bộ chat BQL vào event công khai. Server quyết định người nhận, phạm vi và quyền chuyển trạng thái. FE cần rollback/reload khi 409, giữ form khi lỗi mạng, hiển thị 403, xử lý hết phiên và hủy subscription khi logout.

## Kiểm thử và nghiệm thu

Chạy từ repository root bằng Bun có sẵn, không cần quyền admin hoặc cài Node:

```powershell
bun test resident-app/tests app/tests/operations-workspace.test.ts app/tests/operations-auth.test.ts app/tests/vinhomes-operations.test.ts app/tests/mock-data-integrity.test.ts
bun test app/tests/operations-work-items.test.ts
bun run --cwd resident-app typecheck
bun run --cwd app typecheck
bun run build:resident
bun run --cwd app build
```

Smoke UI dùng Chrome debugging profile riêng trên 9333 và hai dev server; không dùng profile làm việc vì fixture test thay dữ liệu mẫu:

```powershell
bun app/scripts/auth-browser-smoke.ts
bun app/scripts/workspace-browser-smoke.ts
bun resident-app/scripts/browser-smoke.ts
```

Kiểm tra chính: không trộn phòng cư dân; một ticket/phòng; unread khi có event; thao tác sai role/scope bị chặn; nước không bỏ qua duyệt/thông báo/mở lại; security không đóng chỉ vì đã chuyển cấp; báo cáo đúng ngày/scope; thiếu ảnh hoặc storage đầy không báo thành công. Màn hình kiểm tra ở 320–1440px. Production end-to-end hai app vẫn cần backend chung.
