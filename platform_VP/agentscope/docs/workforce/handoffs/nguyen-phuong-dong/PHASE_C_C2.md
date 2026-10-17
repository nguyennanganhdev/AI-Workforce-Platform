# Phase C/C2 — Registry protocol production provider

Ngày triển khai: **2026-10-11**. Owner theo kế hoạch: **Nguyễn Phương Đông**.
Người thực hiện thay: **Nguyễn Chí Hoàng**. Baseline:
`dev_TeamHoang@a4c2fddac720bb155efaa01eb91266b95f7b7181`.

## Kết quả C2

- `wf_async_protocol_versions`: lưu nội dung protocol bất biến theo đủ Scope,
  tool version, protocol identity/version và canonical schema hash.
- `wf_async_protocol_heads`: current pointer, enabled state và revision CAS theo
  đủ Scope + tool version. Publish version mới không tự bật protocol đã tắt.
- `SqlAsyncProtocolRepository`: PostgreSQL/SQLite insert-on-conflict,
  row-lock trên PostgreSQL, revision CAS, exact old-pin lookup và UOW injection.
- `SqlAsyncProtocolProvider`: bind `AsyncProtocolService` theo server Scope và
  cung cấp `resolve_detail(scope, ref)` đúng signature mà
  `ExecutionProtocolAdapter` đang yêu cầu.
- SQL exports được lazy-load để import AgentScope core không kéo optional SQL.
- Registry production không còn cần fake repository. Provider inbox loader vẫn
  là dependency bắt buộc do Execution C3 inject; production không có default
  thành công giả.

C2 không sửa module Execution, migration `0009`, root bootstrap hay shared
contract. Registry chỉ cung cấp producer thật; C3 tiêu thụ producer này, C7 nối
composition/migration cuối.

## Public API

```python
from agentscope.app.workforce.registry.event_protocols import (
    SqlAsyncProtocolProvider,
    SqlAsyncProtocolRepository,
)

protocol_provider = SqlAsyncProtocolProvider(workforce_database.uows)
protocol_service = protocol_provider.bind(scope, load_persisted_event_context)

# Composition bên Execution/C7:
protocol_adapter = ExecutionProtocolAdapter(
    protocol_service,
    protocol_provider.resolve_detail,
)
```

`load_persisted_event_context(actor, envelope)` thuộc C3 và phải đọc đúng inbox
đã persist, kiểm tra provider identity/grant rồi trả tenant, integration, inbox
ID và thời điểm nhận. Không dựng metadata từ request body.

## Bằng chứng kiểm tra

```powershell
# Chạy từ platform_VP/agentscope
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests\workforce\registry\event_protocols -p "test_*.py" -v
```

Kết quả Registry: **29 passed, 1 PostgreSQL gate skipped**. Năm test C2 chạy
SQL repository thật qua SQLite, gồm DDL PostgreSQL/SQLite, immutable conflict,
stale revision, disable-preserve-pin, full Scope isolation, injected UOW không
commit và Registry SQL → `ExecutionProtocolAdapter` → normalized event.

Regression liên quan: **19/19 Foundation pass** và **14/14 Orchestration pass**.
Bộ Execution cũ dùng `pytest` chưa được chạy toàn bộ vì `.venv` hiện tại không
có `pytest`; không tự cài dependency hay thay manifest trong C2. Test contract
trực tiếp với `ExecutionProtocolAdapter` nằm trong suite Registry đã pass.

PostgreSQL concurrency gate nằm tại `test_phase_c_postgres.py` và cần biến
`WORKFORCE_TEST_POSTGRES_URL` trỏ tới database test riêng. SQLite không được coi
là bằng chứng row-lock/concurrency PostgreSQL.

## Gate C3

Sau khi C2 merge, hai lane C3 được mở. Phan Hoàng Dũng dùng provider ở trên để:

1. Persist đầy đủ `VerifiedProviderContext` trong inbox/job reference.
2. Re-authorize credential trước xử lý lại.
3. Bind service bằng Scope của ExternalOperation, không lấy Scope từ event body.
4. Cung cấp persisted event-context loader request-local.
5. Dùng exact protocol pin cho create result, event và status query.

Bùi Hữu Nghĩa dùng cùng `AsyncProtocolService`/`AsyncProtocolPort` để validate
capability và protocol pin trước tạo draft; không đọc trực tiếp bảng Registry.
