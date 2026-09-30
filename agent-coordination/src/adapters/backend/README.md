# Bàn giao DEV-3 — adapter Coordination

Triển khai theo `docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md` ngày 30/09/2026.
Chỉ chứa code dưới `adapters/backend`, `adapters/reception`, `adapters/tools` và
test tương ứng. Python 3.11+, chỉ dùng standard library. Không đổi dependency,
entrypoint, schema chuẩn, backend API, UI, AgentScope hoặc persistence của owner khác.

## Phần đã triển khai

- `client.py`: Core API client async, endpoint mapping tường minh, credential provider,
  envelope/response guards, deadline, giới hạn response, lỗi có mã không lộ body/secret.
- `http_transport.py`: HTTP JSON thật bằng urllib, từ chối redirect, không retry ngầm.
- `approval_client.py`: xin/trả lời duyệt quản lý/cư dân; xin/trả lời xác nhận kết quả.
- `../reception/reception_gateway.py`: ticket, hỏi đáp, mention ID, bản phương án,
  cập nhật và xác nhận. Không suy diễn câu “đồng ý” thành approval.
- `../tools/tool_client.py`: offer/respond assignment, work report, alias tool được
  cấu hình sẵn. Model không được truyền endpoint hoặc tự đăng ký tool.
- `events.py`: xác minh event qua port, resolve binding, đưa vào durable inbox một lần.
  Event có mention đến `groupchat` (DEV-2), các event khác đến `supervisor` (DEV-1).
  Đây là **pending delivery**, chưa phải đã thực hiện hành động hoặc đóng ticket.

## Cách ghép (DEV-5)

Đặt `agent-coordination/src` vào Python import path. Namespace package `adapters`
không cần sửa `src/adapters/__init__.py` chung.

```python
from adapters.backend.client import BackendClient
from adapters.backend.http_transport import UrllibTransport
from adapters.backend.approval_client import ApprovalClient
from adapters.backend.events import EventIngress
from adapters.reception.reception_gateway import ReceptionGateway
from adapters.tools.tool_client import ToolClient

# Các dependency dưới đây do composition root cung cấp; không có default giả.
backend = BackendClient(
    base_url=core_origin,
    routes=operation_paths,
    transport=UrllibTransport(),
    headers=service_header_provider,
    validator=canonical_validator,
)
reception = ReceptionGateway(backend)
approvals = ApprovalClient(backend)
tools = ToolClient(backend)
ingress = EventIngress(
    verifier=backend_event_verifier,
    inbox=durable_room_inbox,
    validator=canonical_validator,
    event_types=accepted_backend_event_types,
)
```

Không dùng class trong `tests/` làm dependency production. Không tạo env mới tự đọc:
DEV-5 lấy cấu hình từ `config.py` của mình và truyền vào. HTTPS là mặc định;
`allow_http=True` chỉ bật có chủ đích cho local hoặc mạng nội bộ đã được bảo vệ.

### Operation mapping đề xuất

Đây là tên operation **nội bộ adapter**, không phải API path đã tồn tại. Team Chiến
cung cấp path và semantics tương ứng; DEV-5 điền `routes`. Tất cả hiện dùng POST JSON.

| Operation | Request type | Method |
|---|---|---|
| `reception.ticket` | `ticket.submitted` | `ReceptionGateway.receive_ticket` |
| `reception.message` | `resident.message` | `ReceptionGateway.receive_message` |
| `reception.question` | `resident.question` | `ReceptionGateway.ask_question` |
| `reception.update` | `resident.update` | `ReceptionGateway.send_update` |
| `approval.request` | `approval.requested` | `ApprovalClient.request_plan` |
| `approval.respond` | `approval.responded` | `ApprovalClient.respond_plan` |
| `completion.request` | `completion.requested` | `ApprovalClient.request_completion` |
| `completion.respond` | `completion.responded` | `ApprovalClient.respond_completion` |
| `assignment.offer` | `assignment.offered` | `ToolClient.offer_assignment` |
| `assignment.respond` | `assignment.responded` | `ToolClient.respond_assignment` |
| `work.complete` | `work.completed` | `ToolClient.report_work` |

