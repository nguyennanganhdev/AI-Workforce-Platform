# Danh sách API endpoint cần xây dựng cho hệ thống Vinhomes

## Cập nhật mới nhất: dữ liệu faker nằm trong database V3

Theo yêu cầu mới, `main.py` dùng router V3 và PostgreSQL cho cả demo; không chọn ứng dụng RAM. Đã có script Docker/migration/seed, user theo vai trò, 20 căn hộ/cư dân, ticket, hóa đơn mẫu. `VINHOMES_API_DEMO_MODE=1` chỉ cho chọn user fixture trên loopback; quyền/scope vẫn kiểm tra từ DB. Xem [hướng dẫn database demo](../services/vinhomes-api/HUONG_DAN_DEMO_DATABASE_V3.md).

Đã nối/sửa BQL phân công, ca trực/chuyên môn/capacity, hàng chờ, kiểm tra bằng chứng/nước trước hoàn tất, tạo yêu cầu nghiệm thu và cập nhật trạng thái khi cư dân đồng ý/từ chối. Chat/mention demo lưu message và kết quả mẫu trong DB. Gateway Hono chuyển tiếp sang chế độ faker-database.

Danh sách mock bên dưới là lịch sử bản RAM. Camera/contact, cảnh báo/ACK, phê duyệt điều động/hủy, admin account, tạo agent trong room và đề xuất memory **chưa có đầy đủ router V3**; việc đổi nguồn dữ liệu không mặc nhiên hoàn thiện các endpoint đó. Không cần viết mã agent tool.

## Cập nhật: demo mock theo yêu cầu mới

Đã bổ sung chế độ `VINHOMES_API_DEMO_MODE=1` trên FastAPI cổng 8000 để chạy luồng bằng dữ liệu RAM. Hướng dẫn và contract mẫu: [HUONG_DAN_DEMO_MOCK.md](../services/vinhomes-api/HUONG_DAN_DEMO_MOCK.md).

- Ticket: chat → tạo ticket → BQL nhận → work order → phân công → nhân viên nhận/từ chối → tiến độ → bằng chứng → cư dân nghiệm thu/sửa lại.
- Điều phối: `/staff/available`, `/dispatch-queue`, kiểm tra nhân viên bận.
- Nước: đề xuất → BQL duyệt → thông báo → khóa → khôi phục; chặn hoàn tất khi chưa mở nước.
- An ninh: camera/contact mock, phê duyệt điều động/hủy, cảnh báo → leo thang → ACK. Giữ ánh xạ P0–P3 sang p1–p4.
- Room: list/tạo agent, mention có kết quả mẫu và chống gửi trùng.
- Báo cáo: tần suất sự cố, hóa đơn mock `issued`, tải DOCX.
- Quản trị: tạo/khóa/mở/xóa mềm tài khoản; đề xuất và duyệt/từ chối memory.
- Gateway Hono demo: `http://localhost:3001/api/vinhomes-demo`, chuyển tiếp endpoint cùng `X-Demo-Actor` cho FE/client agent. Đây là chọn vai trò mock, chưa phải gateway ủy quyền phiên người dùng thật.

Danh sách chính xác các method/path của mock được hiển thị tại `/docs` và `/openapi.json`. ID mock, body và trạng thái khác contract database V3; dùng đúng OpenAPI của chế độ đang chạy. Các đánh giá schema/phần chờ contract ngoài bên dưới chỉ áp dụng khi nối dữ liệu thật. Không viết mã agent tool, adapter hoặc worker LLM.

Nguồn: [nghiệp vụ hệ thống](no_need_read-this.md), [tổng hợp agent-rules, nghiệp vụ](no_need_TONG_HOP_AGENT_RULES.md), schema tại `server/drizzle/0000_grey_blockbuster.sql` và `server/drizzle/0001_vinhomes_operations.sql`. **Mục tiêu là cùng service FastAPI cổng 8000 cung cấp API endpoint cho FE và client agent; không viết mã agent tool, adapter tool hoặc hàm gọi tool.** Đường gọi agent được chốt là qua Hono với quyền của người yêu cầu; gateway ủy quyền Hono→FastAPI chưa được nối. Tên file được giữ để không làm hỏng liên kết đã dùng trước đó.

