# Bàn giao DEV-3 — Reception schema V2

Theo `docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md` ngày 01/10/2026.
Chỉ sửa `src/adapters/{backend,reception,tools}/**` và test tương ứng.
Reception ↔ Supervisor chỉ dùng `schema_version: "2.0"`, `message_type`, `message`.
Không nhận V1, không đổi tên envelope cũ, không tự chuyển checkpoint/quyết định cũ.

## Interface cho DEV-1/DEV-5

```python
from adapters.backend.client import BackendClient
from adapters.backend.http_transport import UrllibTransport
from adapters.reception.reception_gateway import ReceptionGateway

backend = BackendClient(
    base_url=core_origin,
    routes=operation_paths,
    transport=UrllibTransport(),
    headers=service_header_provider,
    validator=canonical_validator,
)
gateway = ReceptionGateway(backend, authentication=reception_authentication_provider)
# Inject gateway vào SupervisorService(..., reception=gateway).
verified = await gateway.verify(reception_message, transport_authentication)
receipt = await gateway.send(supervisor_message, verified.context)
```

- `verify` nhận `ReceptionMessage` hoặc mapping V2 đầy đủ, trả đúng
  `supervisor.models.VerifiedReception(context, message, supervisor_run_id)`.
- `send` nhận `SupervisorMessage` hoặc mapping V2 và `groupchat.models.Context`
  hoặc mapping, trả `{message_id, status: accepted | completed}` cho action journal.
  `status` ở đây là ACK API nội bộ, không phải field trong output gửi Reception.
- Guard dùng lại model V2 của DEV-1/DEV-2, kiểm strict type và JSON hữu hạn.
  `facts[].value = null` được giữ nguyên. Bộ canonical validator vẫn bắt buộc;
  adapter không tạo/sửa JSON Schema của DEV-5 hoặc Team Chiến.
- Gateway không xây ID, số điện thoại, địa chỉ hoặc mức ưu tiên từ model.
  Backend phải đối chiếu **toàn bộ snapshot** với dữ liệu đã xác minh; gateway chỉ
  trả snapshot khi backend xác nhận. Backend trả snapshot đổi nội dung/phiên bản
  thay cho bản gửi vào sẽ bị từ chối.

Các wrapper chỉ nhận enum V2: `receive_ticket`, `receive_message`,
`receive_plan_response`, `receive_cancel`; output: `ask_question`, `send_plan`,
`send_update`, `send_completion`. Wrapper input cần `authentication=...`, output
cần `context=...`. Không có `receive_completion_response`.

## API kết nối backend

Các tên dưới đây là operation **nội bộ adapter**, chưa phải endpoint đã triển khai.
Team Chiến cấp API path thật; DEV-5 cấu hình `routes`. Thiếu route sẽ fail closed.
Đây là shape cần chốt cho verification/delivery API, không thêm field vào hai
schema Reception và không xác nhận backend hiện có đã hỗ trợ shape này.

| Operation | POST body | Response thành công |
|---|---|---|
| `reception.verify` | Input V2 phẳng, giữ nguyên | `{message_id, status, data: {message, context, supervisor_run_id, room_command?}}` |
| `reception.send` | `{message: output_V2, context: verified_routing_context}` | `{message_id, status, data: {}}` |

Backend chuyển **chỉ `message` bên trong body delivery** tới Reception; `context`
là sidecar phục vụ API nội bộ. Các mã định tuyến được backend resolve độc lập;
không gán `request_id`, `trace_id`, `binding_id` cũ thành mã V2.
`supervisor_run_id` phải do backend resolve, không tự coi là `context.run_id`.

Header V2 gồm `Idempotency-Key = message_id`, `X-Message-Id`, `X-Correlation-Id`.
Dedup backend luôn có tenant, không chỉ dựa vào header. Không sinh ID khi gửi lại.
HTTP deadline, giới hạn response, chặn redirect, lỗi không lộ body và không retry
ngầm dùng chung Core API client. Mất ACK/timeout trả `outcome_unknown=True` để
DEV-1/DEV-4 reconcile; không coi thiếu ACK là chưa có tác dụng.

`ReceptionAuthentication.headers(authentication)` là port bắt buộc cho input:
xác minh nguồn transport và tạo header delegation/source proof backend hiểu được.
Không lấy identity từ payload; không dùng biến mutable "current user" chung.
Header này không được ghi đè service credential, content type hoặc các mã đối chiếu.
Tên/định dạng proof header do Team Chiến và DEV-5 cấu hình, adapter không tự đoán.
Không có default xác thực giả hoặc permissive.

`ContractValidator.validate(kind, value)` cần hỗ trợ:

| Kind | Dữ liệu kiểm tra |
|---|---|
| `reception_input` | Một schema input V2 chuẩn |
| `reception_output` | Một schema output V2 chuẩn |
| `reception_delivery` | Wrapper routing nội bộ backend |
| `reception_response` | ACK/error API với `message_id` |
| `reception_verified` | Snapshot/context/run và sidecar đã xác minh |
| `request`, `response`, `event` | Envelope API/sự kiện backend hiện hành |

Error response dùng `{message_id, status: "error", error: {code, retryable}}`.
HTTP 403/409 hoặc business error không làm gateway trả một quyết định hợp lệ.
Backend phải lưu kết quả verification để retry trả lại cùng accepted resolution;
dedup không được làm mất input khi Coordination chưa kịp checkpoint.

## Điều kiện backend phải thực thi nguyên tử

1. Xác minh nguồn cư dân qua `source_message_id`, tenant, ticket, generation,
   recipient và phiên bản **đã hiển thị**. Không nâng câu trả lời cũ lên bản mới.
