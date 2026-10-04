# Security MCP — Danh sách port backend cần nối

- **Từ:** Team Phái (Security MCP).
- **Gửi:** Team Chiến.
- **Ngày:** 04/10/2026.
- **Contract:** Security MCP v0.3 (JSON Schema ở `server/src/security-tools/schema/`).

Module nằm ở `server/src/security-tools/`, gồm 22 tool: 16 READ và 6 WRITE. Tool không truy cập DB trực tiếp: mọi dữ liệu đi qua port `SecurityProvider`. Hiện chỉ có provider **mock** (dữ liệu fixture) chạy được; provider thật chưa có nguồn dữ liệu để nối vào.

Điểm vào:

| Export | File | Dùng khi |
|---|---|---|
| `createSecurityMcpHandler(options)` | `index.ts` | Expose qua MCP Streamable HTTP. Trả handler `(Request) => Promise<Response>`, gắn được vào Hono: `app.all(path, (c) => handle(c.req.raw))` |
| `registerSecurityTools(server, identity, options)` | `tools.ts` | Tự dựng MCP `Server` và chỉ cần đăng ký tool. `identity` là `RequestIdentity` (xem §1.1) |
| `configFromEnv()` / `startSecurityMcpServer()` | `index.ts` | Chạy thành service riêng: `bun server/src/security-tools/index.ts` |

## 1. Port bắt buộc

| # | Port | Trong code | Việc Chiến cần làm |
|---|---|---|---|
| 1 | Danh tính đã xác thực | `RequestIdentity` / `AuthenticatedCaller` (`common/context.ts`) | Từ lời gọi đã xác minh, trả `principal_id`, `tenant_id`, `property_id`, `ticket_id`, `task_id` và `modes` (READ/WRITE). Xem §1.1 |
| 2 | Nguồn dữ liệu | `SecurityProvider` (`providers/provider.ts`) | Cài `read(tool, input, ReadContext, ProviderCallOptions)` và `write(tool, input, VerifiedWrite, ProviderCallOptions)`. Xem §2 và §3 |
| 3 | Xác minh lệnh WRITE đã duyệt | `WriteGuard` (`tools.ts`) | Dùng sẵn `createWriteGuard({ issuers })` nếu platform ký grant ES256; hoặc thay bằng cách kiểm approval của backend. Xem §1.2 |
| 4 | Callback của worker | `WorkerCommands` (`providers/mock-write.ts`) | Worker của platform cập nhật dispatch/escalation trực tiếp ở backend, không đi qua MCP. Xem §4 |
| 5 | Mount | `createSecurityMcpHandler` | **WRITE bắt buộc đi route MCP riêng** (ví dụ `/internal/mcp/security`), gọi service-to-service từ ActionExecutor. **READ** đi route đó, hoặc đi `/api/agent-tools/call` qua `DeploymentToolCaller` như technical-tools. Xem §1.3. **Cần Chiến chốt đường cho READ** |

### 1.1. Danh tính

```ts
type AuthenticatedCaller = {
  principal_id: string;
  tenant_id: string;
  property_id: string;
  ticket_id: string | null;   // READ được phép null
  task_id: string | null;     // khác null thì ticket_id phải khác null; WRITE cần cả hai
  modes: ReadonlySet<"READ" | "WRITE">;
};

// Thứ registerSecurityTools thực sự nhận
type RequestIdentity = {
  caller: AuthenticatedCaller;
  correlation_id: string;
  write_headers: {
    execution_grant: string | null;   // header X-Security-Execution-Grant
    idempotency_key: string | null;   // header Idempotency-Key
  };
};
```

Tool không bao giờ lấy tenant/property/ticket/task từ arguments của agent.

Hiện code dựng `RequestIdentity` từ access token JWT (`createAccessTokenVerifier`, gồm claim `sub`, `tenant_id`, `property_id`, `ticket_id`, `task_id` và `scope` là `security:read` / `security:write`). Platform đang dùng agent token `obot_agt_*` kèm run assertion (`botId`, `actorId`), nên cần Chiến chọn một trong hai:

