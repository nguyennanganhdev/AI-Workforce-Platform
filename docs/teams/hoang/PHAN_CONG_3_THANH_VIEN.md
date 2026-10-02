# Kế hoạch Team Hoàng — 3 thành viên

> Cập nhật phân công: từ ngày 01/10/2026, **Phan Hoàng sở hữu thiết kế và tích hợp toàn bộ Reception tools**. Dương Dũng tiếp tục phụ trách Report tools. Code HTTP adapter đã có là baseline để Phan Hoàng tiếp quản, không viết lại từ đầu.

> Tiếp nhận sau review PH16 (01/10/2026, commit `df5eccd`): **Phan Dũng nhận PD11 để chuyển graph sang typed facade/V2; Phan Hoàng nhận PH17 để sửa retry và hoàn thiện HTTP contract**. PH16 đã có tools/validators local nhưng chưa DONE. Chi tiết công việc và nghiệm thu ở mục 5.1.1 và 5.3.2.

## 1. Cách AI nhận việc theo tên

Khi thành viên đưa file này cho AI và nói tên, AI phải thực hiện đúng thứ tự:

1. Đối chiếu tên chính xác: `Phan Dũng`, `Dương Dũng` hoặc `Phan Hoàng`.
2. Chỉ đọc hàng đợi task và folder của người đó trong mục 5.
3. Kiểm tra code và `git status` trước khi chọn việc; không làm lại task `DONE`.
4. Nếu người dùng không nêu task ID, chọn task `READY` đầu tiên chưa đạt tiêu chí nghiệm thu.
5. Nếu task `BLOCKED`, chỉ hoàn thành interface, validator, fixture và contract test độc lập; không giả lập dependency trong production rồi báo hoàn thành.
6. Không sửa folder của người khác. Khi cần đổi contract do người khác sở hữu, tạo integration request trong `docs/teams/hoang/requests/<slug>/`.
7. Chạy test phù hợp và ghi handoff trong `docs/teams/hoang/handoffs/<slug>/`.

AI phải mở đầu kết quả làm việc bằng bốn dòng:

```text
Thành viên: <tên>
Task: <task ID>
Folder được phép sửa: <danh sách>
Dependency đang dùng: <đã có | còn thiếu>
```

## 2. Phạm vi Team Hoàng

Team Hoàng chịu trách nhiệm:

- Reception Agent cố định bằng LangGraph/Python.
- Tool client để Reception gọi API nghiệp vụ qua backend.
- Runtime, checkpoint, interrupt/resume và tích hợp Reception.
- Template, tool, nội dung và xuất file của Report Agent để BQL tạo agent báo cáo.

Team Hoàng không sở hữu database/migration, frontend, API nghiệp vụ chính, routing BQL, Supervisor/AgentScope groupchat, RAG ingestion hoặc hạ tầng triển khai toàn hệ thống.

Luồng Reception bắt buộc:

```text
Tin nhắn → assess_request + policy
         ├─ câu hỏi kiến thức → retrieval → trả lời có nguồn
         ├─ cần làm rõ → chờ cư dân
         ├─ self-help được phép → quy trình đã duyệt
         └─ cần nhân viên/khẩn cấp
                → tạo một ticket draft
                → lấy hồ sơ cư dân đã xác minh
                → thu mô tả + file_ids
                → triage chính thức
                → backend resolve destination/workspace
                → handoff schema đã kiểm tra
                → đăng ký wait → interrupt()
                → event Supervisor → resume đúng ticket/session
```

Một hộp chat chỉ có một `active_ticket_id`. Ảnh lưu ở S3/MinIO do backend quản lý; Reception chỉ giữ `file_id` và `source_message_id`.

## 3. Baseline đã hoàn thành — không làm lại

### 3.1. Phan Dũng — `DONE`

- Workflow Python đã có node phân loại, knowledge/self-help, tạo ticket, hồ sơ, incident, triage, routing, handoff và active-ticket dialogue.
- LLM chỉ đề xuất hành động; policy và code quyết định nhánh thực thi.
- Graph giữ `pending_file_refs` qua nhiều lượt hỏi hồ sơ, chống trùng và không ghi đè ảnh cũ bằng lượt mới.
- Hỗ trợ tin nhắn chỉ có ảnh, ảnh trước khi chọn căn hộ và ảnh bổ sung sau handoff.
- Graph yêu cầu backend xác nhận ảnh đã được liên kết trước khi xóa pending reference.