## 1. Quy ước thiết kế

- Mỗi endpoint thực hiện một hành động rõ ràng, có input/output, quyền gọi, phạm vi BQL/tenant, lỗi và event kết quả.
- Lệnh thay đổi trạng thái cần kiểm tra transition và chống gọi lặp; quyết định phê duyệt, điều động và cảnh báo phải có audit.
- API kiểm tra quyền xem dữ liệu trong phạm vi được giao. Nếu có endpoint `@mention`, context chỉ gồm thông tin cần thiết của room và ticket liên quan.
- Danh sách dưới đây là backlog endpoint, **không khẳng định** mọi endpoint đã có hoặc database cục bộ đã chạy đủ migration.

## 2. Backlog theo luồng

| Ưu tiên | Nhóm | API endpoint cần cung cấp | Client gọi | Tình trạng trong FastAPI V3 |
| --- | --- | --- | --- | --- |
| P1 | Định tuyến | `GET /management-units/resolve` theo tòa/domain/loại dịch vụ; endpoint xác minh phạm vi căn hộ/cư dân | Reception, client nội bộ | Đã có `GET /management-units/resolve`; cần rà contract theo loại dịch vụ và quyền cư dân |
| P1 | Chat | Tạo/list cuộc chat, gửi/lấy tin nhắn, gắn ticket vào chat | Cư dân, Reception | Chưa thấy trong các router được nạp ở `main.py` |
| P1 | Ticket | Tạo/lấy/list ticket; timeline; chuyển trạng thái; thông báo ticket được tiếp nhận | Reception, Supervisor, cư dân | Đã có ticket, timeline, status và `tickets.channel_id`; còn thiếu endpoint thông báo cư dân |
| P1 | Triage/điều phối | Đánh giá ticket, chọn chuyên môn, giao task, phản hồi “đã chuyển nhân viên” | Supervisor, client nội bộ | Đã có triage ở V3; cần endpoint phản hồi về Reception. Route task cũ chưa được nạp vào `main.py` |
| P1 | Nhân viên | Tra nhân viên rảnh, phân công, nhận/từ chối, check-in, cập nhật tiến độ, hàng chờ | Supervisor, Technical, Security, nhân viên | Đã có work order/assignment và một số field operations; cần kiểm tra availability, queue và SLA |
| P1 | Bằng chứng/xác nhận | Tải ảnh, lấy ảnh theo ticket, cư dân xác nhận hoàn tất, xử lý khi cư dân không đồng ý | Nhân viên, cư dân | Đã có evidence/file và QC; cần xác nhận cư dân theo đúng quy trình |
| P1 | Phê duyệt | Tạo yêu cầu, duyệt/từ chối điều động, hủy điều động, khóa nước | BQL, người có thẩm quyền | Đã có approval tổng quát; cần rule và trạng thái riêng cho từng hành động |
| P2 | Tri thức | Tra FAQ, nội quy, dịch vụ, hướng dẫn kỹ thuật, SOP khẩn cấp theo tòa/khu đô thị | Reception, Technical, Security | Chưa thấy API tri thức trong FastAPI V3 |
| P2 | Kỹ thuật nước | Yêu cầu khóa nước, duyệt, thông báo cắt nước, xác nhận khóa/mở, thông báo khôi phục | Technical, BQL, nhân viên | Cần bổ sung quy trình chuyên biệt và event/thông báo |
| P2 | An ninh | Phân cấp P0–P3; tra metadata camera; tìm bảo vệ; điều động; ACK cảnh báo; leo thang; hủy có lý do | Security, bảo vệ, người trực, BQL | Đã có security incident/checkpoint/handover; thiếu phần camera, cảnh báo/ACK và điều động đầy đủ |
| P2 | Thông báo | Lấy/list thông báo, đánh dấu đã đọc, phát event chat/ticket/cảnh báo theo người nhận | Cư dân, nhân viên, BQL | Chưa thấy trong FastAPI V3 |
| P2 | Group chat/agent | Tạo/list agent, tự thêm vào room, gửi tin nhắn có `@mention`, lấy trạng thái và kết quả xử lý | BQL, Supervisor, client nội bộ | Chưa thấy trong FastAPI V3; Context Builder là xử lý nội bộ, không phải endpoint riêng bắt buộc |
| P3 | Báo cáo | Truy vấn ticket/hóa đơn theo scope, tạo job báo cáo, lấy trạng thái, tải DOCX | Report agent, BQL | Chưa thấy API tạo DOCX; cần xác minh nguồn hóa đơn |
| P3 | Tài khoản | Duyệt đăng ký, tạo BQL/nhân viên, kích hoạt/khóa/xóa tài khoản | Admin | Có API quản trị ở server Hono; chưa có trong FastAPI V3; cần chọn nơi sở hữu chức năng |
| P3 | Memory | Đề xuất dữ liệu, admin xem/duyệt/từ chối, phiên bản và rút lại | Agent, Admin | Chưa thấy trong FastAPI V3 |