- **(a)** Gateway mint access token ngắn hạn theo các claim trên, và MCP giữ nguyên verifier hiện tại. Dùng được cho cả READ và WRITE.
- **(b)** Host tự resolve `RequestIdentity` từ `botId`/`actorId` đã verify, rồi truyền thẳng vào `registerSecurityTools`. Với cách này, phía Team Phái sẽ viết thêm adapter `DeploymentToolCaller` tương tự `technical-tools/entry.ts`.
  - Run assertion chỉ có `botId`/`actorId`, không có `ticket_id`/`task_id`, nên **(b) chỉ đủ cho READ** (`ticket_id = task_id = null`, `modes = {READ}`).
  - Cần Chiến chỉ rõ `tenant_id` và `property_id` lấy từ đâu khi chỉ biết `botId`/`actorId` (deployment của bot gắn với một building? hay một tenant nhiều building?).

Chỉ ActionExecutor được có mode `WRITE`; agent chỉ có `READ`.

### 1.2. Lệnh WRITE

Mỗi lệnh WRITE phải kèm:
- **Header `X-Security-Execution-Grant`:** JWS ES256 do dịch vụ approval ký.
- **Header `Idempotency-Key`.**

MCP dựng lại `ActionBinding` từ grant, arguments và context, rồi so `payload_hash` (SHA-256 của JCS). Lệch ở bất kỳ đâu thì từ chối, không gọi provider. Chi tiết claim ở spec v0.3 §4 và trong `common/execution-grant.ts`.

Hiện chưa có dịch vụ approval nào ký grant. Không cấu hình `writeGuard` thì WRITE bị ẩn khỏi `tools/list` và bị từ chối ở `tools/call`; nghĩa là module **chạy READ-only được ngay**.

### 1.3. Vì sao WRITE không đi `/api/agent-tools/call`

`DeploymentToolCaller` chỉ nhận `{ name, args, botId, actorId, initiator }` và trả `{ text, isError }`. Đường này thiếu ba thứ mà WRITE bắt buộc phải có:
- Không có chỗ cho header grant và `Idempotency-Key` (§1.2).
- Không có `ticket_id`/`task_id` (§1.1).
- Người gọi là agent, trong khi WRITE chỉ dành cho ActionExecutor.

Vì vậy nếu READ đi qua `/api/agent-tools/call`, adapter của Team Phái sẽ **chỉ đăng ký 16 tool READ** ở đường đó. 6 tool WRITE chỉ có trên route MCP riêng.

## 2. Port nguồn dữ liệu READ

Provider nhận `ReadContext` đã xác thực và phải lọc theo `tenant_id`/`property_id` cho mọi query và join. Resource ngoài scope trả `NOT_FOUND`. Wrapper validate lại toàn bộ output theo schema; sai shape hoặc sai enum thì trả `PROVIDER_INVALID_RESPONSE`.

### 2.1. Thời gian và hủy lời gọi

Mỗi lời gọi provider nhận thêm `ProviderCallOptions`:

```ts
type ProviderCallOptions = {
  signal: AbortSignal;   // bị abort khi hết budget của wrapper
  deadline: number;      // epoch ms; provider không được chờ quá mốc này
};
```

- Budget của wrapper cho một tool là **25 giây** (`TOOL_BUDGET_MS`). Hết budget thì wrapper trả `PROVIDER_TIMEOUT` và abort `signal`.
- `CoreClient` (nếu dùng HTTP, xem cuối §2) có timeout riêng **20 giây** (`CORE_REQUEST_TIMEOUT_MS`), ngắn hơn budget để còn thời gian trả lỗi có kiểu.
- Query DB nên truyền `signal` xuống driver, hoặc tự đặt statement timeout nhỏ hơn `deadline`.
- Với WRITE, bị abort **không đồng nghĩa rollback**: kết quả được coi là chưa biết và phải đối soát qua ledger (§3).

