# Integration request — C6 → Phan Huy Hoàng / Nguyễn Chí Hoàng

Ngày **11/10/2026**. Người gửi: **Phan Hoàng Dũng**.
Nhánh `feat/wf-execution`, commit đầu vào `69e21f7` (C1–C5 đã merge).
Tasks PHD-14–17, E2E toàn lát cắt. Không yêu cầu bàn giao lại C1/C2/C5.

## C6-01 — Query sau revoke làm mất operation fact — chặn nghiệm thu

**Owner: Phan Huy Hoàng**, phối hợp Dũng chạy lại consumer test.
Module: `orchestration/workflows/_service.py`,
`WorkflowService.apply_query_result`.

Caller thật: `OperationReconciler.reconcile` →
`WorkflowEventAdapter(query_sink=workflow_service.apply_query_result)`.
Input gồm Scope, operation reference, timer ID, exact protocol hash,
source hash, observed_at, status/facts/version/terminal; dùng caller UOW.

Tái hiện:

1. Customer HTTP mở workflow, consent HTTP, Execution tạo operation pending.
2. Revoke original partner route trong DB.
3. Query transport trả kết quả hợp lệ; reconciler ghi operation fact trong UOW.
4. Query hook C4 ghi Workflow/checkpoint/public events rồi gọi enqueue trigger.
   Authorization phát hiện revoke và ném `PermissionError`.
5. Caller UOW rollback toàn bộ, operation fact cũng mất. Provider-event hook
   hiện đã xử lý đúng bằng cách giữ fact và suppress Workflow/public send.

Yêu cầu: kiểm tra original grant/closed/binding phù hợp trước khi thay Workflow
và phát event; route revoke không được làm mất fact provider đã xác minh.
Trả `WorkflowRecord` nguyên binding để Execution commit fact. Mismatch pin,
Scope, correlation hoặc lỗi DB thật vẫn phải fail/rollback; không catch mọi
`PermissionError` để trả success ở Execution.

Test thuộc Dũng:
`tests/workforce/e2e/async_tickets/test_phase_c_c6.py::C6SliceTests::test_query_after_route_revoke_keeps_fact_without_send`.
Marker `xfail(strict=True, raises=PermissionError)` chỉ ghi nhận lỗi baseline;
không tính pass. Test kiểm tra rollback fact/Workflow trước khi rethrow lỗi
đã biết. Sau fix, bỏ marker, xác nhận operation fact commit, Workflow không
đổi, không continuation/model/public send mới.

```powershell
$env:PYTHONPATH='src;tests/workforce/fixtures'
& "$env:TEMP\wf-execution-venv\Scripts\python.exe" -m pytest `
  tests/workforce/e2e/async_tickets/test_phase_c_c6.py `
  -k query_after_route_revoke -q -rx
```

Dũng không sửa source Orchestration ngoài owned paths hoặc đổi shared hook.

Regression C4 riêng còn một failure tại test có sẵn
`C4SqlSliceTests.test_bounded_wait_observes_committed_worker_result`: thời hạn
1 giây nhận 202 thay vì kỳ vọng 200, đã tái hiện cả khi chạy suite riêng.
PHH kiểm tra deadline/đồng bộ worker trong test; HTTP 202 khi chưa hoàn tất
là fallback hợp lệ nên chưa kết luận đây là lỗi sản phẩm. Không tăng timeout
hoặc sửa test của PHH trong lane Dũng.
Diagnostic riêng có worker succeeded/receipt completed, không job error;
chưa kết luận lỗi sản phẩm. Kết quả regression không được tính xanh cho đến
khi PHH xử lý hoặc chốt rõ điều kiện chạy test này.

## C6-02 — Composition approval ACK và continuation

**Owner: Nguyễn Chí Hoàng (C7)**, phối hợp Phan Huy Hoàng và Dũng.

`PartnerApprovalService` cần `commands.authorize_approval` để load original
Scope/audience/binding/grant trước cached read. `SqlPartnerRequestRepository`
đã có callback injection; root composition cần cấu hình thật, không đoán
Scope từ provider/customer payload.

Consent ACK được `record_result` ngay trong command ledger. Continuation C4
cũng ghi `RequestResult` cho `ApprovalCause.request_id`; dùng lại consent
command ID sẽ xung đột immutable result. Fixture C6 `_ApprovalCommands`
minh họa cách nối bằng ledger C4 hiện có:

- Persist ACK consent theo request gốc để retry trả đúng kết quả cũ.
- Claim command continuation riêng, deterministic theo ID command consent;
  enqueue `ApprovalCause` tham chiếu command mới, cùng UOW với consent/ACK.
- Không enqueue lại khi consent replay; không tạo private dedupe ledger.
- HTTP tests retry cả trước/sau consume: một provider create, ACK không đổi.

C7 chọn adapter production phù hợp hoặc thống nhất seam với PHH; không import
fixture vào source production và không fabricate auth/runtime/catalog.

## C6-03 — Wiring / metadata / gates của C7

**Owner: Nguyễn Chí Hoàng.**

- Dùng chung canonical UOW factory cho Foundation, Registry, Execution,
  Orchestration và Lifecycle. `execution.create_repository(uow_factory=uows)`.
- Gateway/ingress/reconciler dùng `RegistryExecutionProtocols` và exact pin.
- Register `provider_event: processor.handle_job`,
  `workforce.workflow.continue: WorkflowContinuationJobHandler(...)`.
- Register scoped `operation_reconcile`: lấy `job.scope`, operation/timer refs
  từ durable job; gọi `reconciler.reconcile`; không tạo provider inbox giả.
- `WorkflowEventAdapter(..., query_sink=workflow.apply_query_result)`;
  mount Execution/Orchestration routers với customer/manager/provider auth thật.
- C5 case binding phải commit trước first workflow turn, evidence writer cùng
  UOW với checkpoint/output; runtime/eval giữ đủ Scope/version/hash pins.
- Metadata vẫn qua exports Foundation/Registry/Execution/Orchestration/Lifecycle;
  C6 không thêm schema. Execution metadata sáu bảng và legacy verified context
  theo [request C3](INTEGRATION_REQUEST_PHD_C3.md).
- Migration additive sau head thực tế, không sửa revision đã merge. C6
  `create_all` chỉ tạo DB test, không thay nghiệm thu migration.

Môi trường còn thiếu: dedicated `WORKFORCE_TEST_POSTGRES_URL` và C7 application
factory `WORKFORCE_E2E_FACTORY`. Docker Linux engine hiện không chạy.

Gate PostgreSQL mới:
`tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py`:
8 concurrent signed HTTP deliveries, 8 concurrent SQL inbox applies, một
Workflow fact revision và một continuation/model turn. Dùng schema ngẫu nhiên
riêng; chỉ cleanup schema test. Chưa được chạy khi chưa có DSN.

Ba gate application factory cũ giữ nguyên assertions và điều kiện chạy;
chỉ sửa skip reason để không báo sai rằng C1–C5 implementations còn thiếu.
Không tính các skip này là bằng chứng đã nghiệm thu toàn application.

## Điều kiện đóng request / mở C7

PHH sửa C6-01, Dũng bỏ strict xfail và chạy lại C6; C7/môi trường cung cấp DSN
để chạy race gate. Commit C6 cần merge vào develop2 theo bảng tuần tự của đội.
Composition/migration/CI cuối vẫn do Chí Hoàng triển khai sau gate, không do
Dũng sửa ngoài phạm vi để làm tests xanh.