## 3. Nhóm endpoint V3 đã có thể tái sử dụng

- **Phạm vi, ticket:** `GET /management-units/resolve`, `GET/POST /tickets`, `GET /tickets/{ticket_id}`, `PATCH /tickets/{ticket_id}/status`, `GET /tickets/{ticket_id}/timeline`.
- **Đánh giá và điều phối:** triage/assessment, task, work order, assignment và phản hồi phân công.
- **Hiện trường:** work order status, một số field operations, QC, evidence, file và approval.
- **An ninh cơ bản:** security incident, checkpoint và handover.

Các route V3 được nạp trong `services/vinhomes-api/src/vinhomes_api/main.py`; route nghiệp vụ cũ ở các thư mục `tasks/`, `work_orders/`, `approvals/` không mặc nhiên có mặt trong ứng dụng FastAPI hiện tại. Khi triển khai endpoint, kiểm tra router nào thực sự được nạp và contract/schema của từng route trước khi tái sử dụng.

## 4. Đối chiếu độ đầy đủ của database schema

Đánh giá dưới đây dựa trên **SQL migration trong repo**, chưa xác minh database cục bộ đã áp dụng migration hoặc có dữ liệu mẫu. `server/drizzle/0000_grey_blockbuster.sql` là schema nền tảng rộng; `0001_vinhomes_operations.sql` và `0002_vinhomes_qc_redo.sql` bổ sung nghiệp vụ hiện trường.

