# Kế hoạch và triển khai API schema V2 Reception ↔ Supervisor

- Ngày: 2026-10-01
- Contract chuẩn: `schema_v2` trong `SCHEMA_RECEPTION_SUPERVISOR_V1.md`; schema_v1 chỉ để đối chiếu.
- Phạm vi: API FastAPI và persistence PostgreSQL để trao đổi dữ liệu. Không thêm AI/LLM, prompt, tool runtime hoặc xử lý thay agent.

## Hiện trạng đã rà soát

- API đã có tạo ticket/draft, lấy context cư dân, xem tiến độ, gửi quyết định phương án và cập nhật trạng thái.
- Luồng phương án hiện tách duyệt BQL và cư dân; các API đó chưa dùng envelope message V2.
- Chưa có Pydantic/OpenAPI model cho `ReceptionToSupervisorMessage` và `SupervisorToReceptionResult`, cũng chưa có inbox/outbox V2 bền vững.
- Cơ chế xác thực hiện dùng danh tính người dùng đã xác minh qua Hono hoặc actor demo và phân quyền theo tenant/resource trong FastAPI.

## Luồng dự kiến

1. Reception gọi API tạo message V2. Backend lấy tenant/người gọi từ session, kiểm tra người cư dân có quyền với ticket; không tin ID người/tenant do body tự khai.
2. Backend so khớp ticket, generation, version, workspace và team với PostgreSQL. Ticket đã tồn tại trước khi `ticket_submitted`; endpoint handoff không tạo ticket lần nữa.
3. Backend lưu envelope nguyên bản theo `message_id`, chống gửi trùng và để Supervisor đọc qua inbox API. Cùng ID/cùng payload trả lại kết quả cũ; cùng ID/khác payload trả conflict.
4. Supervisor đọc inbox trong quyền BQL/nhân viên của ticket và gửi kết quả V2. Backend chỉ ghi result sau khi kiểm tra loại message, request cư dân đang chờ và trạng thái nghiệp vụ liên quan.
5. Reception đọc result đã lưu trong phạm vi cư dân sở hữu ticket. API trả dữ liệu; caller/agent tự diễn giải hội thoại và chọn bước tiếp.

## Endpoint đề xuất

- `POST /api/domains/vinhomes/resident/reception-supervisor/messages` — nhận input Reception V2; kiểm tra/persist, áp dụng quyết định cư dân qua quy tắc backend hiện có khi message là duyệt/từ chối/yêu cầu sửa phương án.
- `GET /api/domains/vinhomes/operations/resident-cases/reception-supervisor/teams/{team_id}/inbox` — trả các message V2 chưa được Supervisor xử lý cho team mà actor có quyền.
- `POST /api/domains/vinhomes/operations/resident-cases/reception-supervisor/results` — nhận và ghi output Supervisor V2; không tự thực thi agent.
- `GET /api/domains/vinhomes/resident/reception-supervisor/tickets/{ticket_id}/results` — lấy result mới nhất của đúng ticket/generation cho cư dân sở hữu.

## Các kiểm tra bắt buộc

- Validate đúng enum, trường và schema version `2.0` ở boundary.
- Đối chiếu `tenant_id`, `workspace_id`, `team_id`, `ticket_id`, `ticket_code`, `ticket_generation` và `ticket_version` với dữ liệu server; generation lấy từ ticket hiện tại, version so sánh đúng snapshot.
- Kiểm tra cư dân qua session và quyền sở hữu ticket; kiểm tra BQL/Supervisor qua grants và workspace/team/ticket liên quan.
- Tối đa một yêu cầu đang chờ cư dân cho mỗi ticket generation: câu hỏi bổ sung hoặc duyệt phương án. Chỉ nhận đúng `message_type` tương ứng bước đang chờ.
- Idempotency toàn tenant theo `message_id`; cùng ID nhưng payload khác conflict. Quyết định lặp bằng ID mới không được áp dụng lần hai.
- `plan_approved`/`plan_rejected`/`plan_change_requested` chỉ xử lý plan đang `resident_pending`; `completed` chỉ được phát khi điều kiện hoàn tất/nghiệm thu backend đạt; `cancelled` chỉ xác nhận khi ticket đã được backend hủy.
- `cancel_requested` chỉ ghi nhận yêu cầu; không tự hủy ticket. `error.message` không được tự động chuyển thành câu trả lời hiển thị cho cư dân.
- Audit metadata không chứa nội dung tin nhắn, số điện thoại, ảnh hoặc payload PII.

## Các thay đổi sẽ thực hiện

