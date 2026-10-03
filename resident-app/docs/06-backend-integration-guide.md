# Hướng dẫn BE tích hợp Resident và Operations

Ngày bàn giao: 01/10/2026. Đọc cùng [hiện trạng FE và các luồng](05-workspace-fe-handoff.md).

**Trạng thái: hợp đồng tích hợp đề xuất, chưa phải API đã triển khai hoặc đã được BE phê duyệt.** Ví dụ ID, endpoint và payload trong tài liệu dùng để thống nhất producer/consumer. Tận dụng auth/domain service hiện có; không tạo hệ thống tài khoản hoặc ticket thứ hai chỉ để khớp tên URL minh họa.

## 1. Kiến trúc và phạm vi bàn giao

```text
resident-app (3011) ─┐
                    ├─ Backend chung ─ Database / File storage / Event delivery
app Operations (3020)┘
```

Hai frontend không gọi trực tiếp nhau, không chia sẻ localStorage và không import component của nhau. Cư dân, BQL và nhân viên cùng truy cập một ticket ID do BE cấp, với payload và thao tác được giới hạn theo quyền.

Đã có UI: đăng nhập/đăng ký cư dân; đăng nhập nhân viên; hội thoại và ticket cư dân; quản trị hồ sơ; nhóm BQL; danh sách công việc chung, lịch sử và xử lý hiện trường; báo cáo mẫu. Auth adapter hiện báo chưa kết nối. Dữ liệu nghiệp vụ vẫn là mock.

Backend đọc ticket hiện hữu nằm ở [ticket-routes.ts](../../server/src/business/ticket-routes.ts), trả danh sách cho actor `management`/`admin`. DTO [vinhomes-ticket.ts](../../shared/vinhomes-ticket.ts) mới là summary, chưa đủ làm contract detail/command cho các luồng dưới đây. Không suy ra các endpoint đề xuất bên dưới đã tồn tại.

## 2. Điểm thay adapter của FE

| Nhu cầu | File hiện hữu | Thay đổi khi tích hợp |
|---|---|---|
| Auth cư dân | `resident-app/src/features/auth/auth-service.ts`, `src/main.tsx` | Gọi auth thật, bootstrap session, bỏ guard preview trong chế độ thật |
| Chat/ticket cư dân | `resident-app/src/services/conversations.ts`, `resident-service.ts`, `src/app/App.tsx` | Chuyển reducer đồng bộ sang API async; loading, retry, cache theo user |
| Auth nhân viên | `app/src/features/vinhomes-operations/auth/auth-service.ts`, `app/src/routes/_authed.tsx` | Session và quyền từ server; không lấy preview account làm actor |
| Tài khoản/nhóm/hiện trường | `app/src/features/vinhomes-operations/workspace/service.ts`, `use-workspace.ts` | Repository/API async theo resource, không GET/PUT toàn bộ `WorkspaceState` |
| Danh sách công việc | `workspace/work-items.ts`, `WorkPage.tsx` | Map ticket/task/work order từ BE thành một read model, không nhân bản ticket |
| Chi tiết workflow | `workspace/TicketDetail.tsx` | Dùng API command và allowedActions; bỏ nút đóng vai cư dân |
| Phiếu cũ | `hooks/use-operations-data.ts`, `components/technician/` | Nối cùng task/work order thật; giữ checklist, báo giá, ảnh và lịch sử làm lại |
| Báo cáo | `workspace/ReportsPage.tsx`, `docx.ts` | Job/report/file từ BE; không lấy tổng tiền mẫu làm doanh thu thật |

Các đường dẫn Operations viết ngắn trong bảng nằm dưới `app/src/features/vinhomes-operations/`. Lưu trữ mock cũ/mới chưa phải schema database. Không import snapshot demo hoặc tự chuyển P1→P0 trên payload BE. Enum severity thật cần chốt P0–P3 một lần ở contract chung.

## 3. Auth, scope và role

Đề xuất bootstrap session trả dữ liệu sau; có thể mở rộng endpoint session hiện hữu thay vì tạo mới:

```json
{
  "user": { "id": "user-tech-01", "displayName": "Nguyễn Văn Hùng" },
  "role": "technical",
  "accountStatus": "active",
  "scopes": [{ "buildingId": "building-01", "code": "S2.01" }],
  "memberships": [],
  "permissions": ["work.read_assigned", "work.update_assigned"]
}
```