File nền:

- `agent-reception/src/graph/workflow.py`
- `agent-reception/src/graph/workflow_validation.py`
- `agent-reception/src/graph/workflow_contracts.py`
- `agent-reception/src/prompts/workflow.py`
- `agent-reception/tests/graph/test_image_references.py`

### 3.2. HTTP tool adapter — `DONE_BASELINE`, chuyển ownership cho Phan Hoàng

- Đã có `BackendToolPort` dùng HTTP, endpoint cấu hình được.
- Request mutation giữ nguyên `idempotency_key` khi retry.
- Đã kiểm tra `file_ids`, loại trùng và yêu cầu `linked_file_ids` từ backend.
- Ca timeout liên tiếp đã có test trả `unknown`, không tự tạo key mới. Review PH16 phát hiện chuỗi 503/`not_applied` rồi mất response trả nhầm kết quả cũ; lỗi này được giao PH17 ở mục 5.3.2.
- Đã có contract test bằng HTTP backend giả lập.

Phần baseline này do Dương Dũng đã hoàn thành ở giai đoạn trước. Từ lần cập nhật này, mọi thay đổi mới trong `agent-reception/src/tools/**` và `agent-reception/tests/tools/**` thuộc Phan Hoàng; AI của Dương Dũng không tiếp tục chọn task Reception tool.

File nền:

- `agent-reception/src/tools/backend.py`
- `agent-reception/tests/tools/test_backend.py`

### 3.3. Phan Hoàng — `DONE` trong phạm vi local/contract

- Đã có SQLite checkpointer bền vững cho local/test.
- Restart runtime có thể đọc lại state, `active_ticket_id` và file references.
- Đã có validator snapshot phục hồi từ backend khi checkpoint chưa tồn tại.
- Đã có `BackendSessionResolver` với endpoint cấu hình được.

File nền:

- `agent-reception/src/persistence/sqlite.py`
- `agent-reception/src/persistence/recovery.py`
- `agent-reception/src/adapters/backend/session.py`
- `agent-reception/tests/persistence/test_sqlite.py`
- `agent-reception/tests/adapters/backend/test_session.py`

Mốc baseline trước PH16 có **158 Python tests đạt**. Mốc kiểm thử code `df5eccd` sau PH16 có **332 đạt, 5 thất bại**: 4 ca AD01 thuộc PH17 và 1 ca AD02 thuộc tích hợp graph/PD11. Năm ca thất bại thuộc hai vấn đề, không phải năm lỗi độc lập. Xem [handoff PH16](handoffs/phan-hoang/PH16.md), [kịch bản và kết quả kiểm thử](handoffs/phan-hoang/PH16_ADVERSARIAL_TESTS.md) và [request chuyển consumer/API](requests/phan-hoang/PH16_TYPED_TOOLS_INTEGRATION.md). Những kết quả local này chưa chứng minh endpoint thật, auth thật, PostgreSQL nhiều replica hoặc Supervisor thật đã tích hợp.

## 4. Quyền sở hữu folder

| Thành viên | Được sửa | Không được sửa trực tiếp |
|---|---|---|
| **Phan Dũng** | `agent-reception/src/graph/**`, `src/prompts/**`, `tests/graph/**`, `tests/evals/**`; `agent-report/templates/**`, `schemas/**`, `prompts/**`, `examples/**`; `server/src/reporting/narrative/**`, `layouts/**` | HTTP/backend adapter, persistence, transport, DB, Supervisor |
| **Dương Dũng** | `server/src/reporting/tools/**`, `metrics/**`, `application/**` và test tương ứng | Toàn bộ `agent-reception/**`, graph, prompt, session resolver, persistence, DB/migration |
| **Phan Hoàng** | `agent-reception/src/tools/**`, `tests/tools/**`, `src/persistence/**`, `src/adapters/backend/session.py`, `src/adapters/transport/**`, `src/adapters/events/**`, `src/adapters/model/**`, `src/observability/**`, `src/index.*`, `src/config.*`, `tests/persistence/**`, `tests/runtime/**`, `tests/integration/**`, `tests/adapters/backend/test_session.py`, package config/README; phần Report runtime ở mục 5.3 | Logic graph/prompt, API backend, DB/migration, UI, AgentScope Supervisor |

