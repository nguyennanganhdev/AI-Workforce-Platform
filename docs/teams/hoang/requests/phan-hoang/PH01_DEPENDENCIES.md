# PH01 — Request review và dependency C01/C06/P01

Owner yêu cầu: Phan Hoàng. Ngày: 30/09/2026.
Trạng thái: bản yêu cầu trong repo, **chưa có xác nhận/gửi ngoài repo**.
Request được cập nhật Markdown theo yêu cầu người dùng để phản ánh graph PD Python;
không sửa runtime/contracts/package của owner khác hoặc tự đóng dependency.

## PD01 / DD01 — chốt port nội bộ

Người review: Phan Dũng, Dương Dũng. Nguồn:
[type proposal](../../../../../agent-reception/src/contracts/index.ts),
[semantic](../../integration/PH01_CONTRACTS.md).

- TS proposal trên vẫn `0.1.0-draft.1`, thuộc PH01 và được giữ nguyên. PD01–PD08 đã
  có Python consumer code/tests, contract `0.1.0-python.draft.1`; Python không import
  hoặc conform trực tiếp `ReceptionGraphFactory<State, Operations>` TypeScript.
- Review Python factories tại [graph public API](../../../../../agent-reception/src/graph/__init__.py):
  `create_reception_graph_factory(ReceptionFactoryOptions(...))` và
  `create_reception_workflow_factory(WorkflowOptions(...))`.
  Composer inject `GraphDependencies(model, tools, checkpointer)`; async
  `run/read/resume`, async iterator `stream`, business graph có thêm `recover`.
- Python protocols/input TypedDict nằm trong
  [workflow_contracts.py](../../../../../agent-reception/src/graph/workflow_contracts.py).
  Model dùng `ainvoke(messages)`; tools dùng `async invoke(request)`; policy dùng
  `evaluate_policy`/`search_knowledge`, session resolver dùng `resolve_session`.
  Checkpointer phải là LangGraph Python async-compatible, không dùng TS saver trực tiếp.
- DD01 chốt operation catalog/decoder/backend thật và bridge hoặc Python bindings.
  Wire JSON giữ context/message/event và `idempotencyKey`/`timeoutMs`; Python signal
  là CancellationToken/task cancellation, không serialize AbortSignal qua process.
  Giữ accepted/success/unknown/not_applied semantics; không lấy identity từ model.
- Fixtures PH TypeScript tại `tests/support/fakes.ts` vẫn chỉ phục vụ PH tests.
  Fixtures PD Python tại [workflow_fixture.py](../../../../../agent-reception/tests/graph/workflow_fixture.py)
  và [test_factory.py](../../../../../agent-reception/tests/graph/test_factory.py)
  chỉ tổng hợp, chưa freeze với backend; không đưa test model/ports/InMemorySaver vào production.
- Test mong đợi: producer/consumer compatibility qua boundary thật, invalid input/response bị từ chối;
  accepted không thành completed; timeout không tạo mutation thứ hai với key mới.
- Đang chặn: freeze/commit interface và integration graph/tool thật. PH01 unit/capability
  test có thể tiếp tục độc lập, không coi mock là backend integration.

PH03 chốt Python checkpoint namespace/migration/retention: generic marker
`pd01-python-1`, business marker `pd-workflow-python-1`, schema envelope 1.
Python từ chối checkpoint TS/topology khác, không reset hoặc migrate tự động.
Thread codec là compact JSON tuple `[namespace, threadId]`, root checkpoint_ns rỗng.
PH/Team 5 chốt process/service bridge hoặc Python composition để platform TS gọi
graph; chưa có transport/deployment thật. Chi tiết:
[PYTHON_RUNTIME_INTEGRATION](../phan-dung/PYTHON_RUNTIME_INTEGRATION.md).

## C01 / C06 — hợp đồng backend và binding

