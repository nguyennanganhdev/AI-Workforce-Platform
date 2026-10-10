# Bàn giao Phase B — Bùi Hữu Nghĩa

Ngày: 2026-10-10. Branch `feat/wf-builder`, baseline `818554114c0a8f72107df9625c8e4b3e21883171`.

## Kết quả và phạm vi

Hoàn thành phần độc lập của nhịp B mục 17.9: **Build capability checks/UI với fake ports**. Builder phân biệt create-only/tracking, chọn tool trong Scope, kiểm tra readiness theo protocol đã pin, đề xuất reuse/revise/resume và recheck khi xác nhận. UI có hội thoại, sửa yêu cầu, coverage, policy, blockers, reuse và xác nhận/hủy.

Policy đã theo proposal của Tiến Anh: schema_version, capabilities/event_types/required_facts không rỗng, completion_condition, boolean human_confirmation và `timeout_behavior=status_query|needs_attention`. Bỏ timeout_seconds khỏi policy; operation timeout thuộc protocol. Samples/schema Phase A của Nghĩa được cập nhật; contract chung của Anh/Chí Hoàng giữ nguyên.

Phần này phục vụ BHN-12–14 và các phần cần thiết của BHN-02/03/07/09/10/11. **Không đánh dấu hoàn thành toàn bộ BHN-01–14.** ProposalService là preview session trong bộ nhớ, bounded và scope-isolated; chưa phải durable build session BHN-01. Confirm chỉ xác nhận proposal, chưa sinh manifest/draft/eval hay publish. All-reuse trả completed_reused mà không tạo agent/group/job.

## Public exports và cách nối

`agentscope.app.workforce.builder` export:

- `RequirementExtractor`: nhận model qua existing `generate_structured_output`; dùng SystemMsg/UserMsg/AssistantMsg hiện hữu, schema validation, tối đa 3 attempts, overall deadline và giới hạn input/context. Model retry bên trong cũng bị overall deadline giới hạn. Không gọi model trả phí trong test.
- `CapabilitySelector`: RegistryPort + AsyncProtocolPort + optional injected ProtocolReadinessReader. Query theo từng capability, bounded pagination, filter availability/effect/schema; pin tool/protocol hash, kiểm tra facts/event/channel và query binding. Recheck exact snapshots trước confirm.
- `ProposalService`: prepare(scope, message, client_message_id, proposal_id?, expected_revision?), confirm(scope, proposal_id, expected_revision), cancel(scope, proposal_id). Scope phải do backend xác minh; không lấy từ extraction/UI. Idempotency conflict và revision conflict dùng error chung.
- `BuildProposal` và `ProtocolReadiness`: Builder-local view models, không phải DTO production liên module mới.

UI export `BuilderPanel` và `BuilderClient` tại `features/workforce/builder/index.ts`. Client phải được inject. Panel chỉ gửi message/IDs/revision; không gửi Scope hoặc ReuseDecision tự khai. Chí Hoàng nối client vào API/auth và root route khi endpoint sẵn sàng. Local types là projection của Builder view, không sửa shared TypeScript.

Demo/fake nằm trong `builder/tests/` của frontend và `tests/workforce/builder/` của backend. Production index không export demo hoặc fake client. UI không tạo URL SSE giả, không dùng transport conversation làm build event API.

## Output của owner khác đã tận dụng

- Chí Hoàng: canonical Scope/BusinessProfile/ToolBinding/ReuseDecision, errors và Registry/AsyncProtocol/AgentReuse ports; không sửa các contracts này.
- Đông: public AsyncToolProtocol/EventMapping và FakeAsyncProtocolPort handed-off trong test. Fake Details adapter chuyển exact-pinned config sang readiness view; không import Registry private table/service từ production Builder.
- Anh: policy JSON Schema trong phase_a_schema_bundle dùng để kiểm tra output Builder thật sự tương thích.

Business async intent/policy được đưa rõ vào BusinessProfile.required_constraints dưới marker `builder.async:` trong **preview** để provider không được bỏ qua tracking khi matching. Marker không phải vocabulary chung đã được chốt; consumer chưa có bằng chứng bao phủ policy thì revise cùng identity. Không giả định port recommend_action đủ để reuse. Chí Hoàng/Anh cần chốt typed representation trước production matching.

Chỉ gộp item có exact business profile/async requirements và cùng capability/effect; các potential duplicate có policy/coverage khác nhau bị block để làm rõ. Không match chỉ theo tên/embedding. Đây là bảo vệ proposal, không thay database uniqueness của Lifecycle.

## Kiểm tra