### 2.2. Đối chiếu bảng

Đối chiếu các entity của contract với bảng trên `develop` (`db/schema/security.ts`, `tables.ts`):

| Entity contract | Tool đọc | Bảng hiện có | Tình trạng |
|---|---|---|---|
| `CameraSummary`, `IncidentCamera` | `get_camera_metadata`, `search_cameras`, `get_cameras_by_location`, `get_incident_cameras` | `security_cameras` | Có một phần: status lowercase cần map sang `ONLINE`/`OFFLINE`/`MAINTENANCE`; thiếu `camera_type` (map `UNKNOWN`); `location` là text, không phải `Location`; chưa có liên kết camera–incident |
| `EscalationContact` | `get_escalation_contacts` | `security_emergency_contacts` | Có một phần: `position` → `priority`, `role_label` cần map sang `ContactRole`; thiếu `availability`, `supported_severities`, `channels`. **Không được xuất `phone`**. Bảng giữ `ack_timeout_seconds` **theo từng contact** (5–3600, mặc định 60); contract giữ `ack_timeout_seconds` **theo protocol** (`EmergencyProtocol`), và `ack_deadline_at = created_at + ack_timeout_seconds` |
| `EmergencyEscalation` | `get_emergency_escalation`, `get_incident_escalations` | `security_alerts` + `security_alert_deliveries` | Khác mô hình (xem §5). `version` bắt đầu từ 0, contract bắt đầu từ 1 |
| `Incident` | `get_incident`, `search_incidents` | — | Chưa có. Cần chốt: bảng riêng, hay map lên `tickets` |
| `GuardSummary` | `get_available_guards`, `get_guard_status` | — | Chưa có. `staff_profiles` không có status trực và vị trí hiện tại |
| `Dispatch` | `get_dispatch`, `get_dispatch_history` | — | Chưa có |
| `EmergencyProtocol` | `get_emergency_protocol` | — | Chưa có |
| `EvidenceItem` | `get_incident_evidence` | `evidence_items` | **Không dùng được.** `evidence_items` là bảng ảnh/file của ticket (`file_id` NOT NULL, `purpose`, `provenance`, `uploaded_by`). Contract cần bản ghi `ACTION_RECEIPT` / `OPERATOR_NOTE` / `EXTERNAL_REFERENCE` do chính lệnh WRITE và callback sinh ra, không gắn file. Cần bảng mới |
| `SecurityEvent` | `get_security_event_timeline` | — | Chưa có. `ticket_events` (`ticket_id` NOT NULL, `seq`, `event_type`, `idempotency_key` NOT NULL) chỉ dùng được nếu incident map lên `tickets` (§5 câu 3) và thêm được các `event_type` của security |

Lưu ý: cả 4 bảng `security_*` đều khóa theo `(tenant_id, building_id)`. Vì vậy câu hỏi `property_id` ↔ `buildings.id` (§5 câu 2) quyết định cách lọc scope cho mọi query.

### 2.3. Quy ước dữ liệu

- Timestamp UTC dạng `YYYY-MM-DDTHH:mm:ss.SSSZ`.
- `Id` là chuỗi opaque 1–128 ký tự `[A-Za-z0-9_-]`; uuid dùng được.
- Phân trang: `limit` mặc định 50, tối đa 100. Cursor là chuỗi opaque gắn với scope, principal và filter, **hết hạn sau 15 phút** (`CURSOR_TTL_MS`). Mọi trang của một cursor phải đọc trên cùng snapshot: dữ liệu đổi thì cursor cũ bị từ chối, không trả trang lệch.
- Trạng thái không biết thì không map sang `AVAILABLE`/`OPEN`/`PENDING`.
- **Camera không bao giờ xuất media hay credential.** Output camera bị quét thêm ngoài schema (`cameras/boundary.ts`): field có tên dạng `stream_url`, `snapshot`, `rtsp`, `image`, `password`, `token`… hoặc chuỗi có dạng địa chỉ media đều làm tool trả `PROVIDER_INVALID_RESPONSE`. Không SELECT các cột đó ngay từ đầu.