Quy tắc file dùng chung:

- `agent-reception/src/graph/workflow_contracts.py`: Phan Dũng sở hữu. Phan Hoàng gửi request nếu Reception tool cần đổi graph contract; không sửa âm thầm.
- `agent-reception/src/tools/**` và `agent-reception/tests/tools/**`: Phan Hoàng sở hữu. Dương Dũng không sửa các file này.
- `agent-reception/requirements.txt`, package config và test bootstrap chung: Phan Hoàng sở hữu.
- `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md`: contract liên team; chỉ sửa sau khi Hoàng, Đông và Chiến chốt thay đổi.
- `agent-reception/src/adapters/backend/session.py`: Phan Hoàng sở hữu; Dương Dũng không sửa file này.

## 5. Hàng đợi công việc mới

### 5.1. Phan Dũng — graph, prompt và nội dung Report

Slug: `phan-dung`.

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **PD11** | `READY` | Ưu tiên tiếp nhận PH16: chuyển graph sang 14 method có kiểu và message V2 đã chốt; approval/completion theo `message_type` | Graph gọi `ReceptionTools`; đúng input/output, context, ticket/version; giữ pending khi accepted/unknown; test graph + facade + HTTP và interrupt/resume V2 đạt; phạm vi local ở mục 5.1.1 |
| **PD09** | `READY` | Sửa lifecycle khi ticket đang chờ Supervisor nhưng Reception vừa trả lời knowledge hoặc từ chối sự cố mới | Event Supervisor đến sau lượt trả lời vẫn resume được; không còn `INTERRUPT_MISMATCH`; không tạo ticket thứ hai |
| **PD10** | `DONE_BASELINE` | State ảnh: ảnh chờ, ảnh đã link, ảnh của sự cố mới và ảnh trong câu trả lời interaction | Đã có logic và test; không chọn lại trừ khi test hồi quy thất bại |
| **PD12** | `READY` | Mở rộng eval tiếng Việt cho knowledge, giá tham khảo, self-help, emergency, active ticket và prompt injection | Dataset không có PII thật; assert node, tool calls và state cuối |
| **PD13** | `READY` | Hoàn thiện template/config/prompt Report Agent cho ba báo cáo: nhân viên, doanh thu sửa chữa, tần suất sự cố | Metric chỉ lấy từ tool; thiếu dữ liệu khác 0; hiển thị kỳ, timezone, scope, nguồn và phiên bản metric |
| **PD14** | `READY` | Narrative/layout cho báo cáo complete/partial/empty/error | Không bịa KPI; số liệu và nhận xét truy được nguồn; fixture render ổn định |

AI của Phan Dũng không viết HTTP client hoặc persistence. Khi cần Reception tool mới, mô tả input/output/error cho Phan Hoàng qua request.

#### 5.1.1. PD11 — Phan Dũng tiếp nhận consumer PH16

**Lý do chuyển từ `BLOCKED_CONTRACT` sang `READY`:** [schema message V2](../../SCHEMA_RECEPTION_SUPERVISOR_V1.md) đã chốt ngày 01/10/2026; tools và fixture local có tại `df5eccd`. PD11 làm consumer/test local theo schema này và review đề xuất `ph16.draft.1` với Phan Hoàng. OpenAPI hai endpoint và event resolver thật chưa được freeze; phần đó vẫn chờ PH18/PH13, không được coi contract local là API producer chính thức.

Đầu vào: [PH16_TYPED_TOOLS_INTEGRATION](requests/phan-hoang/PH16_TYPED_TOOLS_INTEGRATION.md), `src/tools/contracts.py`, `facade.py`, `validation.py` và fixture trong `tests/tools/`. Các đường dẫn code ở mục này tính từ `agent-reception/`.

