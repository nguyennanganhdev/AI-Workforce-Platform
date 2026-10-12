# Integration request — C6 → C7

Cập nhật **12/10/2026**. Người gửi: **Phan Hoàng Dũng**.
Tasks PHD-14–17, E2E toàn lát cắt. Không yêu cầu bàn giao lại C1/C2/C5.

**Cập nhật D3 ngày 12/10/2026:** output C7/D1 đã cung cấp production approval
continuation adapter, scoped reconcile handler và composition. D3 đã tiêu thụ
hai adapter này trong SQL/HTTP fault tests; các yêu cầu C6-02/03 bên dưới là
bàn giao lịch sử. Gate CI/PostgreSQL còn lại theo
[request D3](INTEGRATION_REQUEST_PHD_D3.md), không còn báo thiếu code C7.

## C6-01 — Query sau revoke và binding mismatch — đã xử lý

Output Orchestration: [PHH C4](../phan-huy-hoang/PHASE_C_C4.md).

- `WorkflowService.apply_query_result` kiểm tra binding/pin trước, revalidate
  original grant trước mọi thay đổi Workflow/checkpoint/public events.
  Grant bị revoke giữ operation fact đã xác minh trong caller UOW, không
  enqueue continuation. Lỗi binding/pin hoặc DB vẫn fail/rollback.
- Reply sai immutable tuple của customer đã có quyền trả
  `409/WORKFLOW_BINDING_MISMATCH`; sai user hoặc grant bị revoke vẫn
  `403/AUTHORIZATION_DENIED`, không claim command hoặc dispatch.
- Consumer C6 đã bỏ strict xfail và sửa assertion 403 → 409/code.
  Query test xác nhận operation revision/source hash commit, Workflow,
  history/evidence không đổi, worker idle và không thêm model call.
- C6: **11 passed, zero xfail**. PostgreSQL gate skip vì chưa có DSN.

Lệnh và bằng chứng đầy đủ: [PHASE_C_C6.md](PHASE_C_C6.md).
Không còn yêu cầu sửa C4 cho hai lỗi này.

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
- Metadata qua exports Foundation/Registry/Execution/Orchestration/Lifecycle;
  C6 không thêm schema. Execution metadata sáu bảng và legacy verified context
  theo [request C3](INTEGRATION_REQUEST_PHD_C3.md).
- Migration additive sau head thực tế, không sửa revision đã merge. C6
  `create_all` chỉ tạo DB test, không thay nghiệm thu migration.

Môi trường chưa có `WORKFORCE_TEST_POSTGRES_URL` và
`WORKFORCE_E2E_FACTORY`. PostgreSQL gate tại
`tests/workforce/e2e/async_tickets/test_phase_c_c6_postgres.py` chạy
8 concurrent signed HTTP deliveries và 8 concurrent SQL inbox applies;
assert một Workflow fact revision và một continuation/model turn.
Dùng schema ngẫu nhiên riêng, chỉ cleanup schema test. Chạy khi có dedicated DSN;
không tính SQLite hoặc skip là bằng chứng PostgreSQL locks/race.

Ba gate application factory cũ giữ nguyên assertions và điều kiện chạy;
không tính các skip này là đã nghiệm thu toàn application.

## Bàn giao

C6 đã pass trong môi trường hiện có; composition/migration/CI cuối thuộc C7.
Điều phối mở C7 theo baseline tích hợp của đội là bước riêng.
Lượt này chỉ sửa code/tài liệu và kiểm thử, không thực hiện thao tác Git.