| Nhóm endpoint | Bảng/quan hệ hiện có | Kết luận về schema |
| --- | --- | --- |
| Định tuyến, tài khoản | `domains`, `sites`, `zones`, `buildings`, `units`, `unit_residents`, `management_units`, `management_coverage`, `users`, `account_reviews`, `scoped_user_roles` | Đủ nền tảng cho endpoint; cần chốt quy tắc chọn BQL khi coverage chồng lấn và tài khoản chờ duyệt |
| Chat và ticket | `channels`, `channel_memberships`, `messages`, `reception_sessions`, `reception_waits`, `tickets`, `ticket_events`, `ticket_routing_history` | Đủ nền tảng chat và ticket một vấn đề/một room; `tickets.channel_id` có unique, nên không tạo nhiều ticket trên cùng room theo schema hiện tại |
| Triage và điều phối | `ticket_assessments`, `ticket_triage_decisions`, `ticket_triage_reviews`, `agent_teams`, `team_tasks`, `team_mailbox` | Đủ nền tảng dữ liệu; còn phải định nghĩa contract endpoint và state transition |
| Nhân viên, hàng chờ | `staff_profiles`, `staff_shifts`, `staff_specialties`, `dispatch_queue`, `dispatch_attempts`, `work_orders`, `work_assignments`, `sla_policies` | Đủ nền tảng availability, queue và assignment; cần quy tắc chọn nhân viên, timeout và chống tranh chấp |
| Phê duyệt, kỹ thuật nước | `work_approvals`, `service_interruptions`, `interruption_scopes`, `notification_deliveries`, `ticket_events` | Đủ nền tảng để thiết kế endpoint khóa/mở nước; cần chốt người duyệt và thời điểm gửi thông báo |
| Tri thức | `knowledge_bases`, `knowledge_documents`, `knowledge_chunks`, `document_acl`, `retrieval_runs` | Có nơi lưu và kiểm soát tài liệu; API tìm kiếm cần lọc scope và loại tài liệu FAQ/SOP |
| Thông báo | `notification_deliveries` có `user_id`, nguồn event/message, `status`, `read_at` | Đủ cho danh sách và đánh dấu đã đọc; cơ chế phát realtime/push là phần triển khai ngoài schema |
| Group chat và agent | `agents`, `agent_versions`, `channel_agents`, `message_mentions`, `context_snapshots`, `agent_teams` | Đủ nền tảng lưu room, agent và mention; quy tắc dựng context là logic server |
| Báo cáo, hóa đơn | `report_requests`, `report_sources`, `invoices`, `invoice_lines`, `file_objects` | Đủ nền tảng job báo cáo và file DOCX; cần chốt định nghĩa doanh thu và quyền theo scope |
| Memory | `memory_candidates`, `memory_namespaces`, `memory_publications`, `knowledge_reviews` | Đủ nền tảng duyệt và phát hành; cần chốt ai duyệt và quy trình rút lại |
| An ninh cơ bản | `vh_security_incidents`, `vh_security_checkpoints`, `vh_security_handovers`, `ticket_escalations` | Có sự cố, checkpoint và escalation; **chưa thấy bảng camera registry/trạng thái camera**. ACK của `ticket_escalations` chỉ thể hiện người nhận escalation, chưa đủ để khẳng định đã mô hình hóa đầy đủ chuỗi cảnh báo khẩn cấp tới từng người trực |
| Cư dân xác nhận xử lý | `ticket_events`, `ticket_reviews`, `work_orders` | Có thể ghi sự kiện xác nhận vào timeline, nhưng `ticket_reviews` là đánh giá 1–5 sao, không phải bản ghi chấp thuận/từ chối nghiệm thu có cấu trúc. Cần chốt contract; nếu phải lưu từng lần xác nhận và tranh chấp độc lập, cần bổ sung schema |

**Kết luận:** schema nền tảng bao phủ phần lớn danh sách endpoint, nhưng **chưa đủ để khẳng định triển khai trọn vẹn tất cả**. Điểm cần bổ sung hoặc chốt trước là camera metadata, chuỗi cảnh báo khẩn cấp/ACK và xác nhận nghiệm thu của cư dân. SQL `vh_security_incidents.severity` nhận `p1`–`p4`, còn nghiệp vụ dùng P0–P3; ánh xạ đã được chốt bên dưới nên không cần migration riêng cho mức độ. Tài liệu `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md` trên nhánh `dev_TeamHoang` là contract message agent, không phải migration database.

**Quyết định của chủ dự án:** giữ cột database `p1`–`p4`; API nhận thêm `business_severity` và ánh xạ `P0 → p1`, `P1 → p2`, `P2 → p3`, `P3 → p4`. BQL phụ trách phê duyệt điều động bảo vệ, hủy điều động và khóa nước. Endpoint phê duyệt khóa nước phải kiểm tra role quản lý và scope của ticket; không cho admin mặc nhiên duyệt thay BQL.

