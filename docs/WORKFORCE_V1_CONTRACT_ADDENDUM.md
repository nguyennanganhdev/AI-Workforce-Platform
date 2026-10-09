# Workforce v1 — phụ lục triển khai

Áp dụng cho `platform_VP/core` trên `dev_platform`, nối contract đối tác 1.3-draft. API Vinhomes cũ không tự chuyển sang Workforce. Bật bằng `VINHOMES_WORKFORCE_ENABLED=1` sau onboarding; Reception vẫn thuộc backend Vinhomes.

## Danh tính và vòng đời

Customer dùng `Authorization: ApiKey dp_<client_id>.<secret>`. Provider dùng credential riêng, thêm `X-Partner-Timestamp`, `X-Partner-Key-Id`, `X-Partner-Signature: v1=<hex-HMAC-SHA256>` trên POST. Nội dung ký là timestamp ASCII, dấu chấm và **bytes body thực tế**. Sai lệch thời gian tối đa 300 giây. Key được hash; secret ký/context được mã hóa bằng Fernet. Giữ ổn định `AWP_SECRET_KEY`, backup cùng database.

Binding gồm client, user, residence, route, external ticket và external conversation. Customer không chọn agent/session/member. Backend định tuyến supervisor; supervisor dùng TeamCreate/AgentCreate và profile chuyên môn được cấp. Workflow pin phiên bản profile, model/giá, route, integration, catalog tool khi khám phá lần đầu, tài liệu kiến thức. Route/integration đổi hoặc quyền cư trú thu hồi sẽ chặn thực thi tiếp.

Request có `accepted/running/completed/blocked`; workflow có `accepted/active/awaiting_user/awaiting_approval/waiting_external_event/awaiting_confirmation/needs_attention/closed`. Operation có vòng đời riêng. `confirmed` nghĩa là lệnh domain đã được xác nhận, **không** có nghĩa thi công xong; `offered` chưa phải nhân viên đã nhận. Đóng workflow không hủy công việc, không nghiệm thu hoặc đóng ticket Vinhomes.

POST request chờ tối đa 25 giây, trả 200 nếu xong lượt hoặc 202 nếu còn chạy; job đã ghi PostgreSQL không phụ thuộc HTTP connection. Retry phải giữ nguyên external request ID và payload. Cùng ID khác nội dung trả 409. Approval/close cũng dùng chung namespace command theo client.

Approval ràng buộc workflow, audience, arguments hash, quote reference, revision và expiry. Quyết định gửi đến `/partner/approvals/{id}/decision`; không lấy câu “đồng ý” trong chat làm consent. Close dùng revision hiện tại; khi còn công việc ngoài platform phải có `stop_tracking_only=true`, `reason=resident_requested_stop_tracking`.

## Asset capability `minio-images-v1`

Đây là mở rộng được người dùng duyệt cho ảnh, khác schema text-only ban đầu. Route phải bật `asset_capability`. Message vẫn `type=text`, thêm `asset_ids` (tối đa 8). Không nhận URL tùy ý.

| API dưới `/workforce/v1/partner` | Body / kết quả |
|---|---|
| `POST /assets/uploads` | management/user/ticket/conversation, MIME, size, SHA-256 → asset ID, status, POST upload URL/fields, expiry |
| `POST /assets/{id}/complete?external_user_id=...` | Xác minh bytes, SHA, MIME ảnh thực tế, giới hạn pixel → ready |
| `GET /assets/{id}?external_user_id=...` | Metadata đã kiểm quyền |
| `GET /assets/{id}/content?external_user_id=...` | Proxy bytes sau kiểm quyền, không cache công khai |

Chấp nhận JPEG/PNG/WebP, tối đa 10 MiB và 20 triệu pixel. Presigned POST hết hạn sau 15 phút, chỉ đúng staging key/MIME/size. Canonical object được ghi từ bytes đã kiểm chứng; attach chỉ đúng binding và một workflow. Model vision dùng bản JPEG tối đa 768×768 đã bỏ EXIF; provenance/checksum của bản gốc và bản dẫn xuất lưu trong DB. Model chưa khai báo vision sẽ chuyển needs_attention.

