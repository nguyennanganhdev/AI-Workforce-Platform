# Phase B — Protocol registry, normalizer và readiness UI

Ngày: 2026-10-10. Baseline: `develop2@53a139b`. Branch: `codex/npd-phase-b`.
Phạm vi: phần độc lập của NPD-10–12 theo mục 17.9. Không đánh dấu hoàn thành
catalog/endpoint MCP NPD-01–09 hoặc integration runtime Phase C.

## Public exports

`agentscope.app.workforce.registry.event_protocols` giữ nguyên
`AsyncToolProtocol`, `EventMapping` và bổ sung:

- `AsyncProtocolRepository`: boundary persistence có Scope đầy đủ; adapter
  PostgreSQL/session/UOW được nối ở Phase C. Fake repository chỉ trong tests.
- `AsyncProtocolService(repository, scope, load_event_context)`: triển khai
  nguyên ba signature của `AsyncProtocolPort`; scope do server resolve.
- `publish(protocol, expected_snapshot=None, uow=None) -> AsyncProtocolSnapshotRef`.
- `set_enabled(tool_version_id, enabled, expected_snapshot, uow=None)`.
- `get_detailed_snapshot(exact_ref) -> AsyncToolProtocol`: bản chi tiết thuộc
  Registry, resolve theo đủ Scope và exact version/hash. Consumer đọc ordering,
  event_mode, transitions, terminal_statuses, timeout và mapping từ bản đã pin.

Models/schema/hash/samples Phase A giữ nguyên. Không thêm dependency hoặc sửa
shared DTO/schema/types, core MCP, migration, root route hay module owner khác.
Dùng Pydantic/TypeAdapter, jsonschema/referencing, hashlib/json và house components
React/Vite có sẵn. Fake Phase A tái sử dụng normalizer production.

## Persistence và disable/drift

Repository phải atomic compare-and-set current pointer và append immutable
content theo `(scope, tool_version_id, protocol_id, protocol_version)`; cùng
key/hash idempotent, khác hash conflict. Full Scope gồm tenant/domain/area/manager.
Current pointer và enabled tách khỏi content; publish không tự bật lại protocol
đã disable. UOW được forward nguyên trạng, service không tự commit.

`get_snapshot` phục vụ call mới và từ chối protocol đã disable.
Detailed snapshot/capability validation/normalization vẫn đọc được pin cũ;
nhận event còn phải qua auth/grant/inbox reader hiện hành. Coverage dùng phép
AND trên nội dung thật, không tin capability bị sửa trong ref; thiếu coverage
trả `MISSING_REQUIRED_CAPABILITY`.

Migration Phase C cần scope, tool/protocol/version, immutable content/hash,
current reference và enabled state với unique/CAS ở DB. Fake repository chỉ
chứng minh semantics trong process, không chứng minh transaction PostgreSQL.

## Context normalization

Shared ActorContext/port chưa đủ namespace và metadata inbox. Phase B dùng
callback nội bộ bắt buộc, không tạo DTO wire khác:

```python
async def load_event_context(actor, envelope):
    # Owner adapter: authorize grant/scope and verify the exact persisted inbox.
    return tenant_id, provider_integration_id, inbox_event_id, received_at
```

Foundation/Execution cung cấp callback, gọi lại từng event/retry. Callback phải
authorize actor với scope/integration đã bind và kiểm tra đúng envelope đã
persist; không lấy namespace/inbox/time từ payload hoặc suy từ tên tool.
Production không có default callback trả thành công; test dùng AsyncMock.
Khi context DTO chung được chốt, thay injection adapter ở composition.

Service kiểm tra purpose provider_events, tenant khớp Scope, integration khớp
protocol, IDs hợp lệ và received_at có timezone. Normalizer kiểm tra schema,
provider_version, occurred_at, JSON hữu hạn và allowlist facts; hash nguồn
deterministic. Không LLM/network hoặc áp state. Ordering/delta gap, duplicate/
quarantine/reconciliation thuộc Execution; detailed pin giữ đủ policy.

## UI

Import `EventChannelsPanel`, `EventChannelView` từ
`features/workforce/integrations/event_channels/index.ts`. Đây là component view
model, chưa phải API wire DTO mới. Inject channels/loading/error/onRetry; không
copy transport/token/SSE. UI dùng Alert/Badge/Button/Table, có loading/empty/error/
retry, create/event/query/correlation/config/blocker/approval.

Capability không tự chứng minh endpoint/auth/binding sẵn sàng. Create-only không
được hứa tracking; sync/approval không bắt buộc tracking. Disable/drift chặn call
mới nhưng vẫn hiển thị event reception của pin cũ nếu owner xác nhận hợp lệ.
Blocker chỉ render mã allowlist; không render raw error/credential/secret.
Root route và API readiness thật được nối ở Phase C.

## Kiểm chứng và điểm nối

Từ `platform_VP/agentscope`:

```bash
python -m pytest tests/workforce/registry/event_protocols tests/workforce/foundation/test_contracts.py tests/workforce/execution -q
python -m unittest discover -s tests/workforce/registry/event_protocols -p 'test_*.py' -v
node tests/workforce/registry/event_protocols/test_event_channels.mjs
```

Frontend: tsc build và ESLint lane. Python: Black 23.3.0 (79 cột), flake8,
add-trailing-comma, compileall và git diff --check. Kết quả: [STATUS.md](STATUS.md).
SQL/UOW/migration, inbox reader/context, Execution adapter và API/shell wiring:
[INTEGRATION_REQUEST_NPD_PHASE_B.md](INTEGRATION_REQUEST_NPD_PHASE_B.md).
Chưa kiểm tra PostgreSQL concurrency, browser/E2E, HTTP/MCP/provider/worker thật.
Gate [endpoint MCP](INTEGRATION_REQUEST_NPD_ENDPOINT.md) còn mở và độc lập.