- `role` ở ví dụ là role view model FE. Backend đang có actor `management`; map sang `manager` ở adapter. Chốt mapping kỹ thuật/an ninh/vệ sinh với BE, không mặc định các role này đã có trong auth hiện hữu.
- Resident có membership hợp lệ gồm apartment ID/building ID. Không lấy chuỗi vị trí do cư dân nhập làm bằng chứng sở hữu căn hộ.
- FE hiện dùng một scope chính. Nếu BE cấp nhiều tòa, FE cần bổ sung bộ chọn phạm vi, nhưng mọi request vẫn được BE kiểm quyền.
- Đăng ký cư dân nhận `{fullName, phone, password}`, không nhận role/admin claim. Response ánh xạ `nextStep`: `verification-required`, `membership-pending`, `ready`. Không tạo phiên có quyền cư dân khi membership còn pending.
- Nhân viên/BQL chỉ được admin cấp tài khoản, không có đăng ký công khai. Admin gửi thông tin hồ sơ/role/scopes; secret, lời mời và kích hoạt do BE xử lý.
- Khóa tài khoản phải vô hiệu phiên/quyền ở BE; storage event trong demo không phải cơ chế thu hồi phiên thật.
- Chốt cookie hoặc bearer theo auth hiện có. Với cookie khác origin dev, cấu hình credentials/CORS cụ thể cho hai FE và CSRF cho mutation; production chốt domain triển khai. Không đưa token vào URL hoặc dùng cờ preview để xác thực.
- Session hết hạn: giữ bản nháp không chứa mật khẩu nếu phù hợp, đưa về login; logout phải xóa cache user và đóng subscription. Lỗi mạng không được chuyển thành user admin hoặc phiên demo.

## 4. Quan hệ dữ liệu cần thống nhất

| Entity | Trường tối thiểu phục vụ UI | Ràng buộc |
|---|---|---|
| Conversation | id, residentId, title, ticketId nullable, updatedAt, unreadCount | Một phòng tối đa một ticket; phòng hỏi thông tin có thể chưa có ticket |
| Message | id, conversationId, senderType, text, attachments, sequence, createdAt | FE phân biệt tin cư dân, trợ lý và cập nhật công khai |
| Ticket | id, code, conversationId, buildingId, apartmentId nullable, location, title, description, category, severity, stage, version, createdAt | Không tạo ticket mới khi đổi màn hoặc giao lại nhân viên |
| Task | id, ticketId, department, title, assigneeId nullable, status, dueAt | Một ticket có thể có nhiều nhiệm vụ |
| WorkOrder | id, taskId, executorId, attemptNo, redoOfId nullable, stage, version, startedAt, completedAt | Các lần thi công thuộc cùng task, không ghi đè bằng chứng lần trước |
| Evidence | id, workOrderId, fileId, phase, uploadedBy, createdAt | Quyền upload/đọc theo ticket và assignment; BEFORE/AFTER giữ cho flow cũ |
| PublicEvent | eventId, ticketId, message, occurredAt, version | Nội dung cư dân được phép thấy, tách khỏi log nội bộ |
| Invoice/Report | ID, currency, amount, status, thời gian hạch toán và scope | Doanh thu lấy hóa đơn theo quy tắc đã chốt, không lấy giá dự kiến ticket |

BE trả ID quan hệ rõ ràng. `ResidentRequest.id` ánh xạ ticket ID; code hiển thị không dùng thay ID. `WorkPage` mở `?ticket=`, `?task=`, `?job=` tương ứng với các entity; `job` hiện chỉ work order. BQL thấy một dòng/task và các lần thi công trong chi tiết; nhân viên chỉ thấy phiếu được giao. DTO summary hiện tại cần mở rộng hoặc bổ sung endpoint detail, không ép tất cả entity vào một ID.

### Ví dụ detail ticket cho Operations

