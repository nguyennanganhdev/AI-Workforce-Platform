# Phase B — Provider ingress, correlation và reconciliation

Ngày: 10/10/2026. Branch: `feat/wf-execution`. Baseline: `53a139b`.
Theo mục 17.9 của [kế hoạch](../../KE_HOACH_TRIEN_KHAI.md).
**Đã hoàn thiện phần Phase B làm độc lập của lane Dũng**: provider ingress,
operation correlation, reconciliation và fake technician backend cùng
consumer adapters/tests. Chưa nghiệm thu MB toàn platform.

## Luồng và phần code đã có

1. Gateway revalidate Scope/runtime/tool/approval; persist call intent +
   operation/correlation/protocol pin trước network.
2. Creation result bind job ID theo namespace, tách creation succeeded và
   job progress. Timeout-after-write giữ unknown, không retry create mù.
3. HTTP xác minh raw-body auth trước parse. Ingress canonical envelope,
   persist inbox + provider job cùng UOW, commit trước ACK 202.
4. Processor resolve operation từ verified namespace/job/correlation;
   normalize theo bản protocol pin; apply version/order/transition.
5. WorkflowEventAdapter reload original binding, kiểm tra normalized metadata
   với inbox và gọi shared WorkflowPort bằng Scope DTO, operation_ref,
   NormalizedJobEvent trong cùng UOW. Sink response sai binding gây rollback.
6. Query timer chạy qua scoped JobPort, MCP read/query ngoài transaction;
   revision CAS chặn kết quả cũ. Job binding conflict bị chặn. Query status
   chuyển qua query hook riêng với timer cause và observation timestamp,
   không tạo provider inbox ID.
   Terminal không lùi; attention/result hooks được inject rõ, không noop giả.

Code mới/chỉnh nằm trong Execution; không viết Registry storage/normalizer,
Workflow runtime hoặc Foundation production repository.

## Public adapters và cách composition

```python
from agentscope.app.workforce.execution.external_operations import (
    ExecutionProtocolAdapter,
    ExternalOperationAdapter,
)
from agentscope.app.workforce.execution.provider_events import (
    WorkflowEventAdapter,
)

protocols = ExecutionProtocolAdapter(
    async_protocol_port, authorized_exact_detail_resolver, event_port_factory
)
operation_port = ExternalOperationAdapter(operation_service, protocols)
workflow_sink = WorkflowEventAdapter(
    execution_repository,
    workflow_port,
    attention_sink=attention_hook,
    execution_result_sink=result_hook,
    query_sink=query_hook,
)
```

Đây là ví dụ composition, không phải production bootstrap đã có.
`authorized_exact_detail_resolver(scope, ref)` trả public AsyncToolProtocol đúng
exact ref/hash, authorize đủ Scope; không dùng current config cho operation cũ.
`resolve_snapshot(scope, ref)` hỗ trợ pin cũ; get_snapshot lấy ref hiện hành
cho call mới. Gateway/service dùng canonical config hash; wrapper không đổi pin.

`event_port_factory(context)` là callable đồng bộ trả AsyncProtocolPort riêng
cho context persisted: actor/Scope/integration/inbox_event_id/received_at.
Không có fake/default success trong production. Test factory dùng fake của Đông.
Sau khi NCH promote context/signature chung, thay seam này bằng adapter canonical.

Verified principal hiện cần tenant_id/provider_integration_id/actor_id/kind/
purpose=provider_events và ActorContext dưới key actor. Ingress chỉ lưu identity,
processor re-authorize grant. Auth principal không lấy từ public body.
Provider API không nhận manager Scope; operation mới là nguồn owner/binding.

ExternalOperationAdapter trả DTO shared, tự mở transaction nếu uow=None,
join session nếu caller truyền UOW; chưa thay generic UOW bằng AsyncSession bridge.
Manager-only async chưa có shared audience semantics, không fabricate audience.
Canonical projection của record legacy thiếu ref phải qua migration/adapter owner,
không suy ref từ string hash.

Query dùng field job/status cấu hình NPD; provider_version hiện là field của
projected query output. Facts query mặc định rỗng vì chưa có query allowlist chung.
Provider query adapter phải scoped/pinned/read-only và được review.

## Bằng chứng kiểm tra

