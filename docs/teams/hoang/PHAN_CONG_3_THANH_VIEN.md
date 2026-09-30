# Kế hoạch Team Hoàng — Reception agent và Report agent

## 1. Quy tắc dành cho AI

Khi thành viên đưa file này cho AI và nói tên của mình, AI phải:

1. Tìm đúng tên trong mục 4, chỉ nhận các task và folder của người đó.
2. Đọc [schema Reception–Supervisor](../../SCHEMA_RECEPTION_SUPERVISOR_V1.md) trước khi sửa code Reception.
3. Kiểm tra code/API thực tế; đường dẫn và tool trong kế hoạch có thể chưa tồn tại.
4. Không sửa folder của thành viên khác, database, migration, UI, Supervisor hoặc backend ngoài module reporting được giao.
5. Nếu backend chưa có API, viết interface, validator, mock contract trong test và tạo integration request; không đưa mock vào production hoặc báo đã tích hợp xong.
6. Mỗi task phải có test, kết quả chạy và handoff. Không commit file của người khác.

Phạm vi team: Reception agent cố định bằng LangGraph và năng lực Report agent để BQL tạo agent riêng trên platform. File này tập trung làm rõ Reception; công việc Report vẫn được giữ ở mục 8.

## 2. Luồng nghiệp vụ Reception bắt buộc

```text
Nhận tin nhắn cư dân
        ↓
Tra cứu kiến thức và trả lời ngay nếu giải quyết được
        ↓
Cần nhân viên chuyên môn?
   ├─ Không → tiếp tục hội thoại, chưa tạo ticket
   └─ Có
        ↓
Tạo ticket draft đúng một lần và lưu active_ticket_id
        ↓
Lấy hồ sơ cư dân đã xác minh:
tên, số điện thoại, căn hộ, tòa, domain
        ↓
Hỏi làm rõ sự cố, thu mô tả và ảnh
        ↓
Cập nhật ticket + assessment/triage qua backend
        ↓
Backend resolve đúng BQL/workspace bằng building_id + domain_id
        ↓
Gửi schema ticket đã đủ cho Supervisor của workspace đó
        ↓
Nhận ACK đã lưu/enqueue → đăng ký wait → interrupt()
        ↓
Event Supervisor/backend đến → resume đúng session → trả lời cư dân
        ↓
Mọi tin nhắn tiếp theo tiếp tục active_ticket_id, không tạo ticket mới
```

### 2.1. Các nguyên tắc không được vi phạm

- Reception trả lời kiến thức phổ thông hoặc RAG trước. Chỉ bắt đầu ticket khi cần nhân viên, có dấu hiệu khẩn, khách từ chối/tự xử lý thất bại hoặc policy yêu cầu.
- `create_ticket_draft` chỉ chạy khi `active_ticket_id` chưa có. Retry dùng cùng `idempotency_key`.
- Hồ sơ cư dân được backend lấy từ user đã đăng nhập. Model không tự điền tên, số điện thoại, căn hộ, tòa hoặc domain từ lời nói nếu chưa xác minh.
- Định tuyến dùng `building_id` và `domain_id` đã xác minh. `building_name` và `domain_name` chỉ hiển thị; Reception không tự chọn tài khoản BQL/workspace.
- Backend trả `destination_id`, `workspace_id`, `team_id`, route revision và binding cần thiết. Reception không nhận tên tài khoản BQL từ model làm quyền.
- Schema gửi Supervisor phải khớp [SCHEMA_RECEPTION_SUPERVISOR_V1.md](../../SCHEMA_RECEPTION_SUPERVISOR_V1.md), gồm mã ticket, tên/số điện thoại cư dân, căn hộ, tòa, nội dung, triage, facts và ảnh.
- Chỉ gọi `interrupt()` sau khi backend xác nhận handoff đã được lưu và event đã enqueue. Không giữ HTTP request chờ Supervisor.
- Khi resume, kiểm tra `ticket_id`, `ticket_generation`, `correlation_id`, workspace/team và event ID. Event trùng không được trả lời hoặc chạy side effect lần hai.
- Sau khi có `active_ticket_id`, mọi lượt chat trong channel/session đó chỉ bổ sung, hỏi trạng thái, trả lời Supervisor hoặc yêu cầu hủy ticket này. Không gọi `create_ticket_draft` lần nữa.
- Nếu cư dân nêu sự cố mới trong cùng hộp chat, Reception thông báo đang xử lý ticket hiện tại và yêu cầu hoàn tất/đóng ticket hoặc mở cuộc hội thoại mới theo policy. Không gộp hai sự cố vào một ticket.
- Supervisor báo `completed` chưa tự đóng ticket. Backend xác nhận work order/evidence/trạng thái rồi Reception mới nói ticket đã hoàn tất.