1. Sửa `src/graph/workflow_contracts.py`, `workflow.py`, `workflow_validation.py` và test graph thuộc quyền Phan Dũng: protocol/node gọi method có kiểu cho đủ 14 operation, không tự ghép generic request tùy ý hoặc lấy tên operation từ LLM. Điều chỉnh prompt trong phạm vi cần cho enum V2.
2. Chỉ truyền context đã xác thực gồm `tenantId`, `principalId`, `bindingId`, `runId`, `requestId`; giữ timeout/cancellation ở runtime budget. Không đưa `timeoutMs`, `signal`, checkpoint hoặc permissions vào strict tool envelope.
3. Chuyển input/output theo bảng mapping trong request: handoff dùng ticket triple/correlation/reason; event dùng `message_type/message`; interaction giữ version cư dân đã thấy; không suy câu “đồng ý” mơ hồ thành approval. Không tự dựng routing, version hay các ID còn thiếu từ dữ liệu V1.
4. Lưu input/key trước side effect; phân nhánh `success/accepted/failure` đúng kiểu. Giữ pending và file reference khi accepted/unknown hoặc lỗi decode sau HTTP; chỉ xóa file pending khi backend xác nhận. Phối hợp Phan Hoàng chốt version marker và xử lý checkpoint cũ, không tự relabel/replay V1 thành V2 hoặc reset session.
5. Nghiệm thu bằng graph thật gọi facade/HTTP mock: đủ chuỗi tám operation đầu ở mục 5.3.1, interrupt/resume V2, pending qua phục hồi, event sai scope/version bị chặn, không mất ảnh hoặc tạo ticket thứ hai. `completed` vẫn cần kiểm trạng thái đóng ticket từ backend.

**Test lỗi cần tiếp nhận (AD02):** `tests/tools/test_adversarial.py::test_existing_graph_can_reach_http_with_new_backend_port` hiện FAIL với `waiting_operation`, pending `create_ticket_draft`, HTTP calls = 0. Phan Dũng sửa consumer và thêm test trong `tests/graph/**`; Phan Hoàng cập nhật test tích hợp thuộc `tests/tools/**` hoặc `tests/integration/**` để inject `ReceptionTools(BackendToolPort(...))` theo interface đã thống nhất. Test sau chuyển đổi phải kiểm cả luồng, không chỉ số HTTP request lớn hơn 0. Không skip test hoặc nới validator để nhận lại envelope sai.

PD11 bàn giao consumer cho Phan Hoàng nghiệm thu lại PH16 và wiring PH09. Lỗi retry AD01 do PH17 xử lý, không chuyển ownership HTTP adapter cho Phan Dũng.

### 5.2. Dương Dũng — Report tools

Slug: `duong-dung`.

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **DD12** | `READY` | Thiết kế tool Report: filter options, employee performance, feedback details, repair revenue, incident frequency, supporting records, export và export status | Input có kỳ/timezone/scope; output có as-of, metric version, missing-data và source references |
| **DD13** | `READY` | Viết Report tool wrapper và fake backend contract tests | Không raw SQL; không nhận scope do model tự khai; retry/idempotency đúng side effect class |
| **DD14** | `BLOCKED_API` | Nối Report tools với backend dữ liệu thật của Chiến | Hai BQL không đọc chéo; doanh thu phân biệt charged/collected; frequency đếm ticket, không đếm message |

Các task Reception cũ `DD09`–`DD11` đã chuyển thành `PH16`–`PH18`. AI của Dương Dũng không được chọn hoặc tiếp tục các task cũ này.

Ba định nghĩa Report bắt buộc:

- Đánh giá nhân viên: số việc, hoàn thành, đúng hạn, thời gian xử lý, rework, điểm trung bình và số lượt đánh giá.
- Doanh thu sửa chữa: tiền tính phí, thực thu, còn phải thu; phân biệt ngày hoàn thành và ngày thanh toán.
- Tần suất sự cố: nhóm điện/nước/... theo taxonomy chuẩn; tách `incident` khỏi `service_request`.

AI của Dương Dũng không tự tạo API backend hoặc đọc PostgreSQL trực tiếp.

### 5.3. Phan Hoàng — Reception tools, runtime, persistence và tích hợp

Slug: `phan-hoang`.

Folder Report được sửa thêm:

- `agent-report/manifest.json`, `agent-report/README.md`
- `server/src/reporting/contracts/**`, `rendering/**`, `adapters/**`, `index.*`
- `worker/src/jobs/reporting/**` và test tương ứng

Folder Reception tool Phan Hoàng sở hữu:

- `agent-reception/src/tools/**`
- `agent-reception/tests/tools/**`
- Phần wiring tool port tại `agent-reception/src/index.*`, `src/config.*` và test integration thuộc phạm vi Phan Hoàng

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **PH16** | `READY_PARTIAL` | Đã có facade/validator strict cho 14 operation tại `df5eccd`; tiếp nhận consumer PD11 để hoàn tất nghiệm thu, không làm lại phần tools đã có | Đạt local typed contract/system-internal; còn thiếu graph gọi facade và test tích hợp. Chỉ DONE khi điều kiện consumer đạt; API thật thuộc PH18 |
| **PH17** | `READY` | Ưu tiên sửa AD01: retry mất response không dùng lại `not_applied` cũ; hoàn thiện execute/reconcile, idempotency, file confirmation và lỗi có cấu trúc | 4 ca AD01 đạt; phân biệt `not_applied`/`unknown`; giữ body/key; đủ ma trận HTTP/timeout/duplicate, không log token/PII; chi tiết mục 5.3.2 |
| **PH18** | `BLOCKED_API` | Ánh xạ contract tool vào hai endpoint thật của Team Chiến và chạy producer-consumer test | Chỉ hoàn thành khi có OpenAPI/JSON Schema; create/update/triage/route/handoff/wait/follow-up/status/cancel/self-help/emergency chạy với backend thật |
| **PH09** | `READY` | Tạo Python runtime composition: config, model port, graph, tool port, resolver và checkpointer | Có entrypoint Python; config fail-fast; không dùng model TypeScript trực tiếp trong Python; test bằng injected ports |
| **PH10** | `READY_PARTIAL` | Viết transport run/read/resume/stream với authenticated context interface | Không tin tenant/user/thread từ body; contract test request/resume; auth thật chờ Chiến |
| **PH11** | `BLOCKED_DB` | Thay SQLite local bằng PostgreSQL checkpointer cho production; lease/fencing nhiều replica | Cần `TEST_DATABASE_URL`; restart và concurrent worker test đạt; không dùng SQLite production |
| **PH12** | `READY_PARTIAL` | Event consumer + wait registry + buffered event + dedup | Có fake event-store integration test; event trước wait không mất; bus/outbox thật chờ Team 5/Chiến |
| **PH13** | `BLOCKED_API` | Nối graph + tools + backend + Supervisor thật | Chạy E2E knowledge → ticket → handoff → interrupt → resume; không production mock |
| **PH14** | `READY` | Observability và isolation | Trace có request/correlation/ticket ID đã lọc; hai tenant/thread không lẫn; không log ảnh URL/token/điện thoại đầy đủ |
| **PH15** | `READY_PARTIAL` | Report manifest, renderer/export adapter và job contract | Preview chạy bằng fixture; file có source metadata; storage/job thật chờ Chiến/Team 5 |

Phan Hoàng là đầu mối gửi contract cho Team Chiến và Team Đông, nhưng không sửa code của hai team thay họ.

#### 5.3.1. Contract Reception tool Phan Hoàng phải triển khai

Reception chỉ dùng hai cổng HTTP do Team Chiến cung cấp:

```text
POST /internal/reception/operations/execute
POST /internal/reception/operations/reconcile
```

`execute` là transport dùng chung, không phải một tool mở cho model tự truyền tên operation. Phan Hoàng phải cung cấp facade có kiểu cho từng operation; LangGraph gọi facade theo node do code quyết định. `reconcile` là cơ chế phục hồi khi không biết mutation trước đã áp dụng hay chưa, không phải tool nghiệp vụ cho LLM.

Operation bắt buộc:

| Nhóm | Operation |
|---|---|
| Tạo và bàn giao ticket | `create_ticket_draft`, `get_verified_resident_context`, `update_ticket_incident`, `submit_ticket_assessment`, `resolve_management_destination`, `handoff_ticket`, `register_supervisor_wait`, `get_supervisor_event` |
| Lượt chat tiếp theo | `append_ticket_information`, `respond_supervisor_interaction`, `request_ticket_cancellation`, `get_ticket_status` |
| Nhánh đặc biệt | `process_self_help`, `escalate_emergency` |

Envelope gọi backend:

```json
{
  "operation": "<enum cố định>",
  "input": {},
  "context": {
    "tenantId": "verified-context",
    "principalId": "verified-context",
    "bindingId": "verified-context",
    "runId": "verified-context",
    "requestId": "verified-context"
  },
  "idempotency_key": "stable-key"
}
```

