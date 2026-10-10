# Bàn giao Phase A — requirement/policy Builder

Ngày 10/10/2026; baseline đọc: `6bc7d60d1bcf0d1bf49ad9214fad22791b29c274`, branch hiện tại `devTeamDong/Nghia`. Owner: Bùi Hữu Nghĩa.

**Đã hoàn thành gói đề xuất và kiểm tra local. Chưa freeze policy liên module, chưa đạt MA.** Sau pull HEAD `a99d506`, Foundation đã có DTO/ports và export version 1; Registry/Lifecycle vẫn chưa có implementation. Xem [đối chiếu mới](PULL_UPDATE.md) và [mẫu canonical](canonical_samples.json). Không có code production nào import schema từ thư mục bàn giao này. Các DTO đã có dùng export chung; schema extraction/policy còn thiếu vẫn là đề xuất chờ owner chốt.

## 1. Artifact và phạm vi

- [builder.schema.json](builder.schema.json): JSON Schema Draft 2020-12, version đề xuất `bhn.phase-a.proposal.1`, độc lập phiên bản tài liệu 1.4.3.
- [samples.json](samples.json): request/model selection, output một agent và sáu policy khác nhau; toàn bộ ID/model/credential là fixture.
- [canonical_samples.json](canonical_samples.json): BusinessProfile/manifest/tool/protocol-ref/reuse decisions theo contract version 1 đã pull; kiểm tra bằng export thật.
- [PULL_UPDATE.md](PULL_UPDATE.md): thay đổi chữ ký/field và phần còn thiếu sau pull.
- [reuse_inventory.md](reuse_inventory.md): kết quả đọc source, cách tái sử dụng và giới hạn cần adapter.
- [builder_prompt.md](builder_prompt.md): prompt đề xuất cho bước trích yêu cầu, cùng đầu vào backend phải cung cấp.
- [test_phase_a_schema.py](../../../../../tests/workforce/builder/async_capabilities/test_phase_a_schema.py): kiểm tra schema và payload âm/dương, không chạy model/provider.
- [BHN-05](../INTEGRATION_REQUEST_BHN-05.md): model sinh và adapter Foundation.
- [BHN-12](../INTEGRATION_REQUEST_BHN-12.md): canonical policy/manifest/validation snapshot, Chí Hoàng + Tiến Anh.
- [BHN-13](../INTEGRATION_REQUEST_BHN-13.md): protocol/coverage/fake, Phương Đông.

Đây là lát cắt **một agent**. Batch là mở rộng sau, không đổi semantics identity/reuse. Phase A chưa triển khai API/UI, generate manifest, database, provider ingress hoặc workflow.

## 2. Input, output và dữ liệu do backend giữ

| Thành phần | Schema/nguồn | Quy tắc |
|---|---|---|
| Input một message build | `$defs.GenerationRequest` | Có client_message_id, expected_revision, mode=single, message và generation_model; build session lấy từ resource đã xác thực |
| Model sinh | `$defs.ModelSelection` | Dùng shape ChatModelConfig có sẵn: type/credential_id/model/parameters. ID credential legacy là opaque string; không đổi sang UUID tùy tiện |
| Output trích yêu cầu | `$defs.SingleAgentRequirements` (root) | intent=build/clarify/runtime_request, nội dung đề xuất, requirements, resource selections, câu hỏi và policy candidate |
| Model runtime đề xuất | runtime_model_option_id | Tham chiếu một lựa chọn trong danh sách backend cung cấp; backend resolve sang ChatModelConfig. null nghĩa là chưa đề xuất, cần resolve trước sinh manifest |
| Scope và authority | IdentityPort + build session | Scope đủ tenant/domain/area/manager; không nhận scope/actor từ output LLM hoặc request body |
| Snapshot phục vụ recheck | Backend | Giữ catalog revision, reuse check ID, agent catalog revision, protocol/version/hash và proposal revision; model không được tự cấp bằng chứng này |
| Draft/manifest | DraftPort + contracts | Chỉ sau kiểm tra deterministic và xác nhận; output ở đây chưa phải AgentManifest |

Lựa chọn model sinh lưu trong build session của Builder, không thêm vào AgentSpec.model_config_ref. Field canonical model_config_ref là cấu hình/tham chiếu model runtime; Builder phải validate nội dung qua adapter. Sửa lựa chọn model sinh tăng revision, không âm thầm đổi model khi retry và không sửa model của draft/agent đã có.