| Kiểm tra mới | Phạm vi được chứng minh |
|---|---|
| Canonical pin, hash drift, latest v2 không thay event của operation v1 | Exact detailed config và shared fake port của Đông |
| HTTP assigned/on_the_way/arrived/completed, retry từng event | Provider API/inbox/processor + shared DTO/PHH cause schema, fake Workflow sink |
| Wrong namespace/actor/schema; normalizer thay inbox/time/hash/status/facts | Quarantine, zero Workflow apply |
| Sink exception hoặc sai Workflow/audience/group | Rollback inbox outcome + operation facts + sink SQL, retry apply một lần |
| Event đến sớm khi chưa bind job | Correlation nối đúng operation, late create result không làm lùi completed |
| Delta gap/reprocess, terminal regression | Ordering/transition từ config, không hardcode trạng thái vào production |
| Query terminal/CAS/job conflict, timer cause riêng | Không ghi đè fact mới, không gắn nhầm external job hoặc giả provider inbox; query có facts không đổi vẫn tiến version để delta sau không bị gap giả |
| Hai workflow/ticket xen kẽ và close một workflow | Operation/correlation/cause tách biệt; closed workflow giữ fact, không emit chat giả |
| Foundation DurableJobService.enqueue_provider + SQL enqueue double | Cùng session với inbox, scope=None trước owner lookup; rollback cả hai khi enqueue lỗi |
| ExternalOperationPort DTO/Scope/optional UOW/rollback | Không commit transaction do caller sở hữu |
| Consent với CommandClaimResult thật của PHH | Authorize trước replay, exact audience/quote, command idempotency |

Fake Workflow sink dùng schema/proposals thật của PHH nhưng **không** thực thi
Workflow/checkpoint/LLM/SSE/close runtime. SQL tests dùng SQLite, không chứng minh
PostgreSQL locks/races/fencing.

## Kết quả và lệnh chạy lại

Môi trường tạm Python 3.11: `%TEMP%\wf-execution-venv`, project dependencies
service/storage-sql + pytest/aiosqlite/asyncpg. Lần này bổ sung
rfc3339-validator vào virtualenv để PHH runner kiểm tra RFC3339; không sửa
manifest/lockfile hoặc policy của máy.

- Execution/E2E slice + Foundation contracts + Registry Phase A:
  **113 passed, 4 skipped, 62 subtests passed**.
- Foundation Phase B riêng: **10 passed**.
- PHH Phase A runner: **242 passed**, 0 fail/error/skip.
- Ruff E/F, 79 cột: pass; mypy typed definitions: **26 source files**, pass.
- Không chạy lại frontend build/browser vì không đổi frontend trong lượt này.

```powershell
# Từ platform_VP/agentscope
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/execution tests/workforce/e2e tests/workforce/foundation/test_contracts.py tests/workforce/registry/event_protocols -q -rs -p no:cacheprovider --basetemp "$env:TEMP\wf-execution-phase-ab-final"
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest tests/workforce/foundation/async_api --import-mode=importlib -q -p no:cacheprovider
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" tests/workforce/orchestration/phase_a/run_phase_a.py
python -m ruff check src/agentscope/app/workforce/execution tests/workforce/execution tests/workforce/e2e tests/workforce/fixtures --select E,F --line-length 79
python -m mypy src/agentscope/app/workforce/execution --follow-imports=skip --ignore-missing-imports --disallow-untyped-defs --disallow-incomplete-defs
git diff --check
```

Foundation test folder dùng relative imports, chạy riêng với importlib mode.
Lần chạy gộp theo default mode đã lỗi collection; lệnh riêng trên pass.
PHH runner ban đầu thiếu RFC3339 checker đã được khắc phục bằng test dependency.
Không tính hai lần chạy chưa hợp lệ đó là pass.

## Giới hạn kiểm chứng Phase A/B

Một test PostgreSQL cần `WORKFORCE_TEST_POSTGRES_URL` dedicated.
Ba full-platform tests cần `WORKFORCE_E2E_FACTORY=module:function`.
Skip reason trong source còn ghi chung “implementations missing”; không có
nghĩa schema PHH/NPD/BHN/PTA hoặc Phase B Foundation chưa có.

MA chung còn chờ xác nhận contract/proposal và thống nhất fake tại
[integration request Phase A/B](INTEGRATION_REQUEST_PHD-01_PHASE_A.md).
Provider ingress/correlation/reconciliation đã kiểm chứng với fake backend;
chưa chứng minh luồng toàn platform qua runtime thật. Các test bị skip không
được tính là pass. Chưa chạy backend/provider thật, model trả phí hay booking thật.
