# Trạng thái bàn giao — Phó Tiến Anh

Ngày cập nhật: 12/10/2026.

## Phạm vi nghiệm thu

Phase A theo mục 17.9: đặc tả validation và evaluation snapshot.
Task liên quan: PTA-14–PTA-16, phần schema và dữ liệu đối soát.
Nghiệm thu toàn bộ chức năng của các task này thuộc các mốc triển khai kế tiếp.

## Hồ sơ và public exports

| Đầu ra | Đường dẫn / export |
|---|---|
| Đặc tả nghiệp vụ | [BASELINE_PHASE_A.md](BASELINE_PHASE_A.md) |
| JSON Schema | [phase_a/schemas.json](phase_a/schemas.json), `pta-phase-a-1` |
| Mẫu dữ liệu | [phase_a/samples.json](phase_a/samples.json) |
| Aggregate đề xuất | `lifecycle.ValidationReport`, `lifecycle.EvaluationRecord` |
| Bộ xuất schema | `lifecycle.async_evaluation.phase_a_schema_bundle` |
| Contract tests | `tests/workforce/lifecycle/async_evaluation/test_phase_a.py` |

Các mẫu dùng ID và hash minh họa; không phải dữ liệu thực thi hoặc bằng chứng
hash được tính từ nội dung. Snapshot/report/protocol reference dùng DTO shared.
Policy proposal và aggregate Lifecycle chờ chấp thuận đặc tả dùng chung.

## Kết quả kiểm tra

