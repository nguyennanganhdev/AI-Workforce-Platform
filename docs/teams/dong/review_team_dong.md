## 1. Kết luận 3 dòng

- **0% đủ bằng chứng nghiệm thu:** 0/8 nhiệm vụ D01–D08 được đánh dấu "Xong". Đây là tỷ lệ nghiệm thu, không phải tỷ lệ code đã viết.
- **Chưa chạy được end-to-end với LLM thật** trên bản repo này. Gọi độc lập gpt-5.6-luna thành công; chưa có đường chạy Reception → Supervisor → sub-agent → cư dân.
- **Chưa khớp team Hoàng/Lễ tân:** đã tái hiện lỗi schema V1/V2 ở cả hai chiều và lỗi nối graph với HTTP tool port.

## 2. Bảng đối chiếu phân công

Review tại dev_TeamDong, commit 13b911fb0412, ngày 01/10/2026. Không sửa source, manifest hay cấu hình repo; môi trường chạy kiểm tra và log nằm trong /tmp.

Nguồn phân công: [kế hoạch D01–D08 (line 203)](</home/dongg/Bản tải về/AI-Workforce-Platform/docs/KE_HOACH_HOAN_THIEN_5_TEAM.md:203>) và [phân công năm DEV team Đông (line 46)](</home/dongg/Bản tải về/AI-Workforce-Platform/docs/teams/dong/PHAN_CONG_NOI_BO_COORDINATION.md:46>). Tài liệu nội bộ ghi rõ việc V1 đã hoàn thành là giả định lập kế hoạch, không phải xác nhận triển khai — dòng 3.

Quy ước đường dẫn trong bảng: `C/` = agent-coordination/, `R/` = agent-reception/.

| Đầu việc | Trạng thái | Bằng chứng | Ghi chú |
|---|---|---|---|
| D01 — AgentScope: pin version, Python service, hai phiên độc lập, persistence/recovery, ADR | Dở | C/src/adapters/agentscope_adapter.py:12–13 có import AgentScope. Module integration bị skip trong log kiểm tra. | Chưa có manifest/lock, main.py, Dockerfile hoặc dependency AgentScope được pin. |
| D02 — Loader cấu hình published, supervisor template, tạo technical/service sub-agent | Chưa làm | C/src/agents/ chỉ có .gitkeep; C/src/groupchat/ports.py:20–65 mới định nghĩa ParticipantResolver bằng Protocol. | Chưa có implementation nạp release, tạo agent và bind prompt/tools/knowledge. |
| D03 — Plan/delegate, task/mailbox, kết quả và correlation | Dở | C/src/supervisor/planner.py:56–70; C/src/supervisor/service.py:611–617; test Supervisor/Room có pass. | Có logic điều phối, nhưng model, authority và agent invocation trong test dùng fake. |
| D04 — Durable run/checkpoint, interrupt/resume, fencing, callback | Dở | C/src/supervisor/ports.py:8–53; C/src/groupchat/ports.py:98–107; có test recovery pass. | Production persistence chưa được triển khai. Test dùng RAM/JSON roundtrip, không chứng minh restart process thật. |
| D05 — Human handoff, duyệt/nghiệm thu, trả Reception, reopen | Dở | C/src/supervisor/test_reception_v2.py:93–121 kiểm không phát completed sớm; C/src/supervisor/service.py:241–265 giữ gate duyệt. | Logic test chạy được, nhưng backend verification/QC/delivery là fake; giao tiếp thật với Reception đang lệch. |
| D06 — Nhiều loại sub-agent, budget/cost, evaluation trace, version rollback | Dở | C/src/groupchat/models.py:42–45 có giới hạn lượt/timeout; test giới hạn lượt pass. | Chưa có catalogue sub-agent nghiệp vụ và trace LLM thật để nghiệm thu; giới hạn lượt không đủ thay toàn bộ tiêu chí D06. |
| D07 — Nhân viên xác nhận procedure/actual cost, submit contribution có review | Chưa làm | Trong C/src/, có nhận work.completed/actual_cost tại adapters/backend/messages.py:162–163; chưa có flow contribution/procedure-learning. | Nhận chi phí trong payload chưa đáp ứng quy trình yêu cầu nhân viên ghi, xác nhận và submit contribution. |
| D08 — Nạp Report release, bind tool grants, chạy AgentScope trong groupchat BQL | Chưa làm | agent-report/ có template/prompt/schema, nhưng C/src/agents/ chưa có loader; adapter AgentScope từ chối mọi registered tool tại dòng 60–67. | Chưa có đường thực thi Report bằng Coordination. |

