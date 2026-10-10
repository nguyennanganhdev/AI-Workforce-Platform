# Trạng thái bàn giao — Phó Tiến Anh

Ngày đối chiếu: 10/10/2026. Branch: `feat/wf-lifecycle`.

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