Phan Hoàng chịu trách nhiệm với input do Reception tạo: `channel_id`, `title`, `description`, `facts`, `file_ids`, `handoff_reason`, `source_message_id`, message/interaction và bộ ba `ticket_id`/`ticket_generation`/`ticket_version` backend đã trả. Phan Hoàng không tự điền hoặc tin dữ liệu hệ thống như tenant, cư dân, số điện thoại, căn hộ, tòa, domain, severity, priority, BQL, workspace, team hoặc Supervisor; backend phải tra cứu/xác minh và trả lại.

Thứ tự luồng đầu tiên phải được contract test:

```text
create_ticket_draft
→ get_verified_resident_context
→ update_ticket_incident
→ submit_ticket_assessment
→ resolve_management_destination
→ handoff_ticket
→ register_supervisor_wait
→ get_supervisor_event
```

Tiêu chí bắt buộc:

- Mỗi mutation có idempotency key ổn định và reconcile được sau timeout/mất response.
- `file_ids` được loại trùng; không xóa pending reference trước khi backend xác nhận liên kết.
- Tool không nhận `workspace_id`, `management_unit_id`, `team_id` hoặc quyền do model tự khai.
- Handoff chỉ thành công khi backend trả `persisted=true` và `enqueued=true` đúng correlation/ticket/version.
- Response backend được validate trước khi cập nhật LangGraph state; lỗi contract không được biến thành thành công giả.
- Không viết endpoint, query database hoặc logic routing của Team Chiến trong folder Reception.

#### 5.3.2. PH17 — Phan Hoàng tiếp nhận retry và HTTP contract

**Task READY đầu tiên của Phan Hoàng sau đợt bàn giao PH16.** Phạm vi: `agent-reception/src/tools/backend.py`, validator nếu cần và `agent-reception/tests/tools/**`. Giữ facade/contract PH16 đã có; không sửa graph của Phan Dũng để né lỗi transport.

1. **Sửa AD01 trước:** `_post` giữ `last_response` của lần 503/`not_applied` rồi decode lại sau khi lần thử cuối mất response. Phải trả `unknown` khi không biết kết quả lần cuối, không kết luận chưa áp dụng từ response cũ. Body/key không đổi giữa retry/reconcile; không tạo mutation/key mới để “thử lại”.
2. Chạy và làm đạt đủ **4 biến thể** của `tests/tools/test_adversarial.py::test_last_attempt_response_loss_must_not_reuse_previous_not_applied`: `ReadTimeout` và `RemoteProtocolError`, mỗi loại trên `invoke` và `reconcile`. Đây là lỗi của baseline HTTP, không phải lỗi schema V2. Xem bằng chứng trong [AD01](handoffs/phan-hoang/PH16_ADVERSARIAL_TESTS.md).
3. Hoàn thiện ma trận 400/401/403/404/409/410/422/429/5xx/timeout/duplicate theo contract; giữ nghĩa của failure có cấu trúc, accepted, response sai/thiếu, cùng key khác body, hủy task và khôi phục bằng reconcile. Các ca mới đã có một phần coverage, không cần viết lại chỉ để tăng số test. Kiểm token/PII không lọt vào lỗi/log.
4. Giữ các regression đang đạt: retry cùng body/key, receipt handoff đúng ticket/version/correlation, xác nhận đủ file, hai tenant không lẫn response. Không biến lỗi decoder sau HTTP thành `not_applied` hoặc success giả.

**Nghiệm thu PH17:** bốn ca AD01 chuyển từ FAIL sang PASS; bộ tools và các test hồi quy không phát sinh lỗi mới; báo đủ ma trận đã kiểm chứng. Nếu PD11 chưa xong, AD02 vẫn là lỗi tích hợp riêng phải báo rõ, không skip/xfail hoặc ghi toàn bộ suite xanh. Sau PD11 + PH17, Phan Hoàng cập nhật test tích hợp và chạy lại toàn bộ suite để xác nhận hai nguyên nhân của năm ca FAIL đã được xử lý. Không nghiệm thu dedup/transaction/auth của backend thật bằng fixture; PH18 vẫn chờ producer API.

## 6. Dependency liên team