Đối chiếu owner theo phân công nội bộ:

| Đầu việc / owner | Trạng thái | Bằng chứng | Ghi chú |
|---|---|---|---|
| DEV-1 — Tiến: chia việc/chọn lượt, phương án, duyệt, tổng hợp; chuyển Supervisor sang V2 | Dở | C/src/supervisor/planner.py:50; service.py:373; reception_flow.py:12; test Supervisor pass. | Chưa nối model và backend thật. |
| DEV-2 — Tiến Anh: phòng, Task Board, Mailbox, Context Builder, @agent, AgentScope | Dở | C/src/groupchat/room.py:60; context_builder.py:32; adapter AgentScope có code; 6 contract test fail. | Chưa có loader/provider production; schema đã công bố lệch model. |
| DEV-3 — Nghĩa: gateway Reception/backend, approvals, assignment, tools, V2 hai chiều | Dở | C/src/adapters/reception/reception_gateway.py:20; backend/reception_client.py:25; adapter test pass. | URL mapping, credential/delegation và backend validator production chưa được ghép. |
| DEV-4 — Huy: lưu bền vững, restart, hai tiến trình, migration checkpoint V1/V2 | Chưa làm phần adapter production | C/src/persistence/ không có source implementation; tests/support/state_fake.py:9 dùng RAM. | Không có bằng chứng kill/restart hoặc hai process dùng storage thật. |
| DEV-5 — Khánh Duy: service entrypoint, cấu hình/model/auth, manifest/lock/deployment, contract và E2E | Dở | Có tests và schema local; thiếu src/main.py, src/config.py, manifest/lock/Dockerfile/README của Coordination. | Các thành phần chưa được ghép thành dịch vụ chạy được. |

**Bằng chứng chạy:**

- Coordination: [294 pass, 6 fail, 1 module skip](/tmp/cai-dong-review-coordination-runner.log).
- Reception Python: [332 pass, 5 fail](/tmp/cai-dong-review-reception-py-tests.log).
- Reception TypeScript: [25 pass, 0 fail](/tmp/cai-dong-review-reception-ts-tests.log).
- [Inventory phần còn thiếu](/tmp/cai-dong-review-inventory.log).

Coordination chưa pin dependency; lượt kiểm tra dùng Python 3.14.4, Pydantic 2.13.5, pytest 9.1.1. Lệnh pytest thông thường bị lỗi import namespace adapters; kết quả 294/6 được chạy qua runner có sẵn trong repo, tests/supervisor/run_tests.py.

## 3. Kết quả kiểm tra flow a–g

### a. Framework — Không đạt tiêu chí nghiệm thu AgentScope 2.0

Có import và gọi SDK thật trong [agentscope_adapter.py (line 12)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/adapters/agentscope_adapter.py:12>), gồm session.agent.reply(...) tại dòng 123. Tuy nhiên:

- Coordination chưa có requirements/manifest/lock để xác nhận version 2.0.
- Môi trường ban đầu không có AgentScope; module integration dùng pytest.importorskip, nên bị skip.
- Các nơi khởi tạo AgentScopeAdapter và SupervisorService tìm được nằm trong tests, chưa có production composition.

Framework khác còn trong repo: LangGraph, AG2, Agno, CrewAI, ADK, Langroid, LlamaIndex, Microsoft Agent Framework, PydanticAI, Strands, Claude SDK và Mastra — thể hiện trong manifest của các folder agent-*.

Riêng Reception dùng LangGraph đúng theo phân công, không phải bằng chứng dùng sai framework. agent-ag2 import ag2, không phải AgentScope: agent-ag2/src/main.py:5.

### b. Endpoint — Không đạt

Trong agent-coordination/src/, chưa có HTTP server/route registration hoặc entrypoint. Vì vậy, chưa có endpoint HTTP inbound của team Đông để gọi.

Các tên sau hiện là operation của client, chưa phải URL endpoint đã được ghép:

- reception.verify, reception.send
- reception.ticket, reception.message, reception.question, reception.update
- approval.request, approval.respond
- completion.request, completion.respond
- assignment.offer, assignment.respond, work.complete