Bucket private. `AWP_MINIO_ENDPOINT` là endpoint server nội bộ; `AWP_MINIO_UPLOAD_ORIGIN` là origin backend đối tác truy cập được. Không đưa MinIO credentials/customer machine key vào browser. Ảnh đã attach được giữ lại; retention ảnh nghiệp vụ phải được chốt riêng khi onboarding, không suy từ TTL public event. Staging bỏ dở được dọn riêng; không xóa ảnh của workflow mở.

## MCP nghiệp vụ Vinhomes

Service bearer xác thực server MCP; context HMAC có hạn 120 giây ràng buộc user, BQL, workflow, ticket/generation, tool, arguments hash và client reference. Server đọc lại quyền và nghiệp vụ ở Vinhomes, không tin `is_admin` hoặc quyền do LLM gửi.

| Tool | Hiệu lực |
|---|---|
| `get_ticket` | Đọc ticket/plans/work orders, QC và phê duyệt sửa chữa/nghiệm thu của cư dân đúng binding; số tiền nằm trong request_detail do domain tính |
| `get_staff_availability` | Đọc ca, chuyên môn, tải nhân viên trong BQL |
| `propose_plan` | Gọi lệnh đề xuất phương án hiện có; giữ yêu cầu phê duyệt nghiệp vụ |
| `create_work_order` | Gọi lệnh tạo work order hiện có; confirmed không phải hoàn tất thi công |
| `offer_assignment` | Chào công việc cho nhân viên phù hợp; nhân viên vẫn nhận qua API Vinhomes |

Mỗi write phải có grant service actor/BQL/tool; thêm consent hợp lệ hoặc category trong allowlist tự động. Allowlist mặc định rỗng. Platform mặc định xin consent. Business write, MCP idempotency receipt và đăng ký job tracking nằm cùng transaction domain. Timeout/mất response sau dispatch → unknown/needs_attention; platform không gọi lại mù. Operator đối soát bằng bằng chứng qua API reconcile, có audit.

Provider dùng `job.progress/completed/failed/cancelled` theo event_map/schema/transition được onboarding. Outbox domain quan sát phiên bản business state và ghi event bền vững; inbox platform ghi receipt trước 202. Early event quarantine; version trùng/lùi không ghi lặp; xung đột/gap cần kiểm tra. Event đến sau close chỉ ghi nhận đối soát, không mở lại workflow hoặc gọi LLM. Hoàn tất work order không thay thế QC/nghiệm thu domain.

## Public views và quản trị

History/SSE có sequence/cursor theo conversation. SSE heartbeat 15 giây và kiểm quyền liên tục. Cursor hết hạn trả 410; backend lấy snapshot rồi dedupe theo public message ID. Snapshot giữ tối đa 500 message, báo `messages_truncated`; adapter không âm thầm bỏ phần lịch sử bị thiếu. Public event giữ 90 ngày sau close; provider dedupe terminal giữ 180 ngày. Workflow mở không bị dọn theo tuổi.

Console `/console` dùng tài khoản người vận hành, cookie HttpOnly/SameSite và CSRF. Admin quản profile, route, credential, MCP, knowledge; operator đối soát; viewer chỉ đọc. Machine admin key không nằm trong JavaScript. Credential chỉ trả lúc tạo/xoay; thu hồi áp dụng tiếp cho model/tool/public read.

Kiến thức hiện dùng tìm kiếm từ khóa trên tài liệu đã duyệt, phiên bản bất biến và ACL giao giữa profile với route; chưa phải semantic vector RAG. Memory là ghi chú riêng theo workflow/profile, có giới hạn; không được xem là bằng chứng xác minh. Dữ kiện chung nằm trong case file có provenance. Guard số/ngày/mã và Jev tùy chọn giúp kiểm soát; không bảo đảm model thật không bao giờ suy luận sai.