Reception còn có `send_plan`, `receive_plan_response` chỉ cho stage `resident_plan`,
và `send_completion`, `receive_completion_response` gọi cùng ApprovalClient.
`assignment.offer` yêu cầu backend giao việc; Coordination không tự chọn nhân viên.
Ingress chỉ được đăng ký với tên event **đã được backend chấp nhận**, không trỏ
`approval.responded` chưa kiểm quyền trực tiếp vào phòng.

### Request/response và schema

Mỗi method nhận một mapping request đầy đủ theo mục 3: `contract_version="1"`,
`type`, `request_id`, `trace_id`, `idempotency_key`, `context`, `payload`.
Caller giữ cùng idempotency key khi gửi lại cùng thao tác. Không tự sinh key mới mỗi retry.
Không chấp nhận `context` như bằng chứng quyền: backend phải xác minh context bằng
service identity/delegated credential và tra quyền hiện hành. `HeaderProvider.headers()`
phải cung cấp credential đúng caller/request nếu cần delegation; không chia sẻ mutable
"current user" giữa các request đồng thời. Tuyệt đối không để service token toàn quyền
biến `principal_id` tự khai thành người phê duyệt.

`ContractValidator.validate(kind, value)` là bắt buộc; kind gồm `request`, `response`,
`event`. DEV-5 dùng JSON Schema chuẩn của Team Chiến, raise khi dữ liệu sai. Local guards
trong `messages.py` chỉ kiểm field adapter sử dụng, **không thay canonical schema**.
Không tạo file JSON Schema chuẩn hoặc sửa `src/contracts/**` trong thay đổi này.

Các lựa chọn tạm thời cần đối chiếu schema khi ghép:

- `ticket.submitted.payload.report` là text, `facts` là object, attachment IDs là list.
- Mỗi request ở đây đã có ticket/binding/run; generation >= 0, version phương án/kết quả >= 1.
- `cost`/`final_cost` có thể là `null` để biểu thị chưa biết, không chuyển thành 0.
- `assignment.responded` từ chối dùng `reason`; `work.completed` có thể có `actual_cost`.
- `resident.update.status` là string do backend xác nhận; không tự định nghĩa ticket enum.
- JSON response thành công có `{request_id, status: "accepted" | "completed", data: object}`.
  Error có `{request_id, status: "error", error: {code, retryable, ...}}`.
  Hai status trên là operation receipt, **không phải trạng thái ticket/approval**.
- Event envelope theo mục 9.3 kế hoạch chung, `schema_version="1"`; event payload
  dùng field nghiệp vụ của loại thông điệp được cấu hình, không bọc lại nguyên request.

Nếu schema chuẩn khác, sửa local guards/mapping trong scope DEV-3 cùng fixture, không
nới validator để bỏ qua kiểm tra. Error API đã chuẩn hóa không trả raw error details.

### Gửi thông tin ra lễ tân

DEV-3 gửi lệnh đến **backend delivery operation**; backend phải kiểm người nhận,
nghiệm thu, quyền xem ảnh, trạng thái, nội dung và phiên bản trước khi lưu/outbox tới
Reception/UI. Backend xác nhận management approval của đúng plan/version trước khi
gửi resident approval. Không có đường gửi trực tiếp model output đến UI trong adapter.
Phương án, steps, cost, điều kiện và file IDs được giữ nguyên, không có LLM rewrite.

Đây là yêu cầu API tích hợp cần Team Chiến/Hoàng hiện thực hoặc map sang API có cùng
semantics; adapter chưa chứng minh các endpoint/delivery outbox đó đã có. Backend cần
đảm bảo request và dispatch/outbox cùng transaction/idempotency; timeout sau commit
có thể trả `outcome_unknown=True`, caller tra kết quả hoặc retry đúng key theo chính sách.