Nguồn: C/src/adapters/backend/reception_client.py:47,63, approval_client.py:19–31, reception_gateway.py:93–106, tool_client.py:29–38. BackendClient yêu cầu inject mapping operation → URL; thiếu mapping trả operation_not_configured tại dòng 93/118. Tài liệu phân công chưa cung cấp danh sách URL cụ thể để so đủ từng endpoint.

Đã khởi động Reception entrypoint thật, dùng source sao chép nguyên trạng và lockfile trong /tmp, rồi gửi request HTTP:

| Request | Status | Response |
|---|---|---|
| GET /health | 200 | {"status":"ok"} |
| POST /health | 404 | Not Found |
| POST /run | 404 | Not Found |
| GET /read | 404 | Not Found |
| POST /resume | 404 | Not Found |
| POST /ag-ui | 404 | Not Found |

Các đường nghiệp vụ trên là probe, không được khai báo là endpoint hiện có. [Log HTTP](/tmp/cai-dong-review-runtime.log); source [health.ts (line 4)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-reception/src/adapters/transport/health.ts:4>) chỉ mount GET /health.

### c. LLM — Không đạt yêu cầu "mọi agent dùng gpt-5.6-luna"; kết nối độc lập đã đạt

Cấu hình Reception:

- Model mặc định gpt-5.5, không phải model yêu cầu: [config.ts (line 11)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-reception/src/config.ts:11>).
- Đọc model từ RECEPTION_MODEL, key từ OPENAI_API_KEY: dòng 53–66.
- Factory tạo ChatOpenAI: [factory.ts (line 22)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-reception/src/adapters/model/factory.ts:22>).
- Base URL hiệu lực trong lượt chạy: https://api.openai.com/v1 — [log cấu hình đã che key](/tmp/cai-dong-review-model-config.log).

Đã dùng factory hiện có, override model trong harness kiểm tra sang gpt-5.6-luna, gửi request thật. Trích log:

```
request:
  model: gpt-5.6-luna
  message: Reply with the word CONNECTED only.
  apiKey: [REDACTED]
response:
  content: CONNECTED
  model_name: gpt-5.6-luna
  finish_reason: stop
  input_tokens: 14
  output_tokens: 4
```

[Log request/response](/tmp/cai-dong-review-runtime.log).

Đây không phải lượt chạy Supervisor. Coordination mới có ModelClient Protocol tại C/src/supervisor/ports.py:56, chưa có provider implementation/configuration được ghép vào production. Không thể xác nhận mọi agent gọi model thật.

### d. Supervisor routing — Chưa kiểm chứng bằng LLM thật

Planner gọi `await self.client.generate(prompt)` rồi validate quyết định tại [planner.py (line 67)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/supervisor/planner.py:67>). Prompt có schema, state và catalogue agent; source này cho thấy thiết kế chọn agent qua model. Các if/elif trong validator/state machine kiểm điều kiện thực thi; chưa thấy chúng được dùng để chọn chuyên môn bằng keyword trong phần Supervisor đã đọc.

Tuy nhiên, test inject model trả JSON từ danh sách có sẵn: C/tests/supervisor/conftest.py:107–118. Chưa chạy được ba tình huống bằng Supervisor production + LLM thật, vì thiếu model client, catalogue và agent provider production. Không có trace thật để kết luận routing đạt.

### e. Sub-agent — Không đạt

Chưa có implementation loader hoặc cấu hình sub-agent nghiệp vụ kỹ thuật/an ninh/vệ sinh/kế toán trong C/src/agents/; folder chỉ có .gitkeep.

Participant giữ ID và framework reference (C/src/groupchat/models.py:53–59), nhưng chưa thay thế việc tạo agent với system prompt, tools và knowledge.

Các agent đã chạy trong test là A-v1/B-v1/C-v1; test SDK tạo agent với system prompt `Test only` và StubModel: C/tests/integration/test_agentscope_adapter.py:64–73. Không phải sub-agent Vinhomes được nghiệm thu.

### f. Openbot — Không đạt phần kết nối; lời gọi xuyên đường nối chưa kiểm chứng

Openbot có agent HTTP AG-UI: [agent-bot/src/index.ts (line 249)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-bot/src/index.ts:249>) nhận POST /ag-ui, kiểm managed-agent token, rồi xử lý RunAgentInput.

