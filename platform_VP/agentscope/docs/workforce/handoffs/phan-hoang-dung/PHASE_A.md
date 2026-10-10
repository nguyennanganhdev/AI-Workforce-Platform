# Phase A — Operation/inbox và ranh giới liên module

Ngày: 10/10/2026. Thành viên: Phan Hoàng Dũng. Branch: `feat/wf-execution`.
Baseline đã nhận code PHH: `53a139b` (fast-forward từ `origin/develop2`).
Phạm vi theo mục 17.9 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md):
operation/inbox schema và provider-event fixtures, phần hợp đồng
**PHD-14/PHD-15/PHD-17**.

**Đã hoàn thiện đầu ra Phase A của lane Dũng và consumer adapters/tests.**
Gate MA chung vẫn chờ owner chốt/promotion shared contracts; không tự sửa
`contracts/`, Registry, Workflow hoặc migration.

## Schema và exports

Public package `agentscope.app.workforce.execution` export
`get_metadata()` và `create_repository(session_factory)`.
Metadata gồm sáu bảng; chưa áp dụng vào Alembic chain của Foundation;
không auto-DDL production.

Mỗi bảng có `id` khóa chính, `revision` integer và `payload` JSON bắt buộc.
Các record fields ngoài cột dưới đây nằm trong payload.

| Bảng | Cột riêng | Unique |
|---|---|---|
| wf_external_operations | Scope bốn chiều; call_id/workflow_id/provider_integration_id/correlation_id bắt buộc; external_job_id nullable | call_id; correlation_id toàn cục; tenant_id + provider_integration_id + external_job_id |
| wf_provider_event_inbox | tenant_id/provider_integration_id/external_event_id; chưa có manager Scope vì event có thể đến sớm | tenant_id + provider_integration_id + external_event_id |
| wf_tool_calls | Scope + run_id/idempotency_key | Scope + run_id + idempotency_key |
| wf_approvals | Scope + call_id | call_id |
| wf_booking_operations | Scope + call_id | call_id |
| wf_execution_events | Scope + call_id | Không thêm unique business key |

Operation payload giữ scope, call/workflow/conversation/group/ticket/audience,
protocol detail/ref/hash, correlation/job ID, creation_status, job_status,
pending, last_provider_version/last_source_hash và created_at.
Inbox payload giữ canonical envelope/payload_hash, provider identity, received_at,
ingestion_status/error cùng id/revision. Không lưu credential secret/signature.
Payload hash không phải unique constraint thứ hai.
FK/checks liên module và migration/backfill chưa áp dụng.

Sources từ root `platform_VP/agentscope`:

- `src/agentscope/app/workforce/execution/{_tables.py,_repository.py}`.
- `execution/external_operations/{_tables.py,_service.py,_adapter.py,_protocol.py}`.
- `execution/provider_events/{_tables.py,_ingress.py,_processor.py,_workflow.py}`.

Subpackage `external_operations` export ExternalOperationService,
OperationReconciler, **ExternalOperationAdapter**, **ExecutionProtocolAdapter**.
Subpackage `provider_events` export ProviderEventIngress, ProviderEventProcessor,
**WorkflowEventAdapter**. Adapter trả DTO chung; record nội bộ không trở thành
shared DTO thứ hai.

## Điểm nối đã hoàn thiện sau code mới của PHH

| Ranh giới | Bằng chứng mới trong lane Dũng |
|---|---|
| Registry protocol ref → detailed pin | ExecutionProtocolAdapter nhận AsyncProtocolPort và authorized exact-detail resolver. Revalidate AsyncToolProtocol.snapshot_ref; dùng schema_hash canonical của Đông, không hash wrapper nội bộ |
| Persisted inbox → normalize | Processor truyền inbox ID/received_at; request-local event_port_factory bind context vào shared port. Kết quả phải giữ identity/time/namespace/ref/hash/version/correlation và đúng allowlisted mapping |
| Operation → shared port | ExternalOperationAdapter trả ExternalOperation, hỗ trợ optional UOW, không commit khi caller truyền session; get_for_workflow lọc đủ Scope |
| Execution fact → Workflow | WorkflowEventAdapter nhận operation record nhưng reload original binding, chuyển thành operation_ref + NormalizedJobEvent với cùng UOW. Kiểm tra response Scope/workflow/conversation/group/ticket/audience |
| Consent claim → DTO PHH | PartnerApprovalService nhận được CommandClaimResult proposal qua model dump; authorize trước cached read, pending claim không giả completed |
| Cause/schema PHH | Consumer sink test dùng ExternalEventCause/TimerCause/WorkflowTrigger và WorkflowRecord sample thật của PHH; sink chỉ là test double, không phải Workflow runtime |