| Dependency | Owner ngoài Team Hoàng | Team Hoàng làm được trước | Điều kiện tích hợp thật |
|---|---|---|---|
| API ticket/profile/triage/routing/file | Chiến | Interface, validator, fake contract test | OpenAPI/JSON Schema + auth + endpoint test |
| Schema điều phối và approval/completion | Đông + Chiến | V2 message đã chốt; PD11 chuyển consumer và test local | Ánh xạ API/event resolver và kiểm chứng producer-consumer thật qua PH18/PH13 |
| RAG/self-help/giá | Quang + Chiến | Port và hành vi fallback | Tool được đăng ký, có ACL/citation/version |
| PostgreSQL checkpoint/lease | Team 5 | Factory/config/migration-free adapter | DB test riêng và thông số pool/retention |
| Event bus/outbox/inbox | Chiến + Team 5 | Consumer interface, dedup/buffer tests | Event catalog và transport thật |
| S3/MinIO | Chiến + Team 5 | Chỉ truyền `file_ids` và kiểm confirmation | Upload/complete/authorize API thật |

Không đánh dấu task tích hợp là `DONE` chỉ vì fake test đạt.

## 7. Thứ tự triển khai

1. **Tiếp nhận PH16 trước:** Phan Dũng làm PD11 (consumer/V2, AD02); Phan Hoàng làm PH17 (retry/HTTP, AD01). Sau đó nghiệm thu lại PH16, tiếp tục PD09, PH09–PH10 và PH12. Hai owner giữ đúng phạm vi file ở mục 4.
2. **Chốt phần contract còn thiếu:** OpenAPI backend, mapping event resolver và event catalog; dùng schema message Reception–Supervisor V2 đã chốt, không tự sửa shared schema.
3. **Tích hợp thật:** PH18, PH11 và PH13.
4. **Report Agent:** PD13–PD14, DD12–DD14, PH15.
5. **Hardening:** PD12, PH14 và E2E liên team.

Ba người không được cùng sửa một file trong cùng thời điểm. Thay đổi contract đi theo thứ tự: owner contract → consumer update → integration test.

## 8. Test bắt buộc trước handoff

- Python: `python -B -m pytest -q -p no:cacheprovider agent-reception/tests`
- Các chuỗi sự cố PH16/PH17: `python -B -m pytest -q -p no:cacheprovider agent-reception/tests/tools/test_adversarial.py --tb=short`. Mốc `df5eccd`: 45 PASS / 5 FAIL; theo dõi riêng AD01 (PH17) và AD02 (PD11 + test tích hợp Phan Hoàng), không coi đây là kết quả đã xanh.
- Graph: knowledge đủ không tạo ticket; ticket tạo đúng một lần; ảnh không mất qua nhiều lượt; event sai scope bị từ chối.
- Tools do Phan Hoàng sở hữu: đủ validator theo operation; cùng idempotency key khi retry; file link confirmation; lỗi `unknown` không chạy mutation mới; reconcile không nhân đôi side effect.
- Persistence: đóng/mở runtime vẫn đọc đúng state; backend recovery không ghép file/ticket sai user.
- Integration thật chỉ được ghi đạt khi dùng endpoint, database và Supervisor thật.
- Nếu Bun chưa có trong `PATH`, báo chưa chạy TypeScript tests; không ghi là đã đạt.

## 9. Mẫu prompt thành viên gửi cho AI

```text
Tôi là <Phan Dũng | Dương Dũng | Phan Hoàng>, Team Hoàng.

Đọc đầy đủ:
- docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md
- docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md
- docs/KE_HOACH_HOAN_THIEN_5_TEAM.md

Nếu tôi không nêu task ID, hãy kiểm tra code rồi chọn task READY đầu tiên chưa hoàn thành
trong đúng mục mang tên tôi. Không làm lại baseline DONE.

Trước khi sửa, hãy báo tên, task ID, folder được phép sửa và dependency.
Chỉ sửa folder của tôi. Nếu cần đổi contract/file của người khác, tạo integration request
trong docs/teams/hoang/requests/<slug>/ và tiếp tục phần độc lập.

Không đưa fake backend/model/checkpointer vào production path. Thực hiện đến tiêu chí
nghiệm thu, chạy test, ghi handoff và báo rõ phần đã kiểm chứng, phần còn chờ team khác.
```

Slug:

- Phan Dũng: `phan-dung`
- Dương Dũng: `duong-dung`
- Phan Hoàng: `phan-hoang`