Coordination hiện nhận in-process AgentScope Agent qua AgentSessionProvider; chưa có production adapter chuyển invocation sang AG-UI và xử lý stream/result/cancel.

Thiếu đường nối cụ thể gồm: endpoint mapping, credential provider, chuyển Invocation sang RunAgentInput, decoder stream, task/run correlation và cancel/reconciliation. Không có request/response thật qua Supervisor → Openbot để trích.

### g. Tools/dữ liệu — Chưa kiểm chứng hệ thống thật

- Có HTTP transport thật: C/src/adapters/backend/http_transport.py:24–37. Test loopback pass, nhưng phía server loopback là test handler, không phải backend nghiệp vụ.
- ToolClient chuyển command qua backend; allowlist mặc định rỗng: C/src/adapters/tools/tool_client.py:24,40–44.
- AgentScope adapter hiện từ chối registered tools/MCP/skills: dòng 60–67. Đây là điểm chặn technical/report agent gọi tool.
- Team Quang có adapter truy vấn DB cho SOP/work-order và các adapter PoC RAM; chưa có bằng chứng chúng được bind và gọi từ Supervisor thật.

Không có tool nào được xác nhận đã gọi hệ thống nghiệp vụ thật trong flow đang review.

## 4. MOCK PHÁT HIỆN

| Vị trí | Mock/stub/hard-code kiểm chứng được |
|---|---|
| C/tests/integration/test_agentscope_adapter.py:25–55 | StubModel, model test-no-network, trả JSON cố định. |
| C/tests/integration/test_agentscope_adapter.py:64–73 | Agent dùng prompt Test only, không phải prompt nghiệp vụ. |
| C/tests/supervisor/conftest.py:27–49 | Store bằng RAM; JSON roundtrip được ghi rõ không chứng minh process durability. |
| C/tests/supervisor/conftest.py:54–118 | Authority/verifier/model fake; model lấy quyết định từ outputs.pop(0). |
| C/tests/supervisor/conftest.py:121–141 | Validator pass; transport tự trả HTTP 202/accepted. |
| C/tests/support/fakes.py:15,66–113 | Resolver/agent fake; câu trả lời agent tạo bằng chuỗi cố định. |
| C/tests/support/state_fake.py:9–20 | Room state bằng dict và process-local lock, không durable. |
| C/tests/adapters/reception/support.py:44–123 | Auth proof test; V2Transport mô phỏng backend approval, QC và dedup. |
| C/tests/supervisor/test_reception_v2.py:30–73 | Reception verification/delivery và authority projection fake. |
| R/tests/graph/workflow_fixture.py:79–88,124–139 | ScriptedModel, InMemorySaver, ticket/profile/tools synthetic. |
| R/tests/tools/test_adversarial.py:45–70 | Backend HTTP dùng httpx.MockTransport; lỗi response-loss được mô phỏng. |
| C/src/supervisor/reception_flow.py:99; service.py:270 | Lời đáp ứng dụng hard-code: "Yêu cầu đã được tiếp nhận", "Công việc đang được triển khai…". |
| R/src/graph/workflow.py:808,1168–1175 | Lời đáp trạng thái hard-code; không thể dùng chúng làm bằng chứng model đã suy luận/xử lý công việc. |
| server/src/technical-tools/adapters/poc/sensor-read.ts:13; vendor-catalog.ts:11 | Nguồn sensor/vendor RAM; mặc định rỗng, chưa phải feed BMS/IoT/catalog thật. |

Trong C/src/ và R/src/ đã tìm không thấy nhánh bật mock bằng biến MOCK. Điều này không loại bỏ các fake được inject trong tests nêu trên.

## 5. Điểm lệch với team khác

### Lệch 1 — Lễ tân gửi V1, Đông nhận V2: đã chạy tái hiện

- **Hoàng:** [workflow_validation.py (line 243)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-reception/src/graph/workflow_validation.py:243>) tạo schema_version="1.0", thiếu message_type/message.
- **Đông:** [groupchat/reception.py (line 49)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/groupchat/reception.py:49>) yêu cầu V2 và hai trường đó.

Kết quả chạy hàm thật với fixture:

```
schema_version: literal_error
message: missing
message_type: missing
```