Intent=build chỉ nghĩa là đã hiểu yêu cầu tạo agent; không nghĩa là đủ capability, đã được xác nhận hay được phép publish. `missing_capabilities` do model nhận diện chỉ là gợi ý, backend luôn kiểm tra lại. Intent=runtime_request chỉ phân loại để UI hướng người dùng tới luồng xử lý request, không dispatch nghiệp vụ hoặc tự tạo agent.

Tên/mô tả/nhiệm vụ trong bước này là đề xuất; khi clarify hoặc phân loại runtime_request có thể để metadata chưa biết là null và requirements rỗng, không ép model bịa agent. Intent=build yêu cầu đủ các trường này. System prompt và manifest đầy đủ chỉ được generate cho create/revise sau reuse check và xác nhận; agent reuse không sinh lại prompt. Không nhân đôi BusinessProfile/AgentSpec: backend map objective/responsibilities/requirements sang DTO canonical và bổ sung input/output/business_scope/constraints/knowledge bằng dữ liệu đã làm rõ trước khi quyết định identity.

## 3. Requirement và policy đề xuất

Requirement gồm requirement_id cục bộ, capability, required, effect, tracking_goal và reason. ID này không phải UUID tài nguyên platform. `tracking_goal` mô tả **ý định**: none, create_only, until_terminal, until_user_close hoặc unspecified. Effect unknown/tracking unspecified cần clarify; không thể qua bước build đã rõ yêu cầu. Câu hỏi chỉ tập trung phần nghiệp vụ còn thiếu; không hỏi lại tài nguyên backend đã đủ dữ kiện để đề xuất.

| Policy field | Semantics |
|---|---|
| capabilities | Năng lực đã yêu cầu, phải đối chiếu coverage từ Registry; không tự cấp quyền |
| event_types | Tên event được protocol pin chấp nhận; không hardcode event theo domain |
| required_facts | Fact keys chuẩn hóa, có schema và nguồn từ tool/protocol đã xác minh |
| effect | read/write/booking/cancel theo descriptor đã kiểm tra; không theo lời LLM. Policy cấp agent dùng phân loại bảo thủ, từng call vẫn theo effect riêng; nhóm effect hỗn hợp cần owner thống nhất aggregation |
| tracking | none/provider_event/status_query/provider_event_or_status_query — cấu hình năng lực, không phải trạng thái workflow |
| completion | response_delivered, operation_accepted hoặc operation_terminal; all_of là các phép so sánh bằng trên fact đã xác minh, không phải biểu thức thực thi |
| human_confirmation | none hoặc explicit_close; tách với consent/approval trước side effect vốn do execution_policy/Execution xử lý |
| close_policy | auto_close_read_only hoặc explicit_close; side effect luôn explicit_close |
| timeout_behavior | not_applicable, needs_attention hoặc query_then_attention; query_then_attention cần status-query thật |
| max_wait_seconds | Khoảng chờ tracking tối đa; null khi không tracking. Con số 3600 trong fixture chỉ để minh họa, không mặc định production |

`operation_accepted` chỉ đáp ứng yêu cầu create-only đã được xác nhận, không khẳng định công việc bên ngoài hoàn tất. `operation_terminal` mô tả điều kiện thành công; failed/cancelled/unknown được phản ánh theo trạng thái thật của protocol, không ép thành success. Fact absent/unknown không thỏa điều kiện.

Policy tracking đã publish **không bắt runtime chờ** khi tool trả terminal đồng bộ. Runtime chọn continuation từ output đã xác minh: confirmed → xác nhận đóng; pending + coverage → chờ; unknown → reconciliation/needs_attention. HTTP 202 không phải điều kiện chọn lifecycle. Không tạo polling/SSE dependency cho tool terminal-only.

Nếu tool có thể trả pending và requirement đòi kết quả terminal, build phải kiểm tra tracking ngay cả khi đa số lần gọi trả confirmed. Nếu policy chỉ create-only được user chấp nhận thì không cam kết tracking. Provider event và status-query là hai đường thay thế; event + query fallback chỉ được ghi khi cả hai đường đã đủ capability.

## 4. Hard checks sau schema validation

JSON Schema chỉ xác minh cấu trúc và một số quan hệ nội bộ. Các kiểm tra sau thuộc Phase B/contract canonical, không được coi là đã pass từ bộ test local:

1. Resolve model/credential theo manager hiện hành, provider type khớp credential, validate parameters bằng model.Parameters; danh sách model card không phải bằng chứng credential hoạt động hoặc model được quyền dùng. Không chấp nhận secret/endpoint override từ parameters tùy ý.
2. Requirement IDs phải duy nhất; mọi covers_requirements tham chiếu ID hiện có. Resource/version phải tồn tại trong catalog của scope, còn khả dụng. Recheck schema hash/binding trước draft.
3. KB/skill chỉ là binding đúng scope/version/hash, không cấp thêm tool. Catalog text/provider notes coi là dữ liệu không tin cậy, không làm chỉ dẫn hệ thống.
4. Mọi required capability phải covered; optional thiếu được trình bày rõ, không coi complete. `MISSING_REQUIRED_CAPABILITY` khi required thiếu; giảm phạm vi cần user đồng ý và proposal revision mới.
5. Fact predicate phải nằm trong required_facts; fact type/value và event types phải được tool/protocol schema hỗ trợ. Correlation, result terminal/pending/unknown mapping, channel readiness, ordering và timeout policy được Registry xác minh.
6. Nếu requirement yêu cầu tracking/explicit close, policy không được hạ xuống create_only/auto_close; effect và policy phải phù hợp descriptor. Protocol per tool có version/hash bất biến cho validation/eval.
7. Policy-candidate null, unknown effect hoặc thông tin định danh nghiệp vụ thiếu chặn generate draft. Model runtime option phải resolve được, không lấy model sinh thay thế ngầm.
8. Reuse decisions kiểm tra lại trong đúng scope; model không quyết định authorization, business_key hoặc uniqueness. Tên/model khác không đủ tạo agent mới.

Vị trí policy đề xuất là `AgentSpec.execution_policy.async_handling` (chưa canonical). Lifecycle pin policy trong manifest hash cùng protocol snapshots/hash trong tool snapshot; đổi policy/protocol làm invalid evaluation cũ. Không sửa snapshot của version đã publish hoặc operation đang chạy.

## 5. Port call sequence và reuse

Các method đã nêu trong kế hoạch vẫn giữ tên, async và scope-first:

1. Foundation cung cấp adapter model; Builder dùng model sinh đã chọn để extract requirement.
2. `AgentReusePort.find_candidates(scope, business_profile, include_drafts=True)` và `get_candidate(scope, agent_id, version_id)` tìm toàn bộ thư viện đúng scope.
3. `RegistryPort.list_available_tools(scope, query, capabilities, cursor)` phân trang; `get_tool_snapshot(scope, tool_version_id)` lấy descriptor; `AsyncProtocolPort.get_snapshot(scope, tool_version_id)` khi tool có thể pending/requirement cần tracking.
4. Method canonical mới đã pull là `validate_capability_coverage(protocol_snapshot, required_capabilities) -> None`. Snapshot phải lấy qua get_snapshot(scope,...), không nhận từ client. Method/report richer validate_coverage ở BHN-13 vẫn chỉ là đề xuất additive, chưa callable. Builder không gọi normalize_verified_event hoặc provider ingress để thử khả năng.
5. Sau khi hiển thị và user xác nhận, `AgentReusePort.validate_decisions(scope, [business_profile], reuse_decisions, expected_catalog_revision)` và `RegistryPort.check_bindings(scope, bindings)` recheck. requirements của port canonical là Sequence[BusinessProfile], không phải dict extraction. Agent catalog revision và tool catalog revision đều là int nhưng là hai nguồn khác nhau; đặt tên rõ tại caller.
6. Reuse giữ reference, trả completed_reused; create/revise/resume đi qua `DraftPort.create_draft`/`update_draft` đúng signature mục 6.3. Batch_id không truyền ở lát cắt một agent. Lifecycle vẫn phải recheck atomic khi ghi; các check trước đó không giữ chỗ.

| Candidate | Quyết định |
|---|---|
| Same business, ready, đủ cả tracking/policy | reuse agent/version hiện có |
| Same business, draft/eval đang làm | resume draft cùng identity |
| Same business, thiếu tracking nhưng có thể bổ sung | revise cùng agent_id, xác nhận rồi tạo draft/eval mới |
| Same business, connection tắt/credential lỗi/inactive | repair, không clone |
| Uncertain hoặc policy rộng hơn yêu cầu | clarify/đề xuất revise, không âm thầm reuse quyền rộng hơn |
| Không có candidate phù hợp | create sau recheck uniqueness |

AGENT_ALREADY_EXISTS/AGENT_BUILD_IN_PROGRESS/REUSE_DECISION_STALE phải refresh đề xuất; không đổi tên/ID để retry. Không build agent chỉ để chờ một event, không tạo group/job production từ batch.

## 6. Concurrency, lỗi và retry

