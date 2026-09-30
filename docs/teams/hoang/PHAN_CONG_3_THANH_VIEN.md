# Kế hoạch Team Hoàng — 3 thành viên

> Cập nhật sau khi hoàn thành xử lý tham chiếu ảnh, HTTP tool adapter và checkpoint/recovery local.

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

### 3.2. Dương Dũng — `DONE`

- Đã có `BackendToolPort` dùng HTTP, endpoint cấu hình được.
- Request mutation giữ nguyên `idempotency_key` khi retry.
- Đã kiểm tra `file_ids`, loại trùng và yêu cầu `linked_file_ids` từ backend.
- Timeout/mất response trả kết quả `unknown`; không tự tạo key mới.
- Đã có contract test bằng HTTP backend giả lập.

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

Baseline hiện có **158 Python tests đạt**. Điều này chưa chứng minh endpoint thật, auth thật, PostgreSQL nhiều replica hoặc Supervisor thật đã tích hợp.

## 4. Quyền sở hữu folder

| Thành viên | Được sửa | Không được sửa trực tiếp |
|---|---|---|
| **Phan Dũng** | `agent-reception/src/graph/**`, `src/prompts/**`, `tests/graph/**`, `tests/evals/**`; `agent-report/templates/**`, `schemas/**`, `prompts/**`, `examples/**`; `server/src/reporting/narrative/**`, `layouts/**` | HTTP/backend adapter, persistence, transport, DB, Supervisor |
| **Dương Dũng** | `agent-reception/src/tools/**`, `tests/tools/**`; `server/src/reporting/tools/**`, `metrics/**`, `application/**` và test tương ứng | Graph, prompt, session resolver, persistence, DB/migration |
| **Phan Hoàng** | `agent-reception/src/persistence/**`, `src/adapters/backend/session.py`, `src/adapters/transport/**`, `src/adapters/events/**`, `src/adapters/model/**`, `src/observability/**`, `src/index.*`, `src/config.*`, `tests/persistence/**`, `tests/runtime/**`, `tests/integration/**`, `tests/adapters/backend/test_session.py`, package config/README; phần Report runtime ở mục 5.3 | Logic graph, tool nghiệp vụ, DB/migration, UI, AgentScope Supervisor |

Quy tắc file dùng chung:

- `agent-reception/src/graph/workflow_contracts.py`: Phan Dũng sở hữu. Dương Dũng và Phan Hoàng gửi request nếu cần đổi.
- `agent-reception/requirements.txt`, package config và test bootstrap chung: Phan Hoàng sở hữu.
- `docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md`: contract liên team; chỉ sửa sau khi Hoàng, Đông và Chiến chốt thay đổi.
- `agent-reception/src/adapters/backend/session.py`: Phan Hoàng sở hữu; Dương Dũng không sửa file này.

## 5. Hàng đợi công việc mới

### 5.1. Phan Dũng — graph, prompt và nội dung Report

Slug: `phan-dung`.

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **PD09** | `READY` | Sửa lifecycle khi ticket đang chờ Supervisor nhưng Reception vừa trả lời knowledge hoặc từ chối sự cố mới | Event Supervisor đến sau lượt trả lời vẫn resume được; không còn `INTERRUPT_MISMATCH`; không tạo ticket thứ hai |
| **PD10** | `DONE_BASELINE` | State ảnh: ảnh chờ, ảnh đã link, ảnh của sự cố mới và ảnh trong câu trả lời interaction | Đã có logic và test; không chọn lại trừ khi test hồi quy thất bại |
| **PD11** | `BLOCKED_CONTRACT` | Hỗ trợ envelope mới của Team Đông: `ticket.submitted`, `resident.message/question/update`, approval và completion | Chỉ code sau khi shared contract được chốt; đúng request/version/interaction; không hiểu câu “đồng ý” mơ hồ là approval |
| **PD12** | `READY` | Mở rộng eval tiếng Việt cho knowledge, giá tham khảo, self-help, emergency, active ticket và prompt injection | Dataset không có PII thật; assert node, tool calls và state cuối |
| **PD13** | `READY` | Hoàn thiện template/config/prompt Report Agent cho ba báo cáo: nhân viên, doanh thu sửa chữa, tần suất sự cố | Metric chỉ lấy từ tool; thiếu dữ liệu khác 0; hiển thị kỳ, timezone, scope, nguồn và phiên bản metric |
| **PD14** | `READY` | Narrative/layout cho báo cáo complete/partial/empty/error | Không bịa KPI; số liệu và nhận xét truy được nguồn; fixture render ổn định |

AI của Phan Dũng không viết HTTP client hoặc persistence. Khi cần tool mới, mô tả input/output/error cho Dương Dũng qua request.

### 5.2. Dương Dũng — tool và backend client

Slug: `duong-dung`.

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **DD09** | `READY` | Tách schema/validator input-output cho toàn bộ Reception operations khỏi HTTP transport chung | Mỗi operation từ chối field sai; enum/version/file confirmation được kiểm tra runtime |
| **DD10** | `READY` | Hoàn thiện failure/contract tests cho 400/401/403/404/409/410/422/429/5xx/timeout/duplicate | Phân biệt `not_applied` và `unknown`; mutation retry cùng key; không log token/PII |
| **DD11** | `BLOCKED_API` | Ánh xạ endpoint thật cho create/update/triage/route/handoff/status/cancel/self-help/emergency | Chỉ hoàn thành khi có OpenAPI/JSON Schema của Chiến; contract test producer-consumer đạt |
| **DD12** | `READY` | Thiết kế tool Report: filter options, employee performance, feedback details, repair revenue, incident frequency, supporting records, export và export status | Input có kỳ/timezone/scope; output có as-of, metric version, missing-data và source references |
| **DD13** | `READY` | Viết Report tool wrapper và fake backend contract tests | Không raw SQL; không nhận scope do model tự khai; retry/idempotency đúng side effect class |
| **DD14** | `BLOCKED_API` | Nối Report tools với backend dữ liệu thật của Chiến | Hai BQL không đọc chéo; doanh thu phân biệt charged/collected; frequency đếm ticket, không đếm message |