**Đề xuất:** Hoàng chuyển business graph sang V2 đã chốt trong spec; Đông giữ việc từ chối V1 có kiểm soát.

### Lệch 2 — Đông phát V2, Lễ tân đọc output V1: đã chạy tái hiện

- **Đông:** C/src/supervisor/reception_flow.py:19–25 phát message_type/message.
- **Hoàng:** R/src/graph/workflow_validation.py:358–378 chỉ nhận 1.0, đọc status/customer_message; workflow.py:804–829 xử lý các field cũ.

Kết quả: GraphFault INVALID_WORKFLOW_OUTPUT. [Log cả hai chiều](/tmp/cai-dong-review-contracts.log). Phép kiểm dùng source thật và dữ liệu synthetic, không được tính là E2E.

**Đề xuất:** Hoàng cập nhật parser, branches hỏi/duyệt/hủy và output contracts sang V2.

### Lệch 3 — Graph Lễ tân không gọi được HTTP tool port hiện có

- Graph gửi timeoutMs và signal: R/src/graph/workflow.py:1183–1202.
- HTTP port validate bằng CallEnvelope chỉ nhận operation/input/context/idempotencyKey: R/src/tools/validation.py:83–87.
- Contract dùng extra="forbid": R/src/tools/contracts.py:69–76.

Test thật `test_existing_graph_can_reach_http_with_new_backend_port` fail với:

```
phase: waiting_operation
pending: create_ticket_draft
http_calls: 0
```

Ngoài envelope, handoff_ticket của graph gửi full V1 message, trong khi HandoffInput mới nhận ticket reference/correlation/reason để backend tạo V2 (tools/contracts.py:162–166).

**Đề xuất:** Hoàng cung cấp adapter composition xử lý budget/cancellation và migrate input của graph sang contract tool mới.

### Lệch 4 — Schema phòng đã công bố lệch source Đông

- Source có Command.type: C/src/groupchat/models.py:210.
- Source có Context.initiated_by_user_id: dòng 22.
- JSON Schema công bố thiếu các field này.

Đã xác định diff bằng code và chạy 6 test fail; ba test runtime schema báo `Additional properties are not allowed ('type' was unexpected)`. [Log](/tmp/cai-dong-review-coordination-runner.log).

**Đề xuất:** Đông xác định contract chuẩn rồi cập nhật đồng bộ model/schema/examples.

### Lệch 5 — Retry của Hoàng trả sai trạng thái sau mất phản hồi

R/src/tools/backend.py:77–90 giữ response 503 lần trước; nếu lần cuối mất response, code vẫn decode response cũ.

Bốn test fail: kết quả not_applied, mong đợi unknown. [Test nguồn:45 (line 45)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-reception/tests/tools/test_adversarial.py:45>).

**Đề xuất:** Hoàng sửa việc xác định outcome theo lần thử cuối; không dùng response cũ để kết luận mutation chưa áp dụng.

**Auth, mã lỗi và thứ tự gọi trên hệ thống thật: CHƯA KIỂM CHỨNG.** shared/contracts/ mới có .gitkeep; credential/delegation/verifier/authority production chưa được ghép. Không đủ bằng chứng xác nhận ba phía thống nhất các phần này.

## 6. Việc còn thiếu, theo ưu tiên

Ước lượng dưới đây là người-ngày sơ bộ, không phải thời gian đã đo; chưa bao gồm việc xây backend dependency còn thiếu.

