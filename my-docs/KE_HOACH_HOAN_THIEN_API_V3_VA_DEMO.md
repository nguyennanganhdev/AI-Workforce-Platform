# Kế hoạch hoàn thiện API V3 và demo frontend

- Ngày: 01/10/2026.
- Mục tiêu: chạy các luồng demo trên frontend bằng API cổng 8000, đọc/ghi PostgreSQL V3 chứa dữ liệu giả.
- Phạm vi backend: HTTP endpoint, schema/migration cần thiết, seed, quyền/scope và gateway Hono. Không viết agent tool, adapter tool hoặc worker chạy LLM.
- Quy tắc thực hiện: tuân thủ `Agent-rules/`, giữ các thay đổi hiện có và ghi context vào `/changes` cho mỗi task triển khai.

## 1. Điểm xuất phát

Đã có PostgreSQL Docker riêng trên cổng 5544; FastAPI dùng các router V3. Có fixture cư dân, BQL, kỹ thuật, an ninh, admin, căn hộ, ca trực/chuyên môn, coverage, ticket và hóa đơn.

Đã chạy luồng API trên database: chat → ticket → BQL nhận → phân công → nhân viên nhận → khóa/mở nước → ảnh/bằng chứng → hoàn tất → cư dân nghiệm thu. Ticket kết thúc `closed`. Báo cáo đọc hóa đơn `issued`; phản hồi mention mẫu lưu trong database.

Chưa hoàn thiện trên V3: camera/contact, cảnh báo/ACK, phê duyệt điều động/hủy, một số API quản trị, tạo agent trong room và đề xuất memory. FE chưa được nối/xác minh đầy đủ. Gateway hiện dùng nhân vật demo, chưa ủy quyền phiên người dùng thật.

Nguồn: [danh sách endpoint](DANH_SACH_TOOL_API_CAN_XAY_DUNG.md), [hướng dẫn database demo](../services/vinhomes-api/HUONG_DAN_DEMO_DATABASE_V3.md), [context triển khai](../changes/2026-09-30-vinhomes-v3-endpoints.md).

## 2. Quyết định đã chốt

- Dữ liệu giả nằm trong database V3; API nghiệp vụ không chuyển sang lưu RAM hoặc localStorage.
- An ninh: giữ DB `p1`–`p4`, ánh xạ P0→p1, P1→p2, P2→p3, P3→p4. Ánh xạ này áp dụng cho schema sự cố an ninh, không thay các enum severity của triage.
- BQL phụ trách phê duyệt điều động, hủy điều động và khóa nước.
- Báo cáo doanh thu dựa trên hóa đơn `issued`.
- Client agent đi qua Hono với quyền người yêu cầu khi dùng danh tính thật. Demo cục bộ chọn user fixture và vẫn kiểm tra quyền từ DB.
- Chỉ bổ sung schema cho phần thiếu sau khi đối chiếu bảng hiện có; đồng bộ định nghĩa Drizzle, migration và metadata theo quy trình của repo.

## 3. Giai đoạn 1 — Chốt contract và khoảng thiếu schema

### Công việc

1. Lập bảng màn hình FE → endpoint → bảng V3 → quyền → trạng thái triển khai.
2. Đối chiếu OpenAPI đang được mount với backlog; loại endpoint trùng với chức năng Hono đã sở hữu.
3. Với mỗi endpoint còn thiếu, xác định request/response, UUID hoặc ID text đúng schema, pagination, lỗi và version/idempotency khi cần.
4. Rà `ticket_escalations`, `work_approvals`, `users`, membership/scope, `agents`, `channel_agents`, `memory_candidates` để xác định phần tái sử dụng.
5. Thiết kế phần thiếu cho camera/contact và chuỗi cảnh báo. Kiểm tra `work_approvals.kind` trước khi thêm loại điều động/hủy.

### Kết quả cần có

- Bảng contract đủ để triển khai từng endpoint và nối màn hình tương ứng.
- Danh sách migration tối thiểu; không tạo bảng chung để chứa toàn bộ state demo.
- Ma trận quyền cư dân/BQL/nhân viên/admin trên từng hành động.

## 4. Giai đoạn 2 — Hoàn thiện API an ninh trên database

Các path dưới đây là đề xuất; chốt ở giai đoạn 1 trước khi code.

