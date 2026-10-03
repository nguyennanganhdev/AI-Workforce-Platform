# Bàn giao adapter DEV-3 cho dịch vụ độc lập

Các module dưới đây là implementation phía Coordination, không phải service
backend/Reception đã chạy. Không thay schema Reception V2, không chuyển V1 sang V2.
Coordination có thể deploy độc lập; quyền duyệt, QC, ticket và delivery vẫn phải
đến từ dịch vụ có thẩm quyền. Không có fallback dùng RAM để thay nguồn nghiệp vụ.

## Nguồn chuẩn và trạng thái phần DEV-3

Hai schema Reception V2 **đã chốt**, tại `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md`
mục V2 và mục 3 của `docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md`. DEV-3 dùng
model đã có để kiểm đúng boundary; test đối chiếu field/enum với cả hai doc.
Không giao việc định nghĩa lại hai schema này cho bên khác.

`DocumentedContractValidator` kiểm input/output V2 và các wrapper/ACK nội bộ cơ bản.
`PinnedContractValidator` là lựa chọn bổ sung khi owner cung cấp file canonical;
pin hai Reception schema vẫn dùng được với các guard nội bộ, không đòi thêm 12 file.
Đây không phải việc DEV-3 xuất bản schema chung hoặc làm thay DEV-5.

`build_adapters` mặc định bật `reception`, `workflow`. `events`, `authority` là
RPC proposal tùy chọn; `legacy` giữ riêng đường V1 khi có checkpoint cũ. Chỉ route,
auth và validator của tính năng được bật mới bắt buộc. Unknown feature/kind hoặc
bật tính năng thiếu contract phải báo lỗi, không bỏ verification để cho chạy.
Validator inject có thể công bố `supported_kinds` để helper kiểm lúc startup;
nếu không có thuộc tính này thì implementation phải reject kind không hỗ trợ,
và việc kiểm contract diễn ra trước request HTTP.

Code/test/tài liệu adapter phía DEV-3 có thể hoàn tất độc lập. Endpoint production,
accepted proof, worker/storage và log nghiệm thu thật là dependency liên team;
không dùng chúng để kết luận DEV-3 thiếu schema Reception hoặc phải làm thay owner.

## Module đã có

| Module | Trách nhiệm |
|---|---|
| `routes.py` | Nạp mapping operation → path đã được owner cung cấp, kiểm thiếu operation/path sai |
| `credentials.py` | Service bearer credential, đọc mỗi request để hỗ trợ rotation |
| `contract_validator.py` | Schema offline, pin SHA-256, kiểm format và từ chối reference ngoài registry |
| `documented_contracts.py` | Hai boundary V2 theo doc; guard wrapper/ACK nội bộ; pin bổ sung không bỏ guard |
| `reception/authentication.py` | Proof nguồn HMAC tùy chọn, kiểm chữ ký/audience/purpose/expiry/scope/fingerprint |
| `reception_client.py`, `reception_gateway.py` | Verification snapshot nguyên bản và delivery V2; bridge V1 riêng |
| `reception/ingress.py` | Input đã xác minh → inbox bền vững; ACK sau commit; giữ mention sidecar |
| `event_verifier.py`, `events.py` | Verification event committed/context rồi enqueue; không gọi Supervisor inline |
| `authority_client.py` | `inspect`, `authorize_action`, `reconcile` cho DEV-1 qua contract có cấu hình |
| `tools/grants.py` | Lookup grant hiện hành, kiểm agent/task/run/context/operation, gọi tool với ID gốc |
| `business_client.py` | Gọi contract nghiệp vụ được cấu hình; hook procedure/contribution/report không tự tạo workflow |
| `composition.py` | Dựng bundle theo tính năng; không bắt buộc toàn bộ RPC proposal; không mount server/storage |

`BackendClient.call_contract` dành cho contract nội bộ có schema riêng; không ép
lookup/tool/procedure thành envelope Reception hoặc loại message V1 giả.
Observer ghi metadata transport (operation, IDs, latency, HTTP status) và receipt
đã kiểm (identity, status, mã lỗi). HTTP 200 không chứng minh duyệt/QC/thành công
nghiệp vụ; receipt cũng không chứng minh ticket đóng. Không log body/header/token.
Observer lỗi không gây gửi lại mutation. DEV-5 cung cấp sink nhanh, không blocking.

## Các operation cần phía cung cấp xác nhận

Không có URL production mặc định. Một origin chứa các path được duyệt; nếu các
dịch vụ khác origin, tạo client riêng với credential/schema phù hợp. Không cho
model/request chọn origin, path, schema, grant hoặc credential.