| Ưu tiên | Việc cần hoàn thành | Owner theo phạm vi | Công sức |
|---|---|---|---|
| Chặn demo | Đồng bộ business graph/parser/tool inputs của Reception sang V2; thêm producer–consumer contract test | Hoàng + Đông DEV-3/DEV-5 | 1–2 ngày |
| Chặn demo | Ghép Coordination entrypoint, pin AgentScope, cấu hình gpt-5.6-luna, model client, auth và deployment | Đông DEV-5 | 1–2 ngày |
| Chặn demo | Loader agent published; provider thật; nối Openbot/tools có grant, request/result/cancel correlation | Đông DEV-2/DEV-3 + Chiến/Quang | 2–4 ngày |
| Chặn demo | Production StateStore/RoomState; kiểm kill/restart và hai process dùng storage thật | Đông DEV-4 + Chiến/Team 5 | 2–4 ngày |
| Chặn demo | Sửa schema phòng lệch source và lỗi retry not_applied/unknown | Đông DEV-2/DEV-5; Hoàng | 0,5–1 ngày |
| Chặn nghiệm thu | Chạy ba tình huống LLM thật, flow liên team, approvals/QC/cost, trả cư dân; lưu trace đã che key | Đông DEV-5 + Hoàng/Chiến | 1–2 ngày sau khi ghép xong |
| Quan trọng | Migration checkpoint V1/V2; stale version/generation, duplicate và restart thật | Đông DEV-4/DEV-5 + Hoàng | 1–2 ngày |
| Quan trọng | D07: staff contribution procedure/chi phí và review workflow | Đông + Chiến/Quang | 2–3 ngày |
| Quan trọng | D08: Report release/tool grants chạy trong AgentScope groupchat | Đông + Hoàng | 2–4 ngày |
| Nên có | Token/cost budget, evaluation trace, rollback/version tests cho D06 | Đông + Team 5 | 1–2 ngày |

Các log pass hiện tại chứng minh nhiều logic nội bộ đã hoạt động. Chúng chưa đủ để đánh dấu flow Vinhomes hoặc phần việc team Đông là hoàn thành.

## Nên làm gì

Team Đông cần ưu tiên ghép các module hiện có thành một dịch vụ chạy thật, rồi nối model, backend và sub-agent. Chưa cần viết lại Supervisor hay Groupchat.

Plan này giữ nguyên schema Reception ↔ Supervisor V2 đã chốt trong [tài liệu giao tiếp (line 127)](</home/dongg/Bản tải về/AI-Workforce-Platform/docs/SCHEMA_RECEPTION_SUPERVISOR_V1.md:127>). Không giao việc sửa Reception của Hoàng; phía Đông nhận đúng V2, trả đúng V2 và từ chối dữ liệu sai schema.

Mục tiêu nghiệm thu là:

> Một ticket V2 đi vào Coordination → Supervisor dùng gpt-5.6-luna chọn agent → gọi sub-agent Openbot → chạy tool được cấp quyền → nhận kết quả → qua các bước duyệt/nghiệm thu áp dụng → phát output V2.

### 1. Khánh Duy — Ghép Coordination thành dịch vụ chạy được

Đây là việc mở đường cho cả nhóm. Hiện các nơi khởi tạo SupervisorService tìm được vẫn nằm trong tests.

Cần làm:

- Tạo src/main.py, src/config.py, manifest Python, lockfile, Dockerfile và hướng dẫn chạy trong agent-coordination/.
- Pin phiên bản AgentScope đã kiểm chứng, chạy được các import và adapter hiện có. Không chọn version chỉ theo tên "2.0".
- Ghép SupervisorService, Planner, RoomService, ReceptionGateway, backend clients, model client và persistence implementations.
- Mount health/readiness, đầu vào Reception V2 và đầu vào backend events. URL transport phải thống nhất với backend Chiến; không thay đổi payload Reception đã chốt.
- Đầu vào được xác thực và lưu bền vững trước khi xác nhận tiếp nhận; xử lý dài chạy qua worker, không giữ request HTTP chờ cư dân duyệt.
- Readiness phải phản ánh các dependency cần thiết; không trả "ready" chỉ vì mở được cổng.

**Nghiệm thu:** từ checkout sạch, một lệnh khởi động được service; gửi request HTTP V2 thật tới service và thấy ticket/run được lưu. Không khởi tạo service bằng fixture của tests.

**Ước lượng:** 1–2 người-ngày cho bộ khung và composition, sau đó ghép dần adapter của các DEV.

### 2. Nghĩa — Hoàn thiện đường Reception ↔ Đông ↔ backend

Giữ và sử dụng [ReceptionGateway hiện có (line 20)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/adapters/reception/reception_gateway.py:20>), không thêm lớp đổi V1 thành V2.

Cần làm:

- Cung cấp mapping operation → URL thật cho BackendClient. Hiện tên như reception.verify, reception.send, approval.request mới là operation, chưa được ghép thành đường gọi production.
- Implement service credential provider và bằng chứng nguồn/delegation mà backend kiểm được.
- Nối verification vào handle_reception; chỉ đưa snapshot đã xác minh vào Supervisor.
- Nối output Supervisor qua ReceptionGateway.send, để backend kiểm quyền/lưu/delivery.
- Nối các operation phục vụ flow: duyệt quản lý, giao việc, nhận kết quả, kiểm tra/nghiệm thu, tra kết quả thao tác khi mất response.
- Bảo toàn message_id, correlation_id, ticket version/generation và các ID thao tác khi gửi lại.
- Giữ đúng nguyên tắc V2: completed chưa đồng nghĩa đóng ticket; xác nhận hoàn thành/đóng/mở thuộc backend.