- Đề xuất idempotency Builder: khóa `(scope, build_session_id, client_message_id)`, hash body chuẩn hóa gồm message và generation_model. Cùng key/body trả persisted result, khác body trả 409 theo code canonical cần Foundation chốt. Auth kiểm tra trước đọc bản cũ; replay hợp lệ trước CAS revision cũ.
- Thay requirement/model hoặc xác nhận đề xuất dùng expected_revision; output đến muộn không ghi đè proposal mới. Không giữ transaction qua model call. Owner Builder triển khai lưu session; canonical lifecycle identity do Anh bảo vệ.
- Dùng fallback hữu hạn đã có trong ChatModelBase; outer Builder không bọc vòng retry vô hạn. Đề xuất ban đầu một invocation structured-output cho mỗi message, deadline/budget có giới hạn. max_retries model và tổng ngân sách qua các strategy cần adapter Foundation expose; lỗi hết budget trả lỗi rõ, không draft một phần.
- Error chung `{error: {code, message, details, request_id, retryable}}`. Code hiện có MISSING_REQUIRED_CAPABILITY và reuse errors giữ nguyên. Code mới đề xuất BUILD_MODEL_UNAVAILABLE, BUILD_MODEL_INCOMPATIBLE, BUILD_OUTPUT_INVALID, BUILD_BUDGET_EXCEEDED cần Foundation chốt; không coi đã export.
- Model invalid output không tự đổi model hoặc credential. User sửa lựa chọn bằng message/revision mới. Auth errors không retry mù; transient retry bị chặn bởi deadline/budget và idempotency.

## 7. Kiểm tra và giới hạn bằng chứng

Chạy từ `platform_VP/agentscope`, với Python có dependency jsonschema đã khai báo ở pyproject.toml:

```powershell
python -B -m unittest discover -s tests/workforce/builder/async_capabilities -p test_phase_a_schema.py -v
```

Phiên này dùng Python 3.12.10 + jsonschema 4.26.0 trong môi trường tạm `%TEMP%/wf-bhn-phase-a-venv`; không sửa dependency/lockfile của repo. Lệnh tương ứng:

```powershell
& "$env:TEMP\wf-bhn-phase-a-venv\Scripts\python.exe" -B -m unittest discover -s tests/workforce/builder/async_capabilities -p test_phase_a_schema.py -v
```

Kết quả local: 31 tests pass tại thời điểm bàn giao. Bao gồm positive payloads, scope/secret top-level injection, model-selection boundary, policy close/timeout/channel, runtime identity/endpoint rejection, clarification và single-only. Các payload không hợp lệ được tạo bằng mutation trong test để luôn có baseline dương tương ứng.

Kết quả sau pull `a99d506`: tổng 41 tests, **40 pass và 1 skip**. Mẫu DTO kiểm tra bằng canonical JSON export, không copy schema. AsyncProtocolSnapshotRef đã có Python export nhưng chưa có schema bundle, nên ca kiểm tra protocol-ref skip có lý do và đã ghi trong BHN-13.

Sau pull đã bổ sung kiểm tra mẫu DTO bằng schema canonical ở test_canonical_handoff.py; chạy cả hai file bằng pattern test_*.py. Chưa có canonical AsyncHandlingPolicy để kiểm tra policy; chưa chạy model thật, API UI, binding/scope services, reuse concurrency, budget/idempotency runtime, workflow/provider integration hoặc booking. Test schema từ chối field scope không chứng minh scope isolation của service. Parameters là shape mở kế thừa ChatModelConfig, còn cần provider validation; không tuyên bố schema loại được mọi secret lồng trong object/text.

## 8. Điểm cần owner chốt để đóng Phase A/MA

| Owner | Câu hỏi/đầu ra cụ thể | Trạng thái |
|---|---|---|
| Chí Hoàng | DTO nền đã có; còn typed policy/requirement/model sinh, errors và adapter budget/credential | Một phần đã có sau pull; BHN-05/BHN-12 cập nhật |
| Đông | Freeze snapshot/coverage signature, semantics pending/terminal và channel readiness, fake protocol đúng scope | Chờ; BHN-13 đã ghi |
| Tiến Anh | Policy snapshot/hash, semantic validation, reuse coverage và draft concurrency | Chờ; BHN-12 đã ghi |

Hoàn thành phần tự làm được của Phase A: schema proposal, samples, prompt, source inventory, tests và integration requests. Chưa nhận xác nhận từ owner; không tự ghi contract đã thống nhất. Khi có exports, đối chiếu/promote một lần, thay schema đề xuất bằng canonical reference và chạy lại cùng cases trước Phase B.