| Endpoint | Công việc |
| --- | --- |
| `GET /security/cameras` | Đọc camera metadata theo tòa/scope; seed camera online/offline |
| `GET /security/emergency-contacts` | Đọc liên hệ giả, vai trò và thứ tự nhận cảnh báo |
| `POST /tickets/{ticket_id}/emergency-alerts` | Tạo cảnh báo cho sự cố khẩn cấp, ghi người nhận và event |
| `GET /security/alerts` | Danh sách cảnh báo thuộc phạm vi/người nhận |
| `POST /security/alerts/{alert_id}/ack` | Người nhận xác nhận; ghi actor và thời điểm |
| `POST /security/alerts/{alert_id}/escalate` | Chuyển cảnh báo đến người nhận tiếp theo theo quy tắc |
| `POST /work-orders/{id}/security/dispatch-request` | Đề xuất điều động bảo vệ, chờ BQL duyệt |
| `POST /work-orders/{id}/security/cancel-request` | Đề xuất hủy có lý do, chờ BQL duyệt |
| `POST /approvals/{approval_id}/decision` | Mở rộng handler hiện có cho hai loại phê duyệt an ninh |

### Quy tắc nghiệp vụ

- Mọi truy vấn/ghi lọc tenant và scope; người ACK phải là người nhận hợp lệ.
- Phân công an ninh chỉ thực hiện sau phê duyệt điều động; duyệt hủy cập nhật đúng assignment/work order/ticket liên quan.
- Chống tạo cảnh báo/yêu cầu trùng; khóa hàng và kiểm tra trạng thái khi quyết định.
- Ghi event và thông báo in-app cùng transaction.
- Chốt thời hạn ACK và điều kiện leo thang trong contract. Demo có thể gọi endpoint leo thang theo kịch bản; không mặc nhiên cần worker nền.

### Điều kiện hoàn thành

Luồng tạo sự cố → cảnh báo → ACK/leo thang → BQL duyệt điều động → bảo vệ nhận/xử lý → nghiệm thu chạy bằng database. Luồng hủy có lý do chạy được. Sai quyền, thiếu phê duyệt và trạng thái không hợp lệ bị từ chối.

## 5. Giai đoạn 3 — Quản trị, room và memory

| Nhóm | Công việc |
| --- | --- |
| Tài khoản | Rà API Hono hiện có; tái sử dụng hoặc cung cấp facade khi FE cần. Hoàn thiện tạo/duyệt đăng ký, kích hoạt, khóa và xóa mềm theo membership/scope |
| Agent trong room | List, tạo hoặc thêm agent có sẵn vào room; kiểm tra workspace, membership và quyền BQL |
| Memory | Bổ sung đề xuất vào `memory_candidates`; tái sử dụng list/review admin hiện có; kiểm tra namespace/scope và điều kiện duyệt |

Phiên bản/rút lại memory chỉ triển khai nếu nằm trong kịch bản demo đã chọn; ghi rõ quan hệ với publication và tài liệu đã phát hành. Không đánh đồng việc tạo agent record với việc agent đã thực thi LLM.

### Điều kiện hoàn thành

Các thao tác quản trị được lưu DB và hiển thị lại sau restart. Không tạo hai nơi sở hữu trạng thái tài khoản. Người không có quyền không thể thay membership hoặc thêm agent vào room của người khác.

## 6. Giai đoạn 4 — Hoàn thiện bộ dữ liệu demo

1. Seed dữ liệu liên kết đúng FK cho triage, QC/redo, vệ sinh, nhà thầu, ngân sách, checkpoint, sự cố/bàn giao ca, tri thức và memory.
2. Bổ sung dữ liệu an ninh sau migration ở giai đoạn 2.
3. Chuẩn bị kịch bản: nhân viên rảnh/bận, nhận/từ chối việc, BQL duyệt/từ chối, cư dân đồng ý/yêu cầu sửa lại, cảnh báo có ACK/chuyển cấp.
4. Giữ ID fixture ổn định; seed chạy lại không reset state đang demo. Nếu cần reset, cung cấp lệnh riêng có phạm vi rõ, không trộn vào startup.
5. Chọn cách demo hóa đơn: giữ hóa đơn seed hoặc bổ sung endpoint phát hành hóa đơn giả khi cần tạo doanh thu từ việc mới. Không tự suy ra doanh thu từ số ticket đóng.