## 3. State và tool contract của Reception

### 3.1. State LangGraph tối thiểu

```typescript
type ReceptionState = {
  channel_id: string;
  customer_user_id: string;
  reception_session_id: string;
  reception_binding_id: string;

  phase:
    | "knowledge_chat"
    | "ticket_draft"
    | "collecting_profile"
    | "collecting_incident"
    | "routing"
    | "handoff"
    | "waiting_supervisor"
    | "ticket_discussion"
    | "terminal";

  active_ticket_id?: string;
  ticket_code?: string;
  ticket_generation?: number;
  ticket_version?: string;
  correlation_id?: string;

  verified_profile?: {
    resident_id: string;
    resident_name: string;
    phone_number: string;
    unit_id: string;
    unit_number: string;
    building_id: string;
    building_code: string;
    building_name: string;
    domain_id: string;
    domain_name: string;
    location_scope_id: string;
  };

  incident?: {
    title?: string;
    description?: string;
    category_id?: string;
    facts: Fact[];
    file_ids: string[];
  };

  route?: {
    destination_id: string;
    workspace_id: string;
    team_id: string;
    route_revision: number;
    coordination_binding_id: string;
  };

  pending_interaction_id?: string;
  last_processed_event_id?: string;
};
```

State chỉ giữ reference/snapshot cần thiết. Database/backend vẫn là nguồn chính thức cho quyền, ticket version, route và trạng thái.

### 3.2. Tool Reception cần dùng

| Tool đề xuất | Input chính | Output chính | Owner triển khai API |
|---|---|---|---|
| `search_reception_knowledge` | Câu hỏi + context đã xác minh | Câu trả lời có nguồn hoặc `insufficient` | Quang/Chiến; Dương Dũng viết wrapper |
| `create_ticket_draft` | `channel_id`, lý do, idempotency key | ticket ID/code/generation/version | Chiến |
| `get_verified_resident_context` | Ticket ID; user lấy từ auth | Tên, điện thoại, unit/building/domain IDs và tên | Chiến |
| `update_ticket_incident` | Ticket/version, mô tả, facts, file IDs | Version mới, thiếu trường nào | Chiến |
| `submit_ticket_assessment` | Ticket/version, facts/provenance | Triage decision/status chính thức | Chiến |
| `resolve_management_destination` | Ticket ID/version; backend đọc building/domain | Destination, workspace, team, route revision/binding hoặc unresolved | Chiến |
| `handoff_ticket` | Ticket/version, destination và schema v1 | ACK, correlation ID, operation ID | Chiến; Đông nhận ở runtime |
| `append_ticket_information` | Active ticket/version, message/facts/files | Version mới và delivery status | Chiến |
| `respond_supervisor_interaction` | Ticket, interaction ID/revision, answers | Accepted/conflict/expired | Chiến |
| `request_ticket_cancellation` | Active ticket/version, lý do | Accepted/rejected/review | Chiến |
| `get_ticket_status` | Active ticket ID | Trạng thái và interaction đang chờ | Chiến |

