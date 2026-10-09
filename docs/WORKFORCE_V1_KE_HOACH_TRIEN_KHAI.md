# Workforce v1 trên dev_platform: phạm vi và thứ tự triển khai

Cập nhật: 10/10/2026. Đây là kế hoạch triển khai, chưa phải báo cáo tính năng đã hoàn thành.

## 1. Quyết định và trạng thái

- Người dùng cho phép đưa source hiện tại vào `dev_platform`. Đã merge các commit của `feat/platform-core` (`7f3e56e`) vào `dev_platform`, merge commit `5edc7bf`. Không pull/push remote; không đưa thay đổi chưa commit của worktree nguồn vào merge.
- Lõi để phát triển Workforce v1 là `platform_VP/core`, gói `awp`. Backend `platform_VP/services/platform-api/vp` và giao diện/deploy cũ vẫn tồn tại sau merge; chưa xóa hay đổi dịch vụ đang chạy. Cần xác định lại endpoint/service mà console sẽ sử dụng trước khi triển khai.
- Chuẩn mục tiêu là `CONTRACT_TICH_HOP_DOI_TAC.md` bản `1.3-draft`: đối tác gọi `/workforce/v1`, platform gọi công cụ nghiệp vụ qua MCP; không outbound webhook trong luồng v1 mới.
- Người dùng chọn **MinIO quản lý ảnh**. Bổ sung asset contract và năng lực ảnh trong đợt nối Reception; chưa có API asset hay MinIO mới được triển khai trong lượt chốt này.
- Quyền tự động giao một số loại việc **đang chờ xác nhận**: ý trả lời của người dùng còn có thể là câu hỏi về khả năng. Chưa có danh sách loại việc/điều kiện được phép; không coi ví dụ “gọi thợ” trong contract là quyền tự điều động.
- Không sửa trực tiếp vendor `platform_VP/agentscope/src`. Không chạy migration hoặc đổi dữ liệu Vinhomes chỉ vì merge source.

## 2. Ranh giới tích hợp

Reception là agent chat bên Vinhomes. Backend Vinhomes xác thực cư dân và gọi Customer API của platform; giữ mapping riêng cho từng external ticket/hộp chat. Supervisor được chọn từ cấu hình route/workspace, tự tổ chức agent chuyên môn.

Platform gọi MCP nghiệp vụ đã onboarding để tra cứu hoặc thực hiện thao tác được cấp. Backend Vinhomes quản lý nhân viên, quyền, phê duyệt và sự thật công việc. Với operation pending có tracking, backend nghiệp vụ gửi Provider Event; hoặc platform dùng MCP status-query theo capability đã thống nhất. Backend khách hàng nhận response/SSE/history và đưa về Reception/hộp chat tương ứng.

Tách ba vòng đời: một command/request; workflow theo dõi nhiều lượt; operation ở hệ thống nghiệp vụ. Hoàn thành lượt agent không đóng workflow. Close workflow không hủy công việc, không tự nghiệm thu hay đóng ticket Vinhomes. Yêu cầu hủy đi qua công cụ nghiệp vụ được cấp quyền; không ánh xạ thẳng `cancel_requested` thành close.

## 3. Ảnh qua MinIO: thiết kế đề xuất

MinIO lưu bytes; PostgreSQL lưu metadata và quyền. Object không public và object key không phải credential. Platform không tải URL tùy ý từ message. Backend Vinhomes giữ machine key; app cư dân không giữ key platform/MinIO.

Luồng dự kiến:

1. Backend Vinhomes xin upload cho user/ticket/conversation đã xác thực; platform kiểm grant và route, tạo asset/upload record.
2. Cấp upload có thời hạn cho object được chỉ định. Nếu dùng presigned POST, áp điều kiện key, dung lượng và loại nội dung; các điều kiện này vẫn được kiểm tra lại khi finalize.
3. Upload vào MinIO; backend gọi hoàn tất. Platform xác minh object, dung lượng, checksum và nội dung thực tế; ảnh chỉ được attach khi đạt trạng thái `ready`.
4. `start_workflow` hoặc `workflow_reply` tham chiếu `asset_id`; platform kiểm asset thuộc đúng audience/ticket/conversation và bind vào workflow. Không chỉ kiểm cùng tenant.
5. Agent được cấp ảnh/thumbnail qua tầng kiểm quyền. Chỉ đưa ảnh vào model có vision khi cần; caption/OCR suy luận không thay thế ảnh gốc và không trở thành dữ kiện đã xác minh.
6. Phục vụ ảnh bằng URL ngắn hạn hoặc proxy có kiểm quyền. Chọn proxy nếu cần thu hồi tức thời; URL đã cấp còn hiệu lực đến hạn không được coi là đã thu hồi ngay.
7. Retention riêng cho ảnh, bản dẫn xuất và upload bỏ dở; không xóa asset còn được workflow mở hoặc evidence/checkpoint tham chiếu. Thời hạn lưu ảnh cần quy định trong onboarding, không suy từ hạn lưu public event.