### Điều kiện hoàn thành

Mỗi màn hình thuộc kịch bản có dữ liệu đọc từ V3. Không có liên kết ticket/work order/user sai; thay đổi API vẫn còn sau restart. Không gửi cảnh báo ra số điện thoại thật hoặc gọi hệ thống camera ngoài để seed.

## 7. Giai đoạn 5 — Kết nối frontend và gateway

### Thứ tự nối màn hình

1. Cư dân: chat, message, tạo/theo dõi ticket, notification, nghiệm thu.
2. BQL: ticket/triage, dashboard/kanban, work order, availability/queue, phê duyệt.
3. Nhân viên: việc được giao, nhận/từ chối, check-in/tiến độ, bằng chứng, nước/an ninh.
4. QC, vệ sinh, nhà thầu, ngân sách, checkpoint và bàn giao ca.
5. Room/mention, báo cáo DOCX, account và memory.

### Công việc tích hợp

- Dùng một API client và cấu hình base URL; adapter kiểu dữ liệu FE lấy từ contract V3.
- Chuyển từng hook từ mock/localStorage sang query/mutation. Invalidate/refetch dữ liệu liên quan sau lệnh ghi.
- Hiển thị loading, empty, lỗi và 409 version conflict; gửi UUID làm khóa, dùng code riêng để hiển thị.
- Nối ảnh upload/download, tải DOCX, bộ lọc/phân trang và quyền hiển thị theo dữ liệu API.
- Demo cục bộ có thể tiếp tục dùng gateway `X-Demo-Actor`. Nếu kịch bản cần đăng nhập thật, bổ sung Hono xác thực và ủy quyền đến FastAPI; danh tính phải được server kiểm chứng. Giữ ranh giới với code tool.

### Điều kiện hoàn thành

FE đọc/ghi qua API, không còn localStorage làm nguồn trạng thái nghiệp vụ của các màn hình đã nối. Đổi vai trò thấy đúng dữ liệu; reload trang giữ trạng thái từ database.

## 8. Giai đoạn 6 — Chạy kịch bản và bàn giao

- Kịch bản kỹ thuật: ticket → phân công → khóa/mở nước → ảnh → hoàn tất → nghiệm thu → báo cáo.
- Kịch bản an ninh: sự cố khẩn cấp → cảnh báo → ACK/leo thang → phê duyệt → điều động/xử lý; thêm kịch bản hủy.
- Kịch bản ngoại lệ: nhân viên bận, từ chối phân công, BQL từ chối, cư dân yêu cầu sửa lại, request trùng và version cũ.
- Kịch bản quản trị: tài khoản, agent trong room, đề xuất/duyệt memory.
- Kiểm tra dữ liệu còn sau restart và không bị người khác scope đọc/ghi.
- Dùng công cụ kiểm tra hiện có; ghi chính xác những phần đã chạy và chưa chạy. Viết hướng dẫn startup, ID/vai trò, body mẫu và kết quả mong đợi.

### Điều kiện bàn giao

1. Schema/migration/seed và endpoint đồng bộ; Swagger phản ánh contract đang chạy.
2. Các luồng đã chọn đi hết từ FE qua API đến DB, có event/thông báo và trạng thái đúng.
3. Bộ dữ liệu, script chạy và hướng dẫn đủ để người khác tự demo.
4. Phần mô phỏng như phản hồi agent được ghi rõ; không báo đã tích hợp LLM hoặc hệ thống ngoài khi chưa thực hiện.

## 9. Thứ tự triển khai và ranh giới công việc

**Contract/schema → an ninh → quản trị/room/memory → seed bổ sung → FE/gateway → chạy kịch bản/bàn giao.**

Có thể nối các màn hình sử dụng endpoint V3 đã ổn định trước khi hoàn thành mọi nhóm còn thiếu. Không cần chuyển sang dữ liệu thật hoặc viết tool để hoàn thành demo HTTP với database faker.

File này là kế hoạch; chưa xác nhận các đầu việc còn thiếu đã được triển khai. Chưa ước lượng ngày công khi chưa chốt mapping màn hình và migration ở giai đoạn 1.
