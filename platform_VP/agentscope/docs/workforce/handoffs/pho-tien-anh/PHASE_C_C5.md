# C5 — Evaluation đa lượt nối với runtime

Ngày: **11/10/2026**. Owner: **Phó Tiến Anh**.

## Phần đã triển khai

Tiếp nối validator/frozen snapshot/grader Phase A/B, thêm adapter cho shared
`EvaluationRunnerPort`, persistence SQL và durable evaluation job. Không xây
workflow runtime thứ hai hoặc đưa ticket/group vào manifest của agent.

```text
FrozenEvaluation + Scope
 → snapshot/job cùng Foundation UOW
 → Foundation worker / EvaluationJobHandler
 → RuntimeEvaluationRunner: chỉ mock tool + fixed clock
 → driver bootstrap workflow, bind case trong cùng UOW trước enqueue/commit
 → workflow commands / SqlRuntimeContinuation / LeaderTurnRunner / guard
 → CommittedTurnEvidence cùng checkpoint/result/public events trong turn UOW
 → đối soát observation + audit Execution, pin/hash/counts
 → grader Phase B → shared EvaluationReport → SQL
 → check_persisted_release: stale/hard gate + đọc lại evidence đã commit
```

Exports từ `lifecycle.async_evaluation`:

| Export | Mục đích |
|---|---|
| `RuntimeEvaluationRunner` | Adapter shared runner; case input không chứa expected turns |
| `RuntimeCaseDriver` | Seam composition cho bootstrap/commands, model/provider mock và fixed clock; không phải shared port mới |
| `RuntimeObservation`, `RuntimeAudit` | Dữ liệu audit local cần đủ trường; dùng public context/evidence của PHH |
| `SqlRuntimeEvidenceWriter` | Scope-bound writer được inject vào `WorkflowContinuation`; không commit UOW caller |
| `SqlEvaluationRepository` | Frozen input/report, case association, observations, committed evidence theo Scope đủ bốn trường |
| `EvaluationJobService`, `EvaluationJobHandler` | Enqueue atomic cùng input; reload input từ SQL; dùng JobPort/worker của C1 |
| `check_persisted_release` | Kiểm tra report từ SQL và đọc lại toàn bộ runtime evidence; không publish |
| `get_metadata`, `phase_c_schema_bundle` | Metadata additive cho C7 và [schema evidence](phase_c/schemas.json) |

Lazy-load SQL exports, không thêm dependency hoặc eagerly import SQL vào
baseline schema/validation exports. Type hints mới dùng `typing`.

## Invariants

- Case identity là `(Scope, snapshot_id, case_id)`, input hash gồm snapshot,
  stimuli, suite version, runtime profile, test context và exact protocol refs.
  Drift cùng identity bị chặn; đổi frozen input phải tạo snapshot mới.
- Bootstrap gọi callback `bind(workflow_id, uow)` trước job commit. Worker
  không thấy job chưa có case association. Writer chỉ nhận workflow đã bind.
- Evidence immutable theo `(Scope, workflow_id, trigger_id)`. Duplicate cùng
  nội dung idempotent; khác nội dung conflict. Rollback evidence cũng rollback
  checkpoint/result/public output của C4.
- So candidate agent/version và **toàn bộ** protocol refs với snapshot; không
  chỉ so một schema hash. Counters model/tool/token và new operation refs phải
  khớp evidence SQL. Thiếu guard, thiếu audit, reuse/omit evidence bị chặn.
- `approval_cause` không tự chứng minh consent; `provider_cause` không tự chứng
  minh completed. Audit cần đọc quyết định consent/operation/result thật,
  kiểm tra output/arguments/budget; mọi trường bắt buộc, không default pass.
- Completed case replay kiểm tra lại observations/evidence nhưng không chạy
  driver/model/provider. Step đã lưu được reuse khi evaluation bị interrupt.
  Driver phải xử lý durable idempotency tại khe turn commit → observation
  write; C5 không suy ra thành công khi adapter chưa cung cấp original audit.
- Cancel marker được persist trước cancel runtime, chặn reuse/publish. Close
  không xóa checkpoint/protocol/operation refs. Không có hard-delete/purge.
- Report/hash/observations không lưu raw arguments, credential, message text,
  prompt của runtime hoặc exception text. Trace ref là workflow ID owner-scoped;
  đây là sanitized evidence trace, chưa phải transcript text đã redact.
- Publish hook chỉ đọc persisted completed cases; fake report Phase B, thiếu
  hoặc tampered/cancelled runtime evidence không đủ điều kiện. Atomic publish,
  current draft/dependency revalidation và CAS thuộc Lifecycle release/composition.

## Suite và compatibility

Suite mới `pta-lifecycle-2`, giữ gate `pta-gate-1` (completion ≥90%, argument
checks ≥95%, zero hard gates). Không sửa suite bên trong snapshot đã đóng băng.

Đối chiếu C4 cho thấy reference operation vẫn tồn tại sau close để audit;
`tracking_records` trong v2 đếm retained operation refs, không phải số timer
đang chạy. Confirmation fact cũng giữ qua close. Timer status-query đã được
schedule là trigger hợp lệ; policy mặc định leader-turn chạy một lượt model.
Idle không có trigger, duplicate và late event vẫn zero LLM/side effect.

