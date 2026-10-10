# Trạng thái — Nguyễn Phương Đông

Ngày kiểm tra: 2026-10-10. Branch: `dev/TeamDong/dongnpp`.
Baseline: `aaa67a85028580547e49fdade5ab535e4daa3972`; thay đổi Phase A chưa commit.

## Tiến độ

**Đã hoàn thành phần Phase A của Đông tại mục 17.9:** protocol fields,
ordering/mapping, validation, snapshot reference/hash, JSON Schema/samples và
fake `AsyncProtocolPort` để các module làm song song. Chi tiết: [PHASE_A.md](PHASE_A.md).

NPD-10–12 chỉ hoàn thành phần contract/config/fake của nhịp A; chưa đánh dấu
hoàn thành toàn bộ task. NPD-01–09 chưa triển khai catalog/connection/API/UI.
Gate endpoint MCP tại Bước 1 vẫn độc lập với Phase A này, xem
[INTEGRATION_REQUEST_NPD_ENDPOINT.md](INTEGRATION_REQUEST_NPD_ENDPOINT.md).

## Files, exports và phạm vi

- `registry/event_protocols/_models.py`, `__init__.py`: export `AsyncToolProtocol`,
  `EventMapping`; 148 dòng production, tái sử dụng `WorkforceModel`, `ToolEffect`,
  `AsyncProtocolSnapshotRef`, Pydantic, jsonschema và Python standard library.
- `tests/workforce/registry/event_protocols/fakes.py`, `test_protocols.py`:
  fake dùng nguyên `AsyncProtocolPort`, `ActorContext`, `ProviderEventEnvelope`,
  `NormalizedJobEvent`, `Scope` và lỗi capability chung. Fake chỉ trong test.
- Handoff có `PHASE_A.md`, `phase_a_protocol.schema.json`, `phase_a_samples.json`,
  `INTEGRATION_REQUEST_NPD_PHASE_A.md`; README trong lane được cập nhật.
- Chỉ sửa Registry, test Registry và handoff cá nhân. Không sửa shared contracts,
  core MCP, dependency manifests, migration, root routing, fixture chung hoặc UI.

Protocol mẫu có sync, interactive approval, create-only, provider-event-ready,
query-only. Snapshot pin cả namespace/version/hash; config/mapping/policy đổi
hash mới. Event demo `event-003` thuộc `job-123`/`correlation-001`, không phải job thật.
Response MCP/tool/skill không có workflow_state/next_action.

## Bằng chứng kiểm tra

Chạy bằng Python 3.11.16 trong virtualenv `/tmp/npd-phase-a-venv`, cài editable
repo với service dependencies. Không sửa environment/manifest của repo.

Từ `platform_VP/agentscope`:

```bash
python -m pytest tests/workforce/registry/event_protocols tests/workforce/foundation/test_contracts.py -q
python -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
```

- Pytest: **21 passed, 52 subtests passed**, không warning; 12 test Registry mới
  và 9 regression contracts Foundation.
- Unittest discover: **12 tests OK**.
- Schema export và sample snapshot/hash được đối chiếu với code trong test.
- Black 23.3.0 (79 columns), flake8 6.1.0, add-trailing-comma 3.1.0,
  compileall và `git diff --check`: pass.

Tests kiểm tra invalid config/schema, thiếu capability/version, đủ bốn chiều Scope,
provider namespace/purpose, normalization deterministic/allowlist facts, order
metadata, schema/policy hash drift và giữ bản pin cũ khi config đổi.
Normalizer fake không áp state nên không coi đó là test DB ordering/reconciliation.

## Điểm nối và việc tiếp theo

Nhịp B: repository/service/normalizer production và readiness UI trong lane Đông;
Foundation vẫn sở hữu session/uow/auth/jobs/migrations/transport. Chốt context
normalization và detailed snapshot với Chí Hoàng/Dũng theo
[INTEGRATION_REQUEST_NPD_PHASE_A.md](INTEGRATION_REQUEST_NPD_PHASE_A.md) trước khi nối thật.
Không tự đoán integration namespace từ partner/tool name hoặc tự tạo inbox ID
và received_at mới mỗi lần normalize.

Chưa kiểm tra HTTP/MCP thật, DB, worker, inbox/replay/crash/race, frontend/E2E hoặc
sandbox provider. Chưa có schema/table/migration Registry hoặc production
`RegistryPort`/`AsyncProtocolPort` service. Các integration requests mới là file
bàn giao, chưa gửi thông báo cho chat/thành viên khác.
