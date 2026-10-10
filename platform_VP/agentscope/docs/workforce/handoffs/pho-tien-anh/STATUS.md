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