```json
{
  "id": "ticket-01",
  "code": "YC-2026-001",
  "conversationId": "conversation-01",
  "buildingId": "building-01",
  "apartmentId": "apartment-1206",
  "location": { "buildingCode": "S2.01", "displayText": "Căn 1206, khu vực bếp" },
  "title": "Mất điện khu vực bếp",
  "description": "Ổ điện khu vực bếp không có điện từ sáng nay.",
  "category": "electric",
  "severity": "P2",
  "stage": "assigned",
  "version": 3,
  "resident": { "displayName": "Cư dân mẫu", "phone": "0900000000" },
  "taskId": "task-01",
  "currentWorkOrderId": "work-order-01",
  "assignee": { "id": "user-tech-01", "displayName": "Nguyễn Văn Hùng" },
  "allowedActions": ["arrive"],
  "evidence": [],
  "timeline": [{ "id": "event-03", "at": "2026-10-01T08:00:00Z", "label": "Đã phân công kỹ thuật viên" }]
}
```

Đây là ví dụ một task đang hoạt động; ticket nhiều task cần collection riêng. `allowedActions` tính cho actor hiện tại, không phải quyền client tự gửi lên. Resident detail phải là DTO công khai, không trả mọi field nội bộ rồi để FE tự giấu.

## 5. Danh mục API đề xuất

Mọi URL dưới đây là **đề xuất**, không phải chỉ dẫn gọi API đã có. Mutation dùng idempotency và version theo mục 7.

| Method / path đề xuất | Request chính | Response cần có |
|---|---|---|
| GET `/api/resident/conversations` | cursor, limit | items, nextCursor, unreadCount mỗi phòng |
| POST `/api/resident/conversations` | Không nhận residentId thay actor | id, title, ticketId=null |
| GET `/api/resident/conversations/:id/messages` | cursor, limit | Messages có sequence, nextCursor |
| POST `/api/resident/conversations/:id/messages` | clientMessageId, text, fileIds | Message được lưu; trạng thái phản hồi agent nếu async |
| POST `/api/resident/conversations/:id/read` | lastReadSequence | readCursor, unreadCount mới; cursor không lùi |
| POST `/api/resident/tickets` | conversationId, description, location, fileIds | 201 ticket + version; gắn ticket/phòng trong cùng transaction |
| GET `/api/resident/tickets` | status, cursor, limit | Ticket summaries công khai của user |
| GET `/api/resident/tickets/:id` | — | Detail công khai, events, allowedActions |
| GET `/api/operations/work-items` | view=current/history, department, status, q, cursor, limit | Task/work order summary, ticketId, counts và nextCursor |
| GET `/api/operations/tickets/:id` | — | Detail kiểm scope/assignment như ví dụ |
| GET `/api/operations/work-orders/:id` | — | Checklist, báo giá, BEFORE/AFTER, bàn giao, lần làm lại |
| GET `/api/operations/staff` | buildingId, department | Nhân viên hợp lệ, availability, tải việc hiện tại |
| PATCH `/api/operations/me/availability` | available | Trạng thái mới; không tự xóa việc đã giao |
| POST `/api/operations/tickets/:id/commands` | action, expectedVersion, payload | Snapshot/version sau cập nhật và eventIds |
| POST `/api/resident/tickets/:id/commands` | action, expectedVersion, resolutionVersion nếu xác nhận | Snapshot công khai sau mutation |
| GET/POST `/api/admin/accounts` | filter hoặc hồ sơ tạo mới | Account list/detail, activationStatus; không trả mật khẩu |
| POST `/api/admin/accounts/:id/commands` | approve/activate/suspend, expectedVersion | Status/version và audit ID |
| DELETE `/api/admin/accounts/:id` | expectedVersion, confirmation | Kết quả xóa/ngừng hoạt động theo chính sách retention đã chốt |
| GET `/api/management/rooms` | scope | Các nhóm actor được tham gia |
| GET/POST `/api/management/rooms/:id/messages` | cursor hoặc text, mentionAgentIds, ticketId tùy chọn | Message + sequence; phản hồi agent có trạng thái riêng |
| POST `/api/management/rooms/:id/agents` | name, specialty | Agent + membership được tạo nguyên tử |
| POST `/api/management/reports` | kind, from, to, buildingId | 202 jobId, status |
| GET `/api/management/reports/:id` | — | queued/running/ready/failed, error, summary, fileId nếu ready |
| GET `/api/files/:id/download` | — | Download có quyền, filename, MIME, thời hạn nếu dùng signed URL |

List response thống nhất `{items, nextCursor}`; cursor opaque, thứ tự ổn định có ID làm tie-breaker. Giới hạn đề xuất mặc định 20, tối đa 100 cần BE chốt. Không trả toàn bộ lịch sử chat/tất cả tòa nhà rồi lọc ở FE.