Owner cung cấp: Chiến. Xin schema/version/fixtures chính thức cho port tương đương
`resolveAuthorizedReceptionContext`, resolve framework binding và service auth;
**đây là tên nhu cầu, chưa phải endpoint hoặc API đã tồn tại**.

Input cần chốt: service token đúng audience/expiry, operation read/run/resume/cancel,
opaque session/binding reference và correlation/request ID. Identity/tenant/quyền
được server resolve từ authenticated context, không tin ID tự nhận từ browser.

Output cần chốt: execution principal, initiating user, tenant, binding/run ID,
permissions, mapping framework thread/namespace chỉ phía server, contract version;
typed errors không lộ tài nguyên khác user và không chứa token/PII.

Auth/idempotency/error semantics cần chốt: quyền mới bị revoke, token hết hạn,
cross-tenant/user, stale binding/generation, key dedup cho start/resume/cancel,
lease/fencing và truy hồi mutation chưa rõ kết quả. Event schema C01/C08 cần có
source verification, event ID, aggregate version, ticket/generation và interrupt.

Fixture/test mong đợi: hai user cùng tenant, hai tenant, một user hai ticket;
user B read/resume binding A bị từ chối; duplicate/out-of-order event không resume
sai; timeout dùng lại key; revoke có hiệu lực trước read/run/resume.

Đang chặn: PH02 auth/binding và PH03 durable recovery. `shared/contracts/` hiện
chỉ có `.gitkeep`; không tự tạo platform DTO trong Reception để thay thế C01.

## P01 — toolchain và CI runtime riêng

Owner cung cấp: Team 5. Package Reception độc lập, `packageManager: bun@1.3.14`,
direct dependencies pin exact, `bun.lock` riêng. Xin CI chạy từ `agent-reception/`:

```sh
bun install --frozen-lockfile --ignore-scripts
bun run test
bun run typecheck
```

Các lệnh Bun trên chỉ kiểm tra runtime/adapters/contracts TypeScript còn lại;
không chạy graph/evals/report Python. Team 5 cần thêm job Python từ repo root:

```sh
python -B -m pytest -q -p no:cacheprovider agent-reception/tests/graph agent-reception/tests/evals server/tests/reporting/narrative
python -B -m ruff check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
python -B -m ruff format --check agent-reception/src/graph agent-reception/src/prompts agent-reception/tests/graph agent-reception/tests/evals agent-report/schemas agent-report/examples server/src/reporting/narrative server/src/reporting/layouts server/tests/reporting/narrative
```

Local Python đã kiểm tra: Python 3.11.9, langgraph 1.2.11, langgraph-checkpoint 4.2.0,
langchain-core 1.6.0, pytest 9.1.1; Windows có tzdata cho IANA timezone. Owner chốt
manifest/lock và Ruff version/CI image; chưa có frozen Python dependency install/job.
Không dùng các lệnh trên làm bằng chứng CI production đã được tạo.
Kết quả lượt chuyển Python: 137 Python tests pass, Ruff lint/format đạt; runtime
TypeScript riêng 25 tests pass và typecheck đạt. Lượt chỉnh Markdown này không
chạy lại tests hoặc chứng minh backend/persistence/LLM integration.

Đây là job process, không có request/response HTTP. Auth: không cần API key/model,
backend hoặc DB thật cho test. Idempotency: cài frozen không thay lock; lỗi install,
test/typecheck phải làm job fail. Fixture gồm model/tool tổng hợp và MemorySaver
chỉ trong test; không inject production secrets vào job này.

Xin chốt image/runtime Bun, command start, HOST/PORT và liveness `/health` cho
runtime TypeScript hiện tại, cùng lifecycle/transport/deployment Python mới;
health không chứng minh Python graph/backend/model readiness. Root manifest,
lockfile, CI và deployment do Team 5 cập nhật. Không bị chặn chạy local PH01;
chưa xác nhận CI/deployment thật.