**Nghiệm thu:** request thật qua backend thật có log status, receipt và correlation; phản hồi sai version/generation bị chặn; gửi lặp không tạo hành động mới.

Đông có thể hoàn thành contract tests bằng payload V2 chuẩn mà không chờ Hoàng sửa code. Tuy nhiên, phép kiểm đó chỉ nghiệm thu phía Đông; chưa được gọi là luồng liên team thật.

**Ước lượng:** 1–2 người-ngày nếu các API backend cần dùng đã có.

### 3. Tiến Anh — Loader agent và adapter gọi sub-agent Openbot

Hiện AgentInvocationPort đã có ranh giới phù hợp để nối remote agent. Cần bổ sung implementation, không để test FakeAgents là đường chạy duy nhất.

Cần làm:

- Implement loader/resolver lấy agent release đã publish và được cấp quyền từ Platform/backend.
- Nạp đúng version, vai trò, mô tả năng lực, prompt, tool grants và knowledge grants. Supervisor cần biết agent làm được gì để chọn theo LLM.
- Mapping agent → runtime/endpoint phải đến từ cấu hình đã xác minh; model không được tự cung cấp URL.
- Tạo adapter AG-UI thực hiện:
  - Chuyển Invocation thành request Openbot.
  - Gắn thread/run IDs và token đúng scope.
  - Đọc SSE, phân biệt RUN_FINISHED, RUN_ERROR, mất stream và timeout.
  - Chuyển kết quả về AgentOutput, giữ task/run correlation.
  - Không coi HTTP 200 hoặc câu "đã hoàn thành" trong text là bằng chứng công việc thành công.
- Isolate thread/context theo ticket, generation và agent instance.
- Cancel chỉ được xác nhận khi có bằng chứng terminal; mất kết nối phải giữ trạng thái chưa rõ kết quả khi cần.

Chọn đường Openbot phù hợp với model yêu cầu: code agent-bot hiện chủ động từ chối gpt-5.6-*; agent-langgraph có nhánh dùng Responses API tại [index.ts (line 88)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-langgraph/src/index.ts:88>). Nên kiểm chứng đường này cho kết nối đầu tiên.

agent-langgraph còn gọi tool ngược về deployment qua OPENBOT_TOOL_URL, AGENT_TOOL_TOKEN và run assertion. Vì vậy, nối /ag-ui thành công chưa đủ: phải nối cả đường callback tool được xác thực.

**Nghiệm thu:** RoomService gọi một sub-agent Openbot thật, nhận terminal/result thật; hai ticket không dùng chung lịch sử. Có ít nhất một tool call xuyên đường backend thật.

**Ước lượng:** 2–3 người-ngày, phụ thuộc API agent release và cơ chế cấp credential/run assertion.

### 4. Tiến — Supervisor dùng LLM thật để chọn agent và lập phương án

Giữ Planner và state machine hiện có. [Planner đã gọi `ModelClient.generate` (line 67)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/supervisor/planner.py:67>); phần thiếu là implementation và cấu hình production.

Cần làm:

- Implement ModelClient thật, ghép vào runtime AgentScope/Supervisor.
- Cấu hình rõ gpt-5.6-luna, base URL, secret reference/API key và timeout; kiểm tra cấu hình lúc startup.
- Đưa catalogue năng lực đã xác minh vào prompt để model chọn agent, không chỉ đưa các ID khó hiểu.
- Validate quyết định theo schema và catalogue; model chỉ đề xuất, backend vẫn giữ quyền duyệt/giao việc/nghiệm thu.
- Kiểm tra cách xử lý repaired output để không phát sinh side effect trước khi quyết định hợp lệ.
- Ghi trace: model thực tế, request ID, quyết định, agent được chọn, task/run IDs, tool calls, token usage và trạng thái cuối. Che key và dữ liệu nhạy cảm.
- Nối kết quả sub-agent vào Task Board và bước tổng hợp; không dùng câu trả lời mẫu thay kết quả.

