# Phase A — Phó Tiến Anh

Ngày kiểm tra: 2026-10-10.
validation/eval snapshot schema cho PTA-14–PTA-16.

## Đầu ra bàn giao

- [Schema bundle](phase_a/schemas.json), version `pta-phase-a-1`.
- Export: `agentscope.app.workforce.lifecycle.async_evaluation.phase_a_schema_bundle`.
- Schema lấy trực tiếp từ shared DTO baseline và Lifecycle aggregates hiện tại,
  không sao chép/định nghĩa lại shared DTO. Mỗi phần tử trong `schemas` là một
  JSON Schema độc lập; `$defs` và `$ref` được resolve trong chính phần tử đó.
- Contract tests: `tests/workforce/lifecycle/async_evaluation/test_phase_a.py`.

## Validation và snapshot

| Thành phần | Contract hiện tại |
|---|---|
| `EvaluationSnapshot` (shared) | Scope đủ bốn trường; agent/draft/revision/source hash/candidate version; manifest, tool hash, test-context hash và timestamp |
| `ValidationReport` (Lifecycle) | valid/blockers, tool/protocol/dependency hashes và đầy đủ tool snapshots |
| `EvaluationRecord` (Lifecycle) | Shared snapshot/report, suite hash, runtime profile, test context, validation, protocol refs, policy snapshot, gate config, revision/job/artifact refs |
| `AsyncProtocolSnapshotRef` (shared) | protocol ID/version/schema hash/tool version/provider integration/capabilities |
| `AsyncHandlingPolicyProposal` | Schema đề xuất cho owner chung: capabilities/event types/required facts/completion condition/human confirmation/timeout behavior |

Policy proposal chỉ là artifact thiết kế của Phase A, không phải DTO production
thứ hai. Schema_version `1`, timeout `status_query` hoặc `needs_attention`;
không cho ticket/job/workflow/endpoint/roster vào policy. Danh sách capability
phải bao phủ các binding external-operation; phép kiểm bao phủ chạy bằng code,
không được thay thế bằng JSON Schema. `completion_condition` hiện là chuỗi
opaque cho runtime policy consumer, validator không thực thi biểu thức đó.

Snapshot bổ sung nằm trong `EvaluationRecord`, không thêm trường vào shared
`EvaluationSnapshot` khi chưa qua owner. Protocol refs và policy cũng nằm trong
test context được hash; runtime profile/suite/gate/validation được lưu cùng
record. Publish regrade và kiểm tra revision/hash/profile/dependency trước
commit. Không có runtime ticket/group hay team deployment trong manifest.

## Điểm nối đã có trong code

```python
ManifestValidator.freeze(scope, manifest)
# -> (ValidationReport, Tuple[Dict[str, Any], ...], Dict[str, Any])
ResourceValidationPort.validate_resources(scope, manifest)
# -> Dict[str, Any]: valid + dependency evidence, chỉ reference, không secret
AsyncPolicyPort.get_policy(scope, policy_ref)
# -> Dict[str, Any]: policy theo schema đề xuất, resolve trong scope
AsyncProtocolPort.get_snapshot(scope, tool_version_id)
# -> AsyncProtocolSnapshotRef (shared)
EvaluationRunnerPort.run_case(scope, version_snapshot, test_case, execution_mode)
# -> EvaluationCaseResult (shared); execution_mode do backend gán "mock"
VersionUsagePort.get_version_references(scope, version_id)
# -> Tuple[Dict[str, Any], ...]: persisted references từ Orchestration
```

Runner nhận shared snapshot và `test_case` gồm stable `case_run_id`,
`candidate_version_id`, `runtime_profile`, `test_context`, `sandbox_namespace`.
`test_context` gồm suite hash, execution mode, clock, protocol refs, policy,
peer fixtures. Runner không được tự đổi candidate, scope hoặc namespace.
Output dùng `EvaluationCaseResult`; `metrics` phải có tool trace, violation
counts, cost/latency và evidence từng lượt. Thiếu evidence fail closed.

Các blocker thuộc validator: `ASYNC_POLICY_REQUIRED`, `ASYNC_POLICY_INVALID`,
`ASYNC_CAPABILITY_COVERAGE`, `RUNTIME_DATA_IN_POLICY`,
`PROTOCOL_TOOL_MISMATCH`, `PROTOCOL_SNAPSHOT_DRIFT`,
`TOOL_SNAPSHOT_UNAVAILABLE`, `RESOURCE_UNAVAILABLE`. Port lookup failures
không chuyển thành thành công. Drift sau eval chặn publish; version đã pin
không bị publish/rollback thay nội dung.

## Ranh giới owner và giới hạn

- Chí Hoàng: promotion DTO/schema/TypeScript dùng chung và composition/migration.
- Đông: protocol chi tiết, hash/version và capability coverage qua shared port.
- Nghĩa: policy resolution/immutable policy revision qua `AsyncPolicyPort`.
- Huy Hoàng: runtime runner và persisted version usage/checkpoint references.
- Tiến Anh: validator, snapshot aggregate, schemas và consumer contract tests.

Shared baseline hiện chỉ có protocol reference, chưa có full protocol payload;
Lifecycle không tự coi reference là toàn bộ protocol mapping/event schema.
Policy/resource/usage ports chi tiết vẫn dùng dictionary trong code hiện tại.
Schema bundle nêu đúng mức chi tiết này để owner có thể promotion additive;
không tuyên bố các adapter provider hoặc shared policy DTO đã được tích hợp.

Phase A phần Tiến Anh đã có đầu ra review được và tests trong owned paths.
Việc chấp thuận/merge contract chung của các owner chưa được xác nhận. Phase C
(runtime thật, route UI, worker/migration) và nghiệm thu Phase D vẫn chưa xong.
Không tạo integration-request files theo yêu cầu người dùng.

## Xác minh và tái sinh artifact

Từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workforce/lifecycle -q
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from agentscope.app.workforce.lifecycle.async_evaluation import phase_a_schema_bundle
Path('docs/workforce/handoffs/pho-tien-anh/phase_a/schemas.json').write_text(
    json.dumps(phase_a_schema_bundle(), indent=2, ensure_ascii=False) + '\n'
)
PY
```

Kết quả: **45 passed, 12 subtests passed**, SQLite riêng cho tests. Contract
tests kiểm schema hợp lệ, khớp shared baseline, scope đầy đủ, policy hợp lệ/
không hợp lệ và capability thiếu. Các tests lifecycle sẵn có kiểm snapshot,
stale eval, pin/version và restart bằng fake ports. Không chạy live provider,
không sửa shared contracts/migration/UI routing, không commit.
