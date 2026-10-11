# Phase C/C3 — Provider ingress ↔ Operation ↔ Protocol

Ngày: **11/10/2026**, Asia/Saigon. Owner: **Phan Hoàng Dũng**.
Nhánh: `feat/wf-execution`. Baseline: **67ff871**, chứa C1 `a4c2fdd`
và C2 `b9feee2` đã merge vào `develop2`.

**Đã hoàn thiện lane C3 của Dũng** theo
[trình tự Phase C](../PHASE_C_SEQUENCE.md): dùng Foundation C1 và Registry SQL
C2 thật để xử lý provider inbox/operation. Workflow sink trong test vẫn là fake;
chưa nghiệm thu runtime C4, E2E toàn lát cắt C6 hoặc composition/migration C7.

## Đầu vào đã dùng

- C1: `VerifiedProviderContext`, `HmacProviderAuth`,
  `SqlProviderCredentialRepository`, `SqlAlchemyUnitOfWorkFactory`,
  `SqlDurableJobRepository`, `DurableJobService`, `DurableJobWorker`.
- C2: `SqlAsyncProtocolProvider.bind(scope, loader)` và
  `resolve_detail(scope, snapshot_ref)`; SQL immutable versions/current heads.
- Shared: `Scope`, `ProviderEventEnvelope`, `NormalizedJobEvent`,
  `WorkflowPort.apply_external_event(scope, operation_ref, event, uow)`.
- PHH: schemas/cause/WorkflowRecord và fake sink trong owned tests của Dũng;
  không thay Workflow implementation hoặc ghi trực tiếp bảng của PHH.

## Code và exports

- `execution.create_repository(session_factory=None, *, uow_factory=None)`:
  chọn đúng một factory; C3 truyền `WorkforceDatabase.uows`. Transaction do
  Execution mở sẽ explicit commit qua canonical UOW; exception rollback,
  after-commit callback chỉ chạy sau commit. Repository methods nhận UOW từ
  caller không tự commit. Legacy session factory vẫn dùng được.
- `execution.external_operations.RegistryExecutionProtocols(provider,
  repository, auth, operations)`: consumer adapter cho Registry C2, không tạo
  engine, storage hoặc current-pointer cache riêng. Bind service theo Scope
  của operation; create result/event/query đều kiểm tra exact immutable pin.
- `execution.provider_events._context.PersistedProviderEventContext`:
  loader nội bộ, tạo mới mỗi normalization attempt. Đọc inbox trong UOW đang
  apply; đối chiếu actor/full verified context, tenant/integration, envelope
  hash/content, inbox ID/received-at, operation Scope và exact protocol ref/hash;
  re-authorize stored credential trước normalize.
- Ingress persist đầy đủ fields của `VerifiedProviderContext` trong
  `provider_ref`, gồm credential ID, signing-key ID, authenticated-at và nested
  actor. Không persist API key/signing secret. Durable job lưu `receipt_id`
  trỏ tới inbox này; duplicate giữ context/thời gian/receipt gốc.
- Processor truyền UOW cho normalizer. `handle_job(job) -> dict` đáp ứng
  Foundation `JobHandler`, kiểm tra provider job type/namespace so với inbox;
  trả `receipt_id` + `ingestion_status`, không nhầm job succeeded với job
  nghiệp vụ completed.
- HTTP sanitize `PermissionError` của C1: authentication/signature sai trả 401,
  thiếu quyền operation trả 403; xác minh HMAC trên raw bytes trước parse.
  Provider body không nhận Scope.

## Composition được bàn giao

Đoạn dưới dành cho owner composition C7, với dependencies đã được khởi tạo
trong cùng lifespan; C3 không tự mount global routes hoặc bật worker nền.

```python
from agentscope.app.workforce.execution import create_repository
from agentscope.app.workforce.execution.external_operations import (
    ExternalOperationService,
    RegistryExecutionProtocols,
)
from agentscope.app.workforce.execution.provider_events import (
    ProviderEventIngress,
    ProviderEventProcessor,
    WorkflowEventAdapter,
)
from agentscope.app.workforce.registry.event_protocols import (
    SqlAsyncProtocolProvider,
)

uows = workforce_database.uows
repo = create_repository(uow_factory=uows)
operations = ExternalOperationService(repo)
registry_provider = SqlAsyncProtocolProvider(uows)
protocols = RegistryExecutionProtocols(
    registry_provider, repo, provider_auth, operations
)
ingress = ProviderEventIngress(
    repo, provider_auth, protocols, durable_jobs, operations
)
workflow_sink = WorkflowEventAdapter(repo, workflow_port)
processor = ProviderEventProcessor(ingress, workflow_sink)
handlers = {"provider_event": processor.handle_job}
```