1. Thêm DTO Pydantic/OpenAPI khớp chính xác schema_v2.
2. Thêm migration PostgreSQL nhỏ cho message exchange/idempotency/pending-request state, tenant RLS và runtime grants; cập nhật schema Drizzle.
3. Thêm API inbox/result trong router resident/operations hiện có và cập nhật Hono proxy allowlist nếu cần.
4. Tái sử dụng auth, scope, resident plan decision, ticket verification và audit hiện có; không tạo cơ chế AI hoặc quyền mới.
5. Cập nhật tài liệu API và ghi một execution log trong `/changes`.
6. Kiểm tra static/OpenAPI/migration; không chạy business scenario nếu môi trường không phải database demo cô lập.

## Giả định ánh xạ

- `ticket_generation` lấy từ `tickets.reopen_count`; `ticket_version` chuyển qua chuỗi V2 nhưng phải khớp version số nguyên trong database.
- `location_scope_id` lấy từ scope trong coverage của ticket, không lấy làm quyền truy cập độc lập.
- `plan_id` không có trong V2: backend dùng plan duy nhất ở trạng thái `resident_pending` của ticket/generation; nếu không có hoặc có hơn một thì conflict.
- Supervisor API được gọi qua gateway với danh tính management/staff đã xác minh; Reception API dùng session cư dân. Không có client-supplied actor/service role.

## Tiêu chí hoàn thành

- OpenAPI công bố đúng request/response V2 và các route inbox/result.
- Ticket/generation/scope/version, pending request, idempotency và các trạng thái plan/cancel/complete được kiểm tra ở backend.
- API chỉ validate, persist và trả facts/result; không gọi hoặc giả lập Supervisor/Reception runtime.
- Các phần chưa kiểm tra bằng scenario nghiệp vụ được ghi rõ trong execution log.

## Kết quả thực thi ngày 01/10/2026

Đã triển khai bốn endpoint:

- `POST /api/domains/vinhomes/resident/reception-supervisor/messages`
- `GET /api/domains/vinhomes/operations/resident-cases/reception-supervisor/teams/{team_id}/inbox`
- `POST /api/domains/vinhomes/operations/resident-cases/reception-supervisor/results`
- `GET /api/domains/vinhomes/resident/reception-supervisor/tickets/{ticket_id}/results`

Các request dùng Pydantic model chặt theo schema_v2, từ chối thuộc tính ngoài schema, kiểm tra thời gian có múi giờ và xác minh snapshot ticket với PostgreSQL. Backend lấy danh tính từ session Hono, kiểm tra chủ ticket hoặc quyền staff/management trên ticket và workspace; body không cấp quyền bằng `tenant_id`, `resident_id` hay `team_id`.

Message được lưu bất biến theo tenant, `message_id` và payload hash. Gửi lại cùng ID/nội dung trả lại response đã lưu; cùng ID với nội dung khác trả conflict. Một bảng pending có khóa duy nhất cho ticket/generation giữ trạng thái yêu cầu bổ sung hoặc duyệt plan. `correlation_id` chỉ được lưu để truy vết; việc chấp nhận câu trả lời dựa trên pending type, phiên bản hiện hành và message cư dân đã xác thực.

`plan_approved` và `plan_rejected` gọi lại logic quyết định cư dân hiện có; `plan_change_requested` chuyển plan cũ sang `revision_requested` để API tạo plan mới có thể tiếp tục. Migration mở rộng constraint trạng thái plan cho giá trị này. `cancel_requested` chỉ được ghi nhận; `cancelled` chỉ được chấp nhận khi ticket trong database đã bị hủy. `completed` chỉ được chấp nhận khi ticket đã `resolved`/`closed`, mọi work order bắt buộc đã hoàn thành và các evidence ID gửi kèm thuộc ticket.

Migration `0007_reception_supervisor_v2.sql`, tenant RLS, quyền runtime, kiểm tra readiness và schema Drizzle đã được cập nhật. Tạo team hiện lưu `ticket_generation` từ `tickets.reopen_count`, đồng thời định danh idempotency của team bao gồm generation để mở lại ticket có thể tạo phiên team mới.

Xác nhận tĩnh: Python AST parse thành công; import ứng dụng và sinh OpenAPI thành công, OpenAPI có đủ bốn route; TypeScript typecheck thành công. Không chạy test suite hoặc scenario trên database. Migration chưa được áp dụng vì Docker daemon từ chối kết nối qua named pipe, nên các luồng ghi/đọc chưa được chạy trên database trong phiên này.