| Operation | Request schema | Response schema |
|---|---|---|
| `reception.verify` | `reception_input` (V2 phẳng) | `reception_response`; data kiểm `reception_verified` |
| `reception.send` | `reception_delivery` gồm message V2 và context | `reception_response` |
| `approval.request/respond`, `assignment.offer/respond`, `work.complete` | `request` | `response` |
| `event.verify` | `event` | `event_verification_response` |
| `authority.inspect` | `authority_inspect_request` | `authority_inspect_response` |
| `authority.authorize` | `authority_action_request` | `authority_authorize_response` |
| `operation.lookup` | `authority_action_request` | `operation_lookup_response` |
| `tool.grant.verify` | `tool_callback_request` | `tool_grant_response` |
| Tool execute | Grant cấu hình request schema | Grant cấu hình response schema |
| Procedure/contribution/report | `BusinessOperation` cấu hình | `BusinessOperation` cấu hình |

Input Reception trong verify và message V2 bên trong send bám hai wire schema
đã chốt. Operation, wrapper routing, receipt và RPC là contract API nội bộ do
adapter đề xuất; cần owner xác nhận trước khi deploy. Không coi chúng là schema
Reception mới hoặc API backend đã hỗ trợ.
Tất cả response operation nội bộ có `{request_id, status, data}` (event verification
dùng `event_id`, Reception dùng `message_id`); identity phải khớp request.
`status` là `accepted` hoặc `completed`, không phải trạng thái ticket. Business error
theo envelope/mã lỗi trong `client.py`; HTTP 401/403/409 không được đổi thành success.

Event verification data:

```json
{"context": "Context đầy đủ theo model", "event_fingerprint": "SHA-256 wire gốc", "committed": true}
```

Đây là minh họa shape: giá trị `context` thực tế phải là object, không phải string.
Dịch vụ verification kiểm signature/proof, aggregate link, quyền hiện hành,
generation/version, stage/expiry và quyết định đã commit. Adapter kiểm fingerprint
và tenant; không tự khẳng định aggregate ID luôn là ticket ID.

Authority request chứa `request_id`, `context`, `state_version`, `state_fingerprint`,
`state`; authorize/lookup thêm `action`, `action_fingerprint`. Fingerprint dùng JSON
sort_keys, separators `(',', ':')`, ensure_ascii=False, allow_nan=False, SHA-256 UTF-8
theo `messages.fingerprint`. ID lookup là deterministic, không thay ID mutation.
Chỉ gửi state tới dịch vụ đã được cấp quyền đọc; canonical schema phải giới hạn
fields nghiệp vụ theo contract và chủ thể gọi có scope tương ứng.

Response data:

- Inspect: `{state_fingerprint, view}`. `view` theo `AuthorityView`, khớp context và
  state_version; quyền/catalog/QC/recipient phải do dịch vụ có thẩm quyền cung cấp.
- Authorize: `{state_fingerprint, action_fingerprint, allowed: true}`. Peer phải
  kiểm lại quyền/version và fence khi thực sự áp dụng mutation, không chỉ ở lookup.
- Unknown: `{state_fingerprint, action_fingerprint, outcome: "unknown"}`.
- Not applied: thêm `fenced: true`, `fenced_action_id` khớp action. Peer phải thực sự
  chặn sender cũ; một boolean tự khai không thay thế remote fencing.
- Receipt: thêm `receipt` gốc và `wire_fingerprint`. Receipt có identity đúng action,
  status hợp lệ và được kiểm canonical schema. ACK của lookup không là ACK mutation.

Lookup timeout/unavailable/not_found/chưa có route → `unknown`, không resend.
Lookup của action `room` trả `unknown`; DEV-2/DEV-5 ghép reconciler terminal có
bằng chứng cho kênh room. Không dùng receipt backend giả để chứng nhận agent xong.

## Proof nguồn và service credential

`BearerCredentials.from_environment(variable)` dùng tên biến do DEV-5 cấu hình;
không sửa `.env`, không có token mặc định. Credential được đọc lại mỗi request.
Các provider khác implement `headers()` cũng có thể được inject.

`HmacSourceAuthentication` chỉ sử dụng khi cả producer và verifier đồng ý contract.
Không dùng nó để đọc JWT hoặc mặc định cho rằng backend hiểu HMAC. Backend có
cơ chế khác thì inject provider tương ứng; không bỏ verification của message.

Proof: `base64url(JSON claims, không padding).hex(HMAC-SHA256(encoded, issuer_key))`.
Header được cấu hình riêng, không đè Authorization/correlation/idempotency.
Claims chính xác: `version: "1"`, `issuer`, `audience`, `purpose`, `subject`,
`issued_at`, `expires_at` (epoch giây nguyên), `fingerprint`, `scope`.
Keys tối thiểu 32 byte, issuer được allowlist, lifetime tối đa mặc định 300 giây.

- Purpose Reception: `reception`; scope tenant/workspace/ticket/generation.
- Purpose event: `event`; scope tenant/aggregate ID.
- Purpose callback: `tool`; scope tenant/workspace/ticket/generation.