## 6. Command, actor và chuyển trạng thái

Tên dưới đây dựa trên reducer mẫu; BE có thể dùng tên domain khác nhưng phải cung cấp mapping. Stage detail khác status tóm tắt cư dân.

| Action | Actor thật được phép | Điều kiện / kết quả |
|---|---|---|
| assign | BQL đúng scope | Nhân viên active, đúng bộ phận/scope; kiểm tải việc chung. Thành công → assigned; bận → queued + lý do rõ ràng, không báo đã giao |
| arrive | Nhân viên được giao | assigned → on-site |
| ask-consent | Nhân viên được giao | Kỹ thuật on-site → awaiting-consent; lưu phương án/báo giá version |
| consent | Cư dân có quyền với ticket | awaiting-consent → on-site, lưu consent và phiên bản phương án |
| classify-water | Nhân viên được giao | Đánh giá nước nhỏ/lớn ở bước khảo sát; lưu lý do/ảnh |
| request-isolation | Nhân viên được giao | Nước lớn, đã đồng ý phương án → isolation-requested |
| approve-isolation | BQL đúng scope | isolation-requested → isolation-approved; xác định khu vực ảnh hưởng |
| notify-outage | BQL/worker hệ thống được ủy quyền | Tạo yêu cầu thông báo đến đúng tập cư dân; phân biệt queued/delivered/failed |
| isolate | Nhân viên được giao | Sau phê duyệt và điều kiện thông báo đã chốt → isolated |
| start | Nhân viên được giao | Kỹ thuật cần consent; nước lớn cần isolated; security khẩn cần ack → working |
| add-evidence | Nhân viên được giao | File đã upload/kiểm tra, thuộc đúng work order; lưu tác giả và phase |
| restore | Nhân viên được giao | Nước lớn đang xử lý có bằng chứng → restored; tạo thông báo khôi phục |
| submit | Nhân viên được giao | Có bằng chứng; nước lớn đã restore → awaiting-confirmation; security khẩn → controlled |
| confirm | Cư dân có quyền với ticket | awaiting-confirmation + đúng resolutionVersion → completed |
| request-rework | Cư dân có quyền với ticket | Lý do bắt buộc, đúng kết quả cần xác nhận; tạo lượt làm lại, giữ bằng chứng cũ |
| acknowledge | Người trực được phân công | Security P0/P1, ghi actor/time; không đóng ticket |
| escalate | Scheduler/người có quyền trực | Quá hạn chờ hoặc quá hạn ack; ghi lần chuyển cấp và người nhận tiếp theo; vẫn mở |
| raise-emergency | Nhân viên được giao hoặc BQL | Security, lý do bắt buộc; kích hoạt cảnh báo, không được vượt bước xác nhận |
| request-cancel | Nhân viên được giao hoặc BQL | Sự cố không khẩn ở bước cho phép, lý do bắt buộc → cancel-requested |
| approve-cancel | BQL đúng scope | cancel-requested, không phải security khẩn → cancelled |
| manager-close | BQL đúng scope | Security khẩn controlled, có ack và bằng chứng → completed |

**Khác biệt phải xử lý trước production:** reducer mẫu cho BQL thao tác một số bước thay nhân viên và có `resident-consent`/`resident-confirm` để test. Không đưa quyền giả lập đó vào API thật. Giao diện resident chưa có form đồng ý phương án sửa chữa; cần thêm bước này khi BE cung cấp consent/báo giá. FE Operations cần ẩn nút mô phỏng và chờ event thật.

### Mapping hiển thị cư dân

| Stage nghiệp vụ | Status ResidentRequest hiện tại |
|---|---|
| queued, assigned | received |
| on-site, working, các bước khóa/mở nước, controlled, cancel-requested | processing |
| awaiting-confirmation | confirmation |
| completed | completed |
| awaiting-consent | processing + action consent mới cần FE bổ sung |
| cancelled | **Chưa có enum trong resident**; cần thêm trạng thái/nhãn riêng, không map thành completed |