### Endpoint đã bổ sung trong đợt triển khai này

| Endpoint | Chức năng |
| --- | --- |
| `POST/GET /resident/chats` | Tạo và liệt kê chat của người dùng |
| `GET/POST /resident/chats/{channel_id}/messages` | Đọc/gửi tin nhắn trong chat của mình |
| `POST /resident/chats/{channel_id}/tickets` | Tạo một ticket gắn chat, xác minh căn hộ, chọn coverage BQL và báo BQL |
| `POST /tickets/{ticket_id}/routing/ack` | BQL nhận ticket được định tuyến, ghi event và thông báo cư dân |
| `GET /resident/tickets`, `GET /resident/tickets/{ticket_id}` | Xem ticket và timeline an toàn cho cư dân |
| `GET /resident/approvals`, `POST /resident/approvals/{approval_id}/decision` | Xem và xác nhận/từ chối yêu cầu sửa chữa được giao cho mình |
| `GET /my/notifications`, `POST /my/notifications/{notification_id}/read` | Xem và đánh dấu đã đọc thông báo của mình |
| `GET /staff/available` | Tra nhân viên đang trong ca, đúng chuyên môn, còn năng lực nhận việc trong phạm vi BQL |
| `GET /knowledge/search` | Tìm tài liệu đã xuất bản theo domain, scope và ACL được cấp |
| `POST /work-orders/{work_order_id}/water-shutdown-request`, `GET /work-orders/{work_order_id}/water-interruptions` | Nhân viên đề xuất ngừng cấp nước trong phạm vi tòa/zone và theo dõi yêu cầu |
| `POST /water-interruptions/{interruption_id}/notify`, `/start`, `/restore` | BQL thông báo sau khi duyệt; nhân viên ghi nhận ngừng/cấp nước lại và tạo thông báo cho cư dân bị ảnh hưởng |
| `GET /reports/incident-frequency`, `GET /reports/incident-frequency.docx` | Xem và tải báo cáo tần suất sự cố theo tòa, kỳ, quyền BQL |
| `GET /reports/issued-revenue`, `GET /reports/issued-revenue.docx` | Xem và tải giá trị hóa đơn trạng thái `issued` theo tòa, loại dịch vụ và kỳ; có thể chọn category kỹ thuật |
| `GET /admin/memory-candidates`, `POST /admin/memory-candidates/{candidate_id}/review` | Admin xem và duyệt/từ chối đề xuất memory đã khử PII |
| `GET /rooms`, `GET/POST /rooms/{room_id}/messages`, `GET /rooms/{room_id}/mentions/{message_id}` | Đọc/gửi tin nhắn group chat và xem trạng thái mention; chỉ ghi nhận mention vào hàng chờ, chưa thực thi agent |

Các endpoint trên dùng schema hiện có; thông báo tự động cho mọi loại event, worker xử lý mention, camera và cảnh báo khẩn cấp vẫn cần code nghiệp vụ bổ sung. Luồng nước tạo thông báo in-app khi BQL xác nhận phạm vi ảnh hưởng và khi nhân viên ghi nhận cấp nước lại. Báo cáo DOCX hiện tạo trực tiếp từ truy vấn, chưa dùng job `report_requests`. Giá trị hóa đơn `issued` là **số đã xuất hóa đơn**, không phải tiền thực thu. Đây là trạng thái triển khai, không phải xác nhận đã chạy thành công với database thật.

Chủ dự án đã cập nhật phạm vi demo: metadata camera và liên hệ khẩn cấp được seed giả vào PostgreSQL thật. Migration `0003_vinhomes_security.sql` bổ sung bảng và các endpoint tương ứng; chưa kết nối hệ thống camera ngoài.

## 5. Thứ tự triển khai endpoint đề xuất