C3 của BHN đã dùng cùng policy fields `status_query`/`needs_attention`, required
event/fact lists không rỗng và không có `timeout_seconds` trong proposal.
Đã sửa test PTA cũ dùng legacy `query_status` và empty lists; dữ liệu legacy
vẫn bị từ chối. Giữ explicit dialect label để không đổi artifact Phase A.
Query-only thiếu event semantics vẫn là blocker như handoff BHN, không nới schema.

## Kiểm chứng

Từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols:tests/workforce/orchestration/async_workflows .venv/bin/python -m pytest tests/workforce/lifecycle tests/workforce/foundation tests/workforce/builder tests/workforce/registry tests/workforce/orchestration/phase_c --import-mode=importlib -q
PYTHONPATH=src:tests/workforce/fixtures:tests/workforce/registry/event_protocols .venv/bin/python -m pytest tests/workforce/execution tests/workforce/e2e --import-mode=importlib -q -rs
PYTHONPATH=src:tests/workforce/orchestration/async_workflows .venv/bin/python -m unittest discover -s tests/workforce/orchestration/async_workflows -p 'test_*.py' -q
.venv/bin/python -m black --check src/agentscope/app/workforce/lifecycle/async_evaluation tests/workforce/lifecycle/async_evaluation/test_phase_b.py tests/workforce/lifecycle/async_evaluation/test_phase_c.py tests/workforce/lifecycle/async_evaluation/runtime_fixture.py
.venv/bin/python -m flake8 --jobs=1 --max-line-length=88 src/agentscope/app/workforce/lifecycle/async_evaluation tests/workforce/lifecycle/async_evaluation
.venv/bin/python -m mypy src/agentscope/app/workforce/lifecycle/async_evaluation --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
```

Kết quả cuối: **167 passed, 5 skipped, 178 subtests passed** trên nhóm
Lifecycle/Foundation/Builder/Registry/C4; **112 passed, 4 skipped** trên
Execution/E2E hiện có; **14 workflow A/B tests pass** bằng unittest. Trong đó
**22 tests C5 mới pass**. Black vùng thay đổi, Flake8 vùng Lifecycle và mypy
9 source files pass; diff check pass; import baseline không load SQLAlchemy.
Black toàn test folder còn báo `test_phase_a.py` baseline chưa formatted,
không sửa file Phase A chỉ để làm đẹp output.

Năm skip nhóm đầu là bốn Builder UI tests cần demo đang chạy và
`BUILDER_UI_TEST_URL`, cùng một Registry
PostgreSQL gate. Bốn skip nhóm Execution/E2E là một PostgreSQL gate và ba
full-platform tests cần `WORKFORCE_E2E_FACTORY`. Skip reason của các test
full-platform còn ghi implementations missing; C1–C4 đã có source, nhưng
factory deployment đầy đủ chưa được cấp trong phiên này. Không tính skip là pass.

C5 tests gồm năm pattern, real SQL
checkpoint/guard/approval/gateway, scoped persistence, immutable conflicts,
rollback, cancellation/reload, pin drift, missing audit/guard/evidence,
tool disable và authorization revoke trước resume, schema + DDL hai dialect.

Test tận dụng setup SQL/ingress C4 và provider/catalog helpers của Dũng, đồng
thời dùng C2 `SqlAsyncProtocolProvider`/exact resolver và real Execution
`ApprovalService`, `ExecutionPolicy`, `TransactionService`, `ExecutionGateway`.
Không gọi `FakeRunner` Phase B. Scripted `LeaderTurnRunner` adapter trong
`runtime_fixture.py` là test dependency mô phỏng quyết định model; không import
expected suite để dựng output. Catalog authority, descriptor, quote/HITL/secret
resolver là test doubles. Provider events trong C5 là normalized test stimuli;
foreign correlation/decider bị guard thật từ chối. HTTP provider auth/inbox
toàn lát cắt và hai workflow provider live thuộc C6.

## Ranh giới bàn giao

C5 hoàn thiện code và tests cho seam runtime/evidence C4; không tuyên bố
concrete AgentScope Leader/session, model/provider hoặc deployment production
đã chạy. C4 cung cấp `LeaderTurnRunner` như injected seam, concrete engine
vẫn phải được composition nối. Không mount API/UI, không tạo migration hoặc
bật worker production; [yêu cầu C6/C7](INTEGRATION_REQUEST_PTA_C5.md).

SQLite SQL tests không chứng minh PostgreSQL concurrency, kill/restart process,
proxy/SSE sandbox hoặc long-wait retention. Publish/rollback pin, archive/revoke
long-wait/purge và full production acceptance vẫn thuộc D/C7. PTA-01–PTA-16
không được đánh dấu hoàn thành toàn bộ chỉ từ C5.

Rà soát lại C5: chặn ghi đè scope trong khóa truy vấn; đối chiếu identity/revision của payload evidence với hàng SQL; chặn evidence mới và stimulus tiếp theo khi case đã hủy. Bổ sung ba regression tests; chạy lại nhóm Lifecycle/Foundation/Builder/Registry/C4: 167 passed, 5 skipped, 178 subtests passed. Black vùng thay đổi, Flake8 và mypy đều pass. Kết quả Execution/E2E và unittest ở trên là lần kiểm chứng trước.