`provider_auth`/`durable_jobs` cũng dùng cùng UOW factory C1.
Truyền `protocols` vào gateway/reconciler và `ingress` vào Execution router.
Query/attention/result dùng explicit injected hooks khi owner cung cấp;
không suy ra các method chưa có trong shared WorkflowPort.

## Invariants và bằng chứng

Tests C3: `tests/workforce/execution/provider_events/test_execution_c3.py`.
Fixture composition: `tests/workforce/fixtures/phase_c_fakes.py`.

| Kiểm tra | Bằng chứng |
|---|---|
| Raw HMAC → inbox/job SQL → worker → Registry SQL | Bốn status assigned/on_the_way/arrived/completed, duplicate giữ receipt; context đầy đủ, receipt không lộ identity |
| Signature/timestamp sai, thiếu operation hoặc body gửi Scope | 401/403/422, không có inbox/job |
| Credential bị revoke trước process/retry | Không apply Workflow hoặc thay fact; giữ original receipt/time/context |
| Enqueue lỗi sau insert | Rollback cả inbox và durable job trước ACK |
| Sink lỗi sau SQL write | Rollback operation/inbox/sink; callback không phát; retry commit đúng một lần |
| Loader bị thay actor/credential/hash/body/inbox/time/scope/integration/pin/UOW | Từ chối trước Registry normalization |
| Hai manager cùng integration, event xen kẽ | Chọn đúng Scope/pin/workflow, chặn đọc chéo; early event bind qua correlation |
| Current protocol đổi rồi disable | Event/create-result/query vẫn resolve pin cũ; new call bị chặn |
| Query timer scoped qua durable SQL job | Đúng manager, giữ TimerCause; không tạo provider inbox/event ID giả |
| Provider job trỏ receipt của integration khác | Từ chối trước apply |

Production code không dùng FakeAsyncProtocolPort. Test dùng C1 auth/UOW/jobs,
C2 repository/provider thật trên SQLite; API-key authenticator, secret resolver,
MCP backend, tool/runtime ports và Workflow sink là test dependencies.

## Kiểm chứng ngày 11/10/2026

- Execution/E2E slice + Foundation contracts + Registry: **150 passed,
  5 skipped, 76 subtests passed**, gồm **22 tests C3** mới.
- Foundation Phase B + C1: **20 passed**.
- Orchestration Phase B: **14 passed**.
- Ruff E/F 79 cột: pass; mypy: **28 source files**, pass.

Chạy từ `platform_VP/agentscope`, dùng virtualenv tạm đã có từ Phase A/B:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = 'src'
$python = "$env:TEMP\wf-execution-venv\Scripts\python.exe"
& $python -m pytest tests/workforce/execution tests/workforce/e2e tests/workforce/foundation/test_contracts.py tests/workforce/registry/event_protocols -q -rs -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-c3-verified"
& $python -m pytest tests/workforce/foundation/phase_c tests/workforce/foundation/async_api --import-mode=importlib -q -p no:cacheprovider
& $python -m unittest discover -s tests/workforce/orchestration/async_workflows -p 'test_*.py' -q
python -m ruff check src/agentscope/app/workforce/execution tests/workforce/execution tests/workforce/e2e tests/workforce/fixtures --select E,F --line-length 79
python -m mypy src/agentscope/app/workforce/execution --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
git diff --check
```

Hai skip cần dedicated `WORKFORCE_TEST_POSTGRES_URL`; ba skip cần
`WORKFORCE_E2E_FACTORY`. SQLite không chứng minh PostgreSQL row locks/races.
Skip reason cũ của full-platform tests chưa phản ánh đủ code C1/C2 đã merge.
Pytest gộp lần đầu bị trùng basename với Registry; test mới đã đổi tên để
collect đúng. Workflow tests chạy bằng unittest discover theo handoff PHH;
lần thử pytest importlib thiếu module `fakes` không được tính là pass.

## Giới hạn và bàn giao

Không sửa migration `0009`, root bootstrap/contracts/dependency hoặc code owner
khác. Không thêm dependency, đọc `.env`, gọi model trả phí hay provider thật.
Inbox legacy thiếu credential/signing-key/authentication time không được tự
đoán context; consumer thật từ chối, cần owner xác nhận cách xử lý dữ liệu cũ.

[Integration request C3](INTEGRATION_REQUEST_PHD_C3.md) chỉ ghi điểm nối C4/C7
cần owner thực hiện; [STATUS.md](STATUS.md) phản ánh phạm vi đã xong và đang chờ.