Dương Dũng chỉ viết client/tool wrapper của Reception; không tự tạo API/backend. Tool mutation phải có timeout, typed errors, idempotency và optimistic version.

### 3.3. Guard chống tạo ticket thứ hai

Node quyết định phải dùng logic xác định, không chỉ prompt:

```typescript
if (state.active_ticket_id) {
  return routeMessageToActiveTicket(state.active_ticket_id);
}

if (!decision.requires_specialist) {
  return answerFromKnowledge();
}

return createTicketDraftOnce();
```

Backend cũng phải có idempotency/unique guard theo operation. Guard trong graph không đủ khi retry hoặc nhiều replica.

## 4. Phân công ba thành viên

| Thành viên | Vai trò | Task Reception | Task Report |
|---|---|---|---|
| **Phan Dũng** | Graph, hội thoại, prompt và eval | PD01–PD06 | PD07–PD08 |
| **Dương Dũng** | Tools, backend client, schema validation | DD01–DD06 | DD07–DD08 |
| **Phan Hoàng** | Runtime, checkpoint, interrupt/resume và tích hợp | PH01–PH06 | PH07–PH08 |

### 4.1. Phan Dũng — graph và hội thoại

Được sửa:

- `agent-reception/src/graph/**`
- `agent-reception/src/prompts/**`
- `agent-reception/tests/graph/**`
- `agent-reception/tests/evals/**`
- Report: `agent-report/templates/**`, `schemas/**`, `prompts/**`, `examples/**`; `server/src/reporting/narrative/**`, `layouts/**` và test tương ứng.

| Task | Công việc | Điều kiện hoàn thành |
|---|---|---|
| PD01 | Định nghĩa `ReceptionState`, phase và graph factory | Graph chạy bằng fake ports, state serializable/versioned |
| PD02 | Node nhận tin → gọi knowledge → trả lời ngay hoặc quyết định cần chuyên môn | Không tạo ticket khi knowledge đủ; không dùng prompt thay policy khẩn cấp |
| PD03 | Node tạo ticket draft một lần, lấy hồ sơ, hỏi thiếu thông tin/ảnh và fill incident | Có guard `active_ticket_id`; không bịa hồ sơ; câu hỏi không lặp |
| PD04 | Node routing/handoff và đóng gói schema v1 | Không tự chọn workspace; chỉ handoff khi profile/incident/triage đủ |
| PD05 | Node `interrupt()`/resume và hội thoại quanh active ticket | ACK trước interrupt; resume đúng event; tin sau không tạo ticket mới |
| PD06 | Eval: kiến thức đủ, thiếu hồ sơ, nhiều căn hộ, ảnh thiếu, emergency, sự cố mới cùng chat, cancel, event trùng/stale | Dataset tiếng Việt, expected state/tool calls, không dùng PII thật |
| PD07 | Template/config/prompt Report agent để BQL tự tạo | Không SQL/tool tùy ý; pin template/metric version |
| PD08 | Narrative/layout Report, empty/partial/error states | Không bịa KPI; nội dung trỏ nguồn do tool cung cấp |

Phan Dũng không viết HTTP client, persistence hoặc backend. Graph gọi interface tool của Dương Dũng qua contract Phan Hoàng chốt.

### 4.2. Dương Dũng — tools và backend client

Được sửa:

- `agent-reception/src/tools/**`
- `agent-reception/src/adapters/backend/**`
- `agent-reception/tests/tools/**`
- `agent-reception/tests/adapters/backend/**`
- Report: `server/src/reporting/tools/**`, `metrics/**`, `application/**` và test tương ứng.

