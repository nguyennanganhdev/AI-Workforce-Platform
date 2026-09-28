# Review độ đầy đủ database

Phạm vi: database và ERD của tài liệu `docx/01–04`, bổ sung luồng lễ tân → điều phối → group chat → kỹ thuật → cập nhật cư dân. Mốc hiện tại: **190 bảng / 40 module**, gồm 38 bảng shell hiện có và 152 bảng workforce. Đủ mô hình lưu trữ cho phạm vi này không có nghĩa mọi nghiệp vụ của một hệ thống quản lý đô thị đã được triển khai.

## Kết quả rà soát và phần đã bổ sung

Baseline 0046/0047 có 127 bảng mới, đầy đủ inventory domain trong tài liệu nhưng chưa có persistence rõ ràng cho bàn giao giữa agent, lịch sử group chat, khôi phục session và vòng phản hồi kỹ thuật–cư dân. Migration 0048 bổ sung 25 bảng, 0049 bổ sung trigger/exclusion/FORCE RLS, 0050 thêm index cho polling/retry/deadline.

| Thiếu trước rà soát | Bảng đã bổ sung | DB bảo vệ | Service còn phải làm |
|---|---|---|---|
| Hội thoại trước/sau khi tạo ticket | conversation, conversation_subject, conversation_message | Owner của tin USER, thứ tự, reply cùng conversation, immutable history | ACL người đọc, map kênh ngoài, sanitize nội dung |
| Handoff dễ mất khi process restart | handoff, event_receipt | Request key unique, identity/hash pinned, trạng thái chuyển, đích cùng subject, hết hạn không nhận | Atomic inbox + session creation + ack; retry/backoff/dead-letter |
| Không biết agent nào tham gia group chat | session_participant, runtime_message | Version/session FK, một coordinator, sender active, run/version khớp, append order | Chọn agent, thu hẹp capability, model/tool execution |
| Không có recovery state và waiting | session_control, runtime_checkpoint, session_wait | Parent không cycle, lease takeover tăng fence, checkpoint hiện hành/cursor/provider đúng | Lease renewal, scheduler, giới hạn lượt, xử lý timeout, fence mọi external write |
| Chưa phân biệt agent kỹ thuật và người thợ | team, team_member, staff_skill, staff_shift | Loại membership, hiệu lực, shift không trùng người trong tenant | Quyền phân công, matching kỹ năng/khả dụng, nghỉ phép |
| Không có lịch sử giao việc/lịch hẹn | work_assignment, work_appointment | Đúng WO/task/incident/team; một giao việc active; appointment không chồng, chuyển lịch giữ lịch sử | Nhận/từ chối, kiểm tra ca/địa bàn, hẹn với cư dân |
| Tài sản ảnh hưởng chỉ là text | asset, incident_asset | Asset code scoped project, apartment thuộc đúng tower, incident/asset cùng project | Bảo trì định kỳ và vòng đời tài sản nếu mở rộng |
| Tiến độ/ETA không có nguồn kiểm chứng | work_progress | Event thuộc WO/incident, actor và thời điểm khớp; append-only | Command cập nhật WO + event + progress + outbox atomic |
| Lễ tân đọc internal group chat dễ lộ dữ liệu | report_update | Đúng reporter/report/incident, source event/time, ETA khớp progress, không lùi version/time | Lọc nội dung, scope theo user, xử lý lag, phát projection |
| Chưa theo dõi từng lần gửi | notification_delivery | Recipient/event khớp update, unique provider receipt, attempt key | Gửi thật, xác minh callback, retry, tổng hợp delivery_status |
| Callback khó chống replay | provider_event | Provider/event unique, hash và identity pinned, verified timestamp required | Kiểm chữ ký và lưu qua adapter có quyền; DB không kiểm chứng chữ ký |
| SLA chỉ có một deadline | sla_policy, incident_sla, escalation | Policy published/applicable, deadline tính từ policy ELAPSED và cố định; mirror deadline vào Incident | Chọn policy, job phát hiện quá hạn, escalation, thông báo người chịu trách nhiệm |

Tên bảng trong bảng trên được rút gọn theo module. Tên SQL đầy đủ và nhiệm vụ **từng bảng**, kể cả 127 bảng baseline và 38 bảng shell, nằm ở [TABLE_CATALOG](physical/TABLE_CATALOG.md). Mỗi liên kết mở danh sách đầy đủ cột, type, nullable, default, PK, FK, unique, index và CHECK. Trigger/exclusion không được Drizzle snapshot; phải giữ cả migration SQL và tài liệu này.

## Tính nhất quán và giới hạn cần hiểu đúng

- `platform_*` sở hữu cách agent thực thi; `vh_*` sở hữu việc gì thực sự xảy ra. Session kết thúc không tự đóng Incident. Xem [flow](SYSTEM_FLOW.md).
- Nhận trùng có thể bị unique key từ chối; service phải tra receipt và trả kết quả cũ, so sánh request hash. Unique constraint không thay consumer implementation.
- `vh_report_update` là projection theo report, có thể chậm hơn Incident. Read service phải kiểm tra version/thời điểm, trả rõ mốc cập nhật, không suy ra ETA từ lời nói của agent. Event sai thứ tự không được ghi đè trạng thái mới.
- Trạng thái công khai, trạng thái WorkOrder, Incident, notification và session là các state machine khác nhau. Domain service phải chuyển chúng atomic theo shared contracts; SQL không tự điều phối toàn bộ luồng.
- FORCE RLS bao phủ 151 bảng theo tenant; global `platform_domain_package` và 38 bảng shell không dùng policy này. Quyền cư dân trong cùng tenant phải kiểm tra trong service. Actor ID polymorphic và soft domain refs phải xác minh tại boundary.
- Timestamp/version/hash/storage ref hỗ trợ truy vết; hash do service tính, dữ liệu object store và quyền tải file phải được kiểm tra riêng. JSON payload còn cần schema validation tại boundary.
- Runtime message không tự fence mọi lời gọi tool. Runtime worker phải kiểm tra lease và command idempotency trước side effect; fencing checkpoint chỉ bảo vệ checkpoint.
- SLA hiện dùng phút liên tục; chưa có working-day calendar, pause/resume SLA hoặc nhiều cấp chính sách phức tạp. Không dùng `calendar_ref` để giả vờ hỗ trợ business hours.
- Chưa có module kho/vật tư/mua sắm/nhà thầu–hợp đồng/khấu hao, HR đầy đủ, hoàn tiền/đối soát kế toán đầy đủ. Các bảng hiện tại không thay ERP/CMMS. Đây là phần mở rộng cần chốt nghiệp vụ nếu dự án bao gồm chúng.

## Tiêu chí nghiệm thu đợt database

1. Mọi bảng schema xuất hiện trong catalog và snapshot; mỗi bảng có mô tả nhiệm vụ.
2. Migrate database rỗng và nâng cấp từ 0045, giữ user ID hiện có; chạy lần hai an toàn.
3. Database thật từ chối liên kết sai tenant/project/parent, lịch trùng, history bị sửa, checkpoint cũ và resident update sai người/ETA.
4. Generator không thấy schema drift; typecheck, architecture và ERD check đạt.
5. Không sửa runtime/API/UI người dùng đang triển khai; chưa migrate database ứng dụng thật.

Kết quả chạy cụ thể được ghi tại [COVERAGE](COVERAGE.md). Benchmark tải lớn, vận hành backup/restore, retention, partitioning và end-to-end của worker/API thuộc đợt tích hợp, không được suy ra từ các integration test database.