Ba định nghĩa Report bắt buộc:

- Đánh giá nhân viên: số việc, hoàn thành, đúng hạn, thời gian xử lý, rework, điểm trung bình và số lượt đánh giá.
- Doanh thu sửa chữa: tiền tính phí, thực thu, còn phải thu; phân biệt ngày hoàn thành và ngày thanh toán.
- Tần suất sự cố: nhóm điện/nước/... theo taxonomy chuẩn; tách `incident` khỏi `service_request`.

AI của Dương Dũng không tự tạo API backend hoặc đọc PostgreSQL trực tiếp.

### 5.3. Phan Hoàng — runtime, persistence và tích hợp

Slug: `phan-hoang`.

Folder Report được sửa thêm:

- `agent-report/manifest.json`, `agent-report/README.md`
- `server/src/reporting/contracts/**`, `rendering/**`, `adapters/**`, `index.*`
- `worker/src/jobs/reporting/**` và test tương ứng

| Task | Trạng thái | Công việc | Nghiệm thu |
|---|---|---|---|
| **PH09** | `READY` | Tạo Python runtime composition: config, model port, graph, tool port, resolver và checkpointer | Có entrypoint Python; config fail-fast; không dùng model TypeScript trực tiếp trong Python; test bằng injected ports |
| **PH10** | `READY_PARTIAL` | Viết transport run/read/resume/stream với authenticated context interface | Không tin tenant/user/thread từ body; contract test request/resume; auth thật chờ Chiến |
| **PH11** | `BLOCKED_DB` | Thay SQLite local bằng PostgreSQL checkpointer cho production; lease/fencing nhiều replica | Cần `TEST_DATABASE_URL`; restart và concurrent worker test đạt; không dùng SQLite production |
| **PH12** | `READY_PARTIAL` | Event consumer + wait registry + buffered event + dedup | Có fake event-store integration test; event trước wait không mất; bus/outbox thật chờ Team 5/Chiến |
| **PH13** | `BLOCKED_API` | Nối graph + tools + backend + Supervisor thật | Chạy E2E knowledge → ticket → handoff → interrupt → resume; không production mock |
| **PH14** | `READY` | Observability và isolation | Trace có request/correlation/ticket ID đã lọc; hai tenant/thread không lẫn; không log ảnh URL/token/điện thoại đầy đủ |
| **PH15** | `READY_PARTIAL` | Report manifest, renderer/export adapter và job contract | Preview chạy bằng fixture; file có source metadata; storage/job thật chờ Chiến/Team 5 |

Phan Hoàng là đầu mối gửi contract cho Team Chiến và Team Đông, nhưng không sửa code của hai team thay họ.

## 6. Dependency liên team

| Dependency | Owner ngoài Team Hoàng | Team Hoàng làm được trước | Điều kiện tích hợp thật |
|---|---|---|---|
| API ticket/profile/triage/routing/file | Chiến | Interface, validator, fake contract test | OpenAPI/JSON Schema + auth + endpoint test |
| Schema điều phối và approval/completion | Đông + Chiến | Adapter interface và fixture | Contract version được chốt trong shared contracts |
| RAG/self-help/giá | Quang + Chiến | Port và hành vi fallback | Tool được đăng ký, có ACL/citation/version |
| PostgreSQL checkpoint/lease | Team 5 | Factory/config/migration-free adapter | DB test riêng và thông số pool/retention |
| Event bus/outbox/inbox | Chiến + Team 5 | Consumer interface, dedup/buffer tests | Event catalog và transport thật |
| S3/MinIO | Chiến + Team 5 | Chỉ truyền `file_ids` và kiểm confirmation | Upload/complete/authorize API thật |

Không đánh dấu task tích hợp là `DONE` chỉ vì fake test đạt.

## 7. Thứ tự triển khai

1. **Đường găng Reception độc lập:** PD09, DD09–DD10, PH09–PH10 và PH12.
2. **Chốt contract:** SCHEMA Reception–Supervisor mới, OpenAPI backend và event catalog.
3. **Tích hợp thật:** DD11, PH11 và PH13.
4. **Report Agent:** PD13–PD14, DD12–DD14, PH15.
5. **Hardening:** PD12, PH14 và E2E liên team.

Ba người không được cùng sửa một file trong cùng thời điểm. Thay đổi contract đi theo thứ tự: owner contract → consumer update → integration test.

## 8. Test bắt buộc trước handoff

- Python: `python -B -m pytest -q -p no:cacheprovider agent-reception/tests`
- Graph: knowledge đủ không tạo ticket; ticket tạo đúng một lần; ảnh không mất qua nhiều lượt; event sai scope bị từ chối.
- Tools: cùng idempotency key khi retry; file link confirmation; lỗi `unknown` không chạy mutation mới.
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