| Task | Công việc | Điều kiện hoàn thành |
|---|---|---|
| DD01 | HTTP client, auth context, validator, typed error, timeout/correlation | Không log secret/PII thừa; validate response; phân biệt retryable |
| DD02 | Wrappers knowledge, create draft và verified resident context | User lấy từ auth; retry cùng key; response sai schema bị từ chối |
| DD03 | Wrappers update incident, upload/file reference và assessment | Facts có provenance; version conflict trả typed result |
| DD04 | Wrappers resolve destination và handoff schema v1 | Input không nhận workspace từ model; validate ACK/correlation/route |
| DD05 | Wrappers append info, response interaction, cancel và status | Luôn dùng active ticket; stale route/generation không retry mù |
| DD06 | Contract/failure tests: 401/403/404/409/410/422/429/timeout/duplicate | Timeout không tạo key/ticket mới; duplicate trả cùng operation |
| DD07 | Report metric catalog/tools và authorized data port client | KPI tính bằng code; query allowlist; đúng kỳ/timezone |
| DD08 | Report application pipeline, source lineage/idempotency | Retry không tạo artifact chính thức trùng; cross-scope bị từ chối |

Dương Dũng không đọc PostgreSQL trực tiếp và không viết routing algorithm của backend. Nếu API chưa có, tạo request tại `docs/teams/hoang/requests/duong-dung/` với input/output/error/test cần thiết.

### 4.3. Phan Hoàng — runtime và tích hợp

Được sửa:

- `agent-reception/src/index.ts`, `config.ts`, `contracts/**`, `persistence/**`, `observability/**`
- `agent-reception/src/adapters/transport/**`, `events/**`, `model/**`
- `agent-reception/tests/runtime/**`, `persistence/**`, `integration/**`, `support/**`
- Cấu hình package trong `agent-reception/`; `agent-langgraph/**` khi thật sự cần reuse.
- Report: `agent-report/manifest.json`, `README.md`; `server/src/reporting/contracts/**`, `rendering/**`, `adapters/**`, `index.ts`; `worker/src/jobs/reporting/**` và test tương ứng.

| Task | Công việc | Điều kiện hoàn thành |
|---|---|---|
| PH01 | Khởi tạo package, config/model factory, interface graph/tool/checkpointer, healthcheck/test harness | Có scripts chạy/test/typecheck; không secret trong repo |
| PH02 | Transport AG-UI/HTTP, authenticated binding và channel/session resolver | Không tin user/thread/tenant từ browser; một session có active ticket rõ ràng |
| PH03 | Persistent checkpointer, lease/fencing, idempotent operations | Restart không mất active ticket; nhiều replica không chạy tool đúp |
| PH04 | Event consumer, wait registry và `interrupt()`/resume | Event đến trước wait không mất; dedup event; resume đúng ticket/session |
| PH05 | Nối graph Phan Dũng + tools Dương Dũng + backend; integration toàn luồng | Knowledge → draft → profile → incident → route → handoff → wait → resume chạy thật |
| PH06 | Test isolation/recovery/telemetry và bàn giao Team 5 | Hai user/ticket không lẫn; revoke/reroute/reopen được chặn; trace lọc PII |
| PH07 | Report manifest và tích hợp builder Chiến/runtime Đông | BQL tạo Report agent riêng, pin release/template/tool grants |
| PH08 | DOCX renderer, storage adapter, export job và integration | File đúng nguồn/quyền; retry/cancel không publish trùng |

Phan Hoàng là đầu mối contract với Chiến và Đông, không được sửa DB/migration/UI/AgentScope thay owner.

## 5. Folder không thuộc Team Hoàng

- `server/src/db/**`, `server/drizzle/**`, `app/**`, `shared/contracts/**`: Team Chiến.
- `server/src/knowledge/**`, `server/src/technical-tools/**`: Team Quang.
- `agent-coordination/**`: Team Đông.
- `supervisor/**`, worker entrypoint, Docker, CI, charts, root lockfile: Team 5.
- Team Hoàng chỉ sửa `server/src/reporting/**` và `worker/src/jobs/reporting/**` đúng owner ở mục 4.

## 6. Thứ tự thực hiện

### Mốc R0 — Chốt contract

