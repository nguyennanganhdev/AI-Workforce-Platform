# Bàn giao tích hợp C5

Handoff ngày 11/10/2026.

## C6 — Hoàng Dũng: composition E2E

Import từ `agentscope.app.workforce.lifecycle.async_evaluation`:

```python
repository = SqlEvaluationRepository(workforce_database.uows)
writer = SqlRuntimeEvidenceWriter(repository, verified_manager_scope)
# Inject writer vào WorkflowContinuation của PHH dành cho evaluation session.
runner = RuntimeEvaluationRunner(repository, runtime_case_driver)
service = AsyncEvaluationService(runner, fixed_clock)
handler = EvaluationJobHandler(repository, service)
jobs = EvaluationJobService(repository, durable_jobs)
```

Giữ cùng C4 `WorkflowService`, `SqlRuntimeContinuation`, `LeaderTurnRunner`,
guard và Execution gateway; chỉ thay model/provider bằng mock đã kiểm soát.
Không import test `SqlCaseDriver` vào production.

`RuntimeCaseDriver` là seam callback local của consumer, chưa promote shared:

```text
open_case(scope, snapshot, test_case, bind) -> workflow_id
  bind(workflow_id, canonical_uow) -> None
apply(scope, workflow_id, stimulus, operation_key) -> RuntimeObservation
cancel(scope, workflow_id) -> None
```

- Resolve caller Scope/auth bằng C1; tạo group/session/audience riêng theo case.
- `test_case` có stimuli + frozen runtime profile/test context/exact protocol
  refs; không có expected outcomes. Dùng candidate version của snapshot.
- Trong bootstrap UOW, gọi `bind` trước khi job có thể commit/được claim; writer
  không chấp nhận workflow chưa đăng ký. Retry phải giữ cùng workflow identity.
- `apply` gọi commands/continuation/Execution production, dùng operation key
  durable; observe before/after checkpoint và trigger IDs đã commit. Recover
  **original** audit/counters nếu crash sau turn commit trước observation write.
  Không dựng zero counts từ checkpoint cuối hoặc chạy provider create lần nữa.
- Audit consent phải từ Execution approval; completion từ provider/operation,
  argument checks/secret/budget/output claims từ instrumentation xác định.
  `RuntimeAudit` thiếu field tạo runner error, không coi cause là bằng chứng.
- Dùng production query-result path cho timer; không tạo ProviderEventEnvelope,
  inbox ID hoặc external cause giả. Template-only policy cần suite version
  riêng, không đổi expectation trong frozen input để đạt gate.
- `tool_trace_ref` trỏ sanitized committed evidence theo workflow. Transcript
  text redaction/storage và usage retention vẫn cần adapter owner chốt.

Owned fixture `tests/workforce/lifecycle/async_evaluation/runtime_fixture.py`
là ví dụ composition SQL/test doubles; C6 thay normalized stimuli bằng raw
Provider Event API → inbox/worker/Registry C2/Execution C3 rồi C4/SSE. Chờ C5
commit/merge theo bảng điều phối trước mở C6.

## C7 — Chí Hoàng: metadata/jobs/composition

`get_metadata()` trả bốn bảng additive; không tự `create_all` trong production.
Nếu head migration khi ghép đã có bảng cùng tên, đối chiếu schema trước khi
tạo additive revision; không ghi đè migration đã merge.

| Table | Key và nội dung |
|---|---|
| `wf_evaluations` | PK Scope + evaluation_id; snapshot ID/hash/frozen input; report aggregate + record hash |
| `wf_evaluation_cases` | PK Scope + snapshot_id + case_id; unique Scope + workflow_id; input hash, cancelled marker, immutable case result/hash |
| `wf_evaluation_steps` | PK Scope + snapshot_id + case_id + step_index; immutable before/after context + required sanitized audit/hash |
| `wf_evaluation_turn_evidence` | PK Scope + workflow_id + trigger_id; immutable C4 evidence/hash; Scope + workflow + after_revision index |

Scope luôn gồm tenant/domain/area/manager. Metadata là nguồn chính cho types,
nullability, defaults và index names. JSON Schema:
`phase_c_schema_bundle()`, artifact `phase_c/schemas.json`, version
`pta-runtime-evidence-1`; shared snapshot/report/case/evidence DTO không đổi.

Đăng ký `EvaluationJobHandler.job_type` (`workforce.lifecycle.evaluate`) trong
worker của Foundation cùng workflow/provider handlers. Job payload chỉ giữ
evaluation ID; frozen input được load theo scope từ SQL. Enqueue input + job
cùng UOW. Job succeeded chỉ nghĩa xử lý xong; report failed vẫn giữ business
failure và chặn publish. Re-enqueue cùng evaluation ID không tạo job thứ hai;
đánh giá mới dùng evaluation/snapshot ID mới.

Expose report bằng `load_record(verified_scope, evaluation_id)`; API/UI cần
authorization và owner filter. UI `EvaluationReport` Phase B dùng cùng report
shape. Root phải inject concrete Leader engine và driver instrumentation;
không dùng fixture/fake runner để báo production thành công.

Trước publish: revalidate draft/dependencies, freeze current input rồi gọi
`check_persisted_release(repository, scope, evaluation_id, current_frozen)`.
Hook đọc lại case observations/evidence, không gọi model/provider hoặc publish.
Transaction/CAS của version/deployment write phải chống thay draft sau check;
hook không tự giải quyết race giữa current-validation và commit publish.

Giữ frozen snapshot/report/case/step/evidence cùng immutable agent/protocol refs
trong replay/audit window; không purge workflow pending hoặc cần version usage.
Chưa có purge service hoặc shared usage/retention port trong C5. PostgreSQL
race/restart, production concrete Leader, HTTP/UI composition và sandbox vẫn
cần kiểm chứng C6/C7/D; không suy diễn từ SQLite.