Môi trường: Python 3.14.4. Từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workforce -q
```

Kết quả: **17 passed, 48 subtests passed**, gồm 9 Foundation contract tests
và 8 Lifecycle Phase A contract tests.

Phạm vi kiểm tra:

- Schema hợp lệ theo Draft 2020-12 và artifact khớp bộ xuất.
- Schema của snapshot/report/case/protocol reference khớp shared DTO.
- Mẫu validation/evaluation/policy được JSON Schema chấp nhận; mẫu DTO được Pydantic chấp nhận.
- Snapshot thiếu scope, revision không hợp lệ hoặc hash bắt buộc rỗng bị từ chối.
- Evaluation record thiếu các thành phần bắt buộc bị từ chối.
- Policy thiếu trường, sai kiểu, sai timeout hoặc chứa trường runtime ngoài đặc tả bị từ chối.

Black và Flake8 vùng code/test Phase A: pass.
Kiểm tra whitespace bằng `git diff --check`: pass.

## Điều kiện chấp thuận

- Nguyễn Chí Hoàng đối chiếu aggregate đề xuất với producer/consumer và compatibility của DTO shared.
- Nguyễn Phương Đông cung cấp đặc tả protocol payload, hash/version và capability mapping.
- Bùi Hữu Nghĩa thống nhất policy schema, reference và revision.
- Phan Huy Hoàng thống nhất dữ liệu runner và usage/checkpoint references.

Trạng thái chấp thuận đặc tả liên module: chờ đối chiếu của các owner.
JSON Schema chưa xác nhận các điều kiện liên trường, capability coverage,
đóng băng dependency hoặc hành vi phát hành.

## Mốc triển khai tiếp theo

Phase B cần phạm vi riêng cho validation/suites và fake runner sau khi đặc tả
Phase A được chấp thuận. Phase C tích hợp runtime; Phase D kiểm tra chịu lỗi và
retention. Các mốc này chưa nằm trong đầu ra nghiệm thu hiện tại.

API, UI, migration, provider/runner adapter và live E2E chưa thuộc bằng chứng
kiểm tra Phase A. Không có network call tới model hoặc provider trong bộ test này.

## Cập nhật Phase B — 10/10/2026

Đã hoàn thành phần độc lập
**async validation/suites với fake runner** ở mục 17.9, tiếp nối Phase A.
Không dùng điều kiện chờ review Phase A trong ghi chú cũ để dừng nhiệm vụ đã
được giao; các contract proposal còn mở vẫn được ghi rõ và không tự promote.

Task phần đã làm: PTA-14 validation/hash/frozen evidence; PTA-03/05/06/15
suite/grading/report với shared EvaluationRunnerPort, mock-only; stale-eval
guard phục vụ PTA-07/16. Chưa hoàn thành toàn bộ PTA-01–PTA-16.

Files: `lifecycle/async_evaluation/{_validation,_suites,_evaluation}.py`,
exports `__init__.py`, owned `test_phase_b.py`, frontend
`agents/async_evaluation/{EvaluationReport.tsx,index.ts}`, tài liệu Phase B và
integration request. Type hints phần mới dùng `typing`.
Không sửa README bàn giao (đã có diff của user trước phiên), không commit.

Public exports: `AsyncDraftValidator`, `validate_async_draft`, `canonical_hash`,
`FrozenEvaluation`, `freeze_evaluation`, `LifecycleSuite`, `LifecycleCase`,
`ExpectedTurn`, `lifecycle_suite`, `TurnEvidence`, `grade_case`,
`AsyncEvaluationService`, `check_release_evidence`. Shared DTO/schema Phase A
được giữ nguyên. Suite `pta-lifecycle-1`, gate `pta-gate-1`.

Test: **63 passed, 153 subtests passed** trên Lifecycle/Foundation/Builder/
Registry; Black formatting, Flake8, TypeScript build, scoped ESLint pass.
Bằng chứng scope/hash/drift/missing coverage/invalid policy, zero LLM idle,
duplicate side effects, missing consent, false completion, cross-audience,
secret/budget/unbound-tool/argument hard gates, stale report và serialization.
Các event là stimuli test, không event IDs đã persist ở provider inbox.

Mock/live: fake runner/clock trong test; production service không mock thành
công. Chưa DB/runtime/HTTP/provider E2E, browser QA hoặc sandbox onboarding.
Không có migration/dependency mới. Open: canonical policy resolver, detailed
protocol resolver, PHH runtime metrics, usage/checkpoint retention, jobs/API/
UI composition. Phase C nối runtime thật; Phase D kiểm tra publish pin/long
wait/revoke/restart/retention. Không ghi bảng workflow của PHH.

Chi tiết, lệnh tái chạy và giới hạn: [PHASE_B.md](PHASE_B.md).
Yêu cầu owner: [INTEGRATION_REQUEST_PTA_PHASE_B.md](INTEGRATION_REQUEST_PTA_PHASE_B.md).

UI SSR smoke pass: loading/error/empty, failed case, từng lượt và escaping HTML.
`git diff --check` phần PTA sửa pass; full-tree check báo blank line EOF trong
README bàn giao đã có sẵn, giữ nguyên theo yêu cầu user.

## Rà soát lần hai — 10/10/2026

Đã sửa 3 lỗi trong Phase B: freeze không gắn validation cũ với manifest mới;
runner error/nonterminal không được pass; release gate dùng cùng ngưỡng ≥90%
và zero hard gates với evaluation, tính lại aggregate metrics trước phát hành.
Thêm 3 regression tests (đã thấy fail trước sửa, pass sau sửa), gồm guard
phát hiện report completion bị tự thay. Không thay shared DTO/schema hoặc UI.

Kết quả mới nhất: **66 passed, 153 subtests passed** trên Lifecycle/Foundation/
Builder/Registry; Black --check, Flake8, TypeScript build và scoped ESLint pass.
Không sửa README bàn giao, không commit. Runtime/DB/provider/live và browser
QA vẫn chưa chạy; không nâng trạng thái nghiệm thu C/D từ tests Phase B.

## Điều phối Phase C — gate C5 đã hoàn thành

Phó Tiến Anh là owner **C5**. C5 đã bắt đầu sau khi C4 của Phan Huy Hoàng merge
và đã dùng workflow/checkpoint/continuation/event output thật; không coi fake
runner Phase B là nghiệm thu C5.

C1 đã cung cấp canonical UOW/jobs/auth/bootstrap; C2/C3 sẽ cung cấp protocol và
Builder/Execution thật. C5 nối eval đa lượt với chính runtime/guard production,
inject mock provider/fixed clock nhưng dùng cùng checkpoint, approval và tool
policy. Persist evidence/report theo scope, giữ version/hash pin và chặn publish
khi report stale hoặc hard gate fail. Bàn giao schema/index cho migration C7 và
runtime evidence exports cho E2E C6. Các đầu ra này hiện đã được bàn giao.

Theo dõi gate tại [../PHASE_C_SEQUENCE.md](../PHASE_C_SEQUENCE.md).

## Tín hiệu đầu vào C5 từ C4 — 2026-10-11

C4 đã cung cấp `LeaderTurnRunner`, `SqlRuntimeContinuation`,
`CommittedTurnEvidence` và `RuntimeEvidenceWriter` cùng checkpoint/guard/event
thật. Khi commit C4 đã merge vào `develop2`, C5 có thể bắt đầu theo
`../phan-huy-hoang/INTEGRATION_REQUEST_PHH_C4.md`; không cần chờ thêm fake
workflow. Migration/composition production vẫn thuộc C7 và không phải blocker
cho việc nối evaluation runtime trong test C5.

## C5 — HOÀN THÀNH VÀ ĐÃ MERGE — 11/10/2026

Đã hoàn thiện code và SQL/runtime integration tests cho **eval đa lượt nối
seam runtime C4**.

- Tái dùng Phase A/B: scoped validator, immutable frozen snapshot, deterministic
  grading, hard gates và shared report/UI shape; không sửa shared DTO/schema A.
- Tái dùng C1 canonical SQL UOW/jobs/worker; C2 SQL protocol provider và exact
  refs; C3 Builder policy shape và Execution guard/approval/gateway; C4
  SqlRuntimeContinuation/LeaderTurnRunner/WorkflowContinuation/context/evidence.
- Thêm `RuntimeEvaluationRunner`, `RuntimeCaseDriver`, `RuntimeObservation`,
  `RuntimeAudit`, `SqlRuntimeEvidenceWriter`, `SqlEvaluationRepository`,
  `EvaluationJobService`, `EvaluationJobHandler`, `check_persisted_release`,
  `get_metadata`, `phase_c_schema_bundle`. Type hints dùng `typing`.
- Persist frozen input/job cùng UOW; bind case trong bootstrap UOW trước job
  commit; evidence cùng checkpoint/public result UOW. Step/result/report
  immutable/hash, full Scope, replay và cancel marker; không giữ transaction
  qua model/provider. Publish hook đọc lại runtime evidence, chặn fake report,
  thiếu/tampered/cancelled evidence, stale input và hard gates.
- Suite `pta-lifecycle-2`: giữ operation refs/confirmation sau close và chạy
  Leader khi timer có trigger theo C4 mặc định. Frozen suite cũ không thay đổi.
  Sửa test policy legacy sau khi đối chiếu schema BHN C3; không nới validator.

Kết quả: **22 tests C5 pass**; nhóm Lifecycle/Foundation/Builder/Registry/C4
**167 passed, 5 skipped, 178 subtests passed**; Execution/E2E hiện có
**112 passed, 4 skipped**; workflow A/B **14 unittest tests pass**.
Black vùng thay đổi, Flake8, mypy **9 source files**, schema/DDL PostgreSQL và
SQLite compile, lazy import và diff check pass. Black toàn test folder còn
báo baseline `test_phase_a.py` chưa formatted; giữ nguyên file đó.

Mock/live: Workflow SQL/checkpoint/lease/guard, Foundation UOW/jobs và
Execution approval/policy/transactions/gateway thật trên SQLite. Scripted
Leader adapter/model, MCP provider, catalog/authority/quote/HITL/secret resolver
là test doubles, nằm trong tests; không dùng FakeRunner Phase B. C5 provider
events là normalized stimuli, không giả inbox/HTTP đã chạy. Test SQL reload /
injected cancellation không phải process kill/restart hoặc PostgreSQL race.

Skips: 4 Builder UI cần demo đang chạy/`BUILDER_UI_TEST_URL`, 2 PostgreSQL gates cần dedicated DSN và 3
full-platform E2E cần factory composition. Chưa chạy concrete AgentScope
Leader/session production, provider/model/live sandbox, HTTP/UI deployment,
long-wait retention/publish race D. Không đánh dấu toàn bộ PTA-01–PTA-16 xong.

C6 dùng exports runtime/evidence và thay test stimuli bằng provider ingress
thật. C7 gom metadata 4 bảng/index, job handler, concrete Leader/driver và
API/UI composition. C5 đã merge qua PR #64, vì vậy không còn là source chỉ nằm
trong working tree. Phó Tiến Anh không còn đầu việc C5, trừ khi C6 phát hiện lỗi
tích hợp cần trả lại đúng owner.

Chi tiết và lệnh tái chạy: [PHASE_C_C5.md](PHASE_C_C5.md).
Schema/index/signature bàn giao: [INTEGRATION_REQUEST_PTA_C5.md](INTEGRATION_REQUEST_PTA_C5.md)
và [phase_c/schemas.json](phase_c/schemas.json).

Rà soát lại C5: chặn ghi đè scope trong khóa truy vấn; đối chiếu identity/revision của payload evidence với hàng SQL; chặn evidence mới và stimulus tiếp theo khi case đã hủy. Bổ sung ba regression tests; chạy lại nhóm Lifecycle/Foundation/Builder/Registry/C4: 167 passed, 5 skipped, 178 subtests passed. Black vùng thay đổi, Flake8 và mypy đều pass. Kết quả Execution/E2E và unittest ở trên là lần kiểm chứng trước.

## D4 — Code và regression SQL/mock hoàn thành — 12/10/2026

Tiếp nối A/B/C5 và đầu ra D2/D3, thực hiện publish pin, protocol pin, long-wait,
stale evaluation, archive/disable/revoke và rollback trong phạm vi Lifecycle.
Không thay source/shared contract/migration/CI hoặc fixture của owner khác.

- `lifecycle/releases/`: `SqlReleaseService`, `ReleaseSelection`,
  `ReleaseContext`, `PublishedVersion`, `ReleaseValidator`,
  `PinnedVersionAuthorization`, `VersionUsageReader`, `get_release_metadata`,
  `phase_d_schema_bundle`. Type hints dùng `typing`, SQL imports lazy.
- Explicit publish đúng selections, CAS candidate/deployment, revalidation
  current dependencies và C5 committed evidence trong cùng UOW. Một item stale
  rollback cả danh sách. Immutable version giữ candidate ID/hash; lost-response
  replay không tạo version mới. Edit và evaluation cancellation bị serialize
  với release commit. Membership recheck cũng áp dụng với idempotent replay.
- `stage_candidate(..., uow=...)` ghép canonical draft write, không tự commit.
  Không coi staging là full DraftPort/business-key reservation/deduplication.
- Rollback chỉ đổi head sau ownership/compatibility check. Archive ngăn chọn
  mới, giữ old pin; disable/revoke chặn model/tool trước resume, PHH commit
  blocked_authorization. Provider fact sau revoke vẫn persist, không public
  message/wakeup. Không ghi wf_workflows/checkpoint của PHH.
- Giữ immutable version/eval vô thời hạn, không purge/TTL. Usage/checkpoint
  references đọc qua injected port của PHH; không suy đoán usage từ tuổi record.

Kiểm chứng trên checkout hiện tại:

| Nhóm | Kết quả |
|---|---|
| D4 mới, nằm trong nhóm Lifecycle | **28 pass, 4 PostgreSQL gates skip** |
| Lifecycle/Foundation/Builder/Registry/C4 | **233 passed, 17 skipped, 213 subtests passed** |
| Execution/E2E C6/D3 | **134 passed, 8 skipped, 3 subtests passed** |
| Workflow A/B, unittest discovery có `-t .` | **14 tests pass** |
| Black / Flake8 `--max-line-length=88` / mypy 8 source files | Pass |
| JSON Schema artifact / DDL hai dialect / lazy DTO import | Pass |

Lệnh và ma trận: [PHASE_D_D4.md](PHASE_D_D4.md),
`tests/workforce/lifecycle/releases/README.md`. Discovery unittest cũ thiếu
`-t .` không load được relative imports; đã sửa lệnh, không sửa source PHH.
Skips gồm 4 D4 PostgreSQL, 2 PostgreSQL Registry/Execution, 4 C6/D3 PostgreSQL,
12 Builder browser/demo và 3 full-platform factory. Không tính skip là pass.

Long-wait dùng clock tiến 200 ngày, dispose/reconnect SQL pool và worker mới
từ fixture D3. Sau publish v2/rollback/archive/protocol revise+disable, pending
workflow vẫn pin v1/protocol/session cũ; signed provider event resume một lần,
không lặp create, idle/duplicate không thêm calls. Đây là SQL/mock với real
HMAC/HTTP/inbox/checkpoint/guard/evidence, scripted model/provider và test
tool/policy/usage adapters; không phải 200 ngày chờ thật/process kill/live sandbox.

Metadata bốn bảng, schema `pta-release-1` và signature được bàn giao tại
[INTEGRATION_REQUEST_PTA_D4.md](INTEGRATION_REQUEST_PTA_D4.md),
[phase_d/schemas.json](phase_d/schemas.json). Cần Foundation additive migration,
manager auth/API + catalog/bootstrap wiring, owner transactional dependency
adapter và usage reader trước production. PostgreSQL DSN chưa được cấp; D5/D6/D7,
sandbox và canonical concurrent-build uniqueness chưa được nghiệm thu từ D4.