### 2.4. Nếu backend muốn expose HTTP

Có sẵn `RealSecurityProvider` + `CoreClient` (`providers/real-provider.ts`, `client.ts`) nếu backend muốn expose một endpoint HTTP thay vì cấp provider trong tiến trình. Wire format đang giả định là `POST {base}/security/v0.3/query` với body `{ context, tool_call }` và response `{ data }`, có thể đổi theo backend.

## 3. Port ghi WRITE

| Tool | Tác động |
|---|---|
| `create_incident`, `update_incident` | Tạo hoặc sửa incident, kiểm `version` (CAS) |
| `dispatch_guard`, `cancel_dispatch` | Tạo dispatch `PENDING` và giữ chỗ guard; hủy thì nhả guard |
| `escalate_emergency`, `acknowledge_emergency` | Tạo escalation `PENDING` và ghi outbox gửi tin; ghi ACK |

Provider nhận `VerifiedWrite = { context, idempotency_key, claims, binding }` cùng `ProviderCallOptions` (§2.1), và trả `{ data, evidence: WriteEvidence, replayed }` hoặc `ToolError`. Hiện `RealSecurityProvider.write` từ chối mọi lệnh ngay, trước khi gửi gì đi.

Yêu cầu với backend, tất cả trong **một transaction**:

1. Kiểm scope và approval record (`proposal_id`), so hash binding.
2. Claim idempotency key: unique `(tenant_id, property_id, idempotency_key)`, và mỗi `proposal_id` chỉ gắn một operation.
3. Kiểm `version` và precondition nghiệp vụ.
4. Ghi state, evidence, event, outbox và lưu result.

Cần thêm **bảng operation ledger** với các cột: key, payload_hash, proposal_id, status (`IN_PROGRESS` / `UNKNOWN` / `COMMITTED` / `REJECTED`), result, rejection. Ledger phục vụ replay và đối soát (`getOperation`). Logic quyết định replay/conflict từ một bản ghi ledger đã có sẵn ở `decideIdempotency` (`common/idempotency.ts`).

`security_alerts` có `idempotency_key` + `request_hash`, nhưng khóa unique kèm `ticket_id` và chỉ áp cho riêng alert, nên chưa thay được ledger chung.

**Approval record:** `work_approvals` hiện không dùng nguyên trạng được. Bảng bắt buộc `work_order_id` (NOT NULL), trong khi lệnh security không gắn với work order; bảng cũng không có chỗ cho `proposal_id`, `payload_hash` hay `ActionBinding`. Muốn dùng lại thì phải thêm cột và nới ràng buộc, hoặc tạo bảng approval riêng cho security (§5 câu 5).

Role DB của provider chỉ cần `SELECT` trên các bảng ở §2, cộng `INSERT`/`UPDATE` trên các bảng security mới và ledger. Không cần `DELETE`.

## 4. Callback của worker

Các lệnh dưới đây do worker hoặc gateway của platform gọi thẳng backend. Agent không có tool nào để sửa trạng thái callback. Mock đã cài đủ semantics (`createMockWrite().worker`), dùng làm tham chiếu và test.

| Lệnh | Input chính | Do ai gọi |
|---|---|---|
| `recordDispatchStatus` | scope, `event_id`, `dispatch_id`, `expected_version`, trạng thái mới, `failure_code?` | Worker / operator |
| `recordNotificationResult` | scope, `event_id`, `escalation_id`, `expected_version`, `NOTIFIED` / `FAILED`, `provider_reference_id` | Notification worker |
| `recordAckReceipt` | scope, `event_id`, `escalation_id`, `contact_id`, `actor` | Contact gateway; `received_at` do backend đóng dấu |
| `expireEscalation` | scope, `event_id`, `escalation_id`, `expected_version` | SLA worker; backend tự kiểm deadline |