Nước lớn cần chốt chính sách khi thông báo thất bại, thời gian chờ và xử lý khẩn. An ninh cần chốt timeout ack/escalation và người trực dự phòng. Workflow cũ có nhãn tự hoàn thành sau 72h; **không mặc định áp dụng cho ticket mới**, nhất là an ninh khẩn. Cần quyết định nghiệp vụ riêng trước khi bật scheduler.

## 7. Mutation, lỗi và đồng thời

Ví dụ phân công:

```http
POST /api/operations/tickets/ticket-01/commands
Idempotency-Key: assign-ticket-01-client-unique
Content-Type: application/json
```

```json
{
  "action": "assign",
  "expectedVersion": 2,
  "payload": { "staffId": "user-tech-01" }
}
```

BE lấy actor từ session, kiểm quyền và version rồi commit assignment/timeline/version trong một transaction. Delivery event dùng outbox hoặc cơ chế tương đương để không mất thông báo sau khi commit. Cùng idempotency key + cùng payload trả cùng kết quả; cùng key khác payload phải báo xung đột. Chốt TTL key với FE. Hai BQL giao cùng ticket chỉ một mutation thành công.

Error envelope đề xuất:

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "Công việc đã được cập nhật. Vui lòng tải lại.",
    "requestId": "request-01",
    "currentVersion": 4,
    "fieldErrors": {}
  }
}
```

| HTTP | FE cần xử lý |
|---|---|
| 400/422 | Giữ form, hiện lỗi field/điều kiện nghiệp vụ |
| 401 | Bootstrap lại session hoặc về login; không chuyển sang demo |
| 403 | Không có quyền, không tiếp tục mutation |
| 404 | Không tồn tại hoặc không được phép biết resource tồn tại |
| 409 | Tải snapshot mới, giữ nội dung chưa gửi; người dùng xem lại trước khi thử lại |
| 413/415 | Thông báo giới hạn/kích thước hoặc loại file |
| 429 | Hiển thị thời gian thử lại; tuân thủ Retry-After |
| 5xx/mất mạng | Không báo thành công; retry mutation với cùng idempotency key khi kết quả chưa rõ |

Ngày giờ timestamp dùng ISO-8601 UTC; ngày lọc báo cáo dùng ngày địa phương và timezone đã chốt, đề xuất Asia/Ho_Chi_Minh. Không dựa vào đồng hồ trình duyệt để quyết định SLA hoặc quyền chuyển bước.

## 8. Upload, realtime và báo cáo

**Upload:** đề xuất khởi tạo upload `{purpose, ticketId, workOrderId, name, mimeType, size}` → uploadId/URL → finalize → fileId. Command chỉ tham chiếu fileId đã finalized. BE kiểm loại file/kích thước thực, quyền sở hữu và liên kết; ảnh có thể thu nhỏ ở FE nhưng validation vẫn thuộc server. Không lưu data URL trong API nghiệp vụ. Chốt giới hạn chung: resident mẫu nhận file nguồn tối đa 10 MB, tối đa ba ảnh/phản ánh; Operations tối đa ba ảnh/ticket mẫu. Đây chưa phải chính sách storage production.

**Realtime:** BE chọn SSE/WebSocket hoặc polling có cursor trước; FE chưa có subscription thật. Event tối thiểu gồm eventId, ticketId, conversationId nếu có, resourceVersion, occurredAt và loại event. FE dedupe eventId, không để event cũ ghi đè snapshot version mới; mất khoảng event thì refetch. Đọc tin gửi lastReadSequence, không đặt unread về 0 một cách mù khi có tin mới đến đồng thời. Không trả raw prompt/context nhóm BQL cho cư dân.

**Report:** job trạng thái running cần map vào trạng thái đang chờ/tạo của UI. Response ready nên có snapshot criteria, generatedAt, tổng số record, tổng tiền/currency, fileId. Định nghĩa doanh thu theo hóa đơn hợp lệ phải chốt (ngày phát hành hay thanh toán, thuế, hoàn tiền). Không cộng amount của ticket như demo. Tần suất dùng thời điểm tiếp nhận ticket, không đếm mỗi task/lần làm lại như một sự cố mới. Quyền tải file phải được kiểm lại khi download; job thất bại không trả link file giả.

## 9. Thứ tự triển khai và nghiệm thu

### Đợt 1 — Một luồng điện chạy thật

1. BE và FE chốt auth, mapping role/scope, entity IDs, enum, error envelope và API vào OpenAPI chung của repository theo quy ước team.
2. BE cung cấp tài khoản test: cư dân active/pending, kỹ thuật, an ninh, BQL cùng tòa/khác tòa, admin. Có cách reset fixture ở môi trường test, không dùng dữ liệu cá nhân thật.
3. Nối bootstrap session, hồ sơ/căn hộ và danh sách trước. Tắt fallback mock khi đã chọn môi trường API; lỗi server phải hiện lỗi.
4. Nối tạo phòng/ticket, phân công, nhận việc, consent, upload, gửi kết quả, cư dân xác nhận.
5. Nối event/polling để hai trình duyệt thấy cùng kết quả mà không dùng chung localStorage.

### Đợt 2 — Phần mở rộng

Nước lớn; security thường/khẩn; cấp/duyệt/khóa tài khoản; nhóm/agent; report jobs/DOCX; mapping phiếu cũ/checklist/báo giá/rework. Không đưa các nhánh chưa nối vào production với nút mô phỏng còn hoạt động.

### Checklist nghiệm thu liên app

| Tình huống | Kết quả bắt buộc |
|---|---|
| Cư dân gửi hai lần do timeout | Một ticket duy nhất, cùng conversationId; không tạo phiếu trùng |
| Cư dân hỏi tiếp trong phòng | Thêm message vào cùng ticket; vấn đề mới phải phòng mới |
| BQL phân công kỹ thuật | Một dòng công việc tương ứng xuất hiện trong Việc của tôi của đúng người; cùng ticket ID |
| Nhân viên khác/BQL khác tòa mở URL trực tiếp | API từ chối; không chỉ ẩn menu |
| Hai BQL phân công cùng lúc | Một thành công, một 409; UI tải lại và không ghi đè |
| Kỹ thuật chưa có consent/ảnh | BE chặn start/submit đúng điều kiện |
| Cư dân xác nhận kết quả cũ sau rework | BE từ chối theo resolutionVersion; giữ nguyên bằng chứng và lần làm mới |
| Cư dân xác nhận thành công | Cùng ticket chuyển completed; Operations thấy ở Lịch sử, không sao chép record |
| Nước lớn bỏ qua duyệt/thông báo/mở van lại | Command bị chặn theo state machine đã chốt |
| Security không ack/chuyển cấp | Ticket vẫn mở; chỉ actor hợp lệ đóng sau controlled + bằng chứng |
| Khóa tài khoản đang đăng nhập | Request tiếp theo/subscription mất quyền; không thể tiếp tục thao tác |
| Tin đến đúng lúc đánh dấu đã đọc | Không mất tin chưa đọc; reconnect không nhân đôi message |
| Upload hỏng/quá giới hạn/không thuộc user | Không tạo evidence thành công giả; form giữ phần chưa gửi |
| Report theo ngày/tòa nhà | Không lẫn scope; doanh thu khớp bộ hóa đơn test; tải DOCX đúng nội dung snapshot |
| Reload/đổi thiết bị | Dữ liệu lấy từ BE nhất quán, không phụ thuộc key demo trên máy cũ |

Smoke và unit tests hiện có kiểm tra FE/mock, **chưa chứng minh các tiêu chí backend ở bảng này**. Sau tích hợp phải chạy acceptance trên ít nhất hai phiên riêng (resident và Operations).

## 10. Nội dung BE cần trả cho FE khi bắt đầu nối

- OpenAPI/DTO thống nhất, base URL từng môi trường và cơ chế xác thực/CORS.
- Danh sách role/permission, scope/membership và tài khoản test cho từng trạng thái.
- Mapping entity/status/action, quy tắc consent/rework/cancel, SLA và quyền đóng sự cố.
- Ví dụ success/error thực tế; pagination, idempotency TTL và version conflict.
- Contract upload/finalize/download; event transport/reconnect; report job/file.
- Danh sách endpoint đã sẵn sàng và endpoint chưa có, để FE nối theo đợt mà không giả lập thành công.

FE chịu trách nhiệm adapter, cache, loading/error/retry, ẩn nút mô phỏng, map dữ liệu vào UI và test hành trình. BE chịu trách nhiệm xác thực, quyền, persistence, transaction/state machine, idempotency, file, event và báo cáo thật. Hai bên cùng duyệt acceptance và các quyết định nghiệp vụ còn mở.