2. Chặn quyết định sai bước; `information_provided` không tự duyệt phương án.
   Backend lưu nguyên câu hỏi/phương án và cấp ticket version mới khi thay đổi;
   tối đa một yêu cầu cư dân đang chờ trong mỗi ticket/generation.
3. Dedup bền vững `(tenant_id, message_id)` + fingerprint; cùng ID khác nội dung
   báo conflict. Quyết định cùng bước gửi bằng ID mới không tạo thêm công việc.
4. Kiểm lại quyền/version khi áp dụng output; persist yêu cầu đang chờ và outbox
   cùng transaction trước ACK. Không gửi model output trực tiếp ra UI.
5. `plan_approval_requested` cần quản lý duyệt đúng phiên bản; miễn cư dân duyệt
   chỉ do backend quyết định. Giữ nguyên thời gian, chi phí và điều kiện đã lưu.
6. `completed` cần toàn bộ việc xong và QC/quyền công bố, có `result.outcome =
   work_completed`. `cancelled` cần backend xác nhận hủy. Đây không phải đóng ticket.
   `failed.message` là nội dung cho cư dân; `error.message` là chi tiết kỹ thuật,
   backend/Reception không tự đưa nguyên lỗi đó ra màn hình.

Adapter không tự giữ cache dedup/policy trong RAM; các điều kiện trên cần API và
storage backend thật. Test dùng fake để kiểm đường gọi và xử lý khi backend từ chối.

## Backend nghiệp vụ, tiếp tục xử lý và @agent

`ApprovalClient` chỉ gửi/nhận **duyệt quản lý**. `ToolClient` giữ giao việc nhân viên,
nhận/từ chối, ảnh trước/sau và báo hoàn thành. `EventIngress` chỉ nhận
`approval.responded` (management), `assignment.offered/responded`, `work.completed`;
vẫn xác minh event và enqueue qua durable inbox port của DEV-4.

Theo quy tắc 5 mục 3 của tài liệu, envelope API/sự kiện backend và Command phòng
hiện hành vẫn dùng mã version riêng. Đây không phải Reception schema V1 được giữ
lại. Các loại Reception cũ và `resident_plan` V1 bị guard từ chối; không forward
`completion.requested/responded`. `ApprovalClient.request_completion` chỉ là
entrypoint báo `reception_protocol_not_supported` để bridge cũ của DEV-1 vẫn bind
được; hàm không gửi request. DEV-1 có thể xóa entry này trong phạm vi của mình.

Xác nhận kết quả, chưa hài lòng, đóng/mở ticket thuộc backend. Khi cần xử lý tiếp,
backend bàn giao input V2 đầy đủ qua gateway; mở lại ticket đã đóng dùng generation
mới. Gateway không migrate checkpoint V1. DEV-4/DEV-5 phải giải quyết checkpoint
cũ có kiểm soát trước rollout V2; không expose lại giao thức V1 để chạy tiếp.

`gateway.resolve(message, authentication)` trả `ReceptionResolution(verified,
room_command?)`. Sidecar `room_command` do backend cấp là Command DEV-2 hiện có,
payload `mention_agent`, giữ nguyên request/trace/idempotency/room/version/agent ID.
Adapter kiểm command đúng context và instruction; không parse `@tên` để cấp quyền,
không thêm `mentioned_agent_id` vào input V2. Chỉ information input có nguồn cư dân
hợp lệ được mang command này. `verify` báo `mention_requires_groupchat` nếu có
sidecar, tránh bỏ mất định tuyến khi caller chỉ đưa input vào Supervisor.
DEV-5 dùng `resolve` cho nhánh mention, đưa command vào durable worker của DEV-4
rồi DEV-2 kiểm lại membership, context hiện hành và quyền trước khi chạy.

## Kiểm thử và phần còn cần ghép

Python 3.11+, Pydantic V2 đã dùng trong DEV-1/DEV-2; test ghép dùng pytest fixture
harness hiện có. Không sửa dependency/lockfile chung; DEV-5 quản lý các dependency.

```powershell
python -B agent-coordination/tests/adapters/reception/run_tests.py
```

Runner riêng tránh test package che source namespace. Test bao phủ V2 hai chiều,
source/snapshot/time/enum, null fact, quyền, bản cũ/sai bước, một pending request,
dedup quyết định/bản tin, nhiều tenant, reply không tự nâng version, mention sidecar,
hủy, completed/QC, backend yêu cầu xử lý tiếp, timeout/lost ACK và transport HTTP
loopback. Test ghép dùng Supervisor và RoomService thật, fake model/backend/storage.
Harness DEV-1 được import lại với catalog sự kiện backend mới; không sửa file owner.

Bộ test V2 gốc `tests/supervisor/test_reception_v2.py` hiện chưa chạy được với
catalog mới: fixture `tests/supervisor/conftest.py` vẫn đăng ký `ticket.submitted`,
`resident.message`, `completion.responded`, khiến constructor trả
`unsupported_event_mapping`. DEV-1/DEV-5 cần bỏ các mapping Reception V1 này và
cho phản hồi cư dân đi qua gateway V2; DEV-3 không sửa fixture/config của owner khác.

Để chạy production còn cần: paths/semantics và delegated auth từ Team Chiến;
schema chuẩn/canonical validator, mount và Authority authorize/reconcile kênh
`reception` từ DEV-5; durable inbox/checkpoint/fencing từ DEV-4; rollout với Reception
team Hoàng. Test chưa chứng minh API staging, UI, DB transaction hoặc restart thật.