Metadata tối thiểu: asset/upload ID, partner client, audience, route snapshot, external ticket/conversation, workflow nullable trước attach, object key/version, MIME thực tế, kích thước, checksum, trạng thái, thời điểm và quan hệ bản dẫn xuất. Object keys do server sinh, không dùng trực tiếp tên file người dùng.

Nhóm API asset cần đặc tả trước khi code: tạo upload, finalize upload, đọc metadata và lấy nội dung có quyền. Các tên endpoint và schema message đa phần còn là đề xuất; không âm thầm đưa attachment vào schema text-only của contract 1.3. Cần publish capability/addendum tương ứng.

Nguồn kỹ thuật: [MinIO Python SDK API](https://docs.min.io/aistor/developers/sdk/python/api/) có các primitive presigned GET/PUT và POST policy. Việc dùng các primitive đó không tự cung cấp quyền theo workflow; lớp authorization/metadata ở trên thuộc platform.

## 4. Tự động giao việc: chính sách cần chốt

Cần xác nhận người dùng muốn bật tự động giao hay muốn giải thích trước. Nếu bật, danh sách loại việc và điều kiện phải được duyệt cụ thể. Quy tắc được cấu hình/version ở domain, không để LLM suy ra quyền từ nội dung yêu cầu.

Đề xuất cơ chế: supervisor đề xuất nhiệm vụ; công cụ domain kiểm loại việc được cấp, chi phí/phê duyệt cần có, chuyên môn/ca/khả năng nhận việc và phạm vi BQL trong cùng thao tác. Domain tạo/chào công việc idempotent và trả trạng thái thực tế. Platform chỉ nói “đã giao/đã nhận” theo kết quả tương ứng, không đồng nhất `offered` với `accepted`.

Chưa được đưa tool tự điều động vào allowlist trước khi chốt quyền mới. Các phần API, durable runtime, assets và agent isolation có thể triển khai độc lập với quyết định này sau khi kế hoạch được chốt.

## 5. Thứ tự triển khai và nghiệm thu

| Bước | Công việc | Điều kiện nghiệm thu |
|---|---|---|
| P0 | Freeze contract/OpenAPI và phụ lục MCP, assets, quyền; kiểm các điểm mở rộng AgentScope | State/action, approval revision, residence nhiều cư dân, response envelope, asset capability được mô tả rõ |
| P1 | Client/key/grant, route/residence/binding; namespace registry và memory/knowledge ACL; migration PostgreSQL | Không truy cập chéo tenant/BQL/cư dân; workflow cũ không chuyển theo remap |
| P2 | Durable job/checkpoint/lease, command idempotency; start/reply/GET; deadline 200/202 | Retry/mất response/restart không tạo workflow hoặc side effect mới; không hủy job theo HTTP disconnect |
| P3 | Supervisor/team/context, profile/policy/model/tool pin, budget reservation | Agent vào sau đọc được bàn giao; câu hỏi chưa giải quyết không mất; worker đồng thời không vượt khoản đã cấp |
| P4 | Asset service + MinIO và MCP execution/approval/operation intent | Upload/finalize/attach đúng quyền; ảnh sai scope bị chặn; timeout tool chuyển đối soát thay vì gọi lặp |
| P5 | Public events/history/snapshot/SSE; Provider Event signature/inbox/receipt/order; explicit close | Reconnect/dedupe/cursor expiry, event sớm/trễ/sai thứ tự, close-vs-reply/event đúng contract |
| P6 | Vinhomes Workforce client, MCP nghiệp vụ, provider outbox; Reception/UI, console quản trị mới | Luồng cư dân/ảnh → Reception → supervisor → nghiệp vụ → tiến độ → xác nhận chạy bằng hệ thống thực trong sandbox |
| P7 | Fault/load/evaluation và vận hành | 20 workflow đồng thời trên PostgreSQL, bus nhiều process, restart an toàn; đo chất lượng/chi phí model thật riêng |

PostgreSQL giữ nguồn trạng thái/replay. Redis chỉ đánh thức worker/stream. Khi chờ người dùng hoặc operation, lưu checkpoint và giải phóng lượt model/transaction. Không ép mọi tool ghi trả pending: tool confirmed đồng bộ dùng kết quả thật; chỉ operation pending có tracking mới vào `waiting_external_event`.

Không hạ durability sau demo theo một ngày chưa được người dùng xác nhận. Kiểm thử model giả chứng minh orchestration/contract; không được ghi thành nghiệm thu Vinhomes/model thật.

## 6. Trạng thái kiểm tra trong lượt merge

- Merge thành công không conflict; `platform_VP/core` khớp commit nguồn; vendor AgentScope không thay đổi so với trước merge.
- Chưa chạy baseline tests: interpreter của backend `vp` cũ không import được AgentScope app vì thiếu `apscheduler`. Chưa cài thêm dependency vào môi trường cũ; cần môi trường riêng cho `awp` trước khi chạy tests.
- Chưa push, chưa triển khai MinIO/Workforce API, chưa bật tool tự động giao việc.