Yêu cầu chung:
- Trùng `event_id` thì trả `replayed`, không ghi thêm.
- Mỗi callback ghi một event và một evidence trong cùng transaction.
- Callback đến sai thứ tự không làm sống lại trạng thái đã kết thúc.
- Callback làm đổi dữ liệu thì cursor phát ra trước đó phải hết hiệu lực (§2.3).

## 5. Điểm lệch cần chốt

| # | Câu hỏi | Ảnh hưởng | Team Phái phải làm thêm tùy câu trả lời |
|---|---|---|---|
| 1 | Danh tính: chọn (a) access token hay (b) `botId`/`actorId` (§1.1). Nếu (b): `tenant_id`/`property_id` lấy từ đâu | Mount, port 1 | (a): không đổi code. (b): viết hàm dựng `RequestIdentity` từ `botId`/`actorId` theo nguồn Chiến chỉ định |
| 2 | `property_id` của contract ứng với gì bên backend: `buildings.id` hay `access_scopes.id` | Mọi query (bảng `security_*` khóa theo `building_id`) | Không đổi code MCP; ảnh hưởng adapter DB |
| 3 | Incident là bảng riêng hay map lên `tickets` | Tool incident, dispatch, escalation, timeline | Không đổi code MCP; ảnh hưởng adapter DB |
| 4 | Escalation: backend làm một alert gửi lần lượt nhiều contact (`position`, `exhausted`, timeout theo contact); contract làm mỗi escalation một contact, timeout theo protocol, và platform chọn contact dự phòng. Giữ mô hình nào, hay viết adapter chuyển đổi | Tool emergency, worker | Nếu giữ mô hình backend: viết lớp chuyển đổi alert/delivery ↔ escalation |
| 5 | Ai ký grant WRITE và lưu approval record. `work_approvals` không dùng nguyên trạng được (§3): sửa bảng đó hay tạo bảng riêng | Port 3, toàn bộ WRITE | Grant ES256: không đổi code. Kiểm approval kiểu khác: thay `WriteGuard` |
| 6 | Ai viết adapter DB cho `SecurityProvider`: Team Phái (cần Chiến cấp session theo tenant và bảng) hay backend | Port 2 | Nếu Team Phái: viết provider thật, map enum và cột theo §2.2 |
| 7 | READ đi route MCP riêng hay `/api/agent-tools/call` (§1.3) | Mount | Nếu `/api/agent-tools/call`: viết adapter `DeploymentToolCaller` chỉ cho 16 tool READ |

Chưa có các mục 1–3 thì không nối được READ thật. Trong lúc chờ, module chạy READ và WRITE với provider mock.

## 6. Chạy thử với mock

```bash
SECURITY_MCP_PROVIDER=mock SECURITY_MCP_TEST_CONTROL=1 \
SECURITY_MCP_ACCESS_ISSUERS='{"test-issuer":"./jwks.json"}' \
SECURITY_MCP_ACCESS_AUDIENCE=security-mcp \
bun server/src/security-tools/index.ts
```

- `./jwks.json` **không có sẵn trong repo**. Cần tự tạo một cặp key, đặt public key vào `jwks.json`, rồi dùng private key ký access token với `iss = "test-issuer"`, `aud = "security-mcp"` và các claim ở §1.1. Giá trị của mỗi issuer là URL HTTPS, hoặc đường dẫn file cục bộ (chỉ dùng được khi `NODE_ENV` khác `production`).
- `SECURITY_MCP_GRANT_ISSUERS`: thêm vào (cùng dạng JSON) nếu muốn bật WRITE.
- `POST /faults`: chỉ có khi đặt `SECURITY_MCP_TEST_CONTROL=1` và provider là mock. Dùng để bật fault, giữ/nhả barrier, chỉnh đồng hồ giả, reset dữ liệu và chạy lệnh worker (`providers/mock-control.ts`).

## 7. Kiểm thử

289 test trong `server/tests/security-tools/`, chạy trên provider mock, không cần key hay DB:

```bash
bun test server/tests/security-tools
```