Proof gắn với toàn bộ wire, bao gồm source_message_id/ID/version/context khi có.
Issuer xác thực nguồn trước khi ký; adapter không tự ký claims từ input model.
Retry sau expiry cần proof mới cho cùng wire/ID; không đổi phiên bản/nội dung.
Chữ ký không thay business authorization hoặc durable semantic dedup.

## Mount và worker: bàn giao DEV-4/DEV-5

```python
bundle = build_adapters(
    origin=approved_origin, routes=approved_routes,
    credentials=service_credentials, reception_authentication=source_provider,
    legacy=keep_v1_checkpoints,
)
# Mặc định dùng DocumentedContractValidator, không cần 14 file schema.
# DEV-5: SupervisorService(..., reception=bundle.gateway, authority=owner_authority, ...)
ingress = ReceptionIngress(bundle.gateway, inbox=durable_reception_inbox)
# DEV-5 mount: await ingress.receive(input_v2, authentication=transport_proof)
# DEV-4/DEV-5 worker: reauthorize pending context/version; call handle_reception
# through gateway verification, or route verified mention sidecar to DEV-2.
```

Các tên cấu hình trên là dependency do owner cung cấp, không phải biến có sẵn.
Nếu chọn dùng BackendAuthority/BackendEventVerifier, dựng bundle với
`features=frozenset({"reception", "workflow", "authority", "events"})`,
`validator=agreed_internal_validator`, `event_authentication=event_provider`,
và mapping API đã thống nhất. Khi đó mới inject `bundle.authority` vào Supervisor.
`schema_pins=...` là cách bổ sung file canonical thay cho validator inject; không
truyền cả hai. Tính năng chưa bật trả adapter tương ứng là None để owner không
vô tình gọi một RPC chưa ghép.
Không gọi `gateway.verify` trước rồi giả định `handle_reception` bỏ qua verify:
DEV-1 vẫn gọi ReceptionPort.verify. Verification API phải idempotent và giữ
resolution để worker retry không làm mất input. Inbox không persist raw credential;
worker dùng proof/delegation hợp lệ theo contract, giữ source reference/wire gốc.

DEV-4 implement `ReceptionInbox.enqueue_once` và `DurableInbox.enqueue_once`, CAS,
lease, semantic dedup và restart. Inbox ACK chỉ sau durable commit; mất ACK là unknown.
Nếu checkpoint V1 còn sống, cấu hình route V1 riêng; không tự migrate hoặc reset.
Migration chỉ khi đối chiếu được bản ghi nghiệp vụ; dữ liệu thiếu giữ nguyên.

Tool callback gồm request_id/idempotency_key/correlation_id/context/tool/input/
agent_version_id/task_id/run_id. `RemoteToolGrantResolver` nhận grant đúng snapshot,
`GrantedToolClient` kiểm operation allowlist và scope trước execute. Peer kiểm lại
grant/revocation/dedup tại execution. Dạng callback nội bộ này phải được owner
Openbot/DEV-2/DEV-5 ghép với wire thực tế; chưa khẳng định tương thích AG-UI trực tiếp.

## Nghiệm thu và phần chưa thể chứng minh

Test-owned fixtures dùng proof HMAC, schema pin, synthetic authority/backend/inbox.
Đó là kiểm implementation adapter, không là nghiệm thu backend/Reception thật.

Checklist còn cần log production:

1. Endpoint/body/receipt/error/auth hai bên được thống nhất và deploy.
2. Reception gửi V2, hỏi thêm, duyệt/từ chối/sửa, miễn cư dân duyệt, hủy và delivery.
3. Staff nhận việc/ảnh/actual cost; QC và quyền publish; completed không đóng ticket.
4. Sai tenant/phòng/version/generation, stale/duplicate decision và grant revoked.
5. Mất ACK trước/sau commit; lookup/fence; kill/restart và hai worker không double action.
6. Reopen và backend yêu cầu xử lý tiếp; migration V1 đủ/thiếu dữ liệu.
7. Mention ID đã xác minh, hai phòng độc lập, AG-UI terminal/cancel/tool callback.
8. D06 trace/budget/version rollback: adapter giữ correlation/deadline; owner runtime
   cung cấp token usage/budget và release pin. D07 procedure/contribution và D08 Report
   dùng contract/grant riêng; không coi generic business client là workflow đã hoàn tất.

DEV-3 đã chuẩn bị adapter/hook procedure/contribution/report; chưa có contract
thực tế thì không tự invent workflow D07/D08 hoặc đánh dấu chúng nghiệm thu.
DEV-3 không sửa graph V1/tool envelope/retry của Hoàng; schema phòng chung thuộc
DEV-2/DEV-5; model/loader/runtime/storage/service/deployment thuộc các owner tương ứng.
Không sửa manifest/lockfile chung: DEV-5 cần Pydantic hiện có; jsonschema + referencing
chỉ cần khi dùng schema pin. Version kiểm chứng do owner ghi vào manifest/lock.