## EventIngress và inbox (DEV-4/DEV-5)

`EventVerifier.resolve(event, authentication) -> ResolvedEvent(context)` là port bắt buộc.
Authentication là dữ liệu transport do service root cung cấp, không lấy từ event payload.
Verifier xác thực nguồn backend, audience/expiry/replay policy, quyết định đã commit,
sender/recipient, aggregate link, reply correlation, generation và các version hiện hành.
Resolver không được chỉ copy context. API từ chối/hết hạn/stale phải raise `AdapterError`.

`EventIngress.receive(event, authentication=...)` kiểm schema, gọi verifier rồi tạo
`PendingDelivery`: tenant/event ID, fingerprint, target, message type, verified context,
nguyên event. `aggregate_id` có thể là ticket/approval/assignment/result theo catalog;
verifier chịu trách nhiệm liên kết nó với ticket. Event tên gì được quyết định bởi
`event_types: {backend_event_name: documented_payload_type}`. Không có catalog mặc định giả.

`DurableInbox.enqueue_once(delivery) -> bool` phải:

1. Trong một transaction, lưu dedup `(tenant_id,event_id)` + fingerprint và pending item.
2. Trả True nếu mới; False nếu lặp giống hệt; cùng ID khác content raise conflict.
3. Có unique constraint/concurrency protection và generation/version fence tại commit.
4. Bảo đảm ordering theo aggregate; event quá cũ bị xử lý theo policy backend.
5. Sống qua restart. Worker gọi DEV-1/DEV-2 bằng event ID làm idempotency key,
   kiểm lại quyền/version khi consume và ghi kết quả/ack theo cơ chế recovery DEV-4.

Adapter không đánh dấu processed rồi gọi callback trực tiếp: crash giữa hai bước sẽ
làm mất công việc. Enqueue thành công chỉ cho phép ACK ingress; nó không khẳng định
downstream đã chạy. Không có production in-memory inbox. Test chỉ dùng fake để kiểm
interface; restart/fencing thật cần integration với persistence/backend.

## Kiểm thử

Chạy từ repo root bằng PowerShell, không cần cài package hoặc model key:

```powershell
$env:PYTHONPATH = (Resolve-Path agent-coordination/src).Path
python -B -m unittest discover -s agent-coordination/tests/adapters -v
```

Test module dùng fake backend/verifier/validator/inbox để kiểm adapter; transport có
test HTTP loopback thật trên port tạm, không gọi API bên ngoài. Bao phủ schema guard,
quyết định sai loại, bảo toàn nội dung/giá/ảnh/mention, từ chối backend, context mismatch,
response correlation, timeout không retry, event lặp/concurrent/conflict, hai phòng,
lost ACK, từ chối redirect và giới hạn response.

DEV-5 nối lệnh này vào runner/CI trong file mình sở hữu. Chưa kiểm chứng schema chuẩn,
API staging, JSON Schema cross-language, UI/AG-UI, AgentScope hoặc phục hồi process thật.
Không cần viết lại AG-UI trong scope DEV-3 mới; adapter framework thuộc DEV-2.

## Dependency còn lại để nghiệm thu toàn luồng

| Owner | Dependency |
|---|---|
| Team Chiến/Hoàng | Schema chuẩn, API paths, delegated auth, authorized delivery/notifications |
| DEV-5 | Canonical validator, header provider, event verifier, cấu hình/routes, mount service, CI |
| DEV-4 | Durable inbox/dedup/fencing và worker recovery theo port trên |
| DEV-1 | Consumer `target=supervisor`, quyết định chờ/sửa/tiếp tục theo event đã xác minh |
| DEV-2 | Consumer `target=groupchat`, kiểm membership/agent version rồi xử lý mention |

Không có migration, env mới, thay dependency hoặc sửa file owner khác trong bàn giao DEV-3.