Chạy ba tình huống tối thiểu:

1. Rò nước → agent kỹ thuật.
2. Sự cố an ninh → agent an ninh.
3. Yêu cầu vệ sinh → agent dịch vụ/vệ sinh.

Các agent phải có cấu hình/năng lực thật; không chỉ đổi tên A-v1/B-v1.

**Nghiệm thu:** cả ba tình huống có trace request/response LLM thật và quyết định chọn agent phù hợp. Kiểm riêng trường hợp hỏi thêm, agent lỗi và chi phí chưa xác định.

**Ước lượng:** 1–2 người-ngày sau khi có catalogue và invocation adapter.

### 5. Huy — Persistence thật để resume an toàn

Các test recovery hiện dùng RAM/JSON roundtrip. Cần implement các port đang để trống:

- StateStore: lưu Supervisor state, journal, receipt và dedup.
- RoomStatePort: lưu room, tasks, mailbox, active operation và fence.
- Framework session state/reference theo ticket/generation/member.
- Lock/CAS/lease dùng storage bền vững để hai worker không cùng dispatch một thao tác.
- Lookup/reconciliation cho thao tác đã gửi nhưng mất response.
- Khôi phục yêu cầu đang chờ với nguyên ID/nội dung/version.
- Đường xử lý checkpoint V1: migrate khi đủ bằng chứng hoặc từ chối có kiểm soát, không tự reset.

Storage phải theo ranh giới đã thống nhất với backend Chiến; Đông không tự tạo thêm nguồn trạng thái ticket chính thức.

**Nghiệm thu:** kill/restart process ở ba điểm: chờ duyệt, sau gửi request nhưng mất response, đang chạy agent. Chạy hai worker cùng nhận một event và chứng minh không double-dispatch.

**Ước lượng:** 2–4 người-ngày, phụ thuộc storage/API runtime.

### 6. Khánh Duy phối hợp cả nhóm — Tool binding và kiểm thử tích hợp

Hai việc phải làm rõ trước khi gọi là flow thật:

- Adapter AgentScope hiện từ chối mọi registered tool/MCP/skill tại [agentscope_adapter.py (line 60)](</home/dongg/Bản tải về/AI-Workforce-Platform/agent-coordination/src/adapters/agentscope_adapter.py:60>). Phải chọn rõ agent nào dùng runtime local, agent nào dùng Openbot remote, rồi bind tool bằng grant của đường tương ứng. Không chỉ bỏ check này để "cho chạy".
- Sửa lệch JSON Schema phòng với model đang dùng; đưa sáu contract test đang fail về pass. Chốt một lệnh chạy test chung, xử lý lỗi namespace import hiện tại.

Tiến hành nghiệm thu theo ba mức:

- **Mức 1 — Đông sẵn sàng:** service HTTP, model thật, storage thật, output V2 đúng schema.
- **Mức 2 — Đông + Openbot + backend:** Supervisor chọn agent, tool thật chạy, kết quả được lưu/tổng hợp, approval/QC được backend kiểm.
- **Mức 3 — liên team:** Reception Hoàng gửi V2 thật và nhận output V2 thật. Chỉ chạy mức này khi bên Hoàng đáp ứng schema cố định; lỗi phía Hoàng không trở thành task sửa của Đông.

Mỗi mức có log riêng. Những bài dùng synthetic Reception hoặc fake backend phải ghi rõ, không cộng vào bằng chứng E2E thật.

## Thứ tự triển khai đề xuất

- **Đợt 1:** Khánh Duy mở service; Nghĩa nối backend; Tiến Anh làm loader/AG-UI; Huy làm persistence. Tiến chuẩn bị model client và catalogue đầu vào.
- **Đợt 2:** ghép một đường chạy hoàn chỉnh cho sự cố rò nước, có kỹ thuật và chi phí/phê duyệt theo quy định.
- **Đợt 3:** thêm hai tình huống routing, restart/concurrency, lỗi/timeout/cancel và nghiệm thu liên team.

Mốc đầu tiên nên là một flow rò nước chạy thật, không mở rộng đồng thời Report agent hay toàn bộ D07. D07/D08 vẫn là đầu việc còn lại, đưa vào đợt sau khi đường thực thi chung đã được nghiệm thu.