1. Chốt contract chat–ticket–event và quyền cư dân/BQL; nối Reception → Supervisor → nhân viên → cư dân bằng dữ liệu thật.
2. Hoàn thiện availability, hàng chờ, phê duyệt, xác nhận cư dân và thông báo để ticket có thể đi hết vòng đời.
3. Bổ sung endpoint kỹ thuật nước, an ninh khẩn cấp và tra cứu tri thức/SOP sau khi chốt các chỗ thiếu schema.
4. Bổ sung endpoint group chat và `@mention`; sau đó báo cáo DOCX, quản trị tài khoản và memory.

## 6. Quyết định cần chốt

- Tài khoản cư dân tự đăng ký có phải chờ admin duyệt trước khi dùng?
- FE cần thống nhất hiển thị P0–P3 trong khi database giữ p1–p4; phép ánh xạ đã chốt ở trên.
- BQL phụ trách duyệt điều động, hủy điều động và khóa nước; cần chốt thời hạn chờ và cách xử lý từ chối.
- BQL được chọn thế nào khi phạm vi tòa/phân khu hoặc loại dịch vụ chồng lấn?
- API tài khoản sẽ tiếp tục thuộc server Hono hay chuyển sang FastAPI?

## 7. Cập nhật triển khai ngày 2026-10-01

**Chỉ triển khai HTTP endpoint cho FE và agent tools; không viết code tool. Không bổ sung API gọi RAG/answer_or_escalate theo yêu cầu mới nhất.**

Migration 0003/0004 và seed đã được áp dụng vào PostgreSQL demo. Migration 0004 bỏ unique `tickets.channel_id`, nên một chat hiện có thể chứa nhiều ticket; mỗi ticket có sự kiện và idempotency riêng. Các nhận định “chưa có schema”/“một ticket mỗi room” ở phần đối chiếu lịch sử cần đọc cùng cập nhật này.

Đã bổ sung API cho cảnh báo, guard approvals, account membership, room agent/memory, HITL phương án, ảnh hội thoại, thiết bị/số đo/quyền thao tác, hóa đơn/thanh toán demo, báo cáo, đánh giá/phê duyệt agent, Task Board và Mailbox.

**Response cho agent xử lý tiếp:** 49 endpoint JSON trong các nhóm tool/bước hỗ trợ dùng schema `AgentBusinessResponse`. API thuần code: xác thực, kiểm tra quyền/input/điều kiện, đọc/ghi database và trả dữ liệu nghiệp vụ. `agentContext` chỉ có operation, facts, missingFields do validator xác định, resourceContext và source. API không chạy AI/LLM, không sinh câu hỏi/khuyến nghị, không chọn tool hoặc quyết định bước tiếp. Đây là endpoint API, không phải 49 code tool.

Tạo ticket trả snapshot: mã/status/version, nội dung và vị trí đã xác minh, category/BQL phụ trách, phương án/công việc, ảnh và thông báo. Retry phân biệt created/replayed và đọc trạng thái hiện tại. Các nhóm kỹ thuật, bảo vệ, báo cáo và ảnh cũng trả dữ liệu nghiệp vụ để caller/agent tự xử lý tiếp; phê duyệt và quyền vẫn được kiểm tra ở server. Endpoint tải ảnh/DOCX vẫn trả bytes.

Đã kiểm tra cú pháp/lint và khởi động API với schema mới; chưa chạy lại toàn bộ scenario HTTP cho response có agentContext. Không coi kết quả demo trước thay đổi response là xác minh contract mới.

Mapping tool → endpoint, input/output, luồng và ranh giới tích hợp được cập nhật tại [API_NGHIEP_VU_MOI_DATABASE.md](API_NGHIEP_VU_MOI_DATABASE.md). Trạng thái xác minh chính xác nằm trong `changes/2026-10-01-v3-database-business-apis.md`; không suy ra đã tích hợp runtime hoặc provider từ việc endpoint lưu được database.