Consumer tests dùng **FakeAsyncProtocolPort thật của Đông** từ
`tests/workforce/registry/event_protocols/fakes.py`, không copy normalizer.
Doubles/wiring thuộc `tests/workforce/fixtures/phase_ab_fakes.py`.
Test mới: `tests/workforce/execution/provider_events/test_phase_ab.py`;
consent typed-claim tests tại `test_http_and_tools.py`.

## Fixtures và samples

`tests/workforce/fixtures/execution_fakes.py` giữ event_fixture và fixtures cũ.
`async_partners/technician_backend.py` có ProviderBackend.progress_events:
assigned → on_the_way → arrived → completed, IDs A1–A4/B1–B4 retry ổn định.
Các tên ngành/trạng thái này chỉ trong cấu hình/mocks.
Provider API: POST `/workforce/v1/provider/job-events`, GET event-receipts/{id}.

```json
{
  "schema_version": "1",
  "external_event_id": "A2",
  "external_job_id": "FAKE-job-1",
  "client_reference": "server-correlation-A",
  "event_type": "job.on_the_way",
  "provider_version": 2,
  "occurred_at": "2026-10-10T09:00:00Z",
  "data": {"eta_minutes": 0, "note": "TEST PRIVATE NOTE"}
}
```

Sample thuộc mapping protocol của Đông trong consumer fixture; note không đi
vào normalized facts. Correlation thật do platform persist trước network.
ACK sau inbox+job commit, theo ProviderEventReceipt schema_version envelope=1:

```json
{
  "receipt_id": "server-receipt-A",
  "ingestion_status": "accepted",
  "duplicate": false,
  "received_at": "2026-10-10T09:00:01Z"
}
```

Retry trả receipt/thời gian gốc. Public receipt không lộ owner/workflow/payload.
Cùng event ID khác business data → EVENT_ID_CONFLICT 409; envelope chứa
scope/group/actor/callback → PROVIDER_EVENT_INVALID 422.
Signature vẫn xác minh raw body trước parse. Normalization lỗi/identity thay
đổi/schema hoặc pin lệch → quarantine, không apply Workflow.

## Compatibility và phần owner còn chốt

- Record mới lưu cả canonical snapshot_ref + configuration; protocol_hash là
  config schema_hash của Đông. Record cũ không có snapshot_ref vẫn giữ digest cũ,
  không rewrite audit hash hoặc tự đoán canonical ref.
- Canonical ExternalOperation cần PartnerAudience. Manager-only record vẫn dùng
  service nội bộ; adapter shared reject thiếu audience, chờ NCH quyết định.
- Inbox actor là ActorContext thật dưới verified principal do auth server cấp.
  event_port_factory là seam nội bộ tạm chờ canonical verified inbox context.
  Không mutate shared normalizer context giữa request.
- PHH đã có schema/checkpoint/trigger/claim/public payload proposals, chưa có
  production Workflow/runtime. Không còn yêu cầu PHH bàn giao lại schema.
- Attention/result/approval authorization hooks chưa có shared signature;
  dùng injection rõ ràng, thiếu hook thì fail closed.
- Hai shared validation issues PHH phát hiện (revision bool, naive timestamp)
  vẫn do NCH xử lý; không đánh dấu MA pass từ consumer tests của Dũng.

Chi tiết owner/actions ở [request shared contracts](INTEGRATION_REQUEST_PHD-01_PHASE_A.md).
Kết quả test, lệnh chạy và giới hạn Phase B/C ở [PHASE_B.md](PHASE_B.md),
tổng trạng thái ở [STATUS.md](STATUS.md).