Từ `platform_VP/agentscope`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/workforce/lifecycle/async_evaluation -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m tests.workforce.builder.async_capabilities.export_phase_b
```

Từ frontend:

```powershell
.\node_modules\.bin\tsc.cmd -b
.\node_modules\.bin\eslint.cmd src/features/workforce/builder
node node_modules/vite/bin/vite.js --config src/features/workforce/builder/tests/vite.demo.config.mjs --configLoader native --host 127.0.0.1 --port 5175
```

Mở `/src/features/workforce/builder/tests/demo.html`. Demo có 5 kịch bản: ready, reuse, missing capability, tracking/revise, query-only unresolved. Tất cả có nhãn DEMO/FAKE, không có side effect thật.

Optional browser tests từ agentscope (cần Playwright trong môi trường test và Edge có sẵn):

```powershell
$env:BUILDER_UI_TEST_URL='http://127.0.0.1:5175/src/features/workforce/builder/tests/demo.html'
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_ui -v
```

Kết quả review lại ngày 2026-10-10: 40 Builder/Foundation tests (8 Phase A + 23 Phase B + 9 Foundation), 14 Registry protocol tests, 8 Lifecycle schema tests và 4 Edge UI tests pass: **62 Python + 4 UI = 66 tests**. TypeScript build, ESLint vùng Builder, compileall và whitespace checks pass. Browser checks gồm thao tác edit/confirm/cancel, reuse, disabled confirm với missing/query-only và mobile không tràn ngang/không lỗi JavaScript. Ảnh QA: [phase-b-ui.png](phase-b-ui.png).

Môi trường: Python 3.12, Pydantic 2.14, Node 22.18. Repo chưa có npm lockfile; chỉ cài vào node_modules bằng package-lock=false, không đổi package.json/lockfile. Black và Playwright chỉ được cài trong .venv để kiểm tra. Vite shared config gặp lỗi loader/native trên máy hiện tại; dùng owned demo config với native loader, không sửa config chung. Không có model/provider/MCP thật trong tests.

## Điểm còn mở — chuyển tích hợp

1. Query-only không có event mappings nhưng policy Anh bắt buộc event_types. Selector xác nhận channel capability riêng, rồi trả POLICY_EVENT_SEMANTICS_UNRESOLVED nếu không có metadata chứng minh policy event semantics. Không tự tạo event name; cần Anh/Đông/Chí Hoàng chốt cách biểu diễn normalized query updates. Status-query fallback đã chạy được với protocol có policy event metadata hợp lệ.
2. Canonical policy DTO/ref/hash/storage và detailed snapshot accessor chưa tích hợp. ProtocolReadinessReader là Builder-local injected boundary; test adapter không dùng làm production provider.
3. BHN-01 durable persistence, BHN-04/05 draft/manifest generation, BHN-06 KB/skill, full eval/publish/progress UI, FastAPI/root route và transactional races vẫn chưa triển khai end-to-end trong nhịp B bổ sung.
4. Phase C cần Registry/Draft/Reuse providers thật và canonical policy. Không lấy kết quả fake làm bằng chứng race safety, restart recovery hoặc production readiness.

Yêu cầu chi tiết: [INTEGRATION_REQUEST_BHN_PHASE_B.md](INTEGRATION_REQUEST_BHN_PHASE_B.md).

## Review trước bàn giao — 2026-10-10

Đã review lại implementation, hợp đồng policy của Anh, scope/reuse, capability selection và confirmation. Bổ sung 7 regression tests; từng test đã tái hiện lỗi trước sửa và pass sau sửa:

| Ca lỗi | Xử lý |
|---|---|
| Câu hỏi ở cấp ExtractionResult bị bỏ qua với intent build | Giữ câu hỏi trong proposal; chặn confirm đến khi làm rõ. |
| Gộp batch làm mất câu hỏi riêng của item trùng nghiệp vụ | Chỉ gộp khi cả clarification_questions giống nhau; trường hợp khác giữ item và yêu cầu làm rõ. |
| Tool bỏ capability nhưng giữ schema hash | Recheck required_capability trên snapshot hiện tại; refresh proposal và yêu cầu xác nhận lại. |
| Tool bị xóa giữa prepare và confirm | Chuyển LookupError thành stale decision để refresh; không nuốt lỗi phân quyền. |
| Tool truy vấn trạng thái chỉ có capability không liên quan | Yêu cầu tool read-only có capability status_query trước khi tạo binding. |
| Caller sửa dict lồng trong proposal trả về làm thay đổi session | Trả deep copy ở prepare, replay và confirm; session giữ dữ liệu riêng. |
| Tool tạo công việc chuyển thành read-only nhưng giữ hash/capability | Recheck toàn bộ binding còn bao phủ effect yêu cầu; thiếu thì refresh và block confirm. |

Các thay đổi review chỉ thuộc backend/test/handoff của Nghĩa; UI được chạy kiểm tra lại với fixtures xuất từ backend. Edge tests cần chạy ngoài sandbox vì Windows chặn tiến trình Playwright bằng WinError 5; lần chạy được cấp quyền đã pass đủ 4 test.

Kết luận: đủ bàn giao **phần Phase B độc lập của Nghĩa tại mục 17.9**, kèm các giới hạn tích hợp nêu trên. Chưa chứng minh gate MB xuyên module, production readiness hoặc hoàn thành toàn bộ BHN-01–14. Thay đổi vẫn ở working tree, chưa commit/push; khi bàn giao qua Git cần đưa đủ file mới và file đã sửa thuộc bốn vùng ownership vào commit.
