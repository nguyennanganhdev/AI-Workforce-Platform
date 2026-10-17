# Phase A — Đặc tả validation và evaluation snapshot

Chủ sở hữu: Phó Tiến Anh. Ngày đối chiếu: 10/10/2026.
Căn cứ: mục 17.9 của [kế hoạch triển khai](../../KE_HOACH_TRIEN_KHAI.md).

## Mục tiêu nghiệp vụ

Định nghĩa dữ liệu phục vụ kiểm tra và đánh giá từng bản nháp agent. Hồ sơ đánh
giá cần xác định được chủ sở hữu, bản nháp, phiên bản ứng viên và các đầu vào
phụ thuộc tại thời điểm đánh giá, làm căn cứ cho quyết định phát hành.

## Đầu ra

- [Schema bundle](phase_a/schemas.json), phiên bản `pta-phase-a-1`.
- [Mẫu dữ liệu](phase_a/samples.json) cho validation, evaluation record và policy.
- Export schema: `agentscope.app.workforce.lifecycle.async_evaluation.phase_a_schema_bundle`.
- Aggregate đề xuất: `agentscope.app.workforce.lifecycle.ValidationReport` và `EvaluationRecord`.
- Contract tests: `tests/workforce/lifecycle/async_evaluation/test_phase_a.py`.

Mỗi phần tử của `schemas` là một tài liệu JSON Schema độc lập; `$ref` được
phân giải trong `$defs` của chính phần tử đó. DTO dùng chung được nhập trực tiếp
từ `workforce/contracts`. Hai aggregate Lifecycle là đề xuất bàn giao dữ liệu,
chờ owner đặc tả dùng chung đối chiếu producer và consumer.

## Cấu trúc dữ liệu

| Thành phần | Nội dung |
|---|---|
| `ValidationReport` | Kết quả hợp lệ, mã blocker, hash tool/protocol/dependency và dữ liệu tool snapshot |
| `EvaluationSnapshot` — shared DTO | Scope bốn trường, agent/draft/revision, source hash, candidate version, manifest, tool hash, test-context hash và thời điểm tạo |
| `EvaluationRecord` — aggregate đề xuất | Shared snapshot/report, suite hash, runtime profile, test context, validation, protocol refs, policy snapshot, gate config, revision, job và artifact refs |
| `EvaluationCaseResult`, `EvaluationReport` — shared DTO | Trạng thái đánh giá, metrics, hard-gate failures, case results và các hash đối soát |
| `AsyncProtocolSnapshotRef` — shared DTO | Protocol ID/version/schema hash, tool version, provider integration và capabilities |
| `AsyncHandlingPolicyProposal` | Schema đề xuất cho capabilities, event types, required facts, completion condition, human confirmation và timeout behavior |

`AsyncHandlingPolicyProposal` là artifact thiết kế, không phải DTO policy dùng
chung. `schema_version` là `1`; `timeout_behavior` nhận `status_query` hoặc
`needs_attention`. Schema chỉ nhận các trường được khai báo, do đó không nhận
ID ticket/job/workflow, endpoint hoặc roster. `completion_condition` là chuỗi
mô tả; cách diễn giải thuộc đặc tả của thành phần sử dụng policy.

`runtime_profile`, `test_context`, `policy_snapshot`, `gate_config`, tool
snapshots và protocol refs trong aggregate còn dùng mapping. JSON Schema chưa
kiểm tra ngữ nghĩa của các mapping này; chi tiết cần được thống nhất với owner.
Protocol reference không thay thế toàn bộ protocol payload hoặc event schema.

## Nguyên tắc nghiệp vụ cần thống nhất

- Scope gồm `tenant_id`, `domain_id`, `area_id`, `manager_account_id`.
- Mỗi hồ sơ đánh giá gắn với một agent, draft revision và candidate version xác định.
- Snapshot và report phải thống nhất scope, identity, revision và các hash liên quan.
- Policy phải bao phủ capability của binding external-operation.
- Protocol và policy là đầu vào đóng băng của evaluation; runtime ticket/group không thuộc manifest.
- Kết quả đánh giá cần đối soát với draft và dependency trước quyết định phát hành.

Các điều kiện liên trường, hash, capability coverage và tính bất biến cần được
kiểm tra bằng logic nghiệp vụ ở phase triển khai. Contract tests Phase A kiểm
tra cấu trúc dữ liệu, không xác nhận các hành vi runtime này.

## Trách nhiệm phối hợp

| Owner | Nội dung cần thống nhất |
|---|---|
| Nguyễn Chí Hoàng | DTO dùng chung, compatibility và việc tiếp nhận aggregate đề xuất |
| Nguyễn Phương Đông | Protocol payload/version/hash và capability mapping |
| Bùi Hữu Nghĩa | Policy schema, policy reference và revision |
| Phan Huy Hoàng | Dữ liệu đầu vào/đầu ra runner và version usage/checkpoint references |
| Phó Tiến Anh | Validation/evaluation schema, mẫu dữ liệu và contract tests |

## Điều kiện nghiệm thu Phase A

Schema hợp lệ theo Draft 2020-12; DTO shared khớp baseline; mẫu dữ liệu hợp lệ;
thiếu scope hoặc trường bắt buộc bị từ chối; policy sai cấu trúc bị từ chối.
Việc chấp thuận đặc tả dùng chung cần có đối chiếu của các owner liên quan.

## Lệnh kiểm tra

Từ `platform_VP/agentscope`:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/workforce/foundation tests/workforce/lifecycle -q
```

Tái sinh schema artifact:

```bash
PYTHONPATH=src .venv/bin/python - <<'PYTHON'
import json
from pathlib import Path
from agentscope.app.workforce.lifecycle.async_evaluation import phase_a_schema_bundle
Path('docs/workforce/handoffs/pho-tien-anh/phase_a/schemas.json').write_text(
    json.dumps(phase_a_schema_bundle(), indent=2, ensure_ascii=False) + '\n'
)
PYTHON
```