- PH01/PH02 chốt interface nội bộ và binding.
- DD01 chốt tool request/response với Chiến.
- PD01 viết state/graph bằng fake ports.
- Chốt [SCHEMA_RECEPTION_SUPERVISOR_V1.md](../../SCHEMA_RECEPTION_SUPERVISOR_V1.md) với Đông/Chiến.

### Mốc R1 — Trả lời kiến thức và tạo draft

- PD02/PD03 + DD02/DD03 + PH03.
- Demo: câu hỏi giải quyết được không có ticket; câu cần kỹ thuật tạo đúng một draft và lấy đúng hồ sơ.

### Mốc R2 — Routing và handoff

- PD04 + DD04 + PH05.
- Demo: đủ dữ liệu mới resolve; backend chọn đúng workspace; Supervisor nhận đúng schema; retry không tạo team/handoff trùng.

### Mốc R3 — Interrupt và các lượt tiếp theo

- PD05 + DD05 + PH04/PH05.
- Demo: Supervisor hỏi thêm → Reception resume → khách trả lời; bổ sung ảnh/hủy; tất cả dùng cùng ticket. Sự cố mới cùng chat không tạo ticket thứ hai.

### Mốc R4 — Hardening

- PD06 + DD06 + PH06; Team 5 chạy E2E với backend/Supervisor thật.
- Chỉ đóng task khi không còn production mock trong đường nghiệm thu.

Report PD07–PD08, DD07–DD08 và PH07–PH08 chạy song song theo C09/C14/D08; không được làm chậm đường găng Reception.

## 7. Test bắt buộc

1. Knowledge đủ → trả lời, không gọi create ticket.
2. Cần chuyên môn → create draft đúng một lần dù retry.
3. Profile lấy theo user đăng nhập; không cho chọn căn hộ người khác.
4. Thiếu ảnh/mô tả → hỏi tiếp; chưa route/handoff.
5. Building/domain đổi hợp lệ → backend resolve lại; graph không tự giữ workspace cũ.
6. Route unresolved → hỏi/review; không chọn workspace mặc định.
7. Handoff ACK bị mất → retry cùng key, không gửi hai lần.
8. Restart khi đang chờ → phục hồi `active_ticket_id` và wait.
9. Event Supervisor trùng/stale/sai ticket → không resume hoặc trả lời lặp.
10. Tin nhắn tiếp theo, bổ sung ảnh và cancel → cùng active ticket.
11. Cư dân báo sự cố mới cùng hộp chat → không tạo ticket mới; hướng dẫn mở luồng mới theo policy.
12. Supervisor completed nhưng backend chưa xác nhận → không nói ticket đã đóng.

## 8. Prompt giao cho AI

```text
Tôi là <Phan Dũng | Dương Dũng | Phan Hoàng>, Team Hoàng.
Đọc đầy đủ:
- docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md
- docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md
- docs/KE_HOACH_HOAN_THIEN_5_TEAM.md

Tự chọn task chưa hoàn thành đầu tiên thuộc đúng tên tôi và có dependency sẵn sàng.
Chỉ sửa folder được giao ở mục 4. Không sửa file owner khác, DB, migration,
UI, Supervisor, worker entrypoint hoặc root lockfile.
Kiểm tra code/API thật trước khi triển khai; tên tool trong kế hoạch là đề xuất.
Nếu dependency backend chưa có, viết interface + contract tests và tạo request trong
docs/teams/hoang/requests/<slug-của-tôi>/; không đưa mock vào production.
Thực hiện task đến tiêu chí hoàn thành, chạy test phù hợp và ghi handoff tại
docs/teams/hoang/handoffs/<slug-của-tôi>/.
Báo rõ file sửa, test đã chạy, dependency còn thiếu và phần chưa tích hợp thật.
```

Slug: Phan Dũng = `phan-dung`; Dương Dũng = `duong-dung`; Phan Hoàng = `phan-hoang`.
